"""Load and validate project configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


EXPECTED_ARTICLE_LIMIT = 100
EXPECTED_STOCK_COUNT = 13


@dataclass(frozen=True)
class ProjectConfig:
    path: Path
    values: dict[str, Any]

    @property
    def stock_symbols(self) -> tuple[str, ...]:
        values = self.values.get("vertical_slice", {}).get("stock_symbols", [])
        return tuple(str(symbol).strip().upper() for symbol in values)

    @property
    def paths(self) -> dict[str, str]:
        return self.values.get("paths", {})


def load_config(path: Path) -> ProjectConfig:
    """Read YAML config, resolving the config path from the current directory."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Config file not found: {resolved}")
    with resolved.open("r", encoding="utf-8") as stream:
        values = yaml.safe_load(stream) or {}
    if not isinstance(values, dict):
        raise ValueError("Top-level config must be a YAML mapping.")
    return ProjectConfig(path=resolved, values=values)


def validate_vertical_slice(config: ProjectConfig, project_root: Path) -> list[str]:
    """Return human-readable configuration errors; an empty list means valid."""
    errors: list[str] = []
    slice_config = config.values.get("vertical_slice", {})
    if slice_config.get("article_limit") != EXPECTED_ARTICLE_LIMIT:
        errors.append(f"vertical_slice.article_limit must equal {EXPECTED_ARTICLE_LIMIT}.")

    symbols = config.stock_symbols
    if len(symbols) != EXPECTED_STOCK_COUNT:
        errors.append(f"vertical_slice.stock_symbols must contain exactly {EXPECTED_STOCK_COUNT} tickers.")
    if len(set(symbols)) != len(symbols):
        errors.append("vertical_slice.stock_symbols contains duplicate tickers.")
    if any(not symbol.isalnum() for symbol in symbols):
        errors.append("Each stock ticker must contain only letters and digits.")
    if not slice_config.get("benchmark_index"):
        errors.append("vertical_slice.benchmark_index is required.")

    for key in ("schema_ontology", "schema_shapes"):
        relative_path = config.paths.get(key)
        if not relative_path:
            errors.append(f"paths.{key} is required.")
            continue
        if not (project_root / relative_path).is_file():
            errors.append(f"Schema file does not exist: {relative_path}")

    return errors
