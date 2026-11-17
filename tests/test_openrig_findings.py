# -*- coding: utf-8 -*-
"""Unit tests for the historical findings runtime policy mount (D24)."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_findings as of  # noqa: E402

WG = Path(__file__).resolve().parents[1]
EXECUTION_TREE = (
    WG / "runs" / "openrig-completion-round-20261116" / "reports" / "EXECUTION-TREE-v2.json"
)
REAL_SOURCE_SHA256 = (
    "e01443e5a8c76bd9465b8c9b0cfca043411324d8d249ab90b884c401486d36e9"
)
REAL_TEST_IDS_SHA256 = (
    "edd72d1664deaad9302516ba81371e81fe10cc7050a48d71433813b72c8cee6d"
)
REAL_ACCEPTANCE_IDS = [
    "AT-DESIGN-INHERIT-01",
    "AT-DESIGN-INHERIT-02",
    "AT-DESIGN-HUMAN-GATE-01",
    "AT-DESIGN-SOURCE-COVERAGE-01",
    "AT-DESIGN-QA-HISTORY-01",
    "AT-DESIGN-QA-HISTORY-02",
    "AT-DESIGN-QA-HISTORY-03",
    "AT-DESIGN-QA-HISTORY-04",
    "AT-DESIGN-QA-HISTORY-05",
    "AT-DESIGN-QA-HISTORY-06",
    "AT-DESIGN-QA-HISTORY-07",
    "AT-DESIGN-QA-HISTORY-08",
    "AT-DESIGN-INTERFACE-01",
    "AT-DESIGN-START-01",
    "AT-DESIGN-START-02",
    "AT-DESIGN-STATE-MACHINE-01",
    "AT-DESIGN-SUPERVISOR-01",
    "AT-DESIGN-SUPERVISOR-02",
    "AT-DESIGN-READY-01",
    "AT-DESIGN-RESTORE-OUTCOME-01",
    "AT-DESIGN-DEADLINE-01",
    "AT-DESIGN-SCOPE-01",
    "AT-DESIGN-HOPS-01",
    "AT-DESIGN-AUTOMATION-01",
    "AT-DESIGN-AUTOMATION-02",
    "AT-DESIGN-AUTOMATION-03",
    "AT-DESIGN-PREFLIGHT-01",
    "AT-DESIGN-EVIDENCE-01",
    "AT-DESIGN-EVIDENCE-02",
    "AT-DESIGN-GATE-ORDER-01",
    "AT-DESIGN-RENDER-DRIFT-01",
    "AT-DESIGN-TOKEN-GOV-01",
    "AT-DESIGN-CONTEXT-BUDGET-01",
    "AT-DESIGN-CONTINUITY-01",
    "AT-DESIGN-CONTINUITY-02",
    "AT-DESIGN-CONTINUITY-03",
    "AT-DESIGN-CONTINUITY-04",
    "AT-DESIGN-COMPACTION-01",
    "AT-DESIGN-HANDOVER-01",
    "AT-DESIGN-ARCHIVE-01",
    "AT-DESIGN-SEAT-WRITE-01",
    "AT-DESIGN-HUMAN-GATE-02",
    "AT-DESIGN-MANIFEST-01",
    "AT-DESIGN-TOKEN-JOIN-01",
    "AT-DESIGN-TOKEN-READSURFACE-01",
    "AT-DESIGN-TREE-SCHEMA-01",
    "AT-DESIGN-E2E-01",
    "AT-DESIGN-WORKFLOW-INVARIANTS-01",
    "AT-DESIGN-CLOSEOUT-01",
    "AT-DESIGN-CLOSEOUT-02",
    "AT-DESIGN-DUAL-FINAL-01",
    "AT-DESIGN-INTEGRITY-01",
    "AT-DESIGN-INTEGRITY-02",
    "AT-DESIGN-INTEGRITY-03",
    "AT-DESIGN-INTEGRITY-04",
    "AT-DESIGN-INTEGRITY-05",
    "AT-DESIGN-BASELINE-01",
]
ACCEPTANCE_IDS = REAL_ACCEPTANCE_IDS


@pytest.fixture(autouse=True)
def _clear_policy_env(monkeypatch):
    monkeypatch.delenv(of.ENV_VAR, raising=False)


def _counts(policy: dict) -> dict:
    counts = Counter({"DEFERRED": 0})
    for finding in policy["findings"]:
        mapping = finding["mapping"]
        if mapping["kind"] == "defense" and mapping.get("defenseId") in of.DEFENSE_IDS:
            counts[mapping["defenseId"]] += 1
        elif mapping["kind"] == "deferred":
            counts["DEFERRED"] += 1
    return {key: counts[key] for key in sorted(counts)}


def _policy(*, mapped: int = 96, deferred: int = 10) -> dict:
    """A synthetic matrix with the real 106-row shape and valid closure metadata."""
    findings = []
    for index in range(mapped):
        disposition = "adopt" if index < 50 else "already-covered"
        findings.append(
            {
                "findingId": f"HF-{index + 1:03d}",
                "severity": ("S1", "S2", "S3")[index % 3],
                "disposition": disposition,
                "findingClass": "design_gap" if disposition == "adopt" else "already_covered",
                "acceptanceTestId": ACCEPTANCE_IDS[index % len(ACCEPTANCE_IDS)],
                "implementationAnchor": f"fixture implementation anchor {index + 1}",
                "mapping": {
                    "kind": "defense",
                    "defenseId": f"D{index % 25 + 1:02d}",
                },
            }
        )
    for offset in range(deferred):
        index = mapped + offset
        findings.append(
            {
                "findingId": f"HF-{index + 1:03d}",
                "severity": "S2",
                "disposition": "defer",
                "findingClass": "unimplemented",
                "acceptanceTestId": ACCEPTANCE_IDS[index % len(ACCEPTANCE_IDS)],
                "implementationAnchor": f"fixture deferral anchor {index + 1}",
                "mapping": {
                    "kind": "deferred",
                    "decisionId": "H-01",
                    "reason": "explicit historical decision deferral with a named owner",
                },
            }
        )
    policy = {
        "schemaVersion": 1,
        "acceptanceTestInventory": {
            "source": "fixture://EXECUTION-TREE-v2.json#acceptanceMap",
            "sourceSchema": "acceptanceMap",
            "sourceSha256": REAL_SOURCE_SHA256,
            "testIds": list(ACCEPTANCE_IDS),
        },
        "findings": findings,
    }
    policy["counts"] = _counts(policy)
    return policy


def _write_policy(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _invalid_error(tmp_path: Path, payload: dict, needle: str) -> str:
    path = _write_policy(tmp_path / "invalid-policy.json", payload)
    summary, error = of.load_policy(path)
    assert summary is None
    assert error is not None
    assert needle in error, error
    return error


def _defense_finding(policy: dict) -> dict:
    return next(f for f in policy["findings"] if f["mapping"]["kind"] == "defense")


def _deferred_finding(policy: dict) -> dict:
    return next(f for f in policy["findings"] if f["mapping"]["kind"] == "deferred")


def _already_covered_finding(policy: dict) -> dict:
    return next(f for f in policy["findings"] if f["disposition"] == "already-covered")


def _refresh_counts(policy: dict) -> None:
    policy["counts"] = _counts(policy)


# ------------------------------------------------------------------ valid shape
def test_valid_policy_returns_machine_summary(tmp_path):
    path = _write_policy(tmp_path / "policy.json", _policy())
    summary, error = of.load_policy(path)

    assert error is None
    assert summary is not None
    assert summary["path"] == str(path)
    assert summary["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert summary["findingsCount"] == 106
    assert summary["mappedCount"] == 96
    assert summary["deferredCount"] == 10
    assert sum(summary["defenseCounts"].values()) == 96
    assert set(summary["defenseCounts"]).issubset(of.DEFENSE_IDS)
    assert summary["acceptanceTestCount"] == of.EXPECTED_ACCEPTANCE_TESTS
    assert summary["acceptanceTestInventorySha256"] == REAL_SOURCE_SHA256


def test_default_policy_path_uses_the_workspace_layout():
    expected = (
        of.ROOT.parent.parent
        / "deepseek-项目"
        / "10-openrig-deepseek"
        / "docs"
        / "as-built"
        / "historical-findings-policy.json"
    )
    assert of.DEFAULT_POLICY_PATH == expected


def test_product_policy_mounts_the_frozen_106_finding_matrix():
    if not of.DEFAULT_POLICY_PATH.is_file():
        pytest.skip("workspace product policy is not present")
    summary, error = of.load_policy(of.DEFAULT_POLICY_PATH)

    assert error is None, error
    assert summary is not None
    assert summary["findingsCount"] == 106
    assert summary["mappedCount"] >= 90
    assert summary["deferredCount"] >= 1
    assert summary["acceptanceTestCount"] == 57


# ------------------------------------------------------------------ file / schema
def test_missing_policy_is_fail_closed(tmp_path):
    summary, error = of.load_policy(tmp_path / "does-not-exist.json")

    assert summary is None
    assert "missing" in error.lower()
    assert "does-not-exist.json" in error


def test_invalid_json_is_fail_closed(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text("{not-json", encoding="utf-8")

    summary, error = of.load_policy(path)

    assert summary is None
    assert "not valid utf-8 json" in error.lower()


def test_bad_schema_version_is_rejected(tmp_path):
    policy = _policy()
    policy["schemaVersion"] = 2
    _invalid_error(tmp_path, policy, "schemaVersion must be 1")


def test_findings_count_must_be_exactly_106(tmp_path):
    policy = _policy()
    policy["findings"].pop()
    _invalid_error(tmp_path, policy, "exactly 106 entries; got 105")


def test_findings_must_be_a_list(tmp_path):
    policy = _policy()
    policy["findings"] = {"HF-001": {}}
    _invalid_error(tmp_path, policy, "findings must be a list")


def test_duplicate_finding_id_is_rejected(tmp_path):
    policy = _policy()
    policy["findings"][1]["findingId"] = policy["findings"][0]["findingId"]
    _invalid_error(tmp_path, policy, "duplicate findingId: HF-001")


# ------------------------------------------------------------------ mapping
def test_unknown_defense_id_is_rejected(tmp_path):
    policy = _policy()
    _defense_finding(policy)["mapping"]["defenseId"] = "D99"
    _invalid_error(tmp_path, policy, "defenseId must be one of D01..D25; got 'D99'")


def test_deferred_finding_cannot_be_silent(tmp_path):
    policy = _policy()
    policy["findings"][0] = {
        "findingId": "HF-001",
        "mapping": {"kind": "deferred"},
    }
    error = _invalid_error(tmp_path, policy, "decisionId must match")
    assert "reason must be longer than 20 characters" in error


def test_deferred_reason_must_be_longer_than_20(tmp_path):
    policy = _policy()
    _deferred_finding(policy)["mapping"]["reason"] = "too short"
    _invalid_error(tmp_path, policy, "reason must be longer than 20 characters")


def test_deferred_decision_id_shape_is_enforced(tmp_path):
    policy = _policy()
    _deferred_finding(policy)["mapping"]["decisionId"] = "h-01"
    _invalid_error(tmp_path, policy, "decisionId must match ^[A-Z]-; got 'h-01'")


def test_unknown_mapping_kind_is_rejected(tmp_path):
    policy = _policy()
    _defense_finding(policy)["mapping"]["kind"] = "silent"
    _invalid_error(tmp_path, policy, "mapping.kind must be 'defense' or 'deferred'")


def test_mapped_count_must_be_at_least_90(tmp_path):
    policy = _policy(mapped=89, deferred=17)
    assert len(policy["findings"]) == 106
    _invalid_error(tmp_path, policy, "mapped findings must be >= 90; got 89")


def test_deferred_count_must_be_at_least_1(tmp_path):
    policy = _policy(mapped=106, deferred=0)
    _invalid_error(tmp_path, policy, "deferred findings must be >= 1; got 0")


# ------------------------------------------------------------------ closure fields
@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda f: f.pop("severity"), ".severity must be one of S1, S2, S3"),
        (
            lambda f: f.__setitem__("severity", "S9"),
            ".severity must be one of S1, S2, S3",
        ),
        (
            lambda f: f.__setitem__("disposition", "ignore"),
            ".disposition must be one of adopt, already-covered, defer",
        ),
        (
            lambda f: f.__setitem__("findingClass", "vibes"),
            ".findingClass must be one of",
        ),
        (
            lambda f: f.__setitem__("acceptanceTestId", "BAD-ID"),
            ".acceptanceTestId must match",
        ),
        (
            lambda f: f.__setitem__("acceptanceTestId", "AT-TEST-999"),
            ".acceptanceTestId 'AT-TEST-999' is unknown to acceptanceTestInventory",
        ),
        (
            lambda f: f.__setitem__("implementationAnchor", "   "),
            ".implementationAnchor must be 3..240 characters",
        ),
        (
            lambda f: f.__setitem__("implementationAnchor", "a\nb"),
            ".implementationAnchor must not contain control characters",
        ),
        (lambda f: f.pop("implementationAnchor"), ".implementationAnchor must be a non-empty string"),
    ],
)
def test_finding_closure_metadata_is_fail_closed(tmp_path, mutate, needle):
    policy = _policy()
    mutate(_defense_finding(policy))
    _invalid_error(tmp_path, policy, needle)


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda p: p.pop("acceptanceTestInventory"), "acceptanceTestInventory must be a JSON object"),
        (lambda p: p["acceptanceTestInventory"].pop("sourceSha256"),
         "acceptanceTestInventory.sourceSha256 must be 64-hex"),
        (lambda p: p["acceptanceTestInventory"].__setitem__("testIds", ACCEPTANCE_IDS[:-1]),
         "must contain exactly 57 ids; got 56"),
        (lambda p: p["acceptanceTestInventory"].__setitem__(
            "testIds", ACCEPTANCE_IDS[:-1] + [ACCEPTANCE_IDS[0]]),
         "acceptanceTestInventory.testIds contains duplicate id"),
        (lambda p: p["acceptanceTestInventory"].__setitem__(
            "testIds", ACCEPTANCE_IDS[:-1] + ["not-an-at-id"]),
         "acceptanceTestInventory.testIds[56] must match"),
    ],
)
def test_acceptance_test_inventory_is_fail_closed(tmp_path, mutate, needle):
    policy = _policy()
    mutate(policy)
    _invalid_error(tmp_path, policy, needle)


def test_acceptance_inventory_pins_the_real_source_and_ordered_ids():
    assert of.EXPECTED_SOURCE_SHA256 == REAL_SOURCE_SHA256
    assert of.EXPECTED_TEST_IDS_SHA256 == REAL_TEST_IDS_SHA256
    assert (
        hashlib.sha256("\n".join(REAL_ACCEPTANCE_IDS).encode("utf-8")).hexdigest()
        == REAL_TEST_IDS_SHA256
    )


def test_pinned_test_ids_are_the_execution_tree_source_order():
    """The pin must follow acceptanceMap order, not a sorted list of the same ids."""
    if not EXECUTION_TREE.is_file():
        pytest.skip("frozen EXECUTION-TREE-v2.json is not present")
    tree = json.loads(EXECUTION_TREE.read_text(encoding="utf-8"))
    source_ids = list(tree["acceptanceMap"])

    assert source_ids == REAL_ACCEPTANCE_IDS
    source_digest = hashlib.sha256("\n".join(source_ids).encode("utf-8")).hexdigest()
    assert source_digest == REAL_TEST_IDS_SHA256
    assert source_digest == of.EXPECTED_TEST_IDS_SHA256
    sorted_digest = hashlib.sha256(
        "\n".join(sorted(REAL_ACCEPTANCE_IDS)).encode("utf-8")
    ).hexdigest()
    assert sorted_digest != of.EXPECTED_TEST_IDS_SHA256, "sorted order must not satisfy the pin"


def test_acceptance_inventory_rejects_a_sorted_real_id_list(tmp_path):
    policy = _policy()
    policy["acceptanceTestInventory"]["testIds"] = sorted(REAL_ACCEPTANCE_IDS)
    _invalid_error(tmp_path, policy, "testIds digest is not pinned")


def test_acceptance_inventory_rejects_fake_ids_by_ordered_digest(tmp_path):
    policy = _policy()
    policy["acceptanceTestInventory"]["testIds"] = [
        f"AT-FAKE-{index:02d}" for index in range(of.EXPECTED_ACCEPTANCE_TESTS)
    ]
    _invalid_error(tmp_path, policy, "testIds digest is not pinned")


def test_acceptance_inventory_rejects_reordered_real_ids(tmp_path):
    policy = _policy()
    policy["acceptanceTestInventory"]["testIds"] = list(reversed(ACCEPTANCE_IDS))
    _invalid_error(tmp_path, policy, "testIds digest is not pinned")


def test_acceptance_inventory_rejects_a_tampered_source_sha256(tmp_path):
    policy = _policy()
    policy["acceptanceTestInventory"]["sourceSha256"] = "f" * 64
    _invalid_error(tmp_path, policy, "sourceSha256 is not pinned")


def test_declared_counts_must_match_the_matrix(tmp_path):
    policy = _policy()
    first_key = sorted(policy["counts"])[0]
    policy["counts"][first_key] += 1
    _invalid_error(tmp_path, policy, f"counts['{first_key}'] must be")


def test_counts_must_sum_to_the_finding_count(tmp_path):
    policy = _policy()
    policy["counts"]["D01"] += 1
    _invalid_error(tmp_path, policy, "counts values must sum to 106")


def test_counts_must_be_an_object(tmp_path):
    policy = _policy()
    policy.pop("counts")
    _invalid_error(tmp_path, policy, "counts must be a JSON object")


def test_counts_reject_unknown_keys(tmp_path):
    policy = _policy()
    policy["counts"]["D99"] = 1
    _invalid_error(tmp_path, policy, "counts has unknown key 'D99'")


def test_counts_reject_negative_values(tmp_path):
    policy = _policy()
    policy["counts"]["D01"] = -1
    _invalid_error(tmp_path, policy, "counts['D01'] must be a non-negative integer")


# ------------------------------------------------------------------ compatibility
def test_defer_disposition_cannot_claim_a_defense_mapping(tmp_path):
    policy = _policy()
    finding = _deferred_finding(policy)
    finding["mapping"] = {"kind": "defense", "defenseId": "D10"}
    _refresh_counts(policy)
    _invalid_error(tmp_path, policy, "disposition 'defer' but mapping.kind is 'defense'")


def test_adopt_disposition_cannot_use_a_deferred_mapping(tmp_path):
    policy = _policy()
    finding = _defense_finding(policy)
    finding["mapping"] = {
        "kind": "deferred",
        "decisionId": "H-01",
        "reason": "explicit deferred decision that is longer than twenty characters",
    }
    _refresh_counts(policy)
    _invalid_error(tmp_path, policy, "disposition 'adopt' but mapping.kind is 'deferred'")


def test_already_covered_may_use_a_deferred_mapping(tmp_path):
    policy = _policy()
    finding = _already_covered_finding(policy)
    finding["mapping"] = {
        "kind": "deferred",
        "decisionId": "H-01",
        "reason": "already-covered finding is mounted to an explicit historical decision",
    }
    _refresh_counts(policy)
    assert of.validate_policy(policy) == []


def test_accepted_risk_may_be_an_explicit_deferral(tmp_path):
    policy = _policy()
    finding = _deferred_finding(policy)
    finding["findingClass"] = "accepted_risk"
    assert of.validate_policy(policy) == []


def test_already_covered_class_requires_already_covered_disposition(tmp_path):
    policy = _policy()
    finding = _already_covered_finding(policy)
    finding["disposition"] = "adopt"
    assert any(
        "findingClass 'already_covered' but disposition is 'adopt'" in error
        for error in of.validate_policy(policy)
    )


def test_adopted_non_accepted_risk_requires_a_known_test(tmp_path):
    policy = _policy()
    finding = _defense_finding(policy)
    finding["acceptanceTestId"] = "AT-TEST-999"
    assert any(
        "has no known acceptance test and is not an explicit accepted_risk" in error
        for error in of.validate_policy(policy)
    )


def test_adopted_accepted_risk_may_cite_an_unknown_test_as_explicit_risk(tmp_path):
    policy = _policy()
    finding = _defense_finding(policy)
    finding["findingClass"] = "accepted_risk"
    finding["acceptanceTestId"] = "AT-TEST-999"
    assert of.validate_policy(policy) == []


def test_all_errors_are_reported_in_one_pass():
    policy = _policy()
    policy["schemaVersion"] = 2
    policy["findings"][0]["mapping"]["kind"] = "unknown"
    errors = of.validate_policy(policy)

    assert any("schemaVersion" in error for error in errors)
    assert any("mapping.kind" in error for error in errors)
    assert any("mapped+deferred" in error for error in errors)


# ------------------------------------------------------------------ frozen data
def test_embedded_inventory_is_the_real_execution_tree_acceptance_map():
    if not EXECUTION_TREE.is_file():
        pytest.skip("frozen EXECUTION-TREE-v2.json is not present")
    policy = json.loads(of.DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    inventory = policy["acceptanceTestInventory"]
    raw = EXECUTION_TREE.read_bytes()
    tree = json.loads(raw)

    assert inventory["sourceSha256"] == hashlib.sha256(raw).hexdigest()
    assert inventory["testIds"] == list(tree["acceptanceMap"])
    assert len(inventory["testIds"]) == 57
    assert hashlib.sha256(
        "\n".join(inventory["testIds"]).encode("utf-8")
    ).hexdigest() == of.EXPECTED_TEST_IDS_SHA256


def test_actual_policy_contradictions_hf_026_and_hf_052_are_fixed():
    if not of.DEFAULT_POLICY_PATH.is_file():
        pytest.skip("workspace product policy is not present")
    policy = json.loads(of.DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    by_id = {finding["findingId"]: finding for finding in policy["findings"]}

    hf26 = by_id["HF-026"]
    assert hf26["disposition"] == "defer"
    assert hf26["mapping"]["kind"] == "deferred"
    assert hf26["mapping"]["decisionId"] == "H-02"

    hf52 = by_id["HF-052"]
    assert hf52["findingClass"] == "accepted_risk"
    assert hf52["disposition"] == "defer"
    assert hf52["mapping"]["kind"] == "deferred"
    assert hf52["mapping"]["decisionId"] == "H-01"

    assert of.validate_policy(policy) == []


def test_mutating_the_fixed_rows_back_to_the_old_contradictions_is_rejected():
    if not of.DEFAULT_POLICY_PATH.is_file():
        pytest.skip("workspace product policy is not present")
    policy = copy.deepcopy(json.loads(of.DEFAULT_POLICY_PATH.read_text(encoding="utf-8")))
    by_id = {finding["findingId"]: finding for finding in policy["findings"]}

    by_id["HF-026"]["mapping"] = {"kind": "defense", "defenseId": "D10"}
    by_id["HF-052"]["disposition"] = "adopt"
    errors = of.validate_policy(policy)

    assert any("HF-026 has disposition 'defer' but mapping.kind is 'defense'" in e for e in errors)
    assert any("HF-052 has disposition 'adopt' but mapping.kind is 'deferred'" in e for e in errors)


# ------------------------------------------------------------------ resolution
def test_resolve_prefers_environment_over_bundle_and_default(tmp_path, monkeypatch):
    default = _write_policy(tmp_path / "workspace-default.json", _policy())
    run_dir = tmp_path / "run"
    bundle = _write_policy(run_dir / of.POLICY_REL, _policy())
    env_policy = _write_policy(tmp_path / "env-policy.json", _policy())
    monkeypatch.setattr(of, "DEFAULT_POLICY_PATH", default)
    monkeypatch.setenv(of.ENV_VAR, str(env_policy))

    path, reason = of.resolve_policy_path({}, run_dir)

    assert reason is None
    assert path == env_policy
    assert path != bundle
    assert path != default


def test_resolve_prefers_bundle_over_default(tmp_path, monkeypatch):
    default = _write_policy(tmp_path / "workspace-default.json", _policy())
    run_dir = tmp_path / "run"
    bundle = _write_policy(run_dir / of.POLICY_REL, _policy())
    monkeypatch.setattr(of, "DEFAULT_POLICY_PATH", default)

    path, reason = of.resolve_policy_path({}, run_dir)

    assert reason is None
    assert path == bundle


def test_resolve_falls_back_to_workspace_default(tmp_path, monkeypatch):
    default = _write_policy(tmp_path / "workspace-default.json", _policy())
    run_dir = tmp_path / "run"
    monkeypatch.setattr(of, "DEFAULT_POLICY_PATH", default)

    path, reason = of.resolve_policy_path({}, run_dir)

    assert reason is None
    assert path == default


def test_resolve_missing_reports_every_candidate(tmp_path, monkeypatch):
    default = tmp_path / "workspace-default.json"
    run_dir = tmp_path / "run"
    monkeypatch.setattr(of, "DEFAULT_POLICY_PATH", default)

    path, reason = of.resolve_policy_path({}, run_dir)

    assert path is None
    assert reason is not None
    assert of.ENV_VAR in reason
    assert str(run_dir / of.POLICY_REL) in reason
    assert str(default) in reason
