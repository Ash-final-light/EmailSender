"""CLI: python -m job_radar.app MODE. Preview does not send or change notification history."""
import argparse
from datetime import datetime, timedelta
from email.utils import make_msgid
import logging
from pathlib import Path
import sys

from . import sources, curation, views
from .core import (CONFIG, ROOT, LOG, Budget, QuotaPause, checkpoint, mail_settings, now,
                   notify_pause, read, send, write)


def history(data_dir):
    values = read(data_dir / "history.json", {})
    cutoff = now() - timedelta(days=CONFIG["history_days"])
    return {key: value for key, value in values.items()
            if datetime.fromisoformat(value["sent_at"]) > cutoff}


def build(data_dir, budget, output):
    jobs = read(data_dir / "jobs.json", {})
    stats = read(data_dir / "sources.json", {})
    jobs = curation.curate(jobs, data_dir, budget)
    report = curation.report(jobs, history(data_dir), stats, budget)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(views.render(report), encoding="utf-8", newline="\n")
    write(output.with_suffix(".json"), report)
    output.with_suffix(".csv").write_bytes(views.csv_content(report))
    LOG.info("Job preview: %d matched, %d leads, %d status changes",
             len(report["jobs"]), len(report["leads"]), len(report["changes"]))
    return report


def prepare(data_dir, budget, output):
    path = data_dir / "outbox.json"
    if read(path, {}).get("status") in ("prepared", "attempting", "uncertain"):
        raise RuntimeError("Unresolved job email exists; inspect delivery state before retrying")
    report = build(data_dir, budget, output)
    report.update(status="prepared", message_id=make_msgid(domain="qq.com"))
    write(path, report)
    return report


def reserve(data_dir):
    path = data_dir / "outbox.json"
    report = read(path, {})
    if report.get("status") != "prepared":
        raise RuntimeError("Only a prepared job report can be reserved")
    report.update(status="attempting", reserved_at=now().isoformat())
    write(path, report)
    checkpoint()


def confirm(data_dir, report):
    values = history(data_dir)
    sent_at = now().isoformat()
    for group in ("jobs", "engine_unspecified", "leads", "changes"):
        for row in report.get(group, []):
            for key in [row["id"]] + row.get("merged_ids", []):
                values[key] = {"signature": row["signature"], "sent_at": sent_at}
    write(data_dir / "history.json", values)
    report.update(status="sent", sent_at=sent_at)
    write(data_dir / "outbox.json", report)


def deliver(data_dir):
    report = read(data_dir / "outbox.json", {})
    if report.get("status") != "attempting":
        raise RuntimeError("Job email must be reserved and checkpointed first")
    try:
        send(f"【Unity实习雷达】全国客户端岗位｜{report['date']}", views.render(report),
             views.plain(report), report["message_id"], attachments=[
                 (f"Unity实习岗位清单-{report['date']}.html", "html", views.render(report).encode("utf-8")),
                 (f"Unity实习岗位清单-{report['date']}.csv", "csv", views.csv_content(report))])
    except Exception:
        report.update(status="uncertain", updated_at=now().isoformat())
        write(data_dir / "outbox.json", report)
        raise
    confirm(data_dir, report)
    checkpoint()
    LOG.info("Job email accepted by SMTP; recipient inbox placement is not verified")


def resolve(data_dir, confirmed):
    path = data_dir / "outbox.json"
    report = read(path, {})
    if report.get("status") not in ("attempting", "uncertain", "prepared"):
        raise RuntimeError("No unresolved job email")
    if confirmed:
        confirm(data_dir, report)
    else:
        report.update(status="abandoned", updated_at=now().isoformat())
        write(path, report)
    checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["collect", "preview", "preview-seeds", "preview-cached",
                                        "send", "prepare", "reserve", "deliver", "resume",
                                        "confirm-delivered", "release-delivery"])
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, default=ROOT.parent / "artifacts" / "jobs-preview.html")
    parser.add_argument("--weekly-token-limit", type=int)
    args = parser.parse_args()
    budget = Budget(args.data_dir)
    try:
        if args.mode == "resume":
            budget.resume(args.weekly_token_limit)
            LOG.info("Budget pause cleared; used/reserved counts retained; no paid requests made")
            return 0
        if args.weekly_token_limit is not None:
            raise RuntimeError("A budget override is only accepted with explicit resume")
        if args.mode in ("confirm-delivered", "release-delivery"):
            resolve(args.data_dir, args.mode == "confirm-delivered")
            return 0
        budget.gate()
        if args.mode in ("collect", "preview", "preview-seeds", "send"):
            if args.mode == "send":
                mail_settings()
                if read(args.data_dir / "outbox.json", {}).get("status") in ("attempting", "uncertain", "prepared"):
                    raise RuntimeError("Unresolved job email exists; no new collection or duplicate send")
            sources.collect(args.data_dir, budget, seed_only=args.mode == "preview-seeds")
        if args.mode in ("preview", "preview-seeds", "preview-cached"):
            build(args.data_dir, budget, args.output)
        elif args.mode == "send":
            prepare(args.data_dir, budget, args.output)
            reserve(args.data_dir)
            deliver(args.data_dir)
        elif args.mode == "prepare":
            prepare(args.data_dir, budget, args.output)
        elif args.mode == "reserve":
            reserve(args.data_dir)
        elif args.mode == "deliver":
            deliver(args.data_dir)
        checkpoint()
        return 0
    except QuotaPause:
        notify_pause(budget, args.data_dir)
        LOG.error("Job radar awaits user confirmation; progress preserved")
        return 78


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    try:
        sys.exit(main())
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            LOG.error("%s", str(exc))
        else:
            LOG.error("Job radar failed: %s", type(exc).__name__)
        sys.exit(1)
