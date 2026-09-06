"""Helpers shared by the AgentFailureTransfer scripts and tests.

This package contains no scientific interpretation. It only provides
deterministic plumbing: hashing, manifest handling, taxonomy-mapping loading,
reviewer-record loading, and an auditable Cohen's kappa.

The re-exports below are resolved lazily (PEP 562). The public API is exactly
what it was before: ``from agentfailuretransfer import wilson_interval`` and
``import agentfailuretransfer; agentfailuretransfer.cohen_kappa`` both work,
and every submodule remains importable by name. Resolving them on first use
rather than at import time is what lets a Phase 2 reviewer bundle ship a
*subset* of this package -- ``hashing``, ``reviews`` and ``phase2`` -- without
also shipping ``stats``/``agreement`` (which pull in numpy and scipy, and whose
docstrings describe Phase 1 results a blinded reviewer must not see).
"""

from __future__ import annotations

from typing import Any

#: attribute name -> submodule that defines it.
_LAZY: dict[str, str] = {
    "agreement": "agentfailuretransfer.agreement",
    "cohen_kappa": "agentfailuretransfer.agreement",
    "sha256_bytes": "agentfailuretransfer.hashing",
    "sha256_file": "agentfailuretransfer.hashing",
    "MANIFEST_REQUIRED_KEYS": "agentfailuretransfer.manifest",
    "MANIFEST_FILE_ENTRY_KEYS": "agentfailuretransfer.manifest",
    "load_manifest": "agentfailuretransfer.manifest",
    "validate_manifest_schema": "agentfailuretransfer.manifest",
    "verify_manifest_hashes": "agentfailuretransfer.manifest",
    "load_review_jsonl": "agentfailuretransfer.reviews",
    "duplicate_case_ids": "agentfailuretransfer.reviews",
    "bootstrap_kappa": "agentfailuretransfer.stats",
    "cohen_kappa_or_none": "agentfailuretransfer.stats",
    "odds_ratio_woolf": "agentfailuretransfer.stats",
    "permutation_difference_test": "agentfailuretransfer.stats",
    "risk_difference_newcombe": "agentfailuretransfer.stats",
    "risk_ratio_wald": "agentfailuretransfer.stats",
    "wilson_interval": "agentfailuretransfer.stats",
    "FINE_LABELS": "agentfailuretransfer.taxonomy",
    "UNASSIGNED": "agentfailuretransfer.taxonomy",
    "family_for": "agentfailuretransfer.taxonomy",
    "load_family_mapping": "agentfailuretransfer.taxonomy",
}

__all__ = list(_LAZY)


def __getattr__(name: str) -> Any:
    module_name = _LAZY.get(name)
    if module_name is None:
        # AttributeError, not ImportError: `from agentfailuretransfer import
        # paths` relies on this falling through to a submodule import.
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module_name), name)


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()))
