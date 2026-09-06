"""Loading sealed reviewer JSONL records. Labels are never modified."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def load_review_jsonl(path: str | Path) -> list[dict]:
    """Read a sealed ``review_results.jsonl`` verbatim, preserving file order."""
    records: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return records


def duplicate_case_ids(records: Iterable[dict]) -> list[str]:
    """Return the sorted set of case_ids that occur more than once."""
    seen: dict[str, int] = {}
    for record in records:
        case_id = record["case_id"]
        seen[case_id] = seen.get(case_id, 0) + 1
    return sorted(cid for cid, count in seen.items() if count > 1)
