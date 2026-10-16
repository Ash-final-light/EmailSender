"""Persistence, explicit budgets, and SMTP, independent of the news digest."""
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, format_datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import smtplib
import ssl
import subprocess
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(CONFIG["timezone"])
LOG = logging.getLogger("job-radar")


def now():
    return datetime.now(timezone.utc)


def read(path, fallback):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else fallback


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
    temp.replace(path)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalized(text):
    return re.sub(r"\s+", "", str(text or "")).lower()


def domain(url):
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def host_matches(host, suffix):
    return host == suffix or host.endswith("." + suffix)


def public_url(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        return (parts.scheme == "https" and bool(host) and not parts.username
                and not parts.password and parts.port in (None, 443)
                and host not in ("localhost", "localhost.localdomain")
                and "." in host and not re.fullmatch(r"[\d.:]+", host))
    except (ValueError, TypeError):
        return False


def canonical(url):
    p = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in (
                 "pcm", "pagesource", "logid", "share_token", "recommendationcode",
                 "isrecommendation", "sharepageid", "oc", "ref", "source")]
    # SPA job IDs in the hash are meaningful, unlike generic tracking anchors.
    fragment = p.fragment if re.search(r"(position|job)/[\w-]+|jobId=[\w-]+", p.fragment) else ""
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/",
                       urlencode(query), fragment))


def checkpoint():
    if os.getenv("JOB_RADAR_CHECKPOINT") == "1":
        result = subprocess.run(["bash", "scripts/persist-job-state.sh"], cwd=REPO,
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError("State checkpoint failed; no further paid request or email attempted")


class QuotaPause(RuntimeError):
    pass


class Budget:
    def __init__(self, data_dir, config=CONFIG, clock=now):
        self.path = data_dir / "budget.json"
        self.config, self.clock = config, clock
        self.value = read(self.path, {"days": {}, "weeks": {}, "paused": None})
        self.model_calls = 0

    def periods(self):
        local = self.clock().astimezone(TZ)
        day = local.date().isoformat()
        iso = local.isocalendar()
        week = f"{iso.year}-W{iso.week:02d}"
        self.value["days"].setdefault(day, {"search": 0, "details": 0})
        self.value["weeks"].setdefault(week, {"charges": [], "limit": self.config["weekly_token_soft_limit"]})
        if "search" not in self.value["weeks"][week]:
            self.value["weeks"][week]["search"] = sum(v["search"] for k, v in self.value["days"].items()
                if datetime.fromisoformat(k).date().isocalendar()[:2] == iso[:2])
        # Keep a bounded accounting history, without clearing pending approval.
        self.value["days"] = dict(sorted(self.value["days"].items())[-190:])
        self.value["weeks"] = dict(sorted(self.value["weeks"].items())[-30:])
        return self.value["days"][day], self.value["weeks"][week]

    def save(self, durable=False):
        write(self.path, self.value)
        if durable:
            checkpoint()

    def gate(self):
        if self.value.get("paused"):
            raise QuotaPause(self.value["paused"]["reason"])

    def pause(self, reason):
        if not self.value.get("paused"):
            self.value["paused"] = {"reason": reason, "created_at": self.clock().isoformat(),
                                    "notification": "pending"}
            self.save(durable=True)
        raise QuotaPause(self.value["paused"]["reason"])

    @staticmethod
    def tokens(week):
        return sum(c.get("actual", c["reserved"]) for c in week["charges"])

    def reserve_search(self):
        self.gate()
        day, week = self.periods()
        if day["search"] >= self.config["max_search_daily"]:
            self.pause(f"已达到每天 {self.config['max_search_daily']} 次搜索上限，需要确认后继续。")
        if week["search"] >= self.config.get("max_search_weekly", 200):
            self.pause(f"已达到每周 {self.config.get('max_search_weekly', 200)} 次搜索上限，需要确认后继续。")
        day["search"] += 1
        week["search"] += 1
        self.save(durable=True)

    def reserve_detail(self):
        self.gate()
        day, _ = self.periods()
        if day["details"] >= self.config["max_details_daily"]:
            return False
        day["details"] += 1
        self.save()
        return True

    def reserve_model(self, estimate):
        self.gate()
        _, week = self.periods()
        if self.model_calls >= self.config["max_model_calls"]:
            self.pause("本封岗位简报已达到 2 次模型调用上限，剩余候选已保存，等待确认。")
        if self.tokens(week) + estimate > week["limit"]:
            self.pause("模型本周用量加本次预计用量将触及 Token 软预算，等待确认。")
        self.model_calls += 1
        charge = {"id": len(week["charges"]), "created_at": self.clock().isoformat(),
                  "reserved": estimate}
        week["charges"].append(charge)
        self.save(durable=True)
        return charge

    def settle(self, charge, usage):
        if usage is not None:
            charge["actual"] = usage.total_tokens
            charge["input"] = usage.prompt_tokens
            charge["output"] = usage.completion_tokens
        self.save(durable=True)

    def resume(self, weekly_limit=None):
        _, week = self.periods()
        if weekly_limit is not None:
            if not isinstance(weekly_limit, int) or not 1 <= weekly_limit <= 1000000:
                raise RuntimeError("Weekly token limit must be an integer from 1 to 1000000")
            if weekly_limit < self.tokens(week):
                raise RuntimeError("New limit cannot be below already used/reserved tokens")
            week["limit"] = weekly_limit
        self.value["paused"] = None
        self.save(durable=True)


def mail_settings():
    missing = [k for k in ("SMTP_USER", "SMTP_PASSWORD", "MAIL_TO") if not os.getenv(k)]
    if missing:
        raise RuntimeError("Missing mail settings: " + ", ".join(missing))


def send(subject, body, text, message_id=None, attachments=()):
    mail_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("Unity 实习雷达", os.environ["SMTP_USER"]))
    recipients = [x.strip() for x in os.environ["MAIL_TO"].split(",") if x.strip()]
    message["To"] = ", ".join(recipients)
    message["Date"] = format_datetime(now().astimezone(TZ))
    message["Message-ID"] = message_id or make_msgid(domain="qq.com")
    message.set_content(text, charset="utf-8")
    message.add_alternative(body, subtype="html", charset="utf-8")
    for filename, subtype, content in attachments:
        message.add_attachment(content, maintype="text", subtype=subtype, filename=filename)
    security = os.getenv("SMTP_SECURITY") or "ssl"
    host = os.getenv("SMTP_HOST") or "smtp.qq.com"
    if security not in ("ssl", "starttls"):
        raise RuntimeError("SMTP_SECURITY must be ssl or starttls")
    port = int(os.getenv("SMTP_PORT") or (465 if security == "ssl" else 587))
    context = ssl.create_default_context()
    smtp = (smtplib.SMTP_SSL(host, port, timeout=30, context=context) if security == "ssl"
            else smtplib.SMTP(host, port, timeout=30))
    with smtp:
        if security == "starttls":
            smtp.starttls(context=context)
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        if smtp.send_message(message, from_addr=os.environ["SMTP_USER"], to_addrs=recipients):
            raise RuntimeError("Some recipients were refused; delivery result is uncertain")


def notify_pause(budget, data_dir):
    paused = budget.value.get("paused")
    if not paused or paused.get("notification") != "pending":
        return
    day, week = budget.periods()
    count = len(read(data_dir / "jobs.json", {}))
    text = (f"Unity 实习岗位雷达已暂停，等待你确认。\n原因：{paused['reason']}\n"
            f"已保存候选：{count} 条\n今日预留/已发起搜索：{day['search']} 次\n"
            f"本周已用或保守预留模型 Token：{budget.tokens(week)} / {week['limit']}\n"
            "没有继续付费调用。请检查额度或预算，然后通过 Job Radar 工作流的 resume 模式恢复；"
            "恢复不会清空已用次数和 Token。QQ 发信失败时以 Actions 运行记录为准。")
    paused["notification"] = "attempting"
    budget.save(durable=True)
    import html
    try:
        send("【需确认】Unity 实习雷达：额度或预算受限",
             '<div style="font-family:Microsoft YaHei;white-space:pre-wrap">' + html.escape(text) + "</div>", text)
    except Exception:
        paused["notification"] = "uncertain"
        budget.save(durable=True)
        raise
    paused["notification"] = "sent"
    budget.save(durable=True)
