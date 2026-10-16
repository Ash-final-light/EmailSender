"""Responsive, conservative Chinese job emails. Every displayed URL is source-owned."""
import html

from .core import public_url


def esc(value):
    return html.escape(str(value or "未披露"), quote=True)


def link(url, label):
    return f'<a style="color:#087d73" href="{esc(url)}">{esc(label)} →</a>' if public_url(url) else esc(label + "待核实")


def cards(rows, title):
    if not rows:
        return ""
    parts = [f'<h2 style="font-size:21px;margin:28px 0 12px">{esc(title)}</h2>']
    for row in rows:
        a = row.get("analysis") or {}
        heading = a.get("title") if a.get("title") not in (None, "未披露") else row["title"]
        fields = (("公司", a.get("company")), ("城市", a.get("city")), ("薪资", a.get("salary")),
                  ("学历 / 届别", " / ".join([a.get("education", "未披露"), a.get("graduation", "未披露")])),
                  ("出勤 / 时长", " / ".join([a.get("days_per_week", "未披露"), a.get("duration", "未披露")])),
                  ("到岗 / 截止", " / ".join([a.get("arrival", "未披露"), a.get("closing_date", "未披露")])))
        facts = "".join(f'<tr><td style="width:90px;vertical-align:top;color:#667d8c;padding:4px 0">{esc(k)}</td>'
                        f'<td style="padding:4px 0">{esc(v)}</td></tr>' for k, v in fields)
        state = ("详情可读，未见关闭或过期提示" if row["classification"] == "verified_detail"
                 else "已关闭或截止" if row["classification"] == "closed" else "待核实线索")
        summary = a.get("summary") or "仅有搜索线索或受限页面，尚未提取可确认的岗位字段。"
        reasons = a.get("relevance") or "请在原始平台正常查看岗位，核对 Unity、客户端及实习条件。"
        concerns = a.get("concerns") or "详情与当前招聘状态待核实。"
        parts.append(f'''<div style="padding:17px;border:1px solid #dce6eb;margin:0 0 15px">
<div style="font-size:12px;color:#087d73">{esc(row['change'])} · {esc(state)}</div>
<h3 style="font-size:18px;margin:5px 0 12px">{esc(heading)}</h3>
<table role="presentation" width="100%" style="font-size:13px" cellspacing="0" cellpadding="0">{facts}</table>
<p style="font-size:14px;margin:12px 0">{esc(summary)}</p>
<div style="padding:10px 12px;background:#f2f7f8;font-size:13px"><strong>方向相关性：</strong>{esc(reasons)}<br>
<strong>需核对：</strong>{esc(concerns)}</div>
<p style="font-size:13px;margin:12px 0">{link(row['url'], '岗位详情')}　·　{link(a.get('company_website'), '公司官网')}　·　{link(a.get('company_careers'), '官方招聘')}</p>
<div style="font-size:12px;color:#667d8c">来源：{esc(row['source'])} · 页面状态：{esc(row['page_status'])}<br>
首次发现：{esc(row['first_seen'][:10])} · 最近检查：{esc(row['last_checked'][:10])}<br>
官网证据：{esc(a.get('website_evidence'))}；页面可读不等于招聘方保证仍可投递。</div></div>''')
    return "".join(parts)


def render(report):
    matched, leads, changes = len(report["jobs"]), len(report["leads"]), len(report["changes"])
    seed_notice = ("<p style='padding:12px;background:#fff4d8'>仅为公开种子页试点，未进行全网岗位搜索。</p>"
                   if report["sources"].get("seed_only") else "")
    empty = "<p>本期没有新增或实质变化的匹配岗位。不会用过期、社招或非客户端岗位凑数。</p>" if not matched else ""
    source_stats = report["sources"]
    observed = ", ".join(f"{k}: {v}" for k, v in source_stats.get("page_statuses", {}).items()) or "复用当日检查缓存"
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unity 实习岗位雷达</title></head><body style="margin:0;background:#eff2f5;color:#172b3a;font-family:'Microsoft YaHei',Arial,sans-serif;line-height:1.8;word-break:break-word">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:22px 10px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:740px;background:white">
<tr><td style="padding:28px 24px;background:#132f43;color:white"><div style="color:#a5dcd3;font-size:12px;letter-spacing:3px">UNITY INTERNSHIP RADAR</div>
<h1 style="font-size:30px;margin:8px 0">下一站，客户端开发</h1><div>全国 Unity 客户端实习 · 中文岗位简报</div>
<div style="font-size:13px;color:#afc6d5;margin-top:15px">{esc(report['date'])} · 新增或变化岗位 {matched} · 待核实线索 {leads}</div></td></tr>
<tr><td style="padding:24px"><div style="font-size:13px;color:#536c7d">全国不限城市 · 实习生 · Unity 客户端；届别与出勤按岗位展示，不预设个人条件。</div>
{seed_notice}<h2 style="font-size:20px">本期先看</h2><div style="padding:15px 18px;background:#edf6f4;font-size:14px">
详情可核验的新增/变化岗位 {matched} 条，待核实线索 {leads} 条，已关闭或截止变化 {changes} 条。<br>
仍在记录中的可读匹配岗位共 {report['visible_total']} 条；尚未完成归纳的候选 {report['remaining_unprocessed']} 条。</div>
{empty}{cards(report['jobs'], '岗位详情已核验')}{cards(report['leads'], '待核实线索')}{cards(report['changes'], '重要状态变化')}
<h2 style="font-size:20px">来源与用量</h2><p style="font-size:12px;color:#667d8c">本次检索 {source_stats.get('queries', 0)} 组关键词，发现 {source_stats.get('discovered', 0)} 条搜索结果（不是有效岗位数）。<br>
页面检查：{esc(observed)}。登录/验证受限的详情不作为已核验岗位。<br>
本周模型已用/保守预留 {report['usage']['tokens_used_or_reserved']} Token，软预算 {report['usage']['weekly_limit']}。达到预算后需用户确认恢复。</p>
</td></tr><tr><td style="padding:18px 24px;background:#f5f8fa;font-size:12px;color:#667d8c">
事实字段从所列资料摘录，缺失不补写；中文解释含 AI 归纳。首次发现不代表刚发布，页面可读不代表招聘方确认仍开放。请在原始页面核对条件。</td></tr>
</table></td></tr></table></body></html>'''


def plain(report):
    lines = [f"Unity 实习岗位雷达 | {report['date']}", "全国 · Unity 客户端 · 实习"]
    for group in ("jobs", "leads", "changes"):
        lines.append("\n" + {"jobs": "岗位详情已核验", "leads": "待核实线索", "changes": "重要状态变化"}[group])
        for job in report[group]:
            a = job.get("analysis") or {}
            lines += [a.get("title") or job["title"], f"状态：{job['page_status']}",
                      f"公司：{a.get('company', '未披露')} | 城市：{a.get('city', '未披露')} | 薪资：{a.get('salary', '未披露')}",
                      job["url"], "公司官网：" + (a.get("company_website") or "待核实")]
    if not any(report[group] for group in ("jobs", "leads", "changes")):
        lines.append("本期无新增或重要变化的匹配岗位。")
    return "\n".join(lines)
