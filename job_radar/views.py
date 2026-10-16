"""Responsive, conservative Chinese job emails. Every displayed URL is source-owned."""
import html
import csv
import io

from .core import CONFIG, public_url

STATUSES = {"readable": "正文可读", "dynamic_or_empty": "动态页或内容不足", "network_error": "访问失败",
            "oversized": "超过读取大小限制", "restricted": "登录或安全验证受限", "closed": "已明确关闭",
            "expired": "已过截止日期", "missing_unconfirmed": "页面不存在，状态待核实",
            "unverified_domain": "域名尚未纳入核验", "daily_check_limit": "已到本日详情检查上限",
            "unsupported_content": "页面格式暂不支持", "redirect_limit": "重定向过多",
            "detail_context_unconfirmed": "无法确认正文对应当前实习职位"}
STATUSES.update(browser_error="动态页面读取失败", public_post="公开招聘帖，岗位状态待核实")


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
        state = ("客户端实习，引擎未披露" if row["classification"] == "engine_unspecified" else "详情可读，未见关闭或过期提示" if row["classification"] == "verified_detail"
                 else "已关闭或截止" if row["classification"] == "closed" else "待核实线索")
        summary = a.get("summary") or "仅有搜索线索或受限页面，尚未提取可确认的岗位字段。"
        reasons = a.get("relevance") or "请在原始平台正常查看岗位，核对 Unity、客户端及实习条件。"
        concerns = a.get("concerns") or "详情与当前招聘状态待核实。"
        excerpt = '<p style="font-size:12px;color:#667d8c">原始资料节选：' + esc(row["text"][:650]) + '</p>' if not a else ''
        evidence = ("公开详情正文" if row["page_status"] in ("readable", "closed", "expired")
                    else "搜索索引资料；本次未核验到完整详情")
        parts.append(f'''<div style="padding:17px;border:1px solid #dce6eb;margin:0 0 15px">
<div style="font-size:12px;color:#087d73">{esc(row['change'])} · {esc(state)}</div>
<h3 style="font-size:18px;margin:5px 0 12px">{esc(heading)}</h3>
<table role="presentation" width="100%" style="font-size:13px" cellspacing="0" cellpadding="0">{facts}</table>
<p style="font-size:14px;margin:12px 0">{esc(summary)}</p>{excerpt}
<div style="padding:10px 12px;background:#f2f7f8;font-size:13px"><strong>方向相关性：</strong>{esc(reasons)}<br>
<strong>需核对：</strong>{esc(concerns)}</div>
<p style="font-size:13px;margin:12px 0">{link(row['url'], '岗位详情')}　·　{link(a.get('company_website'), '公司官网')}　·　{link(a.get('company_careers'), '官方招聘')}</p>
<div style="font-size:12px;color:#667d8c">来源：{esc(row['source'])} · 页面状态：{esc(STATUSES.get(row['page_status'], '待核实'))}<br>
信息依据：{esc(evidence)}<br>
首次发现：{esc(row['first_seen'][:10])} · 最近检查：{esc(row['last_checked'][:10])}<br>
官网证据：{esc(a.get('website_evidence'))}；页面可读不等于招聘方保证仍可投递。</div></div>''')
    return "".join(parts)


def render(report):
    matched, leads, changes = len(report["jobs"]), len(report["leads"]), len(report["changes"])
    unspecified = len(report.get("engine_unspecified", []))
    seed_notice = ("<p style='padding:12px;background:#fff4d8'>仅为公开种子页试点，未进行全网岗位搜索。</p>"
                   if report["sources"].get("seed_only") else "")
    empty = "<p>本期没有详情可核验的明确 Unity 匹配岗位，其他客户端实习和受限线索见下方。</p>" if not matched else ""
    source_stats = report["sources"]
    observed = "，".join(f"{STATUSES.get(k, '待核实')} {v} 页" for k, v in source_stats.get("page_statuses", {}).items()) or "复用当日检查缓存"
    official = []
    for site in source_stats.get("company_sites", []):
        configured = next((c for c in CONFIG["companies"] if c["name"] == site["company"]), {})
        career = site.get("careers") or configured.get("careers")
        official.append(f"<li>{esc(site['company'])}：{link(site['website'], '公司官网')} · {link(career, '官方招聘入口')}"
                        f"<br>官网：{esc(STATUSES.get(site['status'], '待核实'))}；招聘页：{esc(STATUSES.get(site['careers_status'], '待核实'))}；"
                        f"读取方式：{'浏览器动态加载' if site.get('reader') == 'browser' else '静态公开页面'}；"
                        f"动态读取：{esc(STATUSES.get(site.get('browser_status'), '未记录或无需尝试'))}；"
                        f"发现客户端相关详情链接 {site.get('job_links_found', 0)} 条（含非实习，后续另行筛选）。</li>")
    official_section = ('<h2 style="font-size:20px">官网招聘入口与覆盖情况</h2><p style="font-size:13px">以下为本次检查的公司入口，不代表存在匹配或开放岗位。仅列本次读取到的公开页面和搜索结果；未承诺覆盖站内全部分页。</p>'
                        '<ul style="padding-left:20px;font-size:13px">' + "".join(official) + '</ul>') if official else ""
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unity 实习岗位雷达</title></head><body style="margin:0;background:#eff2f5;color:#172b3a;font-family:'Microsoft YaHei',Arial,sans-serif;line-height:1.8;word-break:break-word">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:22px 10px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:740px;background:white">
<tr><td style="padding:28px 24px;background:#132f43;color:white"><div style="color:#a5dcd3;font-size:12px;letter-spacing:3px">UNITY INTERNSHIP RADAR</div>
<h1 style="font-size:30px;margin:8px 0">下一站，客户端开发</h1><div>全国 Unity 客户端实习 · 中文岗位简报</div>
<div style="font-size:13px;color:#afc6d5;margin-top:15px">{esc(report['date'])} · Unity 岗位 {matched} · 引擎未披露 {unspecified} · 待核实线索 {leads}</div></td></tr>
<tr><td style="padding:24px"><div style="font-size:13px;color:#536c7d">全国不限城市 · 实习生 · Unity 客户端；届别与出勤按岗位展示，不预设个人条件。</div>
{seed_notice}<h2 style="font-size:20px">本期先看</h2><div style="padding:15px 18px;background:#edf6f4;font-size:14px">
详情可核验的 Unity 岗位 {matched} 条，引擎未披露的游戏客户端实习 {unspecified} 条，待核实线索 {leads} 条。<br>
本期发送收集到的全部在列岗位，已发过的也保留；同一岗位的重复来源合并，不按发布时间截断。<br>
明确指向较早毕业届别的历史招聘帖已归档 {report.get('archived_historical', 0)} 条，不算当前岗位。<br>
尚未完成 AI 归纳的候选 {report['remaining_unprocessed']} 条仍保留标题、原始资料和链接。正式邮件附完整 HTML / CSV 清单。</div>
{empty}{cards(report['jobs'], 'Unity 客户端实习')}{cards(report.get('engine_unspecified', []), '游戏客户端实习 · 引擎未披露')}{cards(report['leads'], '待核实线索')}{cards(report['changes'], '重要状态变化')}{official_section}
<h2 style="font-size:20px">来源与用量</h2><p style="font-size:12px;color:#667d8c">本次检索 {source_stats.get('queries', 0)} 组关键词（新增搜索请求 {source_stats.get('new_search_requests', '未记录')} 次，其余复用当日缓存），发现 {source_stats.get('discovered', 0)} 条搜索结果（不是有效岗位数）。<br>
页面检查：{esc(observed)}。登录/验证受限的详情不作为已核验岗位。<br>
本周搜索已发起/保守预留 {report['usage'].get('search_weekly', '未记录')} / {report['usage'].get('search_weekly_limit', 200)} 次。<br>
本周模型已用/保守预留 {report['usage']['tokens_used_or_reserved']} Token，软预算 {report['usage']['weekly_limit']}。达到预算后需用户确认恢复。</p>
</td></tr><tr><td style="padding:18px 24px;background:#f5f8fa;font-size:12px;color:#667d8c">
事实字段从所列资料摘录，缺失不补写；中文解释含 AI 归纳。首次发现不代表刚发布，页面可读不代表招聘方确认仍开放。请在原始页面核对条件。</td></tr>
</table></td></tr></table></body></html>'''


def plain(report):
    lines = [f"Unity 实习岗位雷达 | {report['date']}", "全国 · Unity 客户端 · 实习"]
    for group in ("jobs", "engine_unspecified", "leads", "changes"):
        lines.append("\n" + {"jobs": "Unity客户端实习", "engine_unspecified": "游戏客户端实习·引擎未披露", "leads": "待核实线索", "changes": "重要状态变化"}[group])
        for job in report.get(group, []):
            a = job.get("analysis") or {}
            lines += [a.get("title") or job["title"], f"状态：{STATUSES.get(job['page_status'], '待核实')}",
                      f"公司：{a.get('company', '未披露')} | 城市：{a.get('city', '未披露')} | 薪资：{a.get('salary', '未披露')}",
                      "学历/届别："+a.get("education", "未披露")+" / "+a.get("graduation", "未披露"),
                      "出勤/时长："+a.get("days_per_week", "未披露")+" / "+a.get("duration", "未披露"),
                      a.get("summary", "资料不足"), a.get("concerns", "条件待核实"),
                      job["url"], "公司官网：" + (a.get("company_website") or "待核实"),
                      "官方招聘：" + (a.get("company_careers") or "待核实")]
    if not any(report.get(group) for group in ("jobs", "engine_unspecified", "leads", "changes")):
        lines.append("本期未收集到符合范围的在列岗位。")
    lines.append("\n以下为公司入口，不代表存在匹配或开放岗位：")
    for site in report["sources"].get("company_sites", []):
        lines += [site["company"]+"："+site["website"]]
    return "\n".join(lines)


def csv_content(report):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    fields = ("title", "company", "city", "salary", "education", "graduation", "days_per_week", "duration", "arrival", "closing_date")
    writer.writerow(["分类", "岗位", "公司", "城市", "薪资", "学历", "届别", "每周出勤", "实习时长", "到岗", "截止", "岗位链接", "公司官网", "官方招聘", "核验状态", "首次发现", "最近检查", "中文说明", "原始资料"])
    for group in ("jobs", "engine_unspecified", "leads"):
        for job in report.get(group, []):
            analysis = job.get("analysis") or {}
            cells = [{"jobs":"Unity客户端实习", "engine_unspecified":"游戏客户端实习·引擎未披露", "leads":"待核实线索"}[group]] + [analysis.get(key) or (job["title"] if key == "title" else "未披露") for key in fields]
            cells += [job["url"], analysis.get("company_website") or "待核实", analysis.get("company_careers") or "待核实",
                      STATUSES.get(job["page_status"], "待核实"), job["first_seen"], job["last_checked"], analysis.get("summary", "尚未归纳"), job["text"]]
            # Public source text must not become a spreadsheet formula.
            writer.writerow(["'"+str(value) if str(value).startswith(("=", "+", "-", "@")) else value for value in cells])
    return stream.getvalue().encode("utf-8-sig")
