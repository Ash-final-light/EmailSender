import copy
from datetime import datetime, timedelta, timezone
from email.parser import BytesParser
from email.policy import default
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import main as app

NOW = datetime(2026, 10, 16, 6, tzinfo=timezone.utc)


def item(n=1, category="游戏开发技术", source=None, days=1):
    url = f"https://example.com/article/{n}"
    return {"key": app.fingerprint(url), "title": f"Independent topic {n}",
            "url": url, "summary": "A source summary", "published": (NOW - timedelta(days=days)).isoformat(),
            "source": source or f"Source {n}", "source_id": source or f"Source {n}",
            "category": category, "evidence": "基于来源摘要", "priority": 2,
            "prerelease": False, "id": n}


def report():
    return {"status": "attempting", "message_id": "<unit-test@example.com>",
            "start": "2026-10-09", "end": "2026-10-16", "sources": [],
            "takeaways": ["本周技术观察"], "items": [
                {**item(), "headline": "中文技术新闻", "summary_zh": "这是基于来源的事实摘要。",
                 "impact": "需要结合项目实际验证。", "score": 8}]}


class NewsletterTests(unittest.TestCase):
    def test_url_normalization_and_unsafe_links(self):
        self.assertEqual(app.fingerprint("https://Example.com/news/?id=3&utm_source=x#top"),
                         app.fingerprint("https://example.com/news?id=3"))
        for url in ("javascript:alert(1)", "file:///etc/passwd", "https://user:pass@example.com/"):
            self.assertFalse(app.safe_url(url))
        self.assertIsNone(app.parse_date("2026-10-16T08:00:00"))

    def test_pool_retention_and_refresh(self):
        merged = app.merge_pool([item(1, days=35), item(2)], [item(2), item(3)], NOW)
        self.assertEqual({x["key"] for x in merged}, {item(2)["key"], item(3)["key"]})

    def test_date_history_and_duplicate_filtering(self):
        data = [item(1), item(2, days=8), item(3), item(4)]
        data[3]["title"] = data[2]["title"]
        history = {item(1)["key"]: NOW.isoformat()}
        chosen = app.choose_candidates(data, history, NOW)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["url"], item(3)["url"])

    def test_balances_categories_and_sources(self):
        data = []
        n = 0
        for cat in app.CONFIG["category_weights"]:
            for _ in range(50):
                n += 1
                entry = item(n, category=cat, source=f"{cat} Source {n % 5}")
                # Different short titles must not trigger near-duplicate similarity.
                entry["title"] = f"T{n}"
                data.append(entry)
        config = {**app.CONFIG, "max_candidates": 20}
        chosen = app.choose_candidates(data, {}, NOW, config)
        counts = {c: sum(x["category"] == c for x in chosen) for c in config["category_weights"]}
        self.assertEqual(list(counts.values()), [10, 7, 3])
        self.assertGreater(len({x["source_id"] for x in chosen[:10]}), 1)

    def test_busy_source_cannot_exceed_delivery_budget_in_model_input(self):
        data = []
        for n in range(1, 20):
            value = item(n, source="Busy feed")
            value["title"] = f"T{n}"
            data.append(value)
        selected = app.choose_candidates(data, {}, NOW)
        self.assertEqual(len(selected), app.CONFIG["max_items_per_source"])

    def test_unity_query_filters_unrelated_rendering_and_game_roundups(self):
        source = "Unity 技术检索"
        unrelated, roundup, valid = item(1, source=source), item(2, source=source), item(3, source=source)
        unrelated["title"] = "NVIDIA DLSS model performance"
        roundup["title"] = "Unity Halloween game roundup"
        valid["title"] = "Unity URP rendering optimization"
        selected = app.choose_candidates([unrelated, roundup, valid], {}, NOW)
        self.assertEqual([x["url"] for x in selected], [valid["url"]])

    def test_rejects_invented_duplicate_and_non_chinese_model_output(self):
        pick = {"id": 1, "headline": "中文新闻标题", "summary": "根据来源提供的中文事实摘要。",
                "impact": "对项目开发有参考价值。", "score": 8}
        valid = {"takeaways": ["中文总结"], "items": [pick]}
        self.assertEqual(len(app.validate_digest(json.dumps(valid), [item()])[0]), 1)
        for bad in (
            {**valid, "items": [{**pick, "id": 99}]},
            {**valid, "items": [pick, pick]},
            {**valid, "items": [{**pick, "score": "8"}]},
            {**valid, "items": [{**pick, "summary": "An English only summary"}]},
        ):
            with self.assertRaises(ValueError):
                app.validate_digest(json.dumps(bad), [item()])

    def test_history_only_keeps_recent_sends(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app.write_json(root / "history.json", {"old": (NOW-timedelta(days=91)).isoformat(),
                                                  "new": NOW.isoformat(), "bad": "invalid"})
            self.assertEqual(app.load_history(root, NOW), {"new": NOW.isoformat()})

    def test_failed_delivery_is_uncertain_and_not_marked_sent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app.write_json(root / "outbox.json", report())
            with patch.object(app, "send_mail", side_effect=OSError("network failed")):
                with self.assertRaises(OSError):
                    app.deliver(root)
            self.assertEqual(app.read_json(root / "outbox.json", {})["status"], "uncertain")
            self.assertFalse((root / "history.json").exists())
            with self.assertRaises(RuntimeError):
                app.prepare(root, root / "preview.html")
            with self.assertRaises(RuntimeError):
                app.deliver(root)

    def test_success_marks_sent_and_prevents_a_second_delivery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app.write_json(root / "outbox.json", report())
            with patch.object(app, "send_mail") as sender:
                app.deliver(root)
                with self.assertRaises(RuntimeError):
                    app.deliver(root)
                sender.assert_called_once()
            self.assertIn(item()["key"], app.read_json(root / "history.json", {}))
            self.assertEqual(app.read_json(root / "outbox.json", {})["status"], "sent")

    def test_preview_does_not_modify_stored_data_or_send(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app.write_json(root / "candidates.json", [item()])
            app.write_json(root / "history.json", {})
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            output = root / "preview.html"
            with patch("sys.argv", ["main.py", "--preview", "--offline", "--data-dir", str(root),
                                    "--output", str(output)]), patch.object(app, "build_report", return_value=report()), \
                    patch.object(app, "send_mail") as sender:
                app.main()
                sender.assert_not_called()
            for name, value in before.items():
                self.assertEqual((root / name).read_bytes(), value)
            self.assertFalse((root / "outbox.json").exists())
            self.assertIn("开发者视野", output.read_text(encoding="utf-8"))

    def test_smtp_mime_encoding_and_html_escaping(self):
        value = copy.deepcopy(report())
        value["items"][0]["headline"] = '<script>alert("x")</script>中文'
        self.assertIn("&lt;script&gt;", app.render(value))
        self.assertNotIn('<script>alert', app.render(value))
        fake = MagicMock()
        fake.__enter__.return_value = fake
        fake.send_message.return_value = {}
        with patch.dict("os.environ", {"SMTP_USER": "sender@example.com", "SMTP_PASSWORD": "fake",
                                      "MAIL_TO": "receiver@example.com", "SMTP_SECURITY": "ssl"}), \
                patch.object(app.smtplib, "SMTP_SSL", return_value=fake):
            app.send_mail(value)
        message = fake.send_message.call_args.args[0]
        parsed = BytesParser(policy=default).parsebytes(message.as_bytes())
        self.assertIn("开发者周报", parsed["Subject"])
        self.assertEqual(parsed.get_body(preferencelist=("html",)).get_content_charset(), "utf-8")
        self.assertIn("中文", parsed.get_body(preferencelist=("plain",)).get_content())

    def test_reservation_and_empty_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app.write_json(root / "outbox.json", {**report(), "status": "prepared"})
            app.reserve_delivery(root)
            self.assertEqual(app.read_json(root / "outbox.json", {})["status"], "attempting")
            with self.assertRaises(RuntimeError):
                app.reserve_delivery(root)
            app.write_json(root / "outbox.json", {"status": "empty"})
            with patch.object(app, "send_mail") as sender:
                app.reserve_delivery(root)
                app.deliver(root)
                sender.assert_not_called()

    def test_manual_delivery_resolution_does_not_send(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app.write_json(root / "outbox.json", {**report(), "status": "uncertain"})
            with patch.object(app, "send_mail") as sender:
                app.resolve_delivery(root, True)
                sender.assert_not_called()
            self.assertEqual(app.read_json(root / "outbox.json", {})["status"], "sent")
            self.assertIn(item()["key"], app.read_json(root / "history.json", {}))
            app.write_json(root / "outbox.json", {**report(), "status": "prepared"})
            app.resolve_delivery(root, False)
            self.assertEqual(app.read_json(root / "outbox.json", {})["status"], "abandoned")


if __name__ == "__main__":
    unittest.main()
