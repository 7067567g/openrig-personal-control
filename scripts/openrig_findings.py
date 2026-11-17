#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openrig_findings.py — runtime mount for the historical findings policy (D24).

The policy is a 106-entry findings-to-defense matrix.  Runtime validation reads the
matrix and the embedded, source-bound acceptance-test inventory only; it does not
re-read or re-certify the historical source corpus.  The documented source-coverage
result remains a separate, frozen fact.

Policy discovery order (first existing file wins):
  1. ``$OPENRIG_HISTORICAL_FINDINGS_POLICY`` (an explicit override is fail-closed:
     if it is set but missing, we do not silently fall through);
  2. ``<run-dir>/openrig/HISTORICAL-FINDINGS-POLICY.json`` for a self-contained bundle;
  3. the workspace default under ``ROOT.parent.parent/deepseek-项目/...``.

A missing or invalid policy is a blocking check failure in ``openrig_run check``.
Dependency-free: standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
EXPECTED_FINDINGS = 106
MIN_MAPPED = 90
MIN_DEFERRED = 1
EXPECTED_ACCEPTANCE_TESTS = 57

# Trust anchors for the embedded acceptance inventory.  The runtime accepts only the
# frozen EXECUTION-TREE-v2 source bytes and the exact ordered 57-id acceptanceMap; a
# policy that merely self-reports a hash cannot satisfy these pins.
# Any update to the frozen EXECUTION-TREE-v2 file or reordering of its acceptanceMap
# MUST update these constants and carry a migration note.
EXPECTED_SOURCE_SHA256 = (
    "e01443e5a8c76bd9465b8c9b0cfca043411324d8d249ab90b884c401486d36e9"
)
EXPECTED_TEST_IDS_SHA256 = (
    "edd72d1664deaad9302516ba81371e81fe10cc7050a48d71433813b72c8cee6d"
)

ENV_VAR = "OPENRIG_HISTORICAL_FINDINGS_POLICY"
POLICY_REL = Path("openrig") / "HISTORICAL-FINDINGS-POLICY.json"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = (
    ROOT.parent.parent
    / "deepseek-项目"
    / "10-openrig-deepseek"
    / "docs"
    / "as-built"
    / "historical-findings-policy.json"
)

DEFENSE_IDS = frozenset(f"D{index:02d}" for index in range(1, 26))
DECISION_ID_RE = re.compile(r"^[A-Z]-")
ACCEPTANCE_TEST_ID_RE = re.compile(r"^AT-[A-Z0-9]+(?:-[A-Z0-9]+)+$")
HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")

DISPOSITIONS = frozenset({"adopt", "defer", "already-covered"})
FINDING_CLASSES = frozenset(
    {
        "accepted_risk",
        "already_covered",
        "design_gap",
        "meta_requirement",
        "observed_defect",
        "unimplemented",
    }
)
SEVERITIES = frozenset({"S1", "S2", "S3"})
MIN_ANCHOR_LEN = 3
MAX_ANCHOR_LEN = 240


def resolve_policy_path(
    bridge: dict | None, run_dir: str | Path
) -> tuple[Path | None, str | None]:
    """Resolve the policy file without reading it.

    ``bridge`` is kept in the call signature because this is a run-level policy check;
    policy path discovery deliberately comes from the environment and the run/workspace
    layout, never from a mutable bridge field.

    Returns ``(path, None)`` on success and ``(None, reason)`` when no usable file is
    found.  An explicitly configured environment path that does not exist is an error,
    not an invitation to fall back to a less-specific policy.
    """
    del bridge  # reserved for the stable caller signature; discovery is run/workspace-based
    run_dir = Path(run_dir)

    configured = os.environ.get(ENV_VAR, "").strip()
    if configured:
        env_path = Path(configured).expanduser()
        if env_path.is_file():
            return env_path, None
        return (
            None,
            f"{ENV_VAR} is set to {configured!r} but does not point to a file: {env_path}",
        )

    bundle_path = run_dir / POLICY_REL
    if bundle_path.is_file():
        return bundle_path, None

    default_path = Path(DEFAULT_POLICY_PATH)
    if default_path.is_file():
        return default_path, None

    return (
        None,
        "historical findings policy not found; checked "
        f"{ENV_VAR} (unset), bundle={bundle_path} (missing), "
        f"workspace-default={default_path} (missing)",
    )


def _validate_acceptance_inventory(document: dict, errors: list[str]) -> set[str]:
    """Validate the declared acceptance-test inventory and return its ids.

    The inventory is deliberately embedded in the policy (source + source sha256 +
    explicit ``testIds``) so a runtime check can resolve every cited test without
    reading a mutable external corpus.  The source bytes and the ordered id list are
    pinned to the frozen EXECUTION-TREE-v2 acceptanceMap; a self-reported hash alone is
    not accepted.  The product/workspace test separately re-proves the same provenance.
    """
    inventory = document.get("acceptanceTestInventory")
    if not isinstance(inventory, dict):
        errors.append("acceptanceTestInventory must be a JSON object")
        return set()

    source = inventory.get("source")
    if not isinstance(source, str) or not source.strip():
        errors.append("acceptanceTestInventory.source must be a non-empty string")
    source_schema = inventory.get("sourceSchema")
    if not isinstance(source_schema, str) or not source_schema.strip():
        errors.append("acceptanceTestInventory.sourceSchema must be a non-empty string")
    source_sha256 = inventory.get("sourceSha256")
    if not isinstance(source_sha256, str) or HEX64_RE.fullmatch(source_sha256) is None:
        errors.append("acceptanceTestInventory.sourceSha256 must be 64-hex")
    elif source_sha256 != EXPECTED_SOURCE_SHA256:
        errors.append(
            "acceptanceTestInventory.sourceSha256 is not pinned: expected "
            f"{EXPECTED_SOURCE_SHA256}, got {source_sha256}"
        )

    test_ids = inventory.get("testIds")
    if not isinstance(test_ids, list):
        errors.append("acceptanceTestInventory.testIds must be a list")
        return set()
    if len(test_ids) != EXPECTED_ACCEPTANCE_TESTS:
        errors.append(
            "acceptanceTestInventory.testIds must contain exactly "
            f"{EXPECTED_ACCEPTANCE_TESTS} ids; got {len(test_ids)}"
        )

    known: set[str] = set()
    for index, test_id in enumerate(test_ids):
        if not isinstance(test_id, str) or ACCEPTANCE_TEST_ID_RE.fullmatch(test_id) is None:
            errors.append(
                f"acceptanceTestInventory.testIds[{index}] must match "
                f"{ACCEPTANCE_TEST_ID_RE.pattern}; got {test_id!r}"
            )
            continue
        if test_id in known:
            errors.append(f"acceptanceTestInventory.testIds contains duplicate id {test_id!r}")
            continue
        known.add(test_id)

    # Pin the ordered ids, not a set: a reordering changes the contract even when every
    # id is individually valid.  Only digest a structurally joinable list so malformed
    # entries keep their specific format/count error rather than raising TypeError.
    if len(test_ids) == EXPECTED_ACCEPTANCE_TESTS and all(
        isinstance(test_id, str) for test_id in test_ids
    ):
        digest = hashlib.sha256("\n".join(test_ids).encode("utf-8")).hexdigest()
        if digest != EXPECTED_TEST_IDS_SHA256:
            errors.append(
                "acceptanceTestInventory.testIds digest is not pinned "
                f"(inventory digest mismatch): expected {EXPECTED_TEST_IDS_SHA256}, "
                f"got {digest}"
            )
    return known


def _declared_counts(document: dict, computed: dict[str, int], errors: list[str]) -> None:
    counts = document.get("counts")
    if not isinstance(counts, dict):
        errors.append("counts must be a JSON object")
        return

    declared: dict[str, int] = {}
    for key, value in counts.items():
        if not isinstance(key, str) or (key not in DEFENSE_IDS and key != "DEFERRED"):
            errors.append(f"counts has unknown key {key!r}; expected D01..D25 and DEFERRED")
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"counts[{key!r}] must be a non-negative integer; got {value!r}")
            continue
        declared[key] = value

    missing = sorted(set(computed) - set(declared))
    extra = sorted(set(declared) - set(computed))
    if missing:
        errors.append(f"counts is missing declared keys: {', '.join(missing)}")
    if extra:
        errors.append(f"counts has keys not present in findings: {', '.join(extra)}")
    for key in sorted(set(computed) & set(declared)):
        if declared[key] != computed[key]:
            errors.append(
                f"counts[{key!r}] must be {computed[key]} from findings; got {declared[key]}"
            )
    if sum(declared.values()) != EXPECTED_FINDINGS:
        errors.append(
            f"counts values must sum to {EXPECTED_FINDINGS}; got {sum(declared.values())}"
        )


def validate_policy(document: Any) -> list[str]:
    """Return every schema/semantic error in ``document`` (empty means valid).

    A policy is a closed, machine-checkable claim:

    * exactly 106 uniquely identified findings with valid severity/disposition/
      findingClass/acceptanceTestId/implementationAnchor fields;
    * disposition -> mapping-kind compatibility (a deferral may not claim a defense;
      an adopted row may not silently fall back to a deferred mapping);
    * findingClass -> disposition compatibility for already-covered rows;
    * every acceptanceTestId resolved against the embedded, source-bound inventory;
    * every adopted row carries a known test or is explicitly accepted_risk;
    * declared top-level counts exactly equal the counts computed from the matrix.

    It intentionally makes no claim about source-corpus reads beyond the frozen policy.
    """
    if not isinstance(document, dict):
        return ["policy root must be a JSON object"]

    errors: list[str] = []
    schema = document.get("schemaVersion")
    if schema != SCHEMA_VERSION or isinstance(schema, bool):
        errors.append(f"schemaVersion must be {SCHEMA_VERSION}")

    findings = document.get("findings")
    if not isinstance(findings, list):
        return errors + ["findings must be a list"]

    if len(findings) != EXPECTED_FINDINGS:
        errors.append(
            f"findings must contain exactly {EXPECTED_FINDINGS} entries; got {len(findings)}"
        )

    inventory_ids = _validate_acceptance_inventory(document, errors)

    seen_ids: set[str] = set()
    mapped = 0
    deferred = 0
    computed_counts: Counter[str] = Counter()
    computed_counts["DEFERRED"] = 0

    for index, finding in enumerate(findings):
        label = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{label} must be a JSON object")
            continue

        finding_id = finding.get("findingId")
        if not isinstance(finding_id, str) or not finding_id.strip():
            errors.append(f"{label}.findingId must be a non-empty string")
        else:
            label = finding_id
            if finding_id in seen_ids:
                errors.append(f"duplicate findingId: {finding_id}")
            else:
                seen_ids.add(finding_id)

        severity = finding.get("severity")
        if severity not in SEVERITIES:
            errors.append(f"{label}.severity must be one of S1, S2, S3; got {severity!r}")

        disposition = finding.get("disposition")
        if disposition not in DISPOSITIONS:
            errors.append(
                f"{label}.disposition must be one of "
                f"{', '.join(sorted(DISPOSITIONS))}; got {disposition!r}"
            )

        finding_class = finding.get("findingClass")
        if finding_class not in FINDING_CLASSES:
            errors.append(
                f"{label}.findingClass must be one of "
                f"{', '.join(sorted(FINDING_CLASSES))}; got {finding_class!r}"
            )

        acceptance_test_id = finding.get("acceptanceTestId")
        resolved_test = False
        if (
            not isinstance(acceptance_test_id, str)
            or ACCEPTANCE_TEST_ID_RE.fullmatch(acceptance_test_id) is None
        ):
            errors.append(
                f"{label}.acceptanceTestId must match "
                f"{ACCEPTANCE_TEST_ID_RE.pattern}; got {acceptance_test_id!r}"
            )
        elif inventory_ids:
            if acceptance_test_id in inventory_ids:
                resolved_test = True
            elif not (disposition == "adopt" and finding_class == "accepted_risk"):
                errors.append(
                    f"{label}.acceptanceTestId {acceptance_test_id!r} is unknown to "
                    "acceptanceTestInventory"
                )

        implementation_anchor = finding.get("implementationAnchor")
        if not isinstance(implementation_anchor, str):
            errors.append(f"{label}.implementationAnchor must be a non-empty string")
        else:
            anchor = implementation_anchor.strip()
            if len(anchor) < MIN_ANCHOR_LEN or len(anchor) > MAX_ANCHOR_LEN:
                errors.append(
                    f"{label}.implementationAnchor must be "
                    f"{MIN_ANCHOR_LEN}..{MAX_ANCHOR_LEN} characters after stripping; "
                    f"got length {len(anchor)}"
                )
            if any(ord(ch) < 32 for ch in implementation_anchor):
                errors.append(
                    f"{label}.implementationAnchor must not contain control characters or newlines"
                )

        if disposition == "adopt" and finding_class != "accepted_risk" and not resolved_test:
            errors.append(
                f"{label} is adopted but has no known acceptance test and is not "
                "an explicit accepted_risk"
            )

        mapping = finding.get("mapping")
        if not isinstance(mapping, dict):
            errors.append(f"{label}.mapping must be a JSON object")
            continue

        kind = mapping.get("kind")
        if kind == "defense":
            mapped += 1
            defense_id = mapping.get("defenseId")
            if defense_id not in DEFENSE_IDS:
                errors.append(
                    f"{label}.mapping.defenseId must be one of D01..D25; got {defense_id!r}"
                )
            else:
                computed_counts[defense_id] += 1
            if disposition == "defer":
                errors.append(
                    f"{label} has disposition 'defer' but mapping.kind is 'defense'; "
                    "an explicit deferral must not claim a runtime defense"
                )
        elif kind == "deferred":
            deferred += 1
            computed_counts["DEFERRED"] += 1
            decision_id = mapping.get("decisionId")
            if not isinstance(decision_id, str) or DECISION_ID_RE.match(decision_id) is None:
                errors.append(
                    f"{label}.mapping.decisionId must match ^[A-Z]-; got {decision_id!r}"
                )
            reason = mapping.get("reason")
            if not isinstance(reason, str) or len(reason) <= 20:
                errors.append(
                    f"{label}.mapping.reason must be longer than 20 characters"
                )
            if disposition == "adopt":
                errors.append(
                    f"{label} has disposition 'adopt' but mapping.kind is 'deferred'; "
                    "an adopted row must be backed by a defense (or be explicitly deferred)"
                )
        else:
            errors.append(
                f"{label}.mapping.kind must be 'defense' or 'deferred'; got {kind!r}"
            )

        if finding_class == "already_covered" and disposition != "already-covered":
            errors.append(
                f"{label} has findingClass 'already_covered' but disposition is "
                f"{disposition!r}; expected 'already-covered'"
            )
        elif finding_class in {
            "accepted_risk",
            "design_gap",
            "meta_requirement",
            "observed_defect",
            "unimplemented",
        } and disposition == "already-covered":
            errors.append(
                f"{label} has findingClass {finding_class!r} but disposition is "
                "'already-covered'"
            )

    if mapped + deferred != EXPECTED_FINDINGS:
        errors.append(
            f"mapped+deferred must equal {EXPECTED_FINDINGS}; got {mapped + deferred} "
            f"(mapped={mapped}, deferred={deferred})"
        )
    if mapped < MIN_MAPPED:
        errors.append(f"mapped findings must be >= {MIN_MAPPED}; got {mapped}")
    if deferred < MIN_DEFERRED:
        errors.append(f"deferred findings must be >= {MIN_DEFERRED}; got {deferred}")

    _declared_counts(document, dict(computed_counts), errors)
    return errors


def _summary(document: dict, path: Path, sha256: str) -> dict:
    findings = document["findings"]
    mapped = sum(1 for finding in findings if finding["mapping"]["kind"] == "defense")
    deferred = sum(1 for finding in findings if finding["mapping"]["kind"] == "deferred")
    defense_counts = Counter(
        finding["mapping"]["defenseId"]
        for finding in findings
        if finding["mapping"]["kind"] == "defense"
    )
    disposition_counts = Counter(finding["disposition"] for finding in findings)
    finding_class_counts = Counter(finding["findingClass"] for finding in findings)
    inventory = document["acceptanceTestInventory"]
    return {
        "path": str(path),
        "sha256": sha256,
        "schemaVersion": document.get("schemaVersion"),
        "findingsCount": len(findings),
        "mappedCount": mapped,
        "deferredCount": deferred,
        "defenseCounts": {
            defense_id: defense_counts[defense_id] for defense_id in sorted(defense_counts)
        },
        "dispositionCounts": {
            key: disposition_counts[key] for key in sorted(disposition_counts)
        },
        "findingClassCounts": {
            key: finding_class_counts[key] for key in sorted(finding_class_counts)
        },
        "acceptanceTestCount": len(inventory["testIds"]),
        "acceptanceTestInventorySha256": inventory["sourceSha256"],
    }


def load_policy(path: str | Path) -> tuple[dict | None, str | None]:
    """Load, validate, and summarize one policy file.

    Returns ``(summary, None)`` where summary carries path/sha256/findingsCount/
    mappedCount/deferredCount/defenseCounts.  Returns ``(None, reason)`` on unreadable
    JSON, validation failure, or a duplicate/incomplete matrix.  Never raises for a
    policy-content problem.
    """
    policy_path = Path(path)
    try:
        raw = policy_path.read_bytes()
    except FileNotFoundError:
        return None, f"historical findings policy missing: {policy_path}"
    except OSError as exc:
        return None, f"historical findings policy unreadable: {policy_path}: {exc}"

    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"historical findings policy is not valid UTF-8 JSON: {policy_path}: {exc}"

    errors = validate_policy(document)
    if errors:
        return None, f"historical findings policy invalid: {policy_path}: " + "; ".join(errors)

    sha256 = hashlib.sha256(raw).hexdigest()
    return _summary(document, policy_path, sha256), None


if __name__ == "__main__":  # pragma: no cover
    print("openrig_findings is a library; openrig_run.py enforces the policy at runtime")
    raise SystemExit(2)
