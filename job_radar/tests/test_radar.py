import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

from job_radar import app, core, curation, sources, views


def job(key="a", **changes):
    title = "Unity客户端开发实习生"
    facts = {field: "未披露" for field in curation.FACT_FIELDS}
    facts.update(title=title, company="米哈游", city="上海", salary="200元/天",
                 summary="参与游戏客户端功能开发。", relevance="使用Unity开发客户端。",
                 concerns="请核对出勤条件。", company_website="https://www.mihoyo.com/",
                 company_careers="https://join.mihoyo.com/", website_evidence="预设公司域名")
    value = dict(id=key, title=title, text=title + " 米哈游 上海 200元/天 游戏开发 C#",
                 url="https://www.zhipin.com/job_detail/" + key + ".html",
                 page_status="readable", source="BOSS直聘", first_seen=core.now().isoformat(),
                 last_checked=core.now().isoformat(), deadline=None, analysis=facts)
    value.update(changes)
    return value


class RadarTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.checkpoint = patch("job_radar.core.checkpoint")
        self.checkpoint.start()
        self.addCleanup(self.checkpoint.stop)
        self.budget = core.Budget(self.data)

    def test_canonical_preserves_spa_identity(self):
        one = core.canonical("https://a.jobs.feishu.cn/index/?utm_source=x#/position/123/detail")
        two = core.canonical("https://a.jobs.feishu.cn/index/?utm_source=x#/position/456/detail")
        self.assertNotEqual(one, two)
        self.assertNotIn("utm_", one)
        self.assertTrue(sources.detail_url(one))

    def test_links_reject_credentials_local_and_scripts(self):
        for url in ("javascript:alert(1)", "http://a.com/", "https://127.0.0.1/",
                    "https://localhost/", "https://user:pass@a.com/", "https://a.com:999/"):
            self.assertFalse(core.public_url(url), url)
        self.assertTrue(core.public_url("https://www.zhipin.com/job_detail/1.html"))

    def test_unknown_domains_never_requested(self):
        with patch("job_radar.sources.requests.get") as get:
            self.assertEqual(sources.fetch("https://unapproved.example/job/1")["status"], "unverified_domain")
            get.assert_not_called()

    def test_redirect_is_validated_before_next_request(self):
        response = MagicMock(status_code=302, headers={"Location": "http://127.0.0.1/private"})
        response.__enter__.return_value = response
        with patch("job_radar.sources.requests.get", return_value=response) as get:
            self.assertEqual(sources.fetch("https://www.zhipin.com/job_detail/1")["status"], "unverified_domain")
            self.assertEqual(get.call_count, 1)

    def test_403_and_404_are_not_closed(self):
        for status, expected in ((403, "restricted"), (404, "missing_unconfirmed")):
            response = MagicMock(status_code=status)
            response.__enter__.return_value = response
            with patch("job_radar.sources.requests.get", return_value=response):
                self.assertEqual(sources.fetch("https://www.zhipin.com/job_detail/1")["status"], expected)
            self.assertEqual(curation.classify(job(page_status=expected)), "lead")

    def test_rules_exclude_nonclient_and_noninternship(self):
        for title, text in (("Unity技术美术实习生", "Unity 游戏开发"),
                            ("UE5客户端开发实习", "Unreal 游戏开发"),
                            ("Unity客户端高级工程师", "全职 游戏开发 招聘实习生广告")):
            self.assertEqual(sources.role_kind(title, text), "excluded")
        self.assertEqual(sources.role_kind("Unity XR开发实习生", "Unity XR研发"), "related")
        self.assertEqual(sources.role_kind("客户端开发实习", "使用Unity开发游戏"), "match")

    def test_expired_and_stale_records(self):
        self.assertTrue(sources.expired("截止日期：2025-10-10", "2026-10-16"))
        self.assertEqual(curation.classify(job(text="截止日期：2020-01-01")), "closed")
        self.assertEqual(curation.classify(job(last_checked=(core.now()-timedelta(days=4)).isoformat())), "lead")

    def test_fact_guard_drops_invented_fields(self):
        candidate = job()
        row = {"id": "a", **{field: candidate["analysis"][field] for field in curation.FACT_FIELDS},
               "summary": "参与游戏开发。", "relevance": "客户端实习方向。", "concerns": "核对条件。"}
        row["salary"] = "1000元/天"
        result = curation.apply_extraction(json.dumps({"jobs": [row]}), [candidate])["a"]
        self.assertEqual(result["salary"], "未披露")
        self.assertEqual(result["company_website"], "https://www.mihoyo.com/")
        row["url"] = "https://invented.example/"
        with self.assertRaises(ValueError):
            curation.apply_extraction(json.dumps({"jobs": [row]}), [candidate])

    def test_duplicate_model_ids_rejected(self):
        candidate = job()
        row = {key: value for key, value in candidate["analysis"].items()
               if key in curation.FACT_FIELDS or key in ("summary", "relevance", "concerns")}
        row["id"] = "a"
        with self.assertRaises(ValueError):
            curation.apply_extraction(json.dumps({"jobs": [row, row]}), [candidate])

    def test_search_reserved_before_network_and_cached(self):
        cache = {}
        query = {"query": "Unity 实习"}
        def post(*args, **kwargs):
            self.assertEqual(core.read(self.data / "budget.json", {})["days"][core.now().astimezone(core.TZ).date().isoformat()]["search"], 1)
            return SimpleNamespace(status_code=200, json=lambda: {"code": 200, "data": {"webPages": {"value": []}}})
        with patch.dict("os.environ", {"BOCHA_API_KEY": "unit-test"}), patch("job_radar.sources.requests.post", side_effect=post) as call:
            sources.search(query, self.budget, cache, self.data / "cache.json")
            sources.search(query, self.budget, cache, self.data / "cache.json")
            self.assertEqual(call.call_count, 1)

    def test_search_cap_does_not_make_extra_request(self):
        day, _ = self.budget.periods()
        day["search"] = core.CONFIG["max_search_daily"]
        with patch.dict("os.environ", {"BOCHA_API_KEY": "unit-test"}), patch("job_radar.sources.requests.post") as call:
            with self.assertRaises(core.QuotaPause):
                sources.search({"query": "x"}, self.budget, {}, self.data / "cache.json")
            call.assert_not_called()

    def test_model_reservation_and_actual_reconcile(self):
        charge = self.budget.reserve_model(1500)
        self.assertEqual(self.budget.tokens(self.budget.periods()[1]), 1500)
        self.budget.settle(charge, SimpleNamespace(total_tokens=400, prompt_tokens=300, completion_tokens=100))
        self.assertEqual(self.budget.tokens(self.budget.periods()[1]), 400)

    def test_budget_limit_pause_and_resume_preserves_usage(self):
        self.budget.reserve_model(1000)
        self.budget.periods()[1]["limit"] = 1200
        with self.assertRaises(core.QuotaPause):
            self.budget.reserve_model(500)
        self.budget.resume(2000)
        self.assertEqual(self.budget.tokens(self.budget.periods()[1]), 1000)
        self.assertEqual(self.budget.periods()[1]["limit"], 2000)

    def test_pause_survives_new_week(self):
        with self.assertRaises(core.QuotaPause):
            self.budget.pause("需要确认")
        later = core.Budget(self.data, clock=lambda: core.now()+timedelta(days=10))
        later.periods()
        with self.assertRaises(core.QuotaPause):
            later.gate()

    def test_pause_notification_only_once(self):
        with self.assertRaises(core.QuotaPause):
            self.budget.pause("需要确认")
        with patch("job_radar.core.send") as send:
            core.notify_pause(self.budget, self.data)
            core.notify_pause(self.budget, self.data)
            self.assertEqual(send.call_count, 1)

    def test_signature_ignores_summary_and_check_timestamp(self):
        first = job()
        second = copy.deepcopy(first)
        second["analysis"]["summary"] = "另一种中文概括。"
        second["last_checked"] = core.now().isoformat()
        self.assertEqual(curation.signature(first), curation.signature(second))
        second["analysis"]["salary"] = "300元/天"
        self.assertNotEqual(curation.signature(first), curation.signature(second))

    def test_report_suppresses_old_and_reports_closure(self):
        first = job()
        history = {"a": {"signature": curation.signature(first), "sent_at": core.now().isoformat()}}
        self.assertFalse(curation.report({"a": first}, history, {}, self.budget)["jobs"])
        first["page_status"] = "closed"
        self.assertEqual(len(curation.report({"a": first}, history, {}, self.budget)["changes"]), 1)

    def test_merge_only_same_city_and_description(self):
        first, second, third = job(), job("b"), job("c")
        third["analysis"]["city"] = "北京"
        report = curation.report({"a": first, "b": second, "c": third}, {}, {}, self.budget)
        self.assertEqual(len(report["jobs"]), 2)
        self.assertTrue(any(row.get("merged_ids") for row in report["jobs"]))

    def test_preview_never_sends_or_changes_history(self):
        core.write(self.data / "jobs.json", {"a": job()})
        with patch("job_radar.app.send") as send:
            app.build(self.data, self.budget, self.data / "preview.html")
            send.assert_not_called()
        self.assertFalse((self.data / "history.json").exists())
        self.assertTrue((self.data / "preview.html").exists())

    def test_uncertain_delivery_blocks_automatic_retry(self):
        report = curation.report({"a": job()}, {}, {}, self.budget)
        report.update(status="attempting", message_id="<unit-test@example.com>")
        core.write(self.data / "outbox.json", report)
        with patch("job_radar.app.send", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                app.deliver(self.data)
        self.assertEqual(core.read(self.data / "outbox.json", {})["status"], "uncertain")
        with self.assertRaises(RuntimeError):
            app.prepare(self.data, self.budget, self.data / "preview.html")
        self.assertFalse((self.data / "history.json").exists())

    def test_render_escapes_source_and_refuses_unsafe_link(self):
        candidate = job()
        candidate["analysis"]["summary"] = '<script>alert("x")</script>'
        candidate["analysis"]["company_website"] = "javascript:alert(1)"
        content = views.render(curation.report({"a": candidate}, {}, {}, self.budget))
        self.assertNotIn("<script>", content)
        self.assertNotIn('href="javascript:', content)
        self.assertIn("&lt;script&gt;", content)

    def test_reviewed_directory_refreshes_cached_extraction(self):
        candidate = job()
        candidate["analysis"].update(company="杭州以咏今朝信息科技", company_website=None, company_careers=None)
        report = curation.report({"a": candidate}, {}, {}, self.budget)
        self.assertEqual(report["jobs"][0]["analysis"]["company_website"], "https://millervlogs.com/")
        self.assertIsNone(report["jobs"][0]["analysis"]["company_careers"])
        self.assertIn("人工核对", report["jobs"][0]["analysis"]["website_evidence"])


if __name__ == "__main__":
    unittest.main()
