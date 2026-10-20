"""Re-extract only the two missing public article bodies into a new version.

This script never writes to data/enriched/news_100_v1. It honors robots.txt,
uses one request per URL with a delay, refuses cross-host redirects, and stores
the retrieval time and content checksum. Stored text remains local research data.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "data/output/news_article_selection_manifest.json"
RAW_ENRICH = ROOT / "data/enriched/news_100_v1/articles.jsonl"
RAW_MANIFEST = ROOT / "data/enriched/news_100_v1/enrichment_manifest.json"
OUT = ROOT / "data/enriched_cleaned/news_100_v1"
TARGET_IDS = {
    "NEWS_ARTICLE:3e07f4c27f89a95cbec4",
    "NEWS_ARTICLE:6d66836ff8d2987de058",
}
USER_AGENT = "WFKGVerticalSlice/0.2 (academic research; contact: project owner)"
SELECTOR_VERSION = "cafef_articleblock_vibcontent_v2"


class ArticleBodyV2(HTMLParser):
    """Extract known article containers, including CafeF's current markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.targets: list[int] = []
        self.skip_depth = 0
        self.parts: list[str] = []
        self.rules: list[str] = []

    @staticmethod
    def _match(tag: str, attrs: dict[str, str | None]) -> str | None:
        classes = set((attrs.get("class") or "").lower().split())
        ident = (attrs.get("id") or "").lower()
        itemprop = (attrs.get("itemprop") or "").lower()
        role = (attrs.get("data-role") or "").lower()
        if role == "content": return "data-role=content"
        if itemprop == "articlebody": return "itemprop=articleBody"
        if ident in {"vst_detail", "maincontent", "newscontent"}: return f"#{ident}"
        if "article-content" in classes: return ".article-content"
        if "detail-content" in classes: return ".detail-content"
        # Current CafeF article pages render their article as consecutive
        # section.article-block nodes, not the old #mainContent container.
        if tag == "section" and "article-block" in classes: return "section.article-block"
        # CafeF's VIB feature article uses a dedicated section wrapper.
        if tag == "section" and "vib-content" in classes: return "section.vib-content"
        return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if self._match(tag, a):
            self.targets.append(self.depth)
            self.rules.append(self._match(tag, a) or "")
        active = bool(self.targets)
        if active and tag in {"script", "style", "iframe", "noscript"}:
            self.skip_depth += 1
        elif active and self.skip_depth == 0 and tag in {"p", "br", "li", "h2", "h3", "tr"}:
            self.parts.append("\n")
        self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.depth = max(0, self.depth - 1)
        if self.targets and self.skip_depth and tag in {"script", "style", "iframe", "noscript"}:
            self.skip_depth -= 1
        elif self.targets and self.skip_depth == 0 and tag in {"p", "li", "h2", "h3", "tr"}:
            self.parts.append("\n")
        while self.targets and self.targets[-1] == self.depth:
            self.targets.pop()

    def handle_data(self, data: str) -> None:
        if self.targets and self.skip_depth == 0:
            value = " ".join(data.split())
            if value: self.parts.append(value)

    def text(self) -> str:
        lines = [re.sub(r"\s+", " ", x).strip() for x in "".join(self.parts).splitlines()]
        return "\n".join(x for x in lines if x)


def robots_allows(url: str) -> bool:
    host = urlsplit(url).hostname
    if not host: return False
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"https://{host}/robots.txt")
    request = Request(rp.url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=15) as response:
        rp.parse(response.read().decode("utf-8-sig", "replace").splitlines())
    return rp.can_fetch(USER_AGENT, url)


def extract(article: dict[str, object]) -> dict[str, object]:
    url = str(article["url"])
    start = datetime.now(timezone.utc).isoformat()
    out: dict[str, object] = {
        "articleId": article["articleId"], "url": url, "sourceId": article["sourceId"],
        "extractionVersion": SELECTOR_VERSION, "selectorVersion": SELECTOR_VERSION,
        "retrievedAt": start, "historicalEvidence": False,
    }
    if not robots_allows(url):
        out.update(status="ROBOTS_DISALLOW_OR_UNAVAILABLE", bodyChars=0)
        return out
    host = urlsplit(url).netloc.lower()
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read(5_000_001)
            out.update(httpStatus=response.status, finalUrl=response.geturl(), contentType=response.headers.get("Content-Type", ""))
        if urlsplit(str(out["finalUrl"])).netloc.lower() != host:
            out.update(status="CROSS_HOST_REDIRECT", bodyChars=0)
            return out
        if len(raw) > 5_000_000:
            out.update(status="RESPONSE_TOO_LARGE", bodyChars=0)
            return out
        parser = ArticleBodyV2()
        parser.feed(raw.decode("utf-8", errors="replace"))
        body = parser.text()
        out.update(
            status="FULLTEXT" if len(body) >= 120 else "PARTIAL" if body else "NO_ARTICLE_BODY",
            bodyChars=len(body), bodySha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            responseSha256=hashlib.sha256(raw).hexdigest(),
            selectedRules=sorted(set(parser.rules)),
        )
        if body: out["bodyText"] = body
    except HTTPError as exc:
        out.update(status="HTTP_ERROR", httpStatus=exc.code, bodyChars=0)
    except (URLError, TimeoutError, OSError, UnicodeError) as exc:
        out.update(status="FETCH_ERROR", errorType=type(exc).__name__, bodyChars=0)
    return out


def main() -> None:
    cohort = json.loads(COHORT.read_text(encoding="utf-8"))
    target = [x for x in cohort["articles"] if x["articleId"] in TARGET_IDS]
    if {x["articleId"] for x in target} != TARGET_IDS:
        raise RuntimeError("The fixed cohort does not contain the expected two target articleIds.")
    raw_rows = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))["articles"]
    raw_status = {x["articleId"]: x["status"] for x in raw_rows}
    if any(raw_status.get(aid) != "NO_ARTICLE_BODY" for aid in TARGET_IDS):
        raise RuntimeError("At least one target no longer matches the original missing-body manifest state.")
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for index, article in enumerate(target):
        records.append(extract(article))
        if index + 1 < len(target): time.sleep(1.2)
    with (OUT / "reextracted_missing_articles.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest = {
        "cohortId": cohort["cohortId"], "createdAt": datetime.now(timezone.utc).isoformat(),
        "extractionVersion": SELECTOR_VERSION, "script": "scripts/enrich_news_missing_v2.py",
        "sourceCorpus": "data/enriched/news_100_v1/articles.jsonl",
        "rightsNote": "Public page retrieval only when robots permits. One-copy private thesis research; no redistribution. Current retrieval is not historical RAW evidence.",
        "articles": [{k: v for k, v in x.items() if k != "bodyText"} for x in records],
    }
    (OUT / "reextracted_missing_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({x["articleId"]: {k: x.get(k) for k in ("status", "bodyChars", "bodySha256", "selectedRules", "retrievedAt")} for x in records}, ensure_ascii=True))


if __name__ == "__main__": main()
