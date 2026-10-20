"""Create an auditable directory and manifest for each pipeline run."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from wfkg import __version__
from wfkg.config import ProjectConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_run(config: ProjectConfig, runs_dir: Path, run_id: str) -> Path:
    """Create run folder, preserve config and record schema hashes and model identity."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    config_copy = run_dir / "vertical_slice.yaml"
    config_copy.write_bytes(config.path.read_bytes())

    root = config.path.parent.parent
    schema_paths = {
        name: root / config.paths[name]
        for name in ("schema_ontology", "schema_shapes")
    }
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "package_version": __version__,
        "config_file": config_copy.name,
        "schema_sha256": {name: _sha256(path) for name, path in schema_paths.items()},
        "extractor": config.values.get("extractor", {}),
        "stock_symbols": list(config.stock_symbols),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run_dir
