"""Apply the 08:00 ICT HOSE cutoff to staging Events with verified page times."""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from wfkg.event_processing.effective_trading_date import HoseTradingCalendar, resolve_effective_trading_date

def main(run_dir: Path) -> dict[str, object]:
    stage_path=run_dir/'staging_review.json'
    rows=json.loads(stage_path.read_text(encoding='utf8'))
    raw_rows=[json.loads(line) for line in (ROOT/'data/cleaned/news_100_v1/clean_articles.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
    raw={str(row['articleId']):row for row in raw_rows}
    trusted=json.loads((ROOT/'data/derived/news_timestamp_trust_audit.json').read_text(encoding='utf8'))['sources']
    calendar_path=ROOT/'config/hose_trading_calendar_2026.json'
    calendar=HoseTradingCalendar.load(calendar_path)
    statuses=Counter(); previous_statuses=Counter(row.get('effectiveTradingDateStatus','UNSET') for row in rows); resolved_by_date=Counter()
    for row in rows:
        article_id=row['articleId']; article=raw.get(article_id,{})
        verified=trusted.get(article_id)
        source_timestamp=article.get('publishedAt')
        has_raw_clock=isinstance(source_timestamp,str) and ('T' in source_timestamp or ' ' in source_timestamp)
        result=resolve_effective_trading_date(source_timestamp,timestamp_reliable=has_raw_clock,calendar=calendar,assume_wall_clock_timezone=True)
        row['sourceTimestampRaw']=article.get('publishedAt')
        row['sourceTimestampUsed']=source_timestamp if has_raw_clock else None
        row['timestampReliabilityStatus']='RAW_WALL_CLOCK_ASSUMED_ASIA_HO_CHI_MINH' if has_raw_clock else 'UNRESOLVED_MISSING_PUBLICATION_HOUR'
        row['timestampInterpretation']='Preserve RAW publishedAt wall-clock fields and interpret them as Asia/Ho_Chi_Minh, ignoring the serialized UTC offset, per the project cutoff convention.' if has_raw_clock else 'No clock component in RAW publishedAt.'
        row['timestampSource']={
            'sourceName': verified.get('sourceName') if verified else article.get('sourceName'),
            'sourceUrl': verified.get('sourceUrl') if verified else article.get('url'),
            'pageDisplayedPublishedAt': verified.get('pageDisplayedPublishedAt') if verified else None,
            'verificationNote': (verified.get('verificationNote')+'; effective-date calculation follows configured RAW wall-clock ICT convention.' if verified else 'RAW publishedAt used as Asia/Ho_Chi_Minh wall time by the project convention; this is an explicit timezone assumption, not independent source-page verification.'),
            'sourceEvidencePath': verified.get('snapshotPath') if verified else article.get('provenance',{}).get('snapshotPath'),
            'sourceEvidenceSha256': verified.get('snapshotSha256') if verified else article.get('provenance',{}).get('rawChecksumObservedAtCleaning'),
            'timestampAuditFile': trusted_file_ref(article_id, verified),
        }
        row['effectiveTradingDate'] = result['effectiveTradingDate']
        row['effectiveTradingDateStatus'] = result['status']
        row['effectiveTradingDateReason'] = result['reason']
        row['publicationTimestampLocal'] = result['publicationTimestampLocal']
        row['effectiveTradingDateRule']={
            'ruleId':result['ruleId'],'cutoffLocal':result['cutoffLocal'],'timezone':result['timezone'],
            'calendarFile':'config/hose_trading_calendar_2026.json',
            'calendarBasis':'HOSE official 2026 holiday notices plus observed HOSE trading session dates in KG for 2026-07-16 through 2026-10-16',
            'applied':result['status']=='RESOLVED','timestampInterpretation':'RAW wall-clock fields treated as Asia/Ho_Chi_Minh; serialized offset ignored',
        }
        reasons=[reason for reason in row.get('reviewReasons',[]) if reason!='effectiveTradingDate is not established by model outputs' and not str(reason).startswith('effectiveTradingDate unresolved:')]
        if result['status']!='RESOLVED':
            reasons.append('effectiveTradingDate unresolved: '+str(result['reason']))
        else:
            resolved_by_date[str(result['effectiveTradingDate'])]+=1
        row['reviewReasons']=reasons
        statuses[str(result['status'])]+=1
    stage_path.write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    report_path=run_dir/'report.json'
    report=json.loads(report_path.read_text(encoding='utf8')) if report_path.exists() else {}
    report.update({
        'effectiveTradingDateRuleId':'HOSE_PUBLICATION_CUTOFF_0800_ICT_V1',
        'effectiveTradingDateCutoff':'08:00:00 Asia/Ho_Chi_Minh',
        'effectiveTradingDateStatusCounts':dict(statuses),
        'effectiveTradingDateResolvedByDate':dict(sorted(resolved_by_date.items())),
        'effectiveTradingDateCalendar':'config/hose_trading_calendar_2026.json',
        'effectiveTradingDateTimestampTrustSource':'RAW publishedAt; interpreted as Asia/Ho_Chi_Minh wall time per project convention',
        'effectiveTradingDateSystemRunAt':None,
        'effectiveTradingDateTimezoneAssumption':'RAW publishedAt wall-clock fields are Asia/Ho_Chi_Minh; serialized offset ignored',
    })
    report.setdefault('effectiveTradingDatePreviousStatusCounts',dict(previous_statuses))
    if report_path.exists():
        report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    return {'statusCounts':dict(statuses),'previousStatusCounts':dict(previous_statuses),'resolvedByDate':dict(resolved_by_date)}

def trusted_file_ref(article_id: str, verified: dict[str, object] | None) -> str | None:
    if not verified: return None
    return 'data/derived/news_timestamp_trust_audit.json#'+article_id

if __name__=='__main__':
    target=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'runs/news_event_vertical_slice_20261019'
    print(json.dumps(main(target),ensure_ascii=False))
