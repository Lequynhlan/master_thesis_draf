"""Fetch the fixed news cohort's article text into a separate local corpus.

This intentionally does not modify snapshots or RDF. Article text is copyrighted
source material; keep this one-copy research corpus private and do not redistribute.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/output/news_article_selection_manifest.json"
OUT = ROOT / "data/enriched/news_100_v1"
USER_AGENT = "WFKGVerticalSlice/0.1 (academic research; contact: project owner)"


class ArticleText(HTMLParser):
    """Collect readable text only inside known article-body containers."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.capture_depth: int | None = None
        self.skip_depth = 0
        self.parts: list[str] = []

    @staticmethod
    def _target(tag: str, a: dict[str, str | None]) -> bool:
        classes = set((a.get("class") or "").lower().split())
        ident = (a.get("id") or "").lower()
        return (
            a.get("data-role") == "content"
            or a.get("itemprop") == "articleBody"
            or ident in {"vst_detail", "maincontent", "newscontent"}
            or "article-content" in classes
            or "detail-content" in classes
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if self.capture_depth is None and self._target(tag, a):
            self.capture_depth = self.depth
        if self.capture_depth is not None and tag in {"script", "style", "iframe", "noscript"}:
            self.skip_depth += 1
        elif self.capture_depth is not None and self.skip_depth == 0 and tag in {"p", "br", "li", "h2", "h3", "tr"}:
            self.parts.append("\n")
        self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.depth = max(0, self.depth - 1)
        if self.capture_depth is not None and self.skip_depth and tag in {"script", "style", "iframe", "noscript"}:
            self.skip_depth -= 1
        elif self.capture_depth is not None and self.skip_depth == 0 and tag in {"p", "li", "h2", "h3", "tr"}:
            self.parts.append("\n")
        if self.capture_depth == self.depth:
            self.capture_depth = None

    def handle_data(self, data: str) -> None:
        if self.capture_depth is not None and self.skip_depth == 0:
            cleaned = " ".join(data.split())
            if cleaned:
                self.parts.append(cleaned)

    def text(self) -> str:
        lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)


def fetch(article: dict[str, object]) -> dict[str, object]:
    url = str(article["url"])
    host = urlsplit(url).netloc.lower()
    entry: dict[str, object] = {
        "articleId": article["articleId"], "url": url, "sourceId": article["sourceId"],
        "status": "FETCH_ERROR", "capturedAt": datetime.now(timezone.utc).isoformat(),
    }
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        with urlopen(req, timeout=20) as response:
            status = response.status
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(5_000_001)
            charset = response.headers.get_content_charset() or "utf-8"
        entry.update(httpStatus=status, finalUrl=final_url, contentType=content_type)
        if len(raw) > 5_000_000:
            entry["status"] = "RESPONSE_TOO_LARGE"
            return entry
        if urlsplit(final_url).netloc.lower() != host:
            entry["status"] = "CROSS_HOST_REDIRECT"
            return entry
        parser = ArticleText()
        parser.feed(raw.decode(charset, errors="replace"))
        body = parser.text()
        entry["bodyChars"] = len(body)
        entry["bodySha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        # Many Vietnamese disclosure stories are legitimately only a few lines.
        # The selected container is the complete HTML article body, so classify by
        # whether meaningful article text exists rather than by a long-article cutoff.
        if len(body) >= 120:
            entry["status"] = "FULLTEXT"
            entry["bodyText"] = body
        elif body:
            entry["status"] = "PARTIAL"
            entry["bodyText"] = body
        else:
            entry["status"] = "NO_ARTICLE_BODY"
    except HTTPError as exc:
        entry.update(status="HTTP_ERROR", httpStatus=exc.code)
    except (URLError, TimeoutError, OSError, UnicodeError) as exc:
        entry.update(status="FETCH_ERROR", error=type(exc).__name__)
    return entry


def main() -> int:
    cohort = json.loads(INPUT.read_text(encoding="utf-8"))
    articles = cohort["articles"]
    OUT.mkdir(parents=True, exist_ok=True)
    corpus_path = OUT / "articles.jsonl"
    manifest: dict[str, object] = {
        "cohortId": cohort["cohortId"], "createdAt": datetime.now(timezone.utc).isoformat(),
        "purpose": "Private, noncommercial thesis research; one local copy; no redistribution.",
        "rightsNote": "Robots permission is not a copyright license. Use relies on the research-copy exception as a cautious working assumption; legal applicability to automated bulk capture is not determined here.",
        "articles": [],
    }
    with corpus_path.open("w", encoding="utf-8", newline="\n") as out:
        for index, article in enumerate(articles, 1):
            record = fetch(article)
            body = record.pop("bodyText", None)
            if body:
                out.write(json.dumps({**record, "bodyText": body}, ensure_ascii=False) + "\n")
            manifest["articles"].append(record)
            if index % 10 == 0:
                print(f"progress={index}/{len(articles)} full={sum(x['status']=='FULLTEXT' for x in manifest['articles'])} partial={sum(x['status']=='PARTIAL' for x in manifest['articles'])}", flush=True)
            if index < len(articles):
                time.sleep(1.0)
    statuses: dict[str, int] = {}
    for record in manifest["articles"]:
        statuses[record["status"]] = statuses.get(record["status"], 0) + 1
    manifest["statusCounts"] = statuses
    (OUT / "enrichment_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(statuses, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
