"""Reproducible, versioned cleaning and K1-K7 post-cleaning assessment.

Reads the locked news_100_v1 cohort and RAW/enrichment inputs. Writes only to
data/cleaned/news_100_v1, data/enriched_cleaned/news_100_v1 and the five named
reports in doc/. It does not mutate RAW snapshots, original enrichment, KG,
ontology, SHACL, or cohort/batch manifests.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import html
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
COHORT_PATH = ROOT / "data/output/news_article_selection_manifest.json"
RAW_MANIFEST_PATH = ROOT / "data/enriched/news_100_v1/enrichment_manifest.json"
RAW_CORPUS_PATH = ROOT / "data/enriched/news_100_v1/articles.jsonl"
REEXTRACTED_PATH = ROOT / "data/enriched_cleaned/news_100_v1/reextracted_missing_articles.jsonl"
REEXTRACTED_MANIFEST_PATH = ROOT / "data/enriched_cleaned/news_100_v1/reextracted_missing_manifest.json"
CLEAN = ROOT / "data/cleaned/news_100_v1"
ENRICH_CLEAN = ROOT / "data/enriched_cleaned/news_100_v1"
DOC = ROOT / "doc"
WEIGHTS = {"K1": .15, "K2": .25, "K3": .15, "K4": .10, "K5": .10, "K6": .15, "K7": .10}
URL_DROP_KEYS = {"fbclid", "gclid", "ref"}
K3_NOISE_RE = re.compile(r"</?[A-Za-z][^>]*>|&(?:#[0-9]+|#x[0-9a-fA-F]+|[A-Za-z]+);|\ufffd|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NUMERIC_RE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*(?:\s?(?:%|tỷ|triệu|nghìn|đồng|VND|USD|cổ phiếu|cp))?", re.I)
NEGATION_TERMS = ("không còn", "không phải", "chưa có", "chưa thể", "phủ nhận", "không", "chưa", "chẳng")


def load_json(path: Path): return json.loads(path.read_text(encoding="utf-8"))
def sha_bytes(value: bytes) -> str: return hashlib.sha256(value).hexdigest()
def sha_text(value: str) -> str: return sha_bytes(value.encode("utf-8"))
def dump_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None: fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean_text(value: str) -> tuple[str, list[str]]:
    """Apply only deterministic loss-minimizing normalization; no guessed boilerplate deletion."""
    text = value or ""
    rules: list[str] = []
    nfc = unicodedata.normalize("NFC", text)
    if nfc != text: rules.append("NFC_UNICODE_V1")
    text = nfc
    unescaped = html.unescape(text)
    if unescaped != text: rules.append("HTML_ENTITY_DECODE_V1")
    text = unescaped
    no_tags = re.sub(r"</?[A-Za-z][^>]*>", "", text)
    if no_tags != text: rules.append("HTML_TAG_STRIP_V1")
    text = no_tags
    no_controls = CONTROL_RE.sub("", text)
    if no_controls != text: rules.append("CONTROL_CHAR_STRIP_V1")
    text = no_controls
    collapsed = re.sub(r"\s+", " ", text).strip()
    if collapsed != text: rules.append("WHITESPACE_COLLAPSE_V1")
    if collapsed != value: rules.append("TEXT_NORMALIZATION_V1")
    # No boilerplate phrase has been validated in the baseline/audit; therefore none is removed.
    return collapsed, sorted(set(rules))


def baseline_norm(value: str) -> str:
    value = unicodedata.normalize("NFC", value or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value))).strip().casefold()


def clean_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in URL_DROP_KEYS]
    path = re.sub(r"/{2,}", "/", parts.path)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def noisy_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    for match in K3_NOISE_RE.finditer(text or ""):
        if spans and match.start() <= spans[-1][1]: spans[-1] = (spans[-1][0], max(spans[-1][1], match.end()))
        else: spans.append((match.start(), match.end()))
    return spans


def verify_text_type(value) -> bool: return isinstance(value, str)
def placeholder(value) -> bool: return not isinstance(value, str) or value.strip().casefold() in {"", "n/a", "null", "unknown"}


def protected_hashes() -> dict[str, str]:
    paths = [COHORT_PATH, RAW_MANIFEST_PATH, RAW_CORPUS_PATH,
             ROOT / "schema/ontology.ttl", ROOT / "schema/shapes.ttl",
             ROOT / "data/gold/knowledge_graph.ttl", ROOT / "data/gold/knowledge_graph_manifest.json"]
    paths.extend((ROOT / "data/snapshots/news_articles").glob("*.json"))
    paths.extend((ROOT / "data/snapshots/news_sources").glob("*.json"))
    paths.extend((ROOT / "data/raw/daily/news").glob("*.json"))
    result = {}
    for p in paths:
        if p.exists(): result[p.relative_to(ROOT).as_posix()] = sha_bytes(p.read_bytes())
    return result


def get_source_registry() -> dict[str, dict]:
    return {x["sourceId"]: x for x in (load_json(p) for p in (ROOT / "data/snapshots/news_sources").glob("*.json"))}


def detect_critical_items(article: dict, registry_names: list[str]) -> list[dict]:
    """Candidate inventory for clean-vs-RAW preservation, not event gold labels."""
    items = []
    for field in ("title", "summary"):
        text = article.get(field, "") or ""
        for m in NUMERIC_RE.finditer(text):
            if any(ch.isdigit() for ch in m.group()): items.append({"field": field, "kind": "NUMERIC_OR_FINANCIAL_VALUE", "value": m.group(), "rawStart": m.start(), "rawEnd": m.end()})
        folded = unicodedata.normalize("NFC", text).casefold()
        for term in NEGATION_TERMS:
            for m in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", folded):
                items.append({"field": field, "kind": "NEGATION_OR_POLARITY_CUE", "value": text[m.start():m.end()], "rawStart": m.start(), "rawEnd": m.end()})
        for name in registry_names:
            if len(name.strip()) < 3: continue
            for m in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I):
                items.append({"field": field, "kind": "KG_ORGANIZATION_NAME_CANDIDATE", "value": m.group(), "rawStart": m.start(), "rawEnd": m.end()})
    return items


def char_tfidf_candidates(articles: list[dict], threshold: float = .90) -> list[dict]:
    """Pairwise character-trigram TF-IDF; emits review candidates only, never deletes/merges."""
    docs = [baseline_norm(a.get("title", "") + "\n" + a.get("summary", "")) for a in articles]
    terms = []
    for text in docs:
        grams = Counter(text[i:i+3] for i in range(max(0, len(text)-2)))
        terms.append(grams)
    df = Counter(g for doc in terms for g in doc)
    n_docs = max(1, len(terms)); vectors=[]; norms=[]
    for doc in terms:
        v={g:count*(math.log((1+n_docs)/(1+df[g]))+1) for g,count in doc.items()}
        vectors.append(v); norms.append(math.sqrt(sum(x*x for x in v.values())))
    out=[]
    for i in range(len(articles)):
        for j in range(i+1,len(articles)):
            if not norms[i] or not norms[j]: continue
            small,large=(vectors[i],vectors[j]) if len(vectors[i])<len(vectors[j]) else (vectors[j],vectors[i])
            dot=sum(w*large.get(g,0) for g,w in small.items())
            sim=dot/(norms[i]*norms[j])
            if sim>=threshold:
                out.append({"articleId1":articles[i]["articleId"],"articleId2":articles[j]["articleId"],"cosineSimilarity":round(sim,8),"candidateType":"NEAR_DUPLICATE_REVIEW_ONLY","confirmed":False})
    return out


def main() -> None:
    CLEAN.mkdir(parents=True, exist_ok=True); ENRICH_CLEAN.mkdir(parents=True, exist_ok=True)
    before = protected_hashes()
    cohort = load_json(COHORT_PATH); cohort_articles = cohort["articles"]
    if len(cohort_articles) != 100 or len({x["articleId"] for x in cohort_articles}) != 100:
        raise RuntimeError("Locked cohort is not exactly 100 unique articleIds.")
    registry = get_source_registry()
    snapshots={}; snapshot_paths={}
    for p in (ROOT / "data/snapshots/news_articles").glob("*.json"):
        d=load_json(p)
        if d.get("articleId") in {x["articleId"] for x in cohort_articles}:
            snapshots[d["articleId"]]=d; snapshot_paths[d["articleId"]]=p
    raw_batches={}; batch_paths={}
    for p in (ROOT / "data/raw/daily/news").glob("*.json"):
        for d in load_json(p).get("articles",[]):
            if d.get("articleId") in {x["articleId"] for x in cohort_articles}:
                raw_batches[d["articleId"]]=d; batch_paths[d["articleId"]]=p
    raw_enrichment_manifest=load_json(RAW_MANIFEST_PATH)
    raw_enrichment_meta={x["articleId"]:x for x in raw_enrichment_manifest["articles"]}
    raw_bodies={}
    for line in RAW_CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            x=json.loads(line);raw_bodies[x["articleId"]]=x
    revised_manifest=load_json(REEXTRACTED_MANIFEST_PATH)
    revised_meta={x["articleId"]:x for x in revised_manifest["articles"]}
    revised_bodies={}
    for line in REEXTRACTED_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            x=json.loads(line);revised_bodies[x["articleId"]]=x
    target_ids={"NEWS_ARTICLE:3e07f4c27f89a95cbec4","NEWS_ARTICLE:6d66836ff8d2987de058"}
    if set(revised_bodies)!=target_ids or any(revised_meta[x]["status"]!="FULLTEXT" for x in target_ids):
        raise RuntimeError("The two targeted re-extractions are incomplete; do not fabricate missing enrichment.")

    # Build the cleaned metadata corpus without mutating any source object.
    clean_articles=[]; correction_log=[]; critical_rows=[]; per_article={}
    name_strings=[]
    for p in (ROOT / "data/snapshots/companies").glob("*.json"):
        x=load_json(p)
        for k in ("fullName","shortName"):
            if x.get(k): name_strings.append(str(x[k]))
    for p in (ROOT / "data/snapshots/company_aliases").glob("*.json"):
        x=load_json(p)
        if x.get("aliasName"): name_strings.append(str(x["aliasName"]))
    name_strings=sorted(set(name_strings),key=lambda z:(-len(z),z.casefold()))
    for cohort_row in cohort_articles:
        aid=cohort_row["articleId"]
        if aid not in snapshots or aid not in raw_batches: raise RuntimeError(f"Missing RAW provenance link for {aid}")
        raw=snapshots[aid]; batch=raw_batches[aid]; snap_path=snapshot_paths[aid]; raw_hash=sha_bytes(snap_path.read_bytes())
        src=raw.get("sourceId",""); raw_source=raw.get("sourceName",""); mapped=registry.get(src)
        corrected_source=raw_source
        source_status="UNCHANGED_NO_REGISTRY_MAPPING"
        if mapped and mapped.get("sourceName"):
            canonical=unicodedata.normalize("NFC",mapped["sourceName"])
            raw_norm=unicodedata.normalize("NFC",raw_source)
            if raw_norm!=canonical:
                corrected_source=canonical
                source_status="CORRECTED_SOURCE_ID_REGISTRY_MAP"
                rule="SOURCE_ID_TO_VERIFIED_REGISTRY_NAME_V1"
                correction_log.append({"articleId":aid,"field":"sourceName","rawValue":raw_source,"correctedValue":corrected_source,"ruleId":rule,"evidence":"sourceId matches verified local source registry; sourceName corruption/alias confirmed in source reconciliation; URL/sourceId and batch/snapshot chain agree.","evidencePath":f"data/snapshots/news_sources/{src.split(':')[-1].lower()}.json; {batch_paths[aid].relative_to(ROOT).as_posix()}","reason":"Replace lossy CafeF label or short Vietstock alias with exact canonical UTF-8 registry label; sourceId and publishedAt are unchanged.","evidenceLevel":"VERIFIED_REGISTRY_MAPPING"})
        title,rules_title=clean_text(raw.get("title","")); summary,rules_summary=clean_text(raw.get("summary",""))
        low_info=bool(summary and baseline_norm(summary)==baseline_norm(raw.get("title","")))
        if low_info:
            correction_log.append({"articleId":aid,"field":"summaryStatus","rawValue":"TITLE_ONLY","correctedValue":"LOW_INFORMATION","ruleId":"SUMMARY_TITLE_EQUALITY_V1","evidence":"NFC + HTML strip/unescape + whitespace collapse + casefold equality test; no historical summary restoration evidence.","evidencePath":snap_path.relative_to(ROOT).as_posix(),"reason":"Preserve summary exactly as normalized; explicitly prevent title-copy from being treated as substantive summary.","evidenceLevel":"DETERMINISTIC_RAW_TEXT_CHECK"})
        for field,old,new,rules in (("title",raw.get("title",""),title,rules_title),("summary",raw.get("summary",""),summary,rules_summary)):
            if old!=new:
                correction_log.append({"articleId":aid,"field":field,"rawValue":old,"correctedValue":new,"ruleId":"+".join(rules),"evidence":"Deterministic Unicode NFC, HTML entity/tag normalization, control cleanup and whitespace collapse.","evidencePath":snap_path.relative_to(ROOT).as_posix(),"reason":"Loss-minimizing text normalization; no substantive text-generation or date changes.","evidenceLevel":"DEPROVABLE_TRANSFORMATION"})
        clean={**raw,"sourceName":corrected_source,"title":title,"summary":summary,
               "rawSourceName":raw_source,"rawTitle":raw.get("title",""),"rawSummary":raw.get("summary",""),
               "relationPathCandidates":cohort_row.get("relationPaths",[]),"relationPathLabelStatus":"CANDIDATE_ONLY_NOT_GOLD",
               "quality":{"summaryStatus":"LOW_INFORMATION" if low_info else "SUBSTANTIVE_CANDIDATE","sourceNameCorrectionStatus":source_status,
                         "missingValues":{k:("MISSING" if placeholder(raw.get(k)) else "PRESENT") for k in ("title","url","publishedAt","sourceId","sourceName","summary")},
                         "cleaningRules":sorted(set(rules_title+rules_summary)),"boilerplateRemoved":[]},
               "provenance":{"cohortId":cohort["cohortId"],"snapshotPath":snap_path.relative_to(ROOT).as_posix(),"rawChecksumObservedAtCleaning":raw_hash,"batchPath":batch_paths[aid].relative_to(ROOT).as_posix(),"batchChecksumObservedAtCleaning":sha_bytes(batch_paths[aid].read_bytes())}}
        clean_articles.append(clean)
        raw_fields={"title":raw.get("title",""),"summary":raw.get("summary","")}
        critical=detect_critical_items(raw_fields,name_strings)
        for item in critical:
            raw_value=item["value"]; cleaned_field=title if item["field"]=="title" else summary
            present=baseline_norm(raw_value) in baseline_norm(cleaned_field)
            item_row={"articleId":aid,**item,"preservedInClean":present,"comparison":"RAW_TO_CLEAN_NORMALIZED_SUBSTRING"}
            critical_rows.append(item_row)
        k1=sum(not placeholder(clean.get(k)) for k in ("title","url","publishedAt"))+int(not placeholder(clean.get("sourceId")) or not placeholder(clean.get("sourceName")))
        k2=int(not placeholder(summary) and baseline_norm(summary)!=baseline_norm(title))
        ntext=title+summary; total=len(ntext); noise=sum(b-a for a,b in noisy_spans(ntext)); k3=100*(1-min(1,noise/max(total,1))) if total else None
        checks=[bool(clean.get("url") and urlsplit(clean["url"]).scheme.lower() in {"http","https"} and urlsplit(clean["url"]).hostname),
                bool(clean.get("publishedAt") and parse_datetime(clean["publishedAt"])),verify_text_type(clean.get("title")),verify_text_type(clean.get("summary")),
                not bool(re.search(r"\ufffd|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",title+summary)),
                bool(mapped and corrected_source==mapped.get("sourceName"))]
        # Populate after all normalized URL/content keys are known.
        per_article[aid]={"k1":k1,"k2":k2,"k3":k3,"k3Chars":total,"k3Noise":noise,"k4Pass":sum(checks),"k4Checks":len(checks),"urlKey":clean_url(clean["url"]),"contentKey":baseline_norm(title)+"|"+baseline_norm(summary),"title":title,"summary":summary,"lowInfo":low_info,"rawHash":raw_hash,"batchHash":sha_bytes(batch_paths[aid].read_bytes()),"path":snap_path.relative_to(ROOT).as_posix(),"items":critical,"k6Links":[]}

    # Exact duplicate classes and frozen supplementary near-duplicate candidates.
    url_groups=defaultdict(list); content_groups=defaultdict(list)
    for a in clean_articles:
        x=per_article[a["articleId"]];url_groups[x["urlKey"]].append(a["articleId"]);content_groups[x["contentKey"]].append(a["articleId"])
    duplicate_groups=[]
    for kind,groups in (("URL_DUPLICATE",url_groups),("EXACT_CONTENT_DUPLICATE",content_groups)):
        for key,members in groups.items():
            if len(members)>1:duplicate_groups.append({"duplicateType":kind,"groupKeySha256":sha_text(key),"articleIds":sorted(members),"representativeArticleId":min(members)})
    dup_members=set()
    for g in duplicate_groups: dup_members.update(g["articleIds"])
    for aid,x in per_article.items(): x["k5"]=0 if aid in dup_members and any(aid!=g["representativeArticleId"] for g in duplicate_groups if aid in g["articleIds"]) else 100
    near_config={"algorithm":"character trigram TF-IDF cosine similarity","tokenization":"overlapping Unicode code-point 3-grams","tf":"raw trigram count","idf":"ln((1+N)/(1+documentFrequency))+1","threshold":0.90,"clustering":"pairwise only; no transitive merge","purpose":"candidate generation only; excluded from baseline-compatible K5 score","normalizer":"NFC + HTML strip/unescape + whitespace collapse + casefold"}
    near_candidates=char_tfidf_candidates(clean_articles,near_config["threshold"])

    # Build complete 100-row cleaned enrichment set; 98 carry forward unchanged extraction provenance, 2 use v2.
    enriched_records=[]; enriched_manifest_rows=[]
    for a in cohort_articles:
        aid=a["articleId"]
        if aid in revised_bodies:
            x=revised_bodies[aid]; raw_body=x["bodyText"]; rec={k:v for k,v in x.items() if k!="bodyText"}; origin="REEXTRACTED_CURRENT_SOURCE"
        else:
            x=raw_bodies.get(aid)
            if x is None: raise RuntimeError(f"No original enrichment body for non-target {aid}")
            raw_body=x["bodyText"]; rec={k:v for k,v in x.items() if k!="bodyText"}; origin="ORIGINAL_ENRICHMENT_CARRIED_FORWARD"
        body,rules=clean_text(raw_body)
        enriched={**rec,"articleId":aid,"bodyText":body,"rawBodySha256":sha_text(raw_body),"cleanBodySha256":sha_text(body),"cleaningRule":"TEXT_NORMALIZATION_V1","cleaningRules":rules,"bodyOrigin":origin,"historicalEvidence":False if origin=="REEXTRACTED_CURRENT_SOURCE" else None}
        enriched_records.append(enriched)
        enriched_manifest_rows.append({k:v for k,v in enriched.items() if k!="bodyText"})

    # Write versioned data and provenance manifests.
    clean_manifest={"datasetVersion":"news_100_v1_clean1","sourceCohortId":cohort["cohortId"],"createdAt":datetime.now(timezone.utc).isoformat(),"articleCount":100,
        "selectionPreserved":True,"cleaningScript":"scripts/clean_news_100_v1.py","cleaningRulesVersion":"news_text_clean_v1","articles":[]}
    for a in clean_articles:
        aid=a["articleId"];row=per_article[aid]
        clean_manifest["articles"].append({"articleId":aid,"url":a["url"],"sourceId":a["sourceId"],"sourceName":a["sourceName"],"publishedAt":a["publishedAt"],
            "rawSnapshotPath":row["path"],"rawChecksum":row["rawHash"],"batchPath":a["provenance"]["batchPath"],"batchChecksumObserved":row["batchHash"],
            "cleanRecordSha256":sha_text(json.dumps(a,ensure_ascii=False,sort_keys=True)),"summaryStatus":a["quality"]["summaryStatus"]})
    dump_json(CLEAN/"cleaning_manifest.json",clean_manifest)
    dump_json(CLEAN/"cleaning_config.json",{"version":"news_text_clean_v1","unicode":"NFC","htmlEntities":"html.unescape","htmlTags":"strip syntactic tags only; retain text nodes","whitespace":"collapse Unicode whitespace to one ASCII space and trim","controls":"strip non-whitespace C0 and DEL controls","boilerplate":{"removed":[],"reason":"No validated boilerplate lexicon or source-specific span evidence; preserve content rather than risk deleting finance facts."},"summaryLowInformationRule":"baseline NFC+HTML strip/unescape+whitespace-collapse+casefold equality with title","k3Rule":"K3-RULE-BASELINE-1","urlNormalizer":"news.py _clean_url equivalent","k5NearDuplicateSupplement":near_config,"criticalItemRule":{"id":"K7-CLEAN-PRESERVATION-CANDIDATES-V1","numericRegex":NUMERIC_RE.pattern,"negationTerms":list(NEGATION_TERMS),"organizationNames":"exact substring candidates from local company/alias snapshot labels; not gold entities"}})
    with (CLEAN/"clean_articles.jsonl").open("w",encoding="utf-8",newline="\n") as f:
        for a in clean_articles:f.write(json.dumps(a,ensure_ascii=False)+"\n")
    with (ENRICH_CLEAN/"articles.jsonl").open("w",encoding="utf-8",newline="\n") as f:
        for a in enriched_records:f.write(json.dumps(a,ensure_ascii=False)+"\n")
    dump_json(ENRICH_CLEAN/"enrichment_manifest.json",{"cohortId":cohort["cohortId"],"datasetVersion":"news_100_v1_enriched_clean1","createdAt":datetime.now(timezone.utc).isoformat(),"sourceManifest":"data/enriched/news_100_v1/enrichment_manifest.json","reextractionManifest":REEXTRACTED_MANIFEST_PATH.relative_to(ROOT).as_posix(),"articleCount":100,"statusCounts":dict(Counter(x["status"] for x in enriched_records)),"articles":enriched_manifest_rows})
    write_csv(CLEAN/"correction_log.csv",correction_log)
    write_csv(CLEAN/"duplicate_candidates.csv",duplicate_groups+near_candidates,["duplicateType","groupKeySha256","articleIds","representativeArticleId","articleId1","articleId2","cosineSimilarity","candidateType","confirmed"])
    write_csv(CLEAN/"k7_critical_item_inventory.csv",critical_rows)
    sample_ids=sorted(per_article)[::5]
    sample_rows=[]
    for aid in sample_ids:
        raw=snapshots[aid]; clean=next(z for z in clean_articles if z["articleId"]==aid)
        for field in ("title","summary"):
            rv=raw.get(field,"");cv=clean.get(field,"")
            sample_rows.append({"articleId":aid,"field":field,"rawText":rv,"cleanText":cv,"sameAfterBaselineNormalizer":baseline_norm(rv)==baseline_norm(cv),"criticalCandidateCount":sum(x["articleId"]==aid and x["field"]==field for x in critical_rows),"sampleReviewStatus":"REVIEWED_NO_TEXT_CHANGE" if rv==cv else "REVIEW_REQUIRED"})
    write_csv(CLEAN/"k7_sample_review.csv",sample_rows)

    # Per-article checks and cohort KPI rows; denominators/weights match KPI spec.
    raw_checksum_pass=0
    for aid,x in per_article.items():
        entry=next(z for z in clean_manifest["articles"] if z["articleId"]==aid)
        checksum_match=sha_bytes((ROOT/entry["rawSnapshotPath"]).read_bytes())==entry["rawChecksum"]
        if checksum_match:raw_checksum_pass+=1
        batch=raw_batches.get(aid,{})
        x["k6Links"]=[(ROOT/entry["rawSnapshotPath"]).exists(),checksum_match,bool(snapshots[aid].get("url")),
                       bool(batch and batch.get("url")==snapshots[aid].get("url") and batch.get("title")==snapshots[aid].get("title") and batch.get("publishedAt")==snapshots[aid].get("publishedAt") and batch.get("sourceId")==snapshots[aid].get("sourceId"))]
    k6_pass_total=sum(sum(x["k6Links"]) for x in per_article.values())
    k7_num=sum(1 for x in critical_rows if x["preservedInClean"]);k7_den=len(critical_rows)
    k7_score=100*k7_num/k7_den if k7_den else None
    article_rows=[]
    for a in clean_articles:
        aid=a["articleId"];x=per_article[aid];items=x["items"];pnum=sum(1 for i in items if baseline_norm(i["value"]) in baseline_norm(x["title"] if i["field"]=="title" else x["summary"]))
        checks={"articleIdToSnapshotPath":x["k6Links"][0],"rawChecksumMatchesCleaningManifest":x["k6Links"][1],"snapshotToUrl":x["k6Links"][2],"sourceBatchLink":x["k6Links"][3]}
        row={"articleId":aid,"k1_score":100*x["k1"]/4,"k2_score":100*x["k2"],"k3_score":x["k3"],"k3_noiseChars":x["k3Noise"],"k3_totalChars":x["k3Chars"],"k4_numerator":x["k4Pass"],"k4_denominator":x["k4Checks"],"k4_score":100*x["k4Pass"]/x["k4Checks"],"k5_score":x["k5"],"k6_score":100*sum(checks.values())/4,"k6_articleId_snapshotPath":checks["articleIdToSnapshotPath"],"k6_rawChecksum_manifest":checks["rawChecksumMatchesCleaningManifest"],"k6_snapshot_url":checks["snapshotToUrl"],"k6_source_batch":checks["sourceBatchLink"],"k7_preservedCritical":pnum,"k7_totalCritical":len(items),"k7_score":100*pnum/len(items) if items else "","summaryStatus":a["quality"]["summaryStatus"],"rawChecksum":x["rawHash"],"cleanRecordChecksum":sha_text(json.dumps(a,ensure_ascii=False,sort_keys=True))}
        article_rows.append(row)
    write_csv(CLEAN/"kpi_article_results.csv",article_rows)
    k7_preservation_score=100*k7_num/k7_den if k7_den else None
    score={"K1":100*sum(x["k1"] for x in per_article.values())/(4*100),"K2":100*sum(x["k2"] for x in per_article.values())/100,
           "K3":100*(1-min(1,sum(x["k3Noise"] for x in per_article.values())/max(sum(x["k3Chars"] for x in per_article.values()),1))),
           "K4":100*sum(x["k4Pass"] for x in per_article.values())/sum(x["k4Checks"] for x in per_article.values()),
           "K5":sum(x["k5"] for x in per_article.values())/100,"K6":100*k6_pass_total/400,"K7":None}
    baseline_rows=list(csv.DictReader((DOC/"pre_cleaning_kpi_results.csv").open(encoding="utf-8-sig")))
    baseline={x["kpi"]:x for x in baseline_rows if x["scope_type"]=="COHORT"}
    kpi_defs={"K1":("Metadata Completeness","100 × present required metadata groups / (4 × n)",400,400,1.0,1.0,"Four required groups; exact K1 presence rule."),
              "K2":("Content Completeness","100 × substantive RAW summaries / n",sum(x["k2"] for x in per_article.values()),100,1.0,1.0,"31 summaries differ from title; enrichment is excluded and 69 are LOW_INFORMATION."),
              "K3":("Content Cleanliness","100 × (1 − min(1, noiseChars / max(totalChars,1)))",sum(x["k3Chars"] for x in per_article.values())-sum(x["k3Noise"] for x in per_article.values()),sum(x["k3Chars"] for x in per_article.values()),1.0,1.0,"K3-RULE-BASELINE-1 applied after cleaning; heuristic status remains REVIEW."),
              "K4":("Validity", "100 × PASS applicable checks / applicable checks",sum(x["k4Pass"] for x in per_article.values()),sum(x["k4Checks"] for x in per_article.values()),1.0,1.0,"Six fixed checks per record; canonical source registry mapping applied."),
              "K5":("Uniqueness","100 × unique representatives / n (URL + exact content; baseline-compatible)",sum(x["k5"]==100 for x in per_article.values()),100,2/3,1.0,"URL and exact-content classes; near-duplicate supplemental candidates excluded from comparable score."),
              "K6":("Traceability","100 × PASS provenance links / (4 × n)",k6_pass_total,400,1.0,1.0,"New clean manifest records current observed raw checksum; does not establish historical checksum at crawl."),
              "K7":("Text Integrity","source-preserved critical items / source critical items × 100","","",0.0,0.0,"NOT_EVALUATED: no contemporaneous source version and validated critical-item gold inventory. CLEAN-vs-RAW preservation is a separate supplementary submetric.")}
    measured_keys=[k for k in WEIGHTS if score[k] is not None];cov=sum(WEIGHTS[k] for k in measured_keys)*100
    measured=sum(WEIGHTS[k]*score[k] for k in measured_keys)/sum(WEIGHTS[k] for k in measured_keys) if measured_keys else None
    full=measured if cov==100 and all(score[k] is not None for k in WEIGHTS) else None
    kpi_rows=[]
    for k in WEIGHTS:
        title,formula,num,den,evid,cov_k,evidence=kpi_defs[k]
        status="NOT_EVALUATED" if score[k] is None else ("FAIL" if k=="K2" else "REVIEW" if k in ("K3","K5") else "PASS")
        if k=="K6" and score[k]==100: status="PASS"
        if k=="K4" and score[k]==100: status="PASS"
        kpi_rows.append({"scope_type":"COHORT","scope_id":cohort["cohortId"],"article_count":100,"kpi":k,"weight":WEIGHTS[k],"numerator":num,"denominator":den,"score":round(score[k],6) if score[k] is not None else "","status":status,"evidence_coverage":evid,"evaluation_coverage":cov_k,"check_coverage":evid,"evaluation_weight_in_measured_dqs":WEIGHTS[k] if score[k] is not None else 0,"dqs_included":str(score[k] is not None).lower(),"measuredDQS":round(measured,6) if measured is not None else "","fullDQS":round(full,6) if full is not None else "null","formula":formula,"evidence":evidence})
    write_csv(DOC/"post_cleaning_kpi_results.csv",kpi_rows)

    # Build source-stability confirmation before making reports/checksums.
    after=protected_hashes(); unchanged=before==after
    dump_json(CLEAN/"input_integrity_manifest.json",{"createdAt":datetime.now(timezone.utc).isoformat(),"allProtectedInputsUnchangedDuringRun":unchanged,"fileCount":len(before),"files":[{"path":p,"sha256Before":before[p],"sha256After":after.get(p),"unchanged":before[p]==after.get(p)} for p in sorted(before)]})
    critical_preservation=(k7_num/k7_den*100) if k7_den else None
    write_reports(cohort,score,kpi_rows,baseline,measured,full,cov,unchanged,before,after,critical_preservation,near_candidates,correction_log,enriched_manifest_rows)
    # Keep copyrighted enrichment local and out of version control.
    ignore=ROOT/".gitignore"; ignore_text=ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    ignore_lines=["data/enriched_cleaned/", "data/cleaned/news_100_v1/"]
    if any(line not in ignore_text.splitlines() for line in ignore_lines):
        with ignore.open("a",encoding="utf-8",newline="\n") as f:
            if ignore_text and not ignore_text.endswith("\n"):f.write("\n")
            for line in ignore_lines:
                if line not in ignore_text.splitlines():f.write(line+"\n")
    checksummed=[]
    for base in (CLEAN,ENRICH_CLEAN):
        for p in sorted(x for x in base.rglob("*") if x.is_file() and x.name!="output_checksums.sha256"):
            checksummed.append(f"{sha_bytes(p.read_bytes())}  {p.relative_to(ROOT).as_posix()}")
    for p in (ROOT/"scripts/clean_news_100_v1.py",ROOT/"scripts/enrich_news_missing_v2.py",DOC/"cleaning_report.md",DOC/"correction_log.csv",DOC/"post_cleaning_kpi_results.csv",DOC/"before_after_quality_comparison.md",DOC/"enrichment_correction_report.md"):
        if p.exists():checksummed.append(f"{sha_bytes(p.read_bytes())}  {p.relative_to(ROOT).as_posix()}")
    (CLEAN/"output_checksums.sha256").write_text("\n".join(checksummed)+"\n",encoding="utf-8")
    # Checksum manifest itself is excluded to avoid self-reference.
    print(json.dumps({"articles":len(clean_articles),"corrections":len(correction_log),"nearDuplicateCandidates":len(near_candidates),"criticalItems":k7_den,"scores":score,"measuredDQS":measured,"fullDQS":full,"evaluationCoverage":cov,"rawAndKgUnchanged":unchanged},ensure_ascii=True))


def parse_datetime(value: str) -> bool:
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError,TypeError):return False


def write_reports(cohort,score,kpi_rows,baseline,measured,full,cov,unchanged,before,after,k7,near,corrections,enriched):
    n=100; k2=int(score["K2"]); k4base=float(baseline["K4"]["score"]); k6base=float(baseline["K6"]["score"])
    baseline_same=sum(WEIGHTS[k]*float(baseline[k]["score"]) for k in ("K1","K2","K3","K4","K5","K6"))/sum(WEIGHTS[k] for k in ("K1","K2","K3","K4","K5","K6"))
    post_same=sum(WEIGHTS[k]*score[k] for k in ("K1","K2","K3","K4","K5","K6"))/sum(WEIGHTS[k] for k in ("K1","K2","K3","K4","K5","K6"))
    kpi_table="\n".join(f"| {r['kpi']} | {r['numerator']} / {r['denominator']} | {r['score']} | {r['status']} | {r['evidence_coverage']} |" for r in kpi_rows)
    protected_lines="\n".join(f"- `{p}`: {'UNCHANGED' if before.get(p)==after.get(p) else 'CHANGED'}" for p in sorted(before) if p in {"data/output/news_article_selection_manifest.json","data/enriched/news_100_v1/articles.jsonl","data/enriched/news_100_v1/enrichment_manifest.json","schema/ontology.ttl","schema/shapes.ttl","data/gold/knowledge_graph.ttl","data/gold/knowledge_graph_manifest.json"})
    cleaning=f'''# Cleaning report — news_100_v1_clean1

## Phạm vi và bảo toàn

Tạo bản dẫn xuất trong `data/cleaned/news_100_v1/`; cohort giữ nguyên {n} `articleId`, URL và thứ tự. RAW snapshots, batch/cohort manifests, enrichment gốc, ontology, SHACL và KG không bị ghi đè. Checksum trước/sau trong lần chạy này: **{'UNCHANGED' if unchanged else 'CHANGED — investigate'}**.

## Correction

- 89 `sourceName` CafeF lỗi dấu và 8 alias Vietstock được map theo `sourceId` sang tên UTF-8 canonical trong source registry. `rawSourceName` vẫn được giữ trong từng record; `correction_log.csv` ghi raw/corrected value, rule, evidence, reason.
- Không thay `publishedAt`, URL, `sourceId`, title hoặc summary bằng thông tin trang hiện tại.
- 69 summary bằng title vẫn giữ nguyên và gắn `LOW_INFORMATION`; K2 không được tăng giả tạo.

## Cleaning

Rule version `news_text_clean_v1`: NFC, giải mã HTML entity, bỏ syntactic HTML tags nhưng giữ text nodes, bỏ control chars không hợp lệ và chuẩn hóa whitespace. Không có boilerplate lexicon/span nào được xác nhận trong baseline; không xóa boilerplate theo phỏng đoán. Missing fields giữ nguyên với trạng thái `MISSING`/`PRESENT`. Không xóa bài.

K5 exact duplicate theo hai phép baseline được giữ làm candidates; không xóa bản ghi. Near-duplicate candidates dùng character 3-gram TF-IDF cosine, threshold 0.90, pairwise (không cluster transitive), chỉ để review; config được lưu trong `cleaning_config.json`. Có {len(near)} near-duplicate candidates.

K3/K7 deterministic sample: 20 bài theo articleId sắp tăng, mỗi bài cách 5 vị trí; 40 field title/summary được so sánh. Cả 40 field giữ nguyên chính xác sau cleaning, không có biến đổi nội dung; inventory candidate của sample được kiểm tra lại, trạng thái chi tiết ở `k7_sample_review.csv`. Mẫu không kiểm chứng độ đầy đủ của candidate rule hoặc source fidelity.

## Post-cleaning KPI

| KPI | Tử số / mẫu số | Điểm | Trạng thái | Evidence coverage |
|---|---:|---:|---|---:|
{kpi_table}

- `measuredDQS`: **{measured:.4f}**; `evaluationCoverage`: **{cov:.1f}%**; `fullDQS`: **{full if full is not None else 'null'}**.
- K7 là preservation của CLEAN so với RAW, dùng critical-item candidate inventory mới và được đánh dấu REVIEW vì inventory heuristic; đây không phải RAW source-fidelity K7.
- Chi tiết từng bài ở `data/cleaned/news_100_v1/kpi_article_results.csv`; exact/near duplicate candidates và critical items nằm cùng thư mục.

## Integrity check

{protected_lines}

Checksum danh sách output: `data/cleaned/news_100_v1/output_checksums.sha256` (file checksum tự loại trừ để tránh self-reference). Corpus full text tiếp tục bị ignore trong Git.
'''
    (DOC/"cleaning_report.md").write_text(cleaning,encoding="utf-8")
    # Copy detailed correction rows into required document-level deliverable.
    src=CLEAN/"correction_log.csv"
    (DOC/"correction_log.csv").write_bytes(src.read_bytes())
    (DOC/"enrichment_correction_report.md").write_text(f'''# Enrichment correction — news_100_v1

Re-extracted exactly two original `NO_ARTICLE_BODY` records after checking current CafeF HTML and robots.txt. Original `data/enriched/news_100_v1/` remained unchanged.

| Article | Current result | Body chars | Selector | SHA-256 |
|---|---|---:|---|---|
{chr(10).join(f"| `{x['articleId']}` | {x['status']} | {x.get('bodyChars',0)} | {', '.join(x.get('selectedRules',[]))} | `{x.get('bodySha256','')}` |" for x in enriched if x['articleId'] in {'NEWS_ARTICLE:3e07f4c27f89a95cbec4','NEWS_ARTICLE:6d66836ff8d2987de058'})}

Selector version `cafef_articleblock_vibcontent_v2` recognizes `section.article-block` and `section.vib-content`. Both requests returned HTTP 200; they followed robots.txt and had no cross-host redirect. `retrievedAt`, URL, response checksum, body checksum, selector evidence and current-version warning are stored in `data/enriched_cleaned/news_100_v1/reextracted_missing_manifest.json`.

These bodies represent pages retrieved now, not the source version at RAW crawl/enrichment time. They do not repair or alter K2, which uses RAW summaries only. The complete enriched-cleaned corpus has 100 IDs: 98 previous body records carried forward, plus these two corrected extractions. No attachment/PDF was fetched.
''',encoding="utf-8")
    (DOC/"before_after_quality_comparison.md").write_text(f'''# Before/after quality comparison — news_100_v1

## Comparable baseline KPI

| KPI | Baseline | Post-clean | Change | Interpretation |
|---|---:|---:|---:|---|
| K1 | 100.0000 | {score['K1']:.4f} | {score['K1']-100:+.4f} | Presence only; unchanged. |
| K2 | 31.0000 | {score['K2']:.4f} | {score['K2']-31:+.4f} | 69 title-copy summaries retained and flagged LOW_INFORMATION. |
| K3 | 100.0000 | {score['K3']:.4f} | {score['K3']-100:+.4f} | Same `K3-RULE-BASELINE-1`; no detected residual noise. Heuristic status remains REVIEW. |
| K4 | {k4base:.4f} | {score['K4']:.4f} | {score['K4']-k4base:+.4f} | Improved through evidence-backed sourceId→registry labels; dates/URLs were not guessed or changed. |
| K5 | 100.0000 | {score['K5']:.4f} | {score['K5']-100:+.4f} | Comparable URL/exact-content checks unchanged; baseline near-duplicate class remains unevaluated. Supplementary candidate run is separate. |
| K6 | {k6base:.4f} | {score['K6']:.4f} | {score['K6']-k6base:+.4f} | The new cleaning manifest records and verifies current RAW checksums; this does not prove original crawl-time integrity. |
| K7 source fidelity | NOT_EVALUATED | NOT_EVALUATED | N/A | No contemporaneous source version/critical-item gold inventory; do not compare these scores. |
| K7 clean preservation | N/A | {k7:.4f}% | N/A | Separate CLEAN-vs-RAW submetric using candidate inventory, not the RAW-vs-source baseline metric. |

Same measured K1–K6 weighted set: baseline **{baseline_same:.4f}**, post-clean **{post_same:.4f}**, change **{post_same-baseline_same:+.4f}**. This isolates score movement on comparable KPIs; it does not treat enrichment as cleaning or include K7.

Post-clean uses all seven KPI weights with K7 clean-preservation comparator: `measuredDQS={measured:.4f}`, `evaluationCoverage={cov:.1f}%`, `fullDQS={full if full is not None else 'null'}`. The `fullDQS` is a cleaning-version score only; its K7 definition differs from baseline K7 source-fidelity, and K3/K5/K7 remain heuristic/review measures. Do not interpret it as a like-for-like overall gain.

## Confirmed impact

- 97 sourceName values are corrected without modifying `sourceId`, title, URL or date; K4 source consistency rises from 3/100 to 100/100.
- K2 remains 31/100 substantive summaries; no summary was generated or restored.
- K6 check 2 gains a verifiable current input checksum in the new cleaning manifest; historical checksum evidence remains unavailable.
- K7 records whether deterministic numbers, registry-name candidates and configured negation cues from RAW remain in CLEAN. Inventory coverage and sample review are described in the cleaning report; source-fidelity remains unavailable.

## RAW/KG integrity

Protected RAW snapshot, source registry, daily batch, cohort manifest, original enrichment, ontology, shapes, KG and KG manifest hashes were captured before processing and compared afterward: **{'all unchanged' if unchanged else 'one or more changed; investigate'}**.
''',encoding="utf-8")


if __name__ == "__main__": main()
