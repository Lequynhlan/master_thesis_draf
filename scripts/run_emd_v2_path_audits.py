"""Recompute isolated path audits for baseline EMD v1 and EMD v2 staging."""
from __future__ import annotations
import importlib.util, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/news_event_vertical_slice_20261019"
def main():
    spec = importlib.util.spec_from_file_location("path_audit", ROOT / "scripts/audit_vertical_slice_entity_paths.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
    sources = {
        "fair_baseline_v1": RUN / "emd_v2_experiment/fair_baseline_v1/eae_trigger_conditioned_v1/staging_review_eae.json",
        "emd_v2": RUN / "emd_v2_experiment/eae_trigger_conditioned_v2/staging_review_eae.json",
    }
    results = {}
    for name, source in sources.items():
        out = RUN / "emd_v2_experiment" / "path_audits_fair" / name
        if out.exists() and any(out.iterdir()): raise SystemExit(f"Refusing to overwrite non-empty output: {out}")
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, out / "staging_review.json")
        mod.RUN = out
        results[name] = mod.main()
        print(name, json.dumps(results[name], ensure_ascii=False))
    (RUN / "emd_v2_experiment/path_audits_fair/comparison.json").write_text(json.dumps(results, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
if __name__ == "__main__": main()
