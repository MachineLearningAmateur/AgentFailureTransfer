"""Helpers shared by the AgentFailureTransfer scripts and tests.

This package contains no scientific interpretation. It only provides
deterministic plumbing: hashing, manifest handling, taxonomy-mapping loading,
reviewer-record loading, and an auditable Cohen's kappa.
"""

from agentfailuretransfer.agreement import agreement, cohen_kappa
from agentfailuretransfer.hashing import sha256_bytes, sha256_file
from agentfailuretransfer.manifest import (
    MANIFEST_REQUIRED_KEYS,
    MANIFEST_FILE_ENTRY_KEYS,
    load_manifest,
    validate_manifest_schema,
    verify_manifest_hashes,
)
from agentfailuretransfer.reviews import (
    load_review_jsonl,
    duplicate_case_ids,
)
from agentfailuretransfer.stats import (
    bootstrap_kappa,
    cohen_kappa_or_none,
    odds_ratio_woolf,
    permutation_difference_test,
    risk_difference_newcombe,
    risk_ratio_wald,
    wilson_interval,
)
from agentfailuretransfer.taxonomy import (
    FINE_LABELS,
    UNASSIGNED,
    family_for,
    load_family_mapping,
)

__all__ = [
    "agreement",
    "cohen_kappa",
    "sha256_bytes",
    "sha256_file",
    "MANIFEST_REQUIRED_KEYS",
    "MANIFEST_FILE_ENTRY_KEYS",
    "load_manifest",
    "validate_manifest_schema",
    "verify_manifest_hashes",
    "load_review_jsonl",
    "duplicate_case_ids",
    "bootstrap_kappa",
    "cohen_kappa_or_none",
    "odds_ratio_woolf",
    "permutation_difference_test",
    "risk_difference_newcombe",
    "risk_ratio_wald",
    "wilson_interval",
    "FINE_LABELS",
    "UNASSIGNED",
    "family_for",
    "load_family_mapping",
]
