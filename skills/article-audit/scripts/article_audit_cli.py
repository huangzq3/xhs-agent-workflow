#!/usr/bin/env python3
"""Deterministic contract checks for independent article-audit artifacts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


GENERIC_SCHEMA_VERSION = "article-audit/1.0.0"
XHS_WORKFLOW_SCHEMA_VERSION = "2.4.0"
XHS_WORKFLOW_SCHEMA_VERSIONS = {"2.2.0", "2.3.0", XHS_WORKFLOW_SCHEMA_VERSION}
ACCEPTED_SCHEMA_VERSIONS = {GENERIC_SCHEMA_VERSION} | XHS_WORKFLOW_SCHEMA_VERSIONS
CONTRACT_VERSION = "1.0.0"
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
CORE_DIMENSIONS = {
    "fact_and_source",
    "quote_and_attribution",
    "logic_and_consistency",
    "structure_and_redundancy",
    "language_and_terminology",
    "cross_surface_consistency",
    "uncertainty_and_decisions",
}
FINDING_DIMENSIONS = CORE_DIMENSIONS | {"custom_profile"}
SEVERITIES = {"P0", "P1", "P2"}
VERDICTS = {"passed", "audit_failed", "human_decision_required"}


class AuditContractError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuditContractError(f"文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise AuditContractError(
            f"JSON 无法解析：{path}:{exc.lineno}:{exc.colno} {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise AuditContractError(f"顶层必须是 JSON object：{path}")
    return value


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def auditable_content_view(content: dict[str, Any]) -> Any:
    if content.get("artifact_type") == "content" and isinstance(content.get("payload"), dict):
        payload = copy.deepcopy(content["payload"])
        payload.pop("article_audit_ref", None)
        return {
            "payload": payload,
            "provenance": copy.deepcopy(content.get("provenance", [])),
        }
    return content


def auditable_content_hash(content: dict[str, Any]) -> str:
    return canonical_sha256(auditable_content_view(content))


def audit_payload_hash(audit: dict[str, Any]) -> str:
    return canonical_sha256(audit.get("payload", {}))


def content_hash_from_path(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return hashlib.sha256(raw).hexdigest(), "raw_bytes"
    if (
        isinstance(value, dict)
        and value.get("artifact_type") == "content"
        and isinstance(value.get("payload"), dict)
    ):
        return auditable_content_hash(value), "canonical_json"
    return hashlib.sha256(raw).hexdigest(), "raw_bytes"


def require_object(value: Any, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field} 必须是 object")
        return {}
    return value


def require_list(value: Any, field: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{field} 必须是 array")
        return []
    return value


def require_nonempty_string(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} 必须是非空字符串")


def validate_identity(
    value: Any,
    field: str,
    errors: list[str],
    *,
    reviewer: bool = False,
) -> dict[str, Any]:
    identity = require_object(value, field, errors)
    required = {"actor_type", "actor_id", "context_id", "model_id"}
    missing = sorted(required - set(identity))
    if missing:
        errors.append(f"{field} 缺少字段：" + ", ".join(missing))
    actor_type = identity.get("actor_type")
    if actor_type not in {"agent", "human"}:
        errors.append(f"{field}.actor_type 无效")
    if reviewer and actor_type != "agent":
        errors.append(f"{field}.actor_type 必须是 agent")
    require_nonempty_string(identity.get("actor_id"), f"{field}.actor_id", errors)
    context_id = identity.get("context_id")
    if actor_type == "agent" and (not isinstance(context_id, str) or not context_id.strip()):
        errors.append(f"{field}.context_id 在 actor_type=agent 时必须是非空字符串")
    elif context_id is not None and not isinstance(context_id, str):
        errors.append(f"{field}.context_id 必须是字符串或 null")
    model_id = identity.get("model_id")
    if model_id is not None and (not isinstance(model_id, str) or not model_id.strip()):
        errors.append(f"{field}.model_id 必须是非空字符串或 null")
    return identity


def expected_surface_paths(content: dict[str, Any]) -> set[str]:
    payload = content.get("payload", {})
    expected = {"payload.title", "payload.caption", "payload.hashtags"}
    if payload.get("format") == "image":
        expected.add("payload.cards")
    elif payload.get("format") == "video":
        expected.add("payload.shots")
    if payload.get("assets"):
        expected.add("payload.assets")
    return expected


def validate_audit_document(
    audit: dict[str, Any],
    *,
    content: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    top_required = {
        "schema_version",
        "artifact_type",
        "artifact_id",
        "account_id",
        "run_id",
        "created_at",
        "updated_at",
        "status",
        "provenance",
        "approvals",
        "payload",
    }
    missing_top = sorted(top_required - set(audit))
    if missing_top:
        errors.append("缺少顶层字段：" + ", ".join(missing_top))
    if audit.get("schema_version") not in ACCEPTED_SCHEMA_VERSIONS:
        errors.append(
            "schema_version 必须是受支持版本："
            + ", ".join(sorted(ACCEPTED_SCHEMA_VERSIONS))
        )
    if audit.get("artifact_type") != "article_audit":
        errors.append("artifact_type 必须是 article_audit")
    if audit.get("status") != "ready":
        errors.append("article_audit.status 必须是 ready")
    require_nonempty_string(audit.get("artifact_id"), "artifact_id", errors)
    if audit.get("account_id") is not None:
        require_nonempty_string(audit.get("account_id"), "account_id", errors)
    if audit.get("run_id") is not None:
        require_nonempty_string(audit.get("run_id"), "run_id", errors)
    provenance = require_list(audit.get("provenance"), "provenance", errors)
    audit_source_ids: set[str] = set()
    for index, source_value in enumerate(provenance):
        source = require_object(source_value, f"provenance[{index}]", errors)
        for field in ("source_id", "kind", "captured_at", "summary"):
            require_nonempty_string(source.get(field), f"provenance[{index}].{field}", errors)
        source_id = source.get("source_id")
        if isinstance(source_id, str) and source_id:
            if source_id in audit_source_ids:
                errors.append(f"provenance[{index}].source_id 重复：{source_id}")
            audit_source_ids.add(source_id)
    approvals = require_list(audit.get("approvals"), "approvals", errors)
    if approvals:
        errors.append("article_audit 不接受人工批准记录；人工决定属于调用方门禁")

    payload = require_object(audit.get("payload"), "payload", errors)
    required_payload = {
        "contract_version",
        "content_artifact_id",
        "content_revision",
        "target_uri",
        "content_sha256",
        "hash_mode",
        "author",
        "reviewer",
        "independence",
        "ruleset",
        "scope",
        "risk",
        "claim_inventory",
        "findings",
        "summary",
    }
    missing_payload = sorted(required_payload - set(payload))
    if missing_payload:
        errors.append("payload 缺少字段：" + ", ".join(missing_payload))
    if payload.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"payload.contract_version 必须是 {CONTRACT_VERSION}")
    require_nonempty_string(payload.get("content_artifact_id"), "payload.content_artifact_id", errors)
    revision = payload.get("content_revision")
    if revision is not None and (not isinstance(revision, int) or isinstance(revision, bool) or revision < 1):
        errors.append("payload.content_revision 必须是正整数或 null")
    require_nonempty_string(payload.get("target_uri"), "payload.target_uri", errors)
    if not isinstance(payload.get("content_sha256"), str) or not SHA_RE.fullmatch(payload.get("content_sha256", "")):
        errors.append("payload.content_sha256 无效")
    if payload.get("hash_mode") not in {"canonical_json", "raw_bytes"}:
        errors.append("payload.hash_mode 无效")

    author = validate_identity(payload.get("author"), "payload.author", errors)
    reviewer = validate_identity(payload.get("reviewer"), "payload.reviewer", errors, reviewer=True)
    if author.get("actor_id") and author.get("actor_id") == reviewer.get("actor_id"):
        errors.append("作者与审计者的 actor_id 必须不同")
    if (
        author.get("actor_type") == "agent"
        and author.get("context_id")
        and author.get("context_id") == reviewer.get("context_id")
    ):
        errors.append("作者与审计者的 context_id 必须不同")

    independence = require_object(payload.get("independence"), "payload.independence", errors)
    for field in (
        "separate_agent",
        "separate_context",
        "read_only",
        "prompt_injection_treated_as_data",
    ):
        if independence.get(field) is not True:
            errors.append(f"payload.independence.{field} 必须为 true")
    evidence = require_list(independence.get("evidence"), "payload.independence.evidence", errors)
    if not evidence or any(not isinstance(item, str) or not item.strip() for item in evidence):
        errors.append("payload.independence.evidence 至少需要一条非空说明")

    ruleset = require_object(payload.get("ruleset"), "payload.ruleset", errors)
    require_nonempty_string(ruleset.get("ruleset_id"), "payload.ruleset.ruleset_id", errors)
    require_nonempty_string(ruleset.get("version"), "payload.ruleset.version", errors)
    dimensions = require_list(ruleset.get("core_dimensions"), "payload.ruleset.core_dimensions", errors)
    dimension_values = [item for item in dimensions if isinstance(item, str)]
    if len(dimension_values) != len(dimensions):
        errors.append("payload.ruleset.core_dimensions 必须是字符串")
    if len(dimension_values) != len(set(dimension_values)):
        errors.append("payload.ruleset.core_dimensions 不得重复")
    missing_dimensions = sorted(CORE_DIMENSIONS - set(dimension_values))
    unknown_dimensions = sorted(set(dimension_values) - CORE_DIMENSIONS)
    if missing_dimensions:
        errors.append("payload.ruleset.core_dimensions 缺少：" + ", ".join(missing_dimensions))
    if unknown_dimensions:
        errors.append("payload.ruleset.core_dimensions 包含未知值：" + ", ".join(unknown_dimensions))
    custom_profiles = require_list(
        ruleset.get("custom_profile_refs"), "payload.ruleset.custom_profile_refs", errors
    )
    if any(not isinstance(item, str) or not item.strip() for item in custom_profiles):
        errors.append("payload.ruleset.custom_profile_refs 必须是非空字符串")
    if len(custom_profiles) != len(set(item for item in custom_profiles if isinstance(item, str))):
        errors.append("payload.ruleset.custom_profile_refs 不得重复")

    scope = require_object(payload.get("scope"), "payload.scope", errors)
    surface_paths = require_list(scope.get("surface_paths"), "payload.scope.surface_paths", errors)
    surface_path_values = [item for item in surface_paths if isinstance(item, str)]
    if not surface_paths:
        errors.append("payload.scope.surface_paths 不能为空")
    if any(not isinstance(item, str) or not item.strip() for item in surface_paths):
        errors.append("payload.scope.surface_paths 必须是非空字符串")
    if len(surface_paths) != len(set(surface_path_values)):
        errors.append("payload.scope.surface_paths 不得重复")
    scope_evidence_refs = require_list(
        scope.get("evidence_refs"), "payload.scope.evidence_refs", errors
    )
    require_list(scope.get("limitations"), "payload.scope.limitations", errors)

    risk = require_object(payload.get("risk"), "payload.risk", errors)
    if risk.get("level") not in {"low", "medium", "high"}:
        errors.append("payload.risk.level 无效")
    risk_reasons = require_list(risk.get("reasons"), "payload.risk.reasons", errors)
    if risk.get("level") == "high" and not any(
        isinstance(item, str) and item.strip() for item in risk_reasons
    ):
        errors.append("payload.risk.level=high 时必须记录风险原因")
    if not isinstance(risk.get("model_diversity_used"), bool):
        errors.append("payload.risk.model_diversity_used 必须是 boolean")

    inventory = require_object(payload.get("claim_inventory"), "payload.claim_inventory", errors)
    if inventory.get("method") != "independent_full_text_review":
        errors.append("payload.claim_inventory.method 必须是 independent_full_text_review")
    coverage_notes = require_list(
        inventory.get("coverage_notes"), "payload.claim_inventory.coverage_notes", errors
    )
    if not coverage_notes or any(
        not isinstance(item, str) or not item.strip() for item in coverage_notes
    ):
        errors.append("payload.claim_inventory.coverage_notes 至少需要一条非空覆盖说明")
    claims = require_list(inventory.get("claims"), "payload.claim_inventory.claims", errors)
    claim_ids: set[str] = set()
    claim_by_id: dict[str, dict[str, Any]] = {}
    for index, claim_value in enumerate(claims):
        claim = require_object(claim_value, f"claims[{index}]", errors)
        required = {
            "claim_id",
            "text",
            "kind",
            "materiality",
            "surface_path",
            "source_refs",
            "verification_status",
        }
        missing = sorted(required - set(claim))
        if missing:
            errors.append(f"claims[{index}] 缺少字段：" + ", ".join(missing))
        claim_id = claim.get("claim_id")
        require_nonempty_string(claim_id, f"claims[{index}].claim_id", errors)
        if isinstance(claim_id, str):
            if claim_id in claim_ids:
                errors.append(f"claims[{index}].claim_id 重复：{claim_id}")
            claim_ids.add(claim_id)
            claim_by_id[claim_id] = claim
        require_nonempty_string(claim.get("text"), f"claims[{index}].text", errors)
        require_nonempty_string(claim.get("surface_path"), f"claims[{index}].surface_path", errors)
        if claim.get("kind") not in {"fact", "opinion", "hypothesis", "personal_experience"}:
            errors.append(f"claims[{index}].kind 无效")
        if claim.get("materiality") not in {"material", "non_material"}:
            errors.append(f"claims[{index}].materiality 无效")
        source_refs = require_list(claim.get("source_refs"), f"claims[{index}].source_refs", errors)
        if any(not isinstance(item, str) or not item.strip() for item in source_refs):
            errors.append(f"claims[{index}].source_refs 必须是非空字符串")
        if claim.get("verification_status") not in {
            "verified",
            "unverified",
            "contradicted",
            "not_applicable",
        }:
            errors.append(f"claims[{index}].verification_status 无效")
        if claim.get("kind") == "fact":
            if claim.get("verification_status") == "not_applicable":
                errors.append(f"claims[{index}] 事实主张不能标为 not_applicable")
            if claim.get("verification_status") in {"verified", "contradicted"} and not source_refs:
                errors.append(
                    f"claims[{index}] 事实主张标为 {claim.get('verification_status')} 时必须引用来源"
                )

    findings = require_list(payload.get("findings"), "payload.findings", errors)
    finding_ids: set[str] = set()
    open_counts = {severity: 0 for severity in SEVERITIES}
    open_findings: list[dict[str, Any]] = []
    for index, finding_value in enumerate(findings):
        finding = require_object(finding_value, f"findings[{index}]", errors)
        required = {
            "finding_id",
            "severity",
            "dimension",
            "surface_path",
            "locator",
            "excerpt",
            "issue",
            "claim_refs",
            "evidence_refs",
            "recommendation",
            "status",
        }
        missing = sorted(required - set(finding))
        if missing:
            errors.append(f"findings[{index}] 缺少字段：" + ", ".join(missing))
        finding_id = finding.get("finding_id")
        require_nonempty_string(finding_id, f"findings[{index}].finding_id", errors)
        if isinstance(finding_id, str):
            if finding_id in finding_ids:
                errors.append(f"findings[{index}].finding_id 重复：{finding_id}")
            finding_ids.add(finding_id)
        severity = finding.get("severity")
        if severity not in SEVERITIES:
            errors.append(f"findings[{index}].severity 无效")
        if finding.get("dimension") not in FINDING_DIMENSIONS:
            errors.append(f"findings[{index}].dimension 无效")
        for field in ("surface_path", "locator", "issue", "recommendation"):
            require_nonempty_string(finding.get(field), f"findings[{index}].{field}", errors)
        claim_refs = require_list(finding.get("claim_refs"), f"findings[{index}].claim_refs", errors)
        if any(not isinstance(item, str) or not item.strip() for item in claim_refs):
            errors.append(f"findings[{index}].claim_refs 必须是非空字符串")
        unknown_claims = sorted(
            {item for item in claim_refs if isinstance(item, str)} - claim_ids
        )
        if unknown_claims:
            errors.append(f"findings[{index}] 引用未知 claim_id：" + ", ".join(unknown_claims))
        finding_evidence_refs = require_list(
            finding.get("evidence_refs"), f"findings[{index}].evidence_refs", errors
        )
        if any(not isinstance(item, str) or not item.strip() for item in finding_evidence_refs):
            errors.append(f"findings[{index}].evidence_refs 必须是非空字符串")
        if finding.get("status") not in {"open", "resolved"}:
            errors.append(f"findings[{index}].status 无效")
        if finding.get("status") == "open" and severity in SEVERITIES:
            open_counts[severity] += 1
            open_findings.append(finding)

    for claim_id, claim in claim_by_id.items():
        if claim.get("kind") != "fact":
            continue
        verification = claim.get("verification_status")
        if verification == "contradicted":
            required_severity = "P0"
        elif verification == "unverified":
            required_severity = "P0" if claim.get("materiality") == "material" else "P1"
        else:
            continue
        covered = any(
            finding.get("severity") == required_severity
            and finding.get("status") == "open"
            and claim_id in finding.get("claim_refs", [])
            and finding.get("dimension") == "fact_and_source"
            for finding in findings
            if isinstance(finding, dict)
        )
        if not covered:
            errors.append(
                f"事实主张 {claim_id} 的核实状态为 {verification}，必须有开放 {required_severity} 事实来源问题"
            )

    summary = require_object(payload.get("summary"), "payload.summary", errors)
    verdict = summary.get("verdict")
    if verdict not in VERDICTS:
        errors.append("payload.summary.verdict 无效")
    counts = require_object(summary.get("counts"), "payload.summary.counts", errors)
    for severity in sorted(SEVERITIES):
        count = counts.get(severity)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append(f"payload.summary.counts.{severity} 必须是非负整数")
        elif count != open_counts[severity]:
            errors.append(
                f"payload.summary.counts.{severity}={count}，与开放问题数 {open_counts[severity]} 不一致"
            )
    summary_limitations = require_list(
        summary.get("limitations"), "payload.summary.limitations", errors
    )

    if open_counts["P0"] > 0 and verdict != "audit_failed":
        errors.append("存在开放 P0 时 verdict 必须是 audit_failed")
    if verdict == "passed" and (open_counts["P0"] or open_counts["P1"]):
        errors.append("passed 不得包含开放 P0/P1")
    if verdict == "audit_failed" and not (open_counts["P0"] or open_counts["P1"]):
        errors.append("audit_failed 至少需要一个开放 P0/P1")
    if verdict == "human_decision_required" and open_counts["P0"]:
        errors.append("human_decision_required 不得包含开放 P0")
    if (
        verdict == "human_decision_required"
        and not open_counts["P1"]
        and not any(isinstance(item, str) and item.strip() for item in summary_limitations)
    ):
        errors.append("human_decision_required 必须有开放 P1 或明确的审计局限")

    same_model = (
        author.get("model_id") is None
        or reviewer.get("model_id") is None
        or author.get("model_id") == reviewer.get("model_id")
    )
    if risk.get("level") == "high":
        if same_model and risk.get("model_diversity_used") is True:
            errors.append("高风险内容未记录不同模型，model_diversity_used 不能为 true")
        if not same_model and risk.get("model_diversity_used") is not True:
            errors.append("高风险内容使用不同模型时必须记录 model_diversity_used=true")
        if same_model and verdict == "passed":
            errors.append("高风险内容缺少不同模型复核时不能 verdict=passed")

    if content is not None:
        if content.get("artifact_type") != "content":
            errors.append("--content 必须指向 content artifact")
        content_schema_version = content.get("schema_version")
        if content_schema_version not in XHS_WORKFLOW_SCHEMA_VERSIONS:
            errors.append(
                "xhs content 的 schema_version 必须是受支持版本："
                + ", ".join(sorted(XHS_WORKFLOW_SCHEMA_VERSIONS))
            )
        if audit.get("schema_version") != content_schema_version:
            errors.append("audit 与 content 的 schema_version 必须一致")
        content_payload = require_object(content.get("payload"), "content.payload", errors)
        if audit.get("account_id") != content.get("account_id"):
            errors.append("audit 与 content 的 account_id 不一致")
        if audit.get("run_id") != content.get("run_id"):
            errors.append("audit 与 content 的 run_id 不一致")
        if payload.get("content_artifact_id") != content.get("artifact_id"):
            errors.append("payload.content_artifact_id 与 content 不一致")
        if payload.get("content_revision") != content_payload.get("revision"):
            errors.append("payload.content_revision 与 content 不一致")
        if payload.get("hash_mode") != "canonical_json":
            errors.append("xhs content artifact 的 hash_mode 必须是 canonical_json")
        expected_hash = auditable_content_hash(content)
        if payload.get("content_sha256") != expected_hash:
            errors.append("审计绑定的 content_sha256 与当前稿件不一致")
        authorship = content_payload.get("authorship")
        if not isinstance(authorship, dict):
            errors.append("content.payload.authorship 缺失，无法证明写审分离")
        elif author != authorship:
            errors.append("审计记录的 author 与 content.payload.authorship 不一致")
        missing_surfaces = sorted(expected_surface_paths(content) - set(surface_path_values))
        if missing_surfaces:
            errors.append("审计未覆盖最终呈现表面：" + ", ".join(missing_surfaces))

    known_source_ids = set(audit_source_ids)
    if content is not None:
        for source in content.get("provenance", []):
            if isinstance(source, dict) and isinstance(source.get("source_id"), str):
                known_source_ids.add(source["source_id"])
    reference_groups = [("payload.scope.evidence_refs", scope_evidence_refs)]
    reference_groups.extend(
        (f"claims[{index}].source_refs", claim.get("source_refs", []))
        for index, claim in enumerate(claims)
        if isinstance(claim, dict)
    )
    reference_groups.extend(
        (f"findings[{index}].evidence_refs", finding.get("evidence_refs", []))
        for index, finding in enumerate(findings)
        if isinstance(finding, dict)
    )
    for field, refs in reference_groups:
        if not isinstance(refs, list):
            continue
        unknown_sources = sorted(
            {
                item for item in refs
                if isinstance(item, str) and item.strip() and item not in known_source_ids
            }
        )
        if unknown_sources:
            errors.append(f"{field} 引用未登记来源：" + ", ".join(unknown_sources))

    return errors


def validate_audit_target(audit: dict[str, Any], target_path: Path) -> list[str]:
    raw = target_path.read_bytes()
    content: dict[str, Any] | None = None
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        decoded = None
    if isinstance(decoded, dict) and decoded.get("artifact_type") == "content":
        content = decoded
    errors = validate_audit_document(audit, content=content)
    expected_hash, expected_mode = content_hash_from_path(target_path)
    payload = audit.get("payload", {})
    if isinstance(payload, dict):
        if payload.get("content_sha256") != expected_hash:
            errors.append("审计绑定的 content_sha256 与当前冻结稿件不一致")
        if payload.get("hash_mode") != expected_mode:
            errors.append(
                f"当前冻结稿件的 hash_mode 应为 {expected_mode}"
            )
    return errors


def command_hash(args: argparse.Namespace) -> None:
    digest, mode = content_hash_from_path(Path(args.content).resolve())
    print(json.dumps({"sha256": digest, "hash_mode": mode}, ensure_ascii=False))


def command_validate(args: argparse.Namespace) -> None:
    audit = load_json(Path(args.audit).resolve())
    errors = (
        validate_audit_target(audit, Path(args.target).resolve())
        if args.target
        else validate_audit_document(audit)
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise AuditContractError(f"校验失败，共 {len(errors)} 项")
    print(f"PASS: {Path(args.audit).resolve()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="通用文章独立审计契约辅助器")
    sub = parser.add_subparsers(dest="command", required=True)
    hash_parser = sub.add_parser("hash", help="计算冻结稿件指纹")
    hash_parser.add_argument("content")
    hash_parser.set_defaults(func=command_hash)
    validate = sub.add_parser("validate", help="校验 article_audit artifact")
    validate.add_argument("audit")
    validate.add_argument(
        "--content",
        "--target",
        dest="target",
        help="同时核对冻结稿件；支持 xhs content、Markdown、纯文本或其他文件",
    )
    validate.set_defaults(func=command_validate)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except (AuditContractError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
