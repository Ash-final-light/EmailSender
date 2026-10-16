"""Discover public job URLs and preserve the distinction between snippets and details."""
from datetime import timedelta
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests

from .core import (CONFIG, TZ, LOG, canonical, digest, domain, host_matches, now,
                   normalized, public_url, read, write)

UNITY = r"(?<![a-z])(?:unity(?:3d)?|u3d)(?![a-z])"
INTERN = r"实习|intern"
CLIENT = r"客户端|游戏.{0,10}(?:开发|编程|研发)|游戏程序|gameplay|game\s*(?:client|develop|program)"
NON_CLIENT = r"技术美术|美术|策划|运营|招聘实习|人力资源|测试实习|服务端|后端"
CLOSED = r"当前职位已下线|职位已关闭|岗位已关闭|停止招聘|已停止投递|招聘已结束|该职位已失效|收藏\s*已结束|该职位已结束"
DETAIL = r"/job_detail/[^/?]+|/intern/inn_[^/?]+|/jobs/(?:intern/)?detail|/(?:m/)?position/[\w-]+(?:/detail)?|/jobdetail/[^/?]+|/job/\d+"


def detail_url(url):
    p = urlsplit(url)
    return bool(re.search(DETAIL, p.path) or re.search(r"(?:position|job)/[\w-]+|jobId=[\w-]+", p.fragment)
                or (host_matches(domain(url), "51job.com") and bool(re.search(r"/\d+\.html|positiondetail", p.path)))
                or (company_for(url) and re.search(r"(?:jobId|positionId|postId)=", p.query, re.I)))


def public_post(url):
    return (host_matches(domain(url), "nowcoder.com") and bool(re.search(r"/discuss/\d+", url))
            or host_matches(domain(url), "mp.weixin.qq.com") and "/s/" in url)


def deadline(text):
    span = re.search(r"投递(?:时间|期限|有效期)[\s:：]*\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*[-~～至]\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    match = re.search(r"(?:截止(?:日期|时间)?|validThrough)[\s:：\"']{0,12}"
                      r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text, re.I)
    match = match or span
    if match:
        from datetime import date
        try:
            return date(*map(int, match.groups())).isoformat()
        except ValueError:
            pass
    return None


def expired(text, today=None):
    date = deadline(text)
    return bool(date and date < (today or now().astimezone(TZ).date().isoformat()))


def role_kind(title, text):
    if re.search(NON_CLIENT, title, re.I):
        return "excluded"
    if not (re.search(INTERN, title, re.I)
            or re.search(r"(?:岗位性质|职位性质|工作类型|employmentType)[\s:：\"']{0,10}实习|实习\s*\d+\s*个月", text, re.I)):
        return "excluded"
    if not re.search(UNITY, title + " " + text, re.I):
        if re.search(r"unreal|虚幻|UE[45]", title + " " + text, re.I):
            return "excluded"
        return "engine_unspecified" if (re.search(r"(?:游戏|手游).{0,8}(?:客户端|程序)", title, re.I)
            or re.search(r"客户端.{0,8}(?:开发|实习)", title, re.I) and re.search(r"游戏|手游|gameplay", text, re.I)) else "unknown"
    # A Unity bonus does not turn an explicitly UE-based role into a Unity role.
    if re.search(r"负责.{0,30}(?:UE[45]|Unreal|虚幻).{0,20}(?:开发|维护)|使用\s*(?:UE[45]|Unreal|虚幻).{0,20}(?:开发|实现)", text, re.I):
        return "excluded"
    if re.search(CLIENT, title, re.I):
        return "match"
    if re.search(r"XR|VR|AR|数字孪生|可视化|工业仿真", title, re.I):
        return "related"
    if re.search(CLIENT, text, re.I):
        return "match"
    return "related"


def company_for(url, config=CONFIG):
    host = domain(url)
    for company in config["companies"]:
        for base in [company["website"], company["careers"]] + company.get("entries", []):
            if base and host == domain(base):
                path = urlsplit(base).path.rstrip("/")
                if host_matches(host, "mokahr.com") and not (urlsplit(url).path == path or urlsplit(url).path.startswith(path + "/")):
                    continue
                return company
    return None


def known_company(name, config=CONFIG):
    name = normalized(name)
    if not name or name == "未披露":
        return None
    return next((company for company in config["companies"] + config.get("company_directory", [])
                 if any(normalized(alias) in name for alias in company["aliases"])), None)


def source_name(url):
    host = domain(url)
    for suffix, name in (("zhipin.com", "BOSS直聘"), ("shixiseng.com", "实习僧"), ("nowcoder.com", "牛客"),
                         ("liepin.com", "猎聘"), ("zhaopin.com", "智联招聘"), ("51job.com", "前程无忧")):
        if host_matches(host, suffix):
            return name
    company = company_for(url)
    return company["name"] + "招聘页" if company else host


def allowed_host(host, config=CONFIG):
    domains = config["platforms"] + config.get("public_post_domains", []) + [domain(url) for c in config["companies"]
              for url in [c["website"], c["careers"]] + c.get("entries", []) if url]
    return any(host_matches(host, suffix) for suffix in domains)


def parse_html(payload, current, url=None):
    url = url or current
    soup = BeautifulSoup(payload, "html.parser")
    postings = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            parsed = json.loads(script.string or script.get_text())
            nodes = parsed if isinstance(parsed, list) else [parsed]
            for node in nodes:
                if isinstance(node, dict):
                    nodes.extend(node.get("@graph", []))
                    if node.get("@type") == "JobPosting":
                        postings.append(node)
        except (ValueError, TypeError):
            continue
    links = [urljoin(current, link["href"]) for link in soup.find_all("a", href=True)]
    job_links = [{"url": urljoin(current, link["href"]),
                  "title": link.get_text(" ", strip=True)}
                 for link in soup.find_all("a", href=True)
                 if detail_url(urljoin(current, link["href"]))
                 and re.search(UNITY + "|" + CLIENT, link.get_text(" ", strip=True), re.I)]
    heading = soup.find("h1")
    heading = heading.get_text(" ", strip=True) if heading else ""
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup
    text = main.get_text(" ", strip=True)
    if heading and heading in text:
        text = text[text.index(heading):]
    structured = json.dumps(postings, ensure_ascii=False)
    text = (text[:7500] + ("\nJobPosting: " + structured[:7500] if postings else "")).strip()
    blocked = ("security.html" in current or "passport" in current
               or bool(re.search(r"请完成安全验证|访问验证|请先登录|验证码验证|滑块验证|访问过于频繁|verify you are human|please verify", text[:500], re.I)))
    if blocked:
        return {"status": "restricted", "url": url, "text": ""}
    if len(text) < 80:
        return {"status": "dynamic_or_empty", "url": url, "text": text}
    return {"status": "readable", "url": url, "text": text, "heading": heading,
            "structured": bool(postings), "links": links[:2000], "job_links": job_links}

def fetch(url):
    """Fetch only configured public domains; validate every redirect and cap response size."""
    current = url
    for _ in range(6):
        if not public_url(current) or not allowed_host(domain(current)):
            return {"status": "unverified_domain", "url": url, "text": ""}
        try:
            with requests.get(current, headers={"User-Agent": "UnityInternshipRadar/1.0 (public job reader)"},
                              timeout=(10, 20), allow_redirects=False, stream=True) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    current = urljoin(current, response.headers.get("Location", ""))
                    continue
                if response.status_code in (401, 403, 429, 451):
                    return {"status": "restricted", "url": url, "text": ""}
                if response.status_code == 404:
                    return {"status": "missing_unconfirmed", "url": url, "text": ""}
                response.raise_for_status()
                if "html" not in response.headers.get("Content-Type", "").lower():
                    return {"status": "unsupported_content", "url": url, "text": ""}
                chunks, length = [], 0
                for chunk in response.iter_content(16384):
                    length += len(chunk)
                    if length > 2000000:
                        return {"status": "oversized", "url": url, "text": ""}
                    chunks.append(chunk)
                return parse_html(b"".join(chunks), current, url)
        except requests.RequestException as exc:
            return {"status": "network_error", "url": url, "text": "", "error": type(exc).__name__}
    return {"status": "redirect_limit", "url": url, "text": ""}


def search(query, budget, cache, cache_path):
    key = digest(query["query"])
    day = now().astimezone(TZ).date().isoformat()
    stored = cache.get(key)
    if stored and stored["day"] == day:
        return stored["results"]
    import os
    if not os.getenv("BOCHA_API_KEY"):
        raise RuntimeError("BOCHA_API_KEY is missing")
    budget.reserve_search()
    try:
        response = requests.post(CONFIG["search_endpoint"], headers={
            "Authorization": "Bearer " + os.environ["BOCHA_API_KEY"], "Content-Type": "application/json"},
            json={"query": query["query"], "summary": True, "freshness": "noLimit", "count": 10},
            timeout=(10, 40), allow_redirects=False)
    except requests.RequestException:
        budget.pause("博查请求未完成，已保守计入一次请求；请确认网络或调用额度后恢复。")
    if response.status_code in (401, 402, 403, 429):
        budget.pause(f"博查搜索权限、余额或调用额度受限（HTTP {response.status_code}），需要检查并确认恢复。")
    if response.status_code != 200:
        raise RuntimeError(f"Bocha request failed (HTTP {response.status_code}); no automatic paid retry")
    payload = response.json()
    if payload.get("code", 200) != 200:
        budget.pause("博查返回非成功业务状态，请检查服务额度或权限后确认恢复。")
    data = payload.get("data") or payload
    results = data.get("webPages", {}).get("value", [])
    if not isinstance(results, list):
        raise RuntimeError("Bocha returned an invalid search result structure")
    results = [x for x in results if isinstance(x, dict) and public_url(x.get("url", ""))]
    if query.get("domain"):
        results = [x for x in results if host_matches(domain(x["url"]), query["domain"])]
    cache[key] = {"day": day, "results": results}
    write(cache_path, cache)
    return results


def collect(data_dir, budget, seed_only=False):
    budget.gate()
    jobs = read(data_dir / "jobs.json", {})
    search_cache = read(data_dir / "search-cache.json", {})
    page_cache = read(data_dir / "page-cache.json", {})
    stamp = now().isoformat()
    day = now().astimezone(TZ).date().isoformat()
    stats = {"checked_at": stamp, "seed_only": seed_only, "queries": 0,
             "discovered": 0, "page_statuses": {}, "new_urls": 0}
    search_before = budget.periods()[0]["search"]
    from .browser_reader import BrowserReader
    browser = BrowserReader()

    def page(url, render=False):
        key = digest(canonical(url))
        cached = page_cache.get(key, {})
        if cached.get("day") == day:
            result = cached["result"]
            if not render or result.get("render_attempted") and result.get("render_version") == 3:
                return result
        else:
            if not budget.reserve_detail():
                return {"status": "daily_check_limit", "url": url, "text": ""}
            result = fetch(url)
        if render and CONFIG.get("render_js") and result["status"] in ("dynamic_or_empty", "readable", "oversized") and not result.get("job_links"):
            if budget.reserve_detail():
                rendered = browser.read(url, reserve_view=budget.reserve_detail)
                result["browser_status"] = rendered["status"]
                if rendered["status"] == "readable" or result["status"] != "readable":
                    result = {**rendered, "links": list(dict.fromkeys(result.get("links", []) + rendered.get("links", [])))}
            result["render_attempted"] = True
            result["render_version"] = 3
        stats["page_statuses"][result["status"]] = stats["page_statuses"].get(result["status"], 0) + 1
        page_cache[key] = {"day": day, "result": result}
        write(data_dir / "page-cache.json", {k: v for k, v in page_cache.items() if v["day"] == day})
        return result

    def add(url, title="", snippet="", discovered_from="public_seed", hint=None):
        if not public_url(url):
            return
        url = canonical(url)
        posting = public_post(url)
        if not detail_url(url) and not posting:
            return  # Homepage/search lists are discovery inputs, never individual jobs.
        key = digest(url)
        old = jobs.get(key, {})
        if discovered_from == "search_result" and not old:
            if not re.search(INTERN, title + " " + snippet, re.I):
                return
            if not re.search(UNITY + "|" + CLIENT, title + " " + snippet, re.I):
                return
        result = page(url, render=bool(company_for(url)))
        text = (result.get("text") if result["status"] == "readable" else snippet or old.get("text")) or ""
        heading = result.get("heading") or title or old.get("title", "")
        if not re.search(INTERN, title + " " + heading + " " + text, re.I) and not old:
            return
        state = result["status"]
        if state == "readable":
            if re.search(CLOSED, text):
                state = "closed"
            elif expired(text):
                state = "expired"
            elif posting:
                state = "public_post"
            elif not result.get("structured") and role_kind(heading, text) == "excluded":
                state = "detail_context_unconfirmed"
        company = hint or company_for(url)
        raw_hash = digest(heading + text)
        record = {**old, "id": key, "url": url, "title": heading or title or "岗位标题待核实",
                  "text": text[:8000], "page_status": state, "source": source_name(url),
                  "discovered_from": discovered_from, "first_seen": old.get("first_seen", stamp),
                  "last_checked": stamp, "raw_hash": raw_hash, "deadline": deadline(text),
                  "company_hint": company["name"] if company else old.get("company_hint"),
                  "evidence": "public_post" if posting else "detail"}
        if old.get("raw_hash") != raw_hash:
            record.pop("analysis", None)
        jobs[key] = record
        stats["new_urls"] += int(not old)
        write(data_dir / "jobs.json", jobs)  # Preserve partial work before subsequent paid calls.

    try:
        # Check known homepages and discover actual public job links from official recruitment pages.
        for company in CONFIG["companies"]:
            home = page(company["website"])
            careers = page(company["careers"], render=True)
            linked_jobs = careers.get("job_links", [])
            for entry in company.get("entries", []):
                result = page(entry, render=True)
                linked_jobs += result.get("job_links", [])
            for link in linked_jobs:
                if company_for(link["url"]) == company:
                    add(link["url"], title=link["title"], hint=company, discovered_from="official_careers")
            stats.setdefault("company_sites", []).append({
                "company": company["name"], "website": company["website"],
                "careers": company["careers"],
                "status": home["status"], "careers_status": careers["status"], "job_links_found": len(linked_jobs)})
            LOG.info("Company source checked: %s; careers=%s; candidate links=%d", company["name"], careers["status"], len(linked_jobs))

        if seed_only:
            for url in CONFIG["validation_urls"]:
                add(url, discovered_from="validation_seed")
        else:
            if not __import__("os").getenv("BOCHA_API_KEY"):
                raise RuntimeError("BOCHA_API_KEY is missing; use preview-seeds only for an explicit limited trial")
            queries = CONFIG["queries"]
            if now().astimezone(TZ).weekday() not in (1, 4):
                # 40 on Tue/Fri + 24 on five other days = 200 searches/week.
                offset = now().astimezone(TZ).toordinal() % len(queries)
                queries = (queries[offset:] + queries[:offset])[:CONFIG["search_queries_quiet_day"]]
            for query in queries:
                hits = search(query, budget, search_cache, data_dir / "search-cache.json")
                stats["queries"] += 1
                stats["discovered"] += len(hits)
                for hit in hits:
                    add(hit["url"], hit.get("name") or "", hit.get("summary") or hit.get("snippet") or "",
                        discovered_from="search_result")
        # Recheck every retained active record; previous delivery never excludes it.
        for old in list(jobs.values()):
            if old["last_checked"][:10] != stamp[:10] and old["page_status"] not in ("closed", "expired"):
                add(old["url"], old["title"], old["text"], old.get("discovered_from", "recheck"))
    finally:
        browser.close()
    cutoff = (now() - timedelta(days=CONFIG["retention_days"])).isoformat()
    jobs = {key: value for key, value in jobs.items() if value["last_checked"] >= cutoff}
    write(data_dir / "jobs.json", jobs)
    stats["new_search_requests"] = budget.periods()[0]["search"] - search_before
    write(data_dir / "sources.json", stats)
    budget.save()
    LOG.info("Job collection: %d candidates retained; %d queries; %d new URLs",
             len(jobs), stats["queries"], stats["new_urls"])
    return jobs, stats
