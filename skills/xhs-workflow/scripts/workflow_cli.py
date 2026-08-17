#!/usr/bin/env python3
"""Deterministic state, validation, approval, audit, and rendering for XHS Workflow V2.2."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "2.2.0"
ARTIFACT_TYPES = {
    "run_manifest",
    "account_strategy",
    "persona",
    "topic_report",
    "content",
    "inventory_item",
    "publication",
    "metrics_snapshot",
    "review",
    "experiment",
}
STATUSES = {
    "draft",
    "review_required",
    "approved",
    "rejected",
    "superseded",
    "collecting",
    "idea",
    "review_ready",
    "ready",
    "scheduled",
    "held",
    "publishing",
    "published",
    "failed",
    "unknown",
    "archived",
}
GATES = {f"G{i}" for i in range(7)}
GATE_BY_TYPE = {
    "run_manifest": {"G0", "G5"},
    "account_strategy": {"G1"},
    "persona": {"G1"},
    "topic_report": {"G2"},
    "content": {"G3"},
    "publication": {"G4"},
    "experiment": {"G6"},
}
REGISTER_RULES = {
    "account_strategy": ("account_strategy", "G1", "persona"),
    "persona": ("persona", "G1", "topics"),
    "topic_report": ("topic_report", "G2", "content"),
    "content": ("content", "G3", "inventory"),
    "inventory_item": ("inventory_item", None, "publication"),
    "publication": ("publication", "G4", "measurement"),
    "metrics_snapshot": ("metrics_snapshot", None, "measurement"),
    "review": ("review", None, "iteration"),
    "experiment": ("experiment", "G6", "complete"),
}
PAYLOAD_REQUIRED = {
    "run_manifest": {"objective", "run_type", "strategy_artifact_id", "persona_artifact_id", "content_sequence_no", "current_stage", "runtime_capabilities", "data_scope", "measurement_plan", "artifact_paths", "gate_status", "errors"},
    "account_strategy": {"revision", "supersedes_artifact_id", "lifecycle_stage", "stage_confidence", "persona_mode", "play_mode", "transition", "stage_evidence", "content_objectives", "publishing_policy", "inventory_policy", "measurement_policy", "experience_seed_refs", "limitations"},
    "persona": {"revision", "supersedes_artifact_id", "strategy_artifact_id", "mode", "hypotheses", "validation_plan", "identity", "niche", "audience", "differentiation", "content_pillars", "voice", "boundaries"},
    "topic_report": {"objective", "strategy_artifact_id", "persona_artifact_id", "research_mode", "requested_topics", "evidence", "candidates", "selected_topic_ids", "limitations"},
    "content": {"revision", "strategy_artifact_id", "persona_artifact_id", "topic_report_artifact_id", "topic_id", "content_objective", "content_sequence_no", "format", "title", "caption", "hashtags", "claims", "personal_experiences", "assets", "change_summary"},
    "inventory_item": {"revision", "strategy_artifact_id", "persona_artifact_id", "topic_report_artifact_id", "topic_id", "content_artifact_id", "content_artifact_path", "publication_artifact_id", "publication_artifact_path", "content_sequence_no", "content_objective", "format", "working_title", "same_topic_key", "state", "planned_publish_at", "hold_reason", "policy_check", "measurement_schedule", "history"},
    "publication": {"strategy_artifact_id", "inventory_item_artifact_id", "content_artifact_id", "target_account_id", "platform", "state", "visibility", "asset_order", "policy_check", "post_publish_actions", "attempts"},
    "metrics_snapshot": {"content_artifact_id", "publication_artifact_id", "format", "captured_at", "window", "measurement_kind", "checkpoint_days", "prior_snapshot_artifact_id", "stock_metrics", "flow_metrics", "derived_metrics", "trust_metrics", "qualitative_metrics", "missing_fields", "source"},
    "review": {"strategy_artifact_id", "content_artifact_id", "snapshot_artifact_ids", "baseline", "observations", "hypotheses", "diagnoses", "recommended_interventions", "lifecycle_assessment", "persona_validation", "trust_observations", "long_tail_observations", "limitations"},
    "experiment": {"review_artifact_id", "hypothesis", "intervention_type", "independent_variable", "control", "target_metric", "guardrails", "observation_window", "sample_size_plan", "stop_rule", "state", "strategy_change_proposal"},
}
CAPABILITY_KEYS = {
    "local_json_storage",
    "append_audit_log",
    "human_approval",
    "web_research",
    "authenticated_platform_control",
    "native_image_generation",
    "metrics_collection",
}
CAPABILITY_STATUSES = {"available", "unavailable", "unknown"}
EXECUTION_MODES = {"undetermined", "full", "assisted", "document_only"}
RUN_TYPES = {
    "full_cycle",
    "strategy_review",
    "trial_content",
    "content_production",
    "batch_creation",
    "publication",
    "measurement",
    "long_tail_review",
}
LIFECYCLE_STAGES = {"trial", "scale", "stabilize", "flywheel"}
CONTENT_OBJECTIVES = {"acquisition", "trust", "tag_strengthening"}
THRESHOLD_BASES = {"account_baseline", "experience_seed", "manual", "unset"}
INVENTORY_STATES = {"idea", "draft", "review_ready", "ready", "scheduled", "held", "published", "archived"}
INVENTORY_TRANSITIONS = {
    "idea": {"draft", "archived"},
    "draft": {"review_ready", "held", "archived"},
    "review_ready": {"ready", "held", "draft"},
    "ready": {"scheduled", "held", "draft"},
    "scheduled": {"ready", "held", "published"},
    "held": {"draft", "review_ready", "ready", "archived"},
    "published": {"archived"},
    "archived": set(),
}
PUBLICATION_TRANSITIONS = {
    "draft": {"review_required"},
    "review_required": set(),
    "approved": {"publishing"},
    "publishing": {"published", "failed", "unknown"},
    "published": set(),
    "failed": {"review_required"},
    "unknown": {"published", "failed"},
}
APPROVAL_VOLATILE_FIELDS = {
    "state",
    "attempts",
    "remote_id",
    "remote_url",
    "published_at",
    "last_error",
    "post_publish_actions",
    "current_stage",
    "artifact_paths",
    "gate_status",
    "errors",
}
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{5,127}$")
ACCOUNT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "schemas" / "artifact.schema.json"


class WorkflowError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    timestamp = datetime.now().astimezone().strftime("%Y%m%dt%H%M%S")
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"JSON 无法解析：{path}:{exc.lineno}:{exc.colno} {exc.msg}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"顶层必须是 JSON object：{path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def approval_view(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: approval_view(item)
            for key, item in value.items()
            if key not in APPROVAL_VOLATILE_FIELDS
        }
    if isinstance(value, list):
        return [approval_view(item) for item in value]
    return value


def payload_hash(artifact: dict[str, Any], gate: str | None = None) -> str:
    raw_payload = artifact.get("payload", {})
    if artifact.get("artifact_type") == "run_manifest" and gate == "G0":
        raw_payload = {
            key: raw_payload.get(key)
            for key in ("objective", "run_type", "runtime_capabilities", "data_scope")
        }
    elif artifact.get("artifact_type") == "run_manifest" and gate == "G5":
        raw_payload = {
            key: raw_payload.get(key)
            for key in ("measurement_plan", "data_scope")
        }
    payload = approval_view(raw_payload)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_datetime(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{field} 必须是 ISO 8601 字符串")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} 不是有效的 ISO 8601 时间：{value}")


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


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_positive_int_or_null(value: Any, field: str, errors: list[str]) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
        errors.append(f"{field} 必须是正整数或 null")


def validate_policy_check(value: Any, field: str, errors: list[str]) -> None:
    if value is None:
        return
    check = require_object(value, field, errors)
    required = {"checked_at", "strategy_artifact_id", "action", "decision", "reasons"}
    missing = sorted(required - set(check))
    if missing:
        errors.append(f"{field} 缺少字段：" + ", ".join(missing))
    if check.get("checked_at"):
        parse_datetime(check.get("checked_at"), f"{field}.checked_at", errors)
    if check.get("action") not in {"publish", "modify", "delete"}:
        errors.append(f"{field}.action 无效")
    if check.get("decision") not in {"allowed", "blocked", "needs_human"}:
        errors.append(f"{field}.decision 无效")
    require_list(check.get("reasons"), f"{field}.reasons", errors)


def unknown_capability(*, image_generation: bool = False) -> dict[str, Any]:
    capability: dict[str, Any] = {
        "status": "unknown",
        "capability_id": None,
        "notes": [],
    }
    if image_generation:
        capability["processing_boundary"] = "unknown"
        capability["supports_reference_images"] = None
        capability["returns_local_file"] = None
    return capability


def default_runtime_capabilities(timestamp: str, runtime_name: str | None) -> dict[str, Any]:
    return {
        "runtime_name": runtime_name,
        "captured_at": timestamp,
        "capability_source": "unknown",
        "discovery_status": "pending",
        "execution_mode": "undetermined",
        "capabilities": {
            key: unknown_capability(image_generation=key == "native_image_generation")
            for key in sorted(CAPABILITY_KEYS)
        },
        "limitations": [],
    }


def effective_approval(artifact: dict[str, Any], gate: str) -> bool:
    current_hash = payload_hash(artifact, gate)
    approvals = artifact.get("approvals", [])
    if not isinstance(approvals, list):
        return False
    for approval in reversed(approvals):
        if not isinstance(approval, dict) or approval.get("gate") != gate:
            continue
        if approval.get("decision") != "approved":
            return False
        return approval.get("payload_sha256") == current_hash
    return False


def optional_json_schema_errors(artifact: dict[str, Any]) -> list[str]:
    """Run the bundled Draft 2020-12 schema when jsonschema is available."""
    try:
        import jsonschema
    except ImportError:
        return []
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.FormatChecker(),
        )
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        return [f"无法加载 bundled JSON Schema：{exc}"]
    errors = []
    for error in sorted(validator.iter_errors(artifact), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"JSON Schema {path}: {error.message}")
    return errors


def validate_artifact(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
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
    missing = sorted(required - set(artifact))
    if missing:
        errors.append("缺少顶层字段：" + ", ".join(missing))

    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须是 {SCHEMA_VERSION}")
    artifact_type = artifact.get("artifact_type")
    if artifact_type not in ARTIFACT_TYPES:
        errors.append(f"不支持的 artifact_type：{artifact_type}")
    artifact_id = artifact.get("artifact_id")
    if not isinstance(artifact_id, str) or not ID_RE.fullmatch(artifact_id):
        errors.append("artifact_id 格式无效")
    account_id = artifact.get("account_id")
    if not isinstance(account_id, str) or not ACCOUNT_RE.fullmatch(account_id):
        errors.append("account_id 格式无效")
    run_id = artifact.get("run_id")
    if run_id is not None and (not isinstance(run_id, str) or not run_id.startswith("run_") or not ID_RE.fullmatch(run_id)):
        errors.append("run_id 必须为 null 或 run_ 开头的稳定 ID")
    parse_datetime(artifact.get("created_at"), "created_at", errors)
    parse_datetime(artifact.get("updated_at"), "updated_at", errors)
    if artifact.get("status") not in STATUSES:
        errors.append(f"status 无效：{artifact.get('status')}")

    provenance = require_list(artifact.get("provenance"), "provenance", errors)
    for index, source in enumerate(provenance):
        if not isinstance(source, dict):
            errors.append(f"provenance[{index}] 必须是 object")
            continue
        for field in ("source_id", "kind", "captured_at", "summary"):
            if not source.get(field):
                errors.append(f"provenance[{index}] 缺少 {field}")
        if source.get("kind") in {"web_source", "platform_data"} and not source.get("url"):
            errors.append(f"provenance[{index}] 的 {source.get('kind')} 必须包含 url")
        if "quote" in source and source.get("quote_verified") is not True:
            errors.append(f"provenance[{index}] 含 quote 时必须 quote_verified=true")
        if source.get("captured_at"):
            parse_datetime(source.get("captured_at"), f"provenance[{index}].captured_at", errors)

    approvals = require_list(artifact.get("approvals"), "approvals", errors)
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            errors.append(f"approvals[{index}] 必须是 object")
            continue
        if approval.get("gate") not in GATES:
            errors.append(f"approvals[{index}].gate 无效")
        if approval.get("decision") not in {"approved", "rejected", "revoked"}:
            errors.append(f"approvals[{index}].decision 无效")
        if approval.get("actor_type") != "human":
            errors.append(f"approvals[{index}] 只能由 human 作出")
        sha = approval.get("payload_sha256")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            errors.append(f"approvals[{index}].payload_sha256 无效")
        current_hash = payload_hash(artifact, approval.get("gate"))
        if approval.get("decision") == "approved" and sha != current_hash:
            later_same_gate = any(
                isinstance(item, dict) and item.get("gate") == approval.get("gate")
                for item in approvals[index + 1 :]
            )
            if not later_same_gate:
                errors.append(f"{approval.get('gate')} 批准已因 payload 变化失效")
        if approval.get("at"):
            parse_datetime(approval.get("at"), f"approvals[{index}].at", errors)

    payload = require_object(artifact.get("payload"), "payload", errors)
    if artifact_type in PAYLOAD_REQUIRED:
        missing_payload = sorted(PAYLOAD_REQUIRED[artifact_type] - set(payload))
        if missing_payload:
            errors.append("payload 缺少字段：" + ", ".join(missing_payload))

    if artifact_type == "run_manifest":
        if payload.get("run_type") not in RUN_TYPES:
            errors.append("payload.run_type 无效")
        if payload.get("current_stage") not in {
            "scope", "strategy", "persona", "topics", "content", "inventory",
            "publication", "measurement", "iteration", "complete",
        }:
            errors.append("payload.current_stage 无效")
        for field in ("strategy_artifact_id", "persona_artifact_id"):
            value = payload.get(field)
            if value is not None and (not isinstance(value, str) or not value):
                errors.append(f"payload.{field} 必须是非空字符串或 null")
        validate_positive_int_or_null(
            payload.get("content_sequence_no"), "payload.content_sequence_no", errors
        )
        measurement_plan = require_object(payload.get("measurement_plan"), "payload.measurement_plan", errors)
        for field in ("snapshot_windows", "trust_metrics", "long_tail_checkpoints_days", "qualitative_rubric_refs"):
            require_list(measurement_plan.get(field), f"payload.measurement_plan.{field}", errors)
        checkpoints = measurement_plan.get("long_tail_checkpoints_days", [])
        if isinstance(checkpoints, list):
            if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in checkpoints):
                errors.append("payload.measurement_plan.long_tail_checkpoints_days 只能包含正整数")
            if len(checkpoints) != len(set(checkpoints)):
                errors.append("payload.measurement_plan.long_tail_checkpoints_days 不得重复")
        gates = require_object(payload.get("gate_status"), "payload.gate_status", errors)
        if set(gates) != GATES:
            errors.append("payload.gate_status 必须且只能包含 G0-G6")
        runtime = require_object(payload.get("runtime_capabilities"), "payload.runtime_capabilities", errors)
        if runtime.get("capability_source") not in {"runtime_advertised", "human_declared", "mixed", "unknown"}:
            errors.append("payload.runtime_capabilities.capability_source 无效")
        if runtime.get("discovery_status") not in {"pending", "partial", "complete"}:
            errors.append("payload.runtime_capabilities.discovery_status 无效")
        if runtime.get("execution_mode") not in EXECUTION_MODES:
            errors.append("payload.runtime_capabilities.execution_mode 无效")
        if runtime.get("captured_at"):
            parse_datetime(runtime.get("captured_at"), "payload.runtime_capabilities.captured_at", errors)
        capabilities = require_object(runtime.get("capabilities"), "payload.runtime_capabilities.capabilities", errors)
        if set(capabilities) != CAPABILITY_KEYS:
            errors.append("payload.runtime_capabilities.capabilities 必须且只能包含规定的 7 项能力")
        for capability_name in sorted(CAPABILITY_KEYS):
            entry = require_object(
                capabilities.get(capability_name),
                f"payload.runtime_capabilities.capabilities.{capability_name}",
                errors,
            )
            if entry.get("status") not in CAPABILITY_STATUSES:
                errors.append(f"runtime capability {capability_name} status 无效")
            capability_id = entry.get("capability_id")
            if capability_id is not None and not isinstance(capability_id, str):
                errors.append(f"runtime capability {capability_name} capability_id 必须是 string 或 null")
            if entry.get("status") == "available" and not capability_id:
                errors.append(f"runtime capability {capability_name} 可用时必须记录 capability_id")
            require_list(entry.get("notes"), f"runtime capability {capability_name}.notes", errors)
        image_capability = capabilities.get("native_image_generation", {})
        if isinstance(image_capability, dict):
            if image_capability.get("processing_boundary") not in {"local", "external", "unknown"}:
                errors.append("runtime capability native_image_generation.processing_boundary 无效")
            for field in ("supports_reference_images", "returns_local_file"):
                value = image_capability.get(field)
                if value is not None and not isinstance(value, bool):
                    errors.append(f"runtime capability native_image_generation.{field} 必须是 boolean 或 null")
        require_list(runtime.get("limitations"), "payload.runtime_capabilities.limitations", errors)

        data_scope = require_object(payload.get("data_scope"), "payload.data_scope", errors)
        required_scope_fields = {"allowed_sources", "external_processing", "personal_data"}
        if set(data_scope) != required_scope_fields:
            errors.append("payload.data_scope 必须且只能包含 allowed_sources、external_processing、personal_data")
        require_list(data_scope.get("allowed_sources"), "payload.data_scope.allowed_sources", errors)
        external_processing = require_list(
            data_scope.get("external_processing"), "payload.data_scope.external_processing", errors
        )
        for index, entry in enumerate(external_processing):
            if not isinstance(entry, dict):
                errors.append(f"payload.data_scope.external_processing[{index}] 必须是 object")
                continue
            for field in ("capability_id", "purpose", "data_categories"):
                if not entry.get(field):
                    errors.append(f"payload.data_scope.external_processing[{index}] 缺少 {field}")
            require_list(
                entry.get("data_categories"),
                f"payload.data_scope.external_processing[{index}].data_categories",
                errors,
            )
        require_list(data_scope.get("personal_data"), "payload.data_scope.personal_data", errors)
    elif artifact_type == "account_strategy":
        if payload.get("lifecycle_stage") not in LIFECYCLE_STAGES:
            errors.append("account_strategy.lifecycle_stage 无效")
        if payload.get("stage_confidence") not in {"low", "medium", "high"}:
            errors.append("account_strategy.stage_confidence 无效")
        if payload.get("persona_mode") not in {"assumed", "validated"}:
            errors.append("account_strategy.persona_mode 无效")
        if payload.get("play_mode") not in {"trend", "ip", "hybrid", "undecided"}:
            errors.append("account_strategy.play_mode 无效")
        transition = require_object(payload.get("transition"), "payload.transition", errors)
        from_stage = transition.get("from_stage")
        if from_stage is not None and from_stage not in LIFECYCLE_STAGES:
            errors.append("account_strategy.transition.from_stage 无效")
        for field in ("rationale", "evidence_refs", "alternative_explanations"):
            if field not in transition:
                errors.append(f"account_strategy.transition 缺少 {field}")
        evidence_refs = require_list(
            transition.get("evidence_refs"), "payload.transition.evidence_refs", errors
        )
        require_list(
            transition.get("alternative_explanations"),
            "payload.transition.alternative_explanations",
            errors,
        )
        if from_stage and from_stage != payload.get("lifecycle_stage") and not evidence_refs:
            errors.append("生命周期阶段发生变化时 transition.evidence_refs 不能为空")
        stage_evidence = require_list(payload.get("stage_evidence"), "payload.stage_evidence", errors)
        for index, item in enumerate(stage_evidence):
            if not isinstance(item, dict):
                errors.append(f"stage_evidence[{index}] 必须是 object")
                continue
            for field in ("signal_id", "observation", "evidence_refs", "confidence"):
                if field not in item:
                    errors.append(f"stage_evidence[{index}] 缺少 {field}")
            if item.get("confidence") not in {"low", "medium", "high"}:
                errors.append(f"stage_evidence[{index}].confidence 无效")
        objectives = require_list(payload.get("content_objectives"), "payload.content_objectives", errors)
        seen_objectives: set[str] = set()
        shares: list[float] = []
        all_shares_present = bool(objectives)
        for index, item in enumerate(objectives):
            if not isinstance(item, dict):
                errors.append(f"content_objectives[{index}] 必须是 object")
                continue
            objective = item.get("objective")
            if objective not in CONTENT_OBJECTIVES:
                errors.append(f"content_objectives[{index}].objective 无效")
            elif objective in seen_objectives:
                errors.append(f"content_objectives[{index}].objective 重复")
            else:
                seen_objectives.add(objective)
            share = item.get("target_share")
            if share is None:
                all_shares_present = False
            elif not is_number(share) or not 0 <= share <= 1:
                errors.append(f"content_objectives[{index}].target_share 必须在 0 到 1 之间或为 null")
            else:
                shares.append(float(share))
        if all_shares_present and objectives and abs(sum(shares) - 1.0) > 1e-6:
            errors.append("content_objectives 全部给出 target_share 时合计必须为 1")
        publishing = require_object(payload.get("publishing_policy"), "payload.publishing_policy", errors)
        if publishing.get("modification_policy") not in {"human_review_required", "prohibited"}:
            errors.append("publishing_policy.modification_policy 无效")
        if publishing.get("deletion_policy") not in {"human_review_required", "prohibited"}:
            errors.append("publishing_policy.deletion_policy 无效")
        if publishing.get("threshold_basis") not in THRESHOLD_BASES:
            errors.append("publishing_policy.threshold_basis 无效")
        if publishing.get("exceptions_require_human") is not True:
            errors.append("publishing_policy.exceptions_require_human 必须为 true")
        for field in ("minimum_observation_hours", "same_topic_cooldown_hours", "breakout_hold_hours"):
            value = publishing.get(field)
            if value is not None and (not is_number(value) or value < 0):
                errors.append(f"publishing_policy.{field} 必须是非负数或 null")
        inventory_policy = require_object(payload.get("inventory_policy"), "payload.inventory_policy", errors)
        if inventory_policy.get("threshold_basis") not in THRESHOLD_BASES:
            errors.append("inventory_policy.threshold_basis 无效")
        coverage = inventory_policy.get("target_coverage_days")
        if coverage is not None and (not is_number(coverage) or coverage < 0):
            errors.append("inventory_policy.target_coverage_days 必须是非负数或 null")
        ready_items = inventory_policy.get("target_ready_items")
        if ready_items is not None and (not isinstance(ready_items, int) or isinstance(ready_items, bool) or ready_items < 0):
            errors.append("inventory_policy.target_ready_items 必须是非负整数或 null")
        measurement = require_object(payload.get("measurement_policy"), "payload.measurement_policy", errors)
        for field in ("trust_metrics", "long_tail_checkpoints_days", "qualitative_rubric_refs"):
            require_list(measurement.get(field), f"measurement_policy.{field}", errors)
        strategy_checkpoints = measurement.get("long_tail_checkpoints_days", [])
        if isinstance(strategy_checkpoints, list):
            if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in strategy_checkpoints):
                errors.append("measurement_policy.long_tail_checkpoints_days 只能包含正整数")
            if len(strategy_checkpoints) != len(set(strategy_checkpoints)):
                errors.append("measurement_policy.long_tail_checkpoints_days 不得重复")
        require_list(payload.get("experience_seed_refs"), "payload.experience_seed_refs", errors)
        require_list(payload.get("limitations"), "payload.limitations", errors)
    elif artifact_type == "persona":
        if payload.get("mode") not in {"assumed", "validated"}:
            errors.append("persona.mode 无效")
        hypotheses = require_list(payload.get("hypotheses"), "payload.hypotheses", errors)
        for index, item in enumerate(hypotheses):
            if not isinstance(item, dict):
                errors.append(f"persona.hypotheses[{index}] 必须是 object")
                continue
            for field in ("hypothesis_id", "statement", "status", "evidence_refs"):
                if field not in item:
                    errors.append(f"persona.hypotheses[{index}] 缺少 {field}")
            if item.get("status") not in {"pending", "supported", "refuted", "inconclusive"}:
                errors.append(f"persona.hypotheses[{index}].status 无效")
        validation_plan = require_object(payload.get("validation_plan"), "payload.validation_plan", errors)
        validate_positive_int_or_null(
            validation_plan.get("sample_target"), "payload.validation_plan.sample_target", errors
        )
        for field in ("diversity_dimensions", "success_signals", "stop_conditions"):
            require_list(validation_plan.get(field), f"payload.validation_plan.{field}", errors)
        if payload.get("mode") == "assumed":
            if not hypotheses:
                errors.append("assumed persona 至少需要一个可证伪假设")
            if not validation_plan.get("success_signals") or not validation_plan.get("stop_conditions"):
                errors.append("assumed persona 必须定义 success_signals 和 stop_conditions")
    elif artifact_type == "topic_report":
        if payload.get("research_mode") not in {"trial_diversification", "focused", "trend_window"}:
            errors.append("topic_report.research_mode 无效")
        candidates = require_list(payload.get("candidates"), "payload.candidates", errors)
        if not candidates:
            errors.append("topic_report 至少需要一个候选选题")
        candidate_ids = {item.get("topic_id") for item in candidates if isinstance(item, dict)}
        selected = require_list(payload.get("selected_topic_ids"), "payload.selected_topic_ids", errors)
        unknown = sorted(set(selected) - candidate_ids)
        if unknown:
            errors.append("selected_topic_ids 引用了不存在的候选：" + ", ".join(unknown))
        evidence_items = require_list(payload.get("evidence"), "payload.evidence", errors)
        evidence_ids = set()
        for index, item in enumerate(evidence_items):
            if not isinstance(item, dict):
                errors.append(f"payload.evidence[{index}] 必须是 object")
                continue
            evidence_id = item.get("evidence_id")
            if not evidence_id:
                errors.append(f"payload.evidence[{index}] 缺少 evidence_id")
            elif evidence_id in evidence_ids:
                errors.append(f"payload.evidence[{index}] evidence_id 重复：{evidence_id}")
            else:
                evidence_ids.add(evidence_id)
            for field in ("kind", "source_ref", "captured_at", "observation", "limitations"):
                if field not in item:
                    errors.append(f"payload.evidence[{index}] 缺少 {field}")
            if item.get("quote") and item.get("quote_verified") is not True:
                errors.append(f"payload.evidence[{index}] 含 quote 时必须 quote_verified=true")
            if item.get("captured_at"):
                parse_datetime(item.get("captured_at"), f"payload.evidence[{index}].captured_at", errors)
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                errors.append(f"payload.candidates[{index}] 必须是 object")
                continue
            for ref in candidate.get("evidence_refs", []):
                if ref not in evidence_ids:
                    errors.append(f"candidate {candidate.get('topic_id')} 引用未知 evidence_id：{ref}")
            if candidate.get("confidence") not in {"low", "medium", "high"}:
                errors.append(f"candidate {candidate.get('topic_id')} confidence 无效")
    elif artifact_type == "content":
        if payload.get("content_objective") not in CONTENT_OBJECTIVES:
            errors.append("content.content_objective 无效")
        validate_positive_int_or_null(
            payload.get("content_sequence_no"), "payload.content_sequence_no", errors
        )
        content_format = payload.get("format")
        if content_format not in {"image", "video", "text"}:
            errors.append("payload.format 必须是 image、video 或 text")
        if content_format == "image" and not payload.get("cards"):
            errors.append("图文内容必须包含 cards")
        if content_format == "video" and not payload.get("shots"):
            errors.append("视频内容必须包含 shots")
        claim_ids: set[str] = set()
        for index, claim in enumerate(require_list(payload.get("claims"), "payload.claims", errors)):
            if not isinstance(claim, dict):
                errors.append(f"claims[{index}] 必须是 object")
                continue
            for field in ("claim_id", "text", "kind", "source_refs", "verification_status"):
                if field not in claim:
                    errors.append(f"claims[{index}] 缺少 {field}")
            claim_id = claim.get("claim_id")
            if claim_id in claim_ids:
                errors.append(f"claims[{index}] claim_id 重复：{claim_id}")
            elif claim_id:
                claim_ids.add(claim_id)
            if claim.get("kind") not in {"fact", "opinion", "hypothesis"}:
                errors.append(f"claims[{index}].kind 无效")
            if claim.get("kind") == "fact":
                if claim.get("verification_status") != "verified" or not claim.get("source_refs"):
                    errors.append(f"claims[{index}] 事实主张必须验证并关联来源")
        for index, experience in enumerate(require_list(payload.get("personal_experiences"), "payload.personal_experiences", errors)):
            if not isinstance(experience, dict) or experience.get("confirmed_by_human") is not True or not experience.get("source_ref"):
                errors.append(f"personal_experiences[{index}] 必须有 source_ref 且经人工确认")
        for index, asset in enumerate(require_list(payload.get("assets"), "payload.assets", errors)):
            if not isinstance(asset, dict):
                errors.append(f"assets[{index}] 必须是 object")
                continue
            if asset.get("rights_basis") not in {"owned", "licensed", "permission", "public_domain", "generated"}:
                errors.append(f"assets[{index}].rights_basis 无效")
            if asset.get("rights_status") != "verified":
                errors.append(f"assets[{index}] 权利状态未验证，不得进入 G3")
            sha = asset.get("sha256")
            if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
                errors.append(f"assets[{index}].sha256 无效")
            if not isinstance(asset.get("contains_personal_data"), bool):
                errors.append(f"assets[{index}].contains_personal_data 必须是 boolean")
            if not isinstance(asset.get("external_processing_approved"), bool):
                errors.append(f"assets[{index}].external_processing_approved 必须是 boolean")
            if asset.get("rights_basis") == "generated":
                if not asset.get("generation_job_id") or not asset.get("generator_capability_id"):
                    errors.append(f"assets[{index}] 生成素材必须记录 generation_job_id 和 generator_capability_id")
    elif artifact_type == "inventory_item":
        state = payload.get("state")
        if state not in INVENTORY_STATES:
            errors.append(f"inventory_item.state 无效：{state}")
        if artifact.get("status") != state:
            errors.append("inventory_item 顶层 status 必须与 payload.state 一致")
        if payload.get("content_objective") not in CONTENT_OBJECTIVES:
            errors.append("inventory_item.content_objective 无效")
        if payload.get("format") not in {"image", "video", "text"}:
            errors.append("inventory_item.format 无效")
        validate_positive_int_or_null(
            payload.get("content_sequence_no"), "payload.content_sequence_no", errors
        )
        if state == "scheduled":
            if not payload.get("planned_publish_at"):
                errors.append("scheduled inventory_item 必须有 planned_publish_at")
            else:
                parse_datetime(payload.get("planned_publish_at"), "payload.planned_publish_at", errors)
        elif payload.get("planned_publish_at") is not None:
            parse_datetime(payload.get("planned_publish_at"), "payload.planned_publish_at", errors)
        if state == "held" and not payload.get("hold_reason"):
            errors.append("held inventory_item 必须说明 hold_reason")
        validate_policy_check(payload.get("policy_check"), "payload.policy_check", errors)
        schedule = require_list(payload.get("measurement_schedule"), "payload.measurement_schedule", errors)
        seen_checkpoints: set[int] = set()
        for index, item in enumerate(schedule):
            if not isinstance(item, dict):
                errors.append(f"measurement_schedule[{index}] 必须是 object")
                continue
            for field in ("checkpoint_days", "due_at", "status", "snapshot_artifact_id", "completed_at"):
                if field not in item:
                    errors.append(f"measurement_schedule[{index}] 缺少 {field}")
            checkpoint = item.get("checkpoint_days")
            if not isinstance(checkpoint, int) or isinstance(checkpoint, bool) or checkpoint <= 0:
                errors.append(f"measurement_schedule[{index}].checkpoint_days 必须是正整数")
            elif checkpoint in seen_checkpoints:
                errors.append(f"measurement_schedule checkpoint 重复：{checkpoint}")
            else:
                seen_checkpoints.add(checkpoint)
            if item.get("due_at"):
                parse_datetime(item.get("due_at"), f"measurement_schedule[{index}].due_at", errors)
            if item.get("status") not in {"pending", "completed", "skipped"}:
                errors.append(f"measurement_schedule[{index}].status 无效")
            if item.get("status") == "completed" and not item.get("snapshot_artifact_id"):
                errors.append(f"measurement_schedule[{index}] 完成时必须引用 snapshot_artifact_id")
            if item.get("completed_at") is not None:
                parse_datetime(item.get("completed_at"), f"measurement_schedule[{index}].completed_at", errors)
        history = require_list(payload.get("history"), "payload.history", errors)
        for index, item in enumerate(history):
            if not isinstance(item, dict):
                errors.append(f"history[{index}] 必须是 object")
                continue
            for field in ("from", "to", "at", "actor_id", "actor_type", "reason"):
                if field not in item:
                    errors.append(f"history[{index}] 缺少 {field}")
            if item.get("from") is not None and item.get("from") not in INVENTORY_STATES:
                errors.append(f"history[{index}].from 无效")
            if item.get("to") not in INVENTORY_STATES:
                errors.append(f"history[{index}].to 无效")
            if item.get("actor_type") not in {"human", "agent"}:
                errors.append(f"history[{index}].actor_type 无效")
            if item.get("at"):
                parse_datetime(item.get("at"), f"history[{index}].at", errors)
    elif artifact_type == "publication":
        state = payload.get("state")
        if state not in PUBLICATION_TRANSITIONS:
            errors.append(f"publication state 无效：{state}")
        if artifact.get("status") != state:
            errors.append("publication 顶层 status 必须与 payload.state 一致")
        if payload.get("target_account_id") != artifact.get("account_id"):
            errors.append("target_account_id 必须与 artifact.account_id 一致")
        validate_policy_check(payload.get("policy_check"), "payload.policy_check", errors)
        actions = require_list(payload.get("post_publish_actions"), "payload.post_publish_actions", errors)
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                errors.append(f"post_publish_actions[{index}] 必须是 object")
                continue
            for field in ("action", "requested_at", "actor_id", "actor_type", "decision", "reasons"):
                if field not in action:
                    errors.append(f"post_publish_actions[{index}] 缺少 {field}")
            if action.get("action") not in {"modify", "delete"}:
                errors.append(f"post_publish_actions[{index}].action 无效")
            if action.get("actor_type") != "human":
                errors.append(f"post_publish_actions[{index}] 只能由 human 决定")
            if action.get("decision") not in {"approved", "rejected"}:
                errors.append(f"post_publish_actions[{index}].decision 无效")
            if action.get("requested_at"):
                parse_datetime(action.get("requested_at"), f"post_publish_actions[{index}].requested_at", errors)
        if state == "published" and not (payload.get("remote_id") or payload.get("remote_url")):
            errors.append("published 状态必须有 remote_id 或 remote_url")
    elif artifact_type == "metrics_snapshot":
        if payload.get("format") not in {"image", "video", "text"}:
            errors.append("metrics_snapshot.format 无效")
        measurement_kind = payload.get("measurement_kind")
        if measurement_kind not in {"initial", "long_tail"}:
            errors.append("metrics_snapshot.measurement_kind 无效")
        checkpoint_days = payload.get("checkpoint_days")
        validate_positive_int_or_null(checkpoint_days, "payload.checkpoint_days", errors)
        if measurement_kind == "long_tail" and checkpoint_days is None:
            errors.append("long_tail metrics_snapshot 必须记录 checkpoint_days")
        if measurement_kind == "long_tail" and not payload.get("prior_snapshot_artifact_id"):
            errors.append("long_tail metrics_snapshot 必须引用 prior_snapshot_artifact_id")
        parse_datetime(payload.get("captured_at"), "payload.captured_at", errors)
        for section in ("stock_metrics", "flow_metrics", "derived_metrics", "trust_metrics"):
            metrics = require_object(payload.get(section), f"payload.{section}", errors)
            for name, value in metrics.items():
                if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                    errors.append(f"payload.{section}.{name} 必须是 number 或 null")
                if section != "derived_metrics" and isinstance(value, (int, float)) and value < 0:
                    errors.append(f"payload.{section}.{name} 不得为负数")
        for index, item in enumerate(require_list(payload.get("qualitative_metrics"), "payload.qualitative_metrics", errors)):
            if not isinstance(item, dict):
                errors.append(f"qualitative_metrics[{index}] 必须是 object")
                continue
            for field in ("metric", "value", "rubric_ref", "evidence_refs", "assessed_by"):
                if field not in item:
                    errors.append(f"qualitative_metrics[{index}] 缺少 {field}")
            if item.get("assessed_by") != "human":
                errors.append(f"qualitative_metrics[{index}].assessed_by 必须为 human")
    elif artifact_type == "review":
        snapshots = require_list(payload.get("snapshot_artifact_ids"), "payload.snapshot_artifact_ids", errors)
        if not snapshots:
            errors.append("review 至少引用一个 metrics_snapshot")
        for index, hypothesis in enumerate(require_list(payload.get("hypotheses"), "payload.hypotheses", errors)):
            if not isinstance(hypothesis, dict):
                errors.append(f"hypotheses[{index}] 必须是 object")
                continue
            for field in ("hypothesis_id", "statement", "evidence_refs", "alternative_explanations", "confidence"):
                if field not in hypothesis:
                    errors.append(f"hypotheses[{index}] 缺少 {field}")
            if hypothesis.get("confidence") not in {"low", "medium", "high"}:
                errors.append(f"hypotheses[{index}].confidence 无效")
        for index, intervention in enumerate(require_list(payload.get("recommended_interventions"), "payload.recommended_interventions", errors)):
            if not isinstance(intervention, dict) or intervention.get("type") not in {"topic", "creative", "distribution", "positioning", "strategy"}:
                errors.append(f"recommended_interventions[{index}].type 无效")
        lifecycle = require_object(payload.get("lifecycle_assessment"), "payload.lifecycle_assessment", errors)
        if lifecycle.get("current_stage") not in LIFECYCLE_STAGES:
            errors.append("lifecycle_assessment.current_stage 无效")
        proposed_stage = lifecycle.get("proposed_stage")
        if proposed_stage is not None and proposed_stage not in LIFECYCLE_STAGES:
            errors.append("lifecycle_assessment.proposed_stage 无效")
        if lifecycle.get("confidence") not in {"low", "medium", "high"}:
            errors.append("lifecycle_assessment.confidence 无效")
        if lifecycle.get("requires_human_confirmation") is not True:
            errors.append("lifecycle_assessment.requires_human_confirmation 必须为 true")
        require_list(lifecycle.get("evidence_refs"), "lifecycle_assessment.evidence_refs", errors)
        require_list(
            lifecycle.get("alternative_explanations"),
            "lifecycle_assessment.alternative_explanations",
            errors,
        )
        persona_validation = require_object(payload.get("persona_validation"), "payload.persona_validation", errors)
        if persona_validation.get("persona_mode") not in {"assumed", "validated"}:
            errors.append("persona_validation.persona_mode 无效")
        if not isinstance(persona_validation.get("revision_recommended"), bool):
            errors.append("persona_validation.revision_recommended 必须是 boolean")
        require_list(persona_validation.get("hypothesis_results"), "persona_validation.hypothesis_results", errors)
        require_list(persona_validation.get("evidence_refs"), "persona_validation.evidence_refs", errors)
        require_list(payload.get("trust_observations"), "payload.trust_observations", errors)
        require_list(payload.get("long_tail_observations"), "payload.long_tail_observations", errors)
    elif artifact_type == "experiment":
        intervention = payload.get("intervention_type")
        if intervention not in {"topic", "creative", "distribution", "positioning", "strategy"}:
            errors.append("experiment.intervention_type 无效")
        if intervention == "positioning" and not payload.get("persona_change_proposal"):
            errors.append("positioning 实验必须包含 persona_change_proposal")
        if intervention == "strategy" and not payload.get("strategy_change_proposal"):
            errors.append("strategy 实验必须包含 strategy_change_proposal")
        for field in ("hypothesis", "independent_variable", "control", "observation_window", "sample_size_plan", "stop_rule"):
            if not isinstance(payload.get(field), str) or not payload.get(field).strip():
                errors.append(f"experiment.{field} 不能为空")

    errors.extend(optional_json_schema_errors(artifact))
    return errors


def find_workspace(start: Path) -> Path:
    start = start.resolve()
    candidates: Iterable[Path] = (start, *start.parents) if start.is_dir() else (start.parent, *start.parents)
    for candidate in candidates:
        if (candidate / "workspace.json").is_file():
            return candidate
    raise WorkflowError(f"无法从 {start} 定位 workspace.json")


def append_audit(root: Path, event: dict[str, Any]) -> None:
    audit_path = root / "audit" / "events.ndjson"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def audit_event(
    root: Path,
    artifact: dict[str, Any],
    actor: str,
    actor_type: str,
    event_type: str,
    reason: str,
    before_status: str | None = None,
    after_status: str | None = None,
) -> None:
    append_audit(
        root,
        {
            "event_id": new_id("event"),
            "at": now_iso(),
            "actor_id": actor,
            "actor_type": actor_type,
            "event_type": event_type,
            "artifact_id": artifact.get("artifact_id"),
            "account_id": artifact.get("account_id"),
            "run_id": artifact.get("run_id"),
            "before_status": before_status,
            "after_status": after_status,
            "payload_sha256": payload_hash(artifact),
            "reason": reason,
        },
    )


def command_init(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    if not ACCOUNT_RE.fullmatch(args.account_id):
        raise WorkflowError("account-id 只能包含小写字母、数字、下划线和连字符，长度 2-64")
    root.mkdir(parents=True, exist_ok=True)
    workspace_path = root / "workspace.json"
    if workspace_path.exists():
        workspace = load_json(workspace_path)
        if workspace.get("schema_version") != SCHEMA_VERSION:
            raise WorkflowError("现有 workspace.json 版本不兼容")
    else:
        workspace = {
            "schema_version": SCHEMA_VERSION,
            "workspace_id": new_id("workspace"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "account_ids": [],
        }
    account_path = root / "accounts" / args.account_id / "account.json"
    if account_path.exists():
        raise WorkflowError(f"账号已存在：{args.account_id}")
    account = {
        "schema_version": SCHEMA_VERSION,
        "account_id": args.account_id,
        "display_name": args.display_name,
        "platform": "xiaohongshu",
        "created_at": now_iso(),
        "status": "active",
    }
    atomic_write_json(account_path, account)
    if args.account_id not in workspace["account_ids"]:
        workspace["account_ids"].append(args.account_id)
        workspace["account_ids"].sort()
    workspace["updated_at"] = now_iso()
    atomic_write_json(workspace_path, workspace)
    for relative in ("runs", "artifacts", "assets", "renders", "audit"):
        (root / relative).mkdir(exist_ok=True)
    audit_event(root, {"artifact_id": None, "account_id": args.account_id, "run_id": None, "payload": account}, args.actor, "human", "account_initialized", "创建账号隔离工作区")
    print(account_path)


def command_new_run(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    workspace = load_json(root / "workspace.json")
    if args.account_id not in workspace.get("account_ids", []):
        raise WorkflowError(f"工作区不存在账号：{args.account_id}")
    run_type = args.run_type
    strategy: dict[str, Any] | None = None
    persona: dict[str, Any] | None = None
    artifact_paths: dict[str, str] = {}

    def load_account_reference(raw_path: str | None, expected_type: str, role: str) -> dict[str, Any] | None:
        if not raw_path:
            return None
        candidate = Path(raw_path)
        path = (candidate if candidate.is_absolute() else root / candidate).resolve()
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise WorkflowError(f"{role} 必须位于当前工作区") from exc
        artifact = load_json(path)
        artifact_errors = validate_artifact(artifact)
        if artifact_errors:
            raise WorkflowError(f"{role} 未通过校验：" + "; ".join(artifact_errors))
        if artifact.get("artifact_type") != expected_type:
            raise WorkflowError(f"{role} 必须指向 {expected_type}")
        if artifact.get("account_id") != args.account_id:
            raise WorkflowError(f"{role} 与本轮 account_id 不一致")
        if artifact.get("status") != "approved":
            raise WorkflowError(f"{role} 必须是 approved，不能引用 {artifact.get('status')} revision")
        if not effective_approval(artifact, "G1"):
            raise WorkflowError(f"{role} 必须具有当前 payload 对应的有效 G1 批准")
        artifact_paths[role] = str(relative)
        return artifact

    strategy = load_account_reference(args.strategy, "account_strategy", "account_strategy")
    persona = load_account_reference(args.persona, "persona", "persona")
    operational_types = RUN_TYPES - {"full_cycle", "strategy_review"}
    if run_type in operational_types and (strategy is None or persona is None):
        raise WorkflowError(f"{run_type} run 必须显式提供已批准的 --strategy 和 --persona")
    if persona and strategy and persona.get("payload", {}).get("strategy_artifact_id") != strategy.get("artifact_id"):
        raise WorkflowError("persona.strategy_artifact_id 与 --strategy 不一致")
    if run_type == "trial_content" and persona and persona.get("payload", {}).get("mode") != "assumed":
        raise WorkflowError("trial_content 必须使用 mode=assumed 的试运营 persona")
    if run_type == "trial_content" and args.content_sequence_no is None:
        raise WorkflowError("trial_content 必须提供 --content-sequence-no")

    run_id = new_id("run")
    timestamp = now_iso()
    strategy_measurement = strategy.get("payload", {}).get("measurement_policy", {}) if strategy else {}
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "run_manifest",
        "artifact_id": new_id("run_manifest"),
        "account_id": args.account_id,
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "status": "review_required",
        "provenance": [
            {
                "source_id": new_id("source"),
                "kind": "user_input",
                "captured_at": timestamp,
                "summary": f"由 {args.actor} 发起本轮目标",
            }
        ],
        "approvals": [],
        "payload": {
            "objective": args.objective,
            "run_type": run_type,
            "strategy_artifact_id": strategy.get("artifact_id") if strategy else None,
            "persona_artifact_id": persona.get("artifact_id") if persona else None,
            "content_sequence_no": args.content_sequence_no,
            "current_stage": "scope",
            "runtime_capabilities": default_runtime_capabilities(timestamp, args.runtime_name),
            "data_scope": {
                "allowed_sources": [],
                "external_processing": [],
                "personal_data": [],
            },
            "measurement_plan": {
                "snapshot_windows": [],
                "trust_metrics": list(strategy_measurement.get("trust_metrics", [])),
                "long_tail_checkpoints_days": list(strategy_measurement.get("long_tail_checkpoints_days", [])),
                "qualitative_rubric_refs": list(strategy_measurement.get("qualitative_rubric_refs", [])),
            },
            "artifact_paths": artifact_paths,
            "gate_status": {gate: "pending" for gate in sorted(GATES)},
            "errors": [],
        },
    }
    if strategy is not None and persona is not None:
        artifact["payload"]["gate_status"]["G1"] = "approved"
    errors = validate_artifact(artifact)
    if errors:
        raise WorkflowError("无法创建 run：" + "; ".join(errors))
    path = root / "runs" / run_id / "run.json"
    atomic_write_json(path, artifact)
    audit_event(root, artifact, args.actor, "human", "run_created", args.objective, None, artifact["status"])
    print(path)


def command_validate(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    errors = validate_artifact(load_json(path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise WorkflowError(f"校验失败，共 {len(errors)} 项")
    print(f"PASS: {path}")


def command_validate_workspace(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    load_json(root / "workspace.json")
    files = sorted((root / "runs").glob("**/*.json")) + sorted((root / "artifacts").glob("**/*.json"))
    failed = 0
    for path in files:
        errors = validate_artifact(load_json(path))
        if errors:
            failed += 1
            print(f"FAIL: {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS: {path}")
    if failed:
        raise WorkflowError(f"工作区有 {failed} 个不合法 artifact")
    print(f"PASS: {len(files)} artifacts")


def command_approve(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    artifact = load_json(path)
    artifact_type = artifact.get("artifact_type")
    if args.gate not in GATE_BY_TYPE.get(artifact_type, set()):
        raise WorkflowError(f"{artifact_type} 不接受门禁 {args.gate}")
    if args.decision == "approved" and args.gate == "G2" and not artifact.get("payload", {}).get("selected_topic_ids"):
        raise WorkflowError("G2 批准前必须明确 selected_topic_ids")
    if args.decision == "approved" and args.gate == "G1" and artifact_type == "account_strategy":
        strategy_payload = artifact.get("payload", {})
        if not strategy_payload.get("stage_evidence"):
            raise WorkflowError("账号战略 G1 批准前至少需要一条 stage_evidence")
        if not strategy_payload.get("content_objectives"):
            raise WorkflowError("账号战略 G1 批准前至少需要一个 content_objective")
    if args.decision == "approved" and args.gate == "G4":
        publication_payload = artifact.get("payload", {})
        policy_check = publication_payload.get("policy_check")
        if not isinstance(policy_check, dict):
            raise WorkflowError("G4 批准前必须完成发布 policy_check")
        if policy_check.get("action") != "publish":
            raise WorkflowError("G4 只能接受 action=publish 的 policy_check")
        if policy_check.get("strategy_artifact_id") != publication_payload.get("strategy_artifact_id"):
            raise WorkflowError("policy_check.strategy_artifact_id 与 publication 不一致")
        if policy_check.get("decision") == "blocked":
            raise WorkflowError("发布策略检查结果为 blocked，不能批准 G4")
        if policy_check.get("decision") not in {"allowed", "needs_human"}:
            raise WorkflowError("G4 批准前 policy_check.decision 必须是 allowed 或 needs_human")
        if policy_check.get("decision") == "needs_human" and not args.notes:
            raise WorkflowError("policy_check=needs_human 时，G4 必须用 --notes 记录人工例外理由")
        root = find_workspace(path)
        inventory_id = publication_payload.get("inventory_item_artifact_id")
        inventory_path = root / "artifacts" / artifact["account_id"] / "inventory_item" / f"{inventory_id}.json"
        inventory = load_json(inventory_path)
        inventory_errors = validate_artifact(inventory)
        if inventory_errors:
            raise WorkflowError("G4 关联的 inventory_item 未通过校验：" + "; ".join(inventory_errors))
        if inventory.get("status") not in {"ready", "scheduled"}:
            raise WorkflowError("G4 关联的 inventory_item 必须是 ready 或 scheduled")
        inventory_payload = inventory.get("payload", {})
        if inventory_payload.get("strategy_artifact_id") != publication_payload.get("strategy_artifact_id"):
            raise WorkflowError("publication 与 inventory_item 的战略引用不一致")
        if inventory_payload.get("content_artifact_id") != publication_payload.get("content_artifact_id"):
            raise WorkflowError("publication 与 inventory_item 的内容引用不一致")
        content_relative = inventory_payload.get("content_artifact_path")
        if not content_relative:
            raise WorkflowError("G4 关联的 inventory_item 缺少 content_artifact_path")
        content_path = (root / content_relative).resolve()
        try:
            content_path.relative_to(root)
        except ValueError as exc:
            raise WorkflowError("inventory_item 的 content_artifact_path 越出工作区") from exc
        content = load_json(content_path)
        content_errors = validate_artifact(content)
        if content_errors:
            raise WorkflowError("G4 关联的 content 未通过校验：" + "; ".join(content_errors))
        if content.get("artifact_id") != publication_payload.get("content_artifact_id"):
            raise WorkflowError("publication.content_artifact_id 与本地 content 不一致")
        if not effective_approval(content, "G3"):
            raise WorkflowError("G4 前需要关联 content 的当前有效 G3")
    if args.decision == "approved" and args.gate == "G0":
        payload = artifact.get("payload", {})
        data_scope = payload.get("data_scope", {})
        if not data_scope.get("allowed_sources"):
            raise WorkflowError("G0 批准前必须明确至少一个 allowed_sources")
        runtime = payload.get("runtime_capabilities", {})
        if runtime.get("discovery_status") not in {"partial", "complete"}:
            raise WorkflowError("G0 批准前必须完成或部分完成运行时能力发现")
        if runtime.get("capability_source") == "unknown":
            raise WorkflowError("G0 批准前必须记录能力信息来源")
        mode = runtime.get("execution_mode")
        if mode not in {"full", "assisted", "document_only"}:
            raise WorkflowError("G0 批准前必须明确 execution_mode")
        capabilities = runtime.get("capabilities", {})
        if capabilities.get("human_approval", {}).get("status") != "available":
            raise WorkflowError("G0 不能在 human_approval 能力不可用时批准")
        if mode in {"full", "assisted"} and capabilities.get("local_json_storage", {}).get("status") != "available":
            raise WorkflowError(f"{mode} 模式需要可用的 local_json_storage")
        if mode == "full" and capabilities.get("append_audit_log", {}).get("status") != "available":
            raise WorkflowError("full 模式需要可用的 append_audit_log")
        if mode == "document_only" and not runtime.get("limitations"):
            raise WorkflowError("document_only 模式必须明确记录自动化限制")
        declared_ids = {
            entry.get("capability_id")
            for entry in capabilities.values()
            if isinstance(entry, dict) and entry.get("capability_id")
        }
        unknown_processing = [
            entry.get("capability_id")
            for entry in data_scope.get("external_processing", [])
            if isinstance(entry, dict) and entry.get("capability_id") not in declared_ids
        ]
        if unknown_processing:
            raise WorkflowError(
                "external_processing 引用了未在能力快照中声明的 capability_id："
                + ", ".join(str(item) for item in unknown_processing)
            )
    if args.decision == "approved" and args.gate == "G5":
        run_payload = artifact.get("payload", {})
        data_scope = run_payload.get("data_scope", {})
        if not data_scope.get("allowed_sources"):
            raise WorkflowError("G5 批准前必须明确至少一个 allowed_sources")
        measurement_plan = run_payload.get("measurement_plan", {})
        if not measurement_plan.get("snapshot_windows"):
            raise WorkflowError("G5 批准前必须明确至少一个 snapshot_window")
        if not measurement_plan.get("trust_metrics"):
            raise WorkflowError("G5 批准前必须明确至少一个 trust_metric")
    before = artifact.get("status")
    decision = {
        "gate": args.gate,
        "decision": args.decision,
        "actor_type": "human",
        "actor_id": args.actor,
        "at": now_iso(),
        "payload_sha256": payload_hash(artifact, args.gate),
        "notes": args.notes or "",
    }
    artifact.setdefault("approvals", []).append(decision)
    if artifact_type == "run_manifest":
        artifact["payload"]["gate_status"][args.gate] = args.decision
        if args.gate == "G0" and args.decision == "approved":
            run_type = artifact["payload"].get("run_type")
            artifact["payload"]["current_stage"] = {
                "full_cycle": "strategy",
                "strategy_review": "strategy",
                "trial_content": "topics",
                "content_production": "topics",
                "batch_creation": "topics",
                "publication": "publication",
                "measurement": "measurement",
                "long_tail_review": "measurement",
            }[run_type]
            artifact["status"] = "approved"
    elif artifact_type == "publication":
        if args.decision == "approved":
            if artifact["payload"].get("state") != "review_required":
                raise WorkflowError("只有 review_required 的 publication 可以批准 G4")
            artifact["payload"]["state"] = "approved"
            artifact["status"] = "approved"
        elif args.decision == "revoked":
            if artifact["payload"].get("state") != "approved":
                raise WorkflowError("只有尚未发布且已批准的 publication 可以撤销 G4")
            artifact["payload"]["state"] = "review_required"
            artifact["status"] = "review_required"
        else:
            if artifact["payload"].get("state") != "review_required":
                raise WorkflowError("只有 review_required 的 publication 可以拒绝 G4")
            artifact["status"] = "review_required"
    else:
        if args.decision == "approved":
            artifact["status"] = "approved"
            if artifact_type == "experiment":
                artifact["payload"]["state"] = "approved"
        elif args.decision == "rejected":
            artifact["status"] = "rejected"
        else:
            artifact["status"] = "review_required"
    artifact["updated_at"] = now_iso()
    errors = validate_artifact(artifact)
    if errors:
        raise WorkflowError("批准后 artifact 不合法：" + "; ".join(errors))
    atomic_write_json(path, artifact)
    root = find_workspace(path)
    audit_event(root, artifact, args.actor, "human", f"gate_{args.decision}", args.notes or args.gate, before, artifact["status"])
    print(f"{args.decision}: {args.gate} {path}")


def command_transition(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    artifact = load_json(path)
    if artifact.get("artifact_type") != "publication":
        raise WorkflowError("transition 当前只用于 publication")
    payload = artifact["payload"]
    current = payload.get("state")
    target = args.to
    if target not in PUBLICATION_TRANSITIONS.get(current, set()):
        raise WorkflowError(f"不允许的发布状态变化：{current} -> {target}")
    if current == "approved" and target == "publishing" and not effective_approval(artifact, "G4"):
        raise WorkflowError("进入 publishing 前需要当前 payload 对应的有效 G4 批准")
    if current == "unknown" and args.actor_type != "human":
        raise WorkflowError("unknown 只能由人工核对远端状态后解决")
    if current == "failed" and args.actor_type != "human":
        raise WorkflowError("failed 只能由人工决定是否回到 review_required")
    if target == "published" and not (args.remote_id or args.remote_url or payload.get("remote_id") or payload.get("remote_url")):
        raise WorkflowError("published 状态必须提供 remote-id 或 remote-url")

    before = artifact["status"]
    timestamp = now_iso()
    if target == "publishing":
        payload.setdefault("attempts", []).append(
            {
                "attempt_id": new_id("attempt"),
                "started_at": timestamp,
                "ended_at": None,
                "status": "publishing",
                "actor_id": args.actor,
                "error": None,
            }
        )
    elif current == "publishing" and payload.get("attempts"):
        payload["attempts"][-1].update({"ended_at": timestamp, "status": target, "error": args.error})
    if target == "published":
        payload["remote_id"] = args.remote_id or payload.get("remote_id")
        payload["remote_url"] = args.remote_url or payload.get("remote_url")
        payload["published_at"] = timestamp
        payload["last_error"] = None
    elif target in {"failed", "unknown"}:
        payload["last_error"] = args.error or "未提供错误详情"
    elif current == "failed" and target == "review_required":
        artifact.setdefault("approvals", []).append(
            {
                "gate": "G4",
                "decision": "revoked",
                "actor_type": "human",
                "actor_id": args.actor,
                "at": timestamp,
                "payload_sha256": payload_hash(artifact, "G4"),
                "notes": "失败后重新审阅，旧发布批准失效",
            }
        )
    payload["state"] = target
    artifact["status"] = target
    artifact["updated_at"] = timestamp
    errors = validate_artifact(artifact)
    if errors:
        raise WorkflowError("状态变化后 artifact 不合法：" + "; ".join(errors))
    atomic_write_json(path, artifact)
    root = find_workspace(path)
    audit_event(root, artifact, args.actor, args.actor_type, "publication_transition", args.reason, before, target)
    print(f"{current} -> {target}: {path}")


def command_register(args: argparse.Namespace) -> None:
    run_path = Path(args.run).resolve()
    artifact_path = Path(args.artifact).resolve()
    run = load_json(run_path)
    artifact = load_json(artifact_path)
    if run.get("artifact_type") != "run_manifest":
        raise WorkflowError("--run 必须指向 run_manifest")
    artifact_errors = validate_artifact(artifact)
    if artifact_errors:
        raise WorkflowError("待登记 artifact 未通过校验：" + "; ".join(artifact_errors))
    if run.get("account_id") != artifact.get("account_id") or run.get("run_id") != artifact.get("run_id"):
        raise WorkflowError("run 与 artifact 的 account_id/run_id 不一致")
    rule = REGISTER_RULES.get(args.role)
    if not rule:
        raise WorkflowError(f"不支持的登记角色：{args.role}")
    expected_type, required_gate, next_stage = rule
    if artifact.get("artifact_type") != expected_type:
        raise WorkflowError(f"角色 {args.role} 需要 {expected_type}，实际为 {artifact.get('artifact_type')}")
    if required_gate and not effective_approval(artifact, required_gate):
        raise WorkflowError(f"登记 {args.role} 前需要有效 {required_gate}")
    if expected_type == "publication" and artifact.get("status") != "published":
        raise WorkflowError("publication 只有 published 后才能登记为完成")
    if expected_type == "inventory_item" and artifact.get("status") not in {"ready", "scheduled"}:
        raise WorkflowError("inventory_item 必须达到 ready 或 scheduled 才能登记并进入发布阶段")
    if expected_type in {"metrics_snapshot", "review"} and artifact.get("status") != "ready":
        raise WorkflowError(f"{expected_type} 必须是 ready 状态")
    if expected_type in {"metrics_snapshot", "review"} and not effective_approval(run, "G5"):
        raise WorkflowError(f"登记 {expected_type} 前 run manifest 需要有效 G5")
    root = find_workspace(run_path)
    try:
        relative = artifact_path.relative_to(root)
    except ValueError as exc:
        raise WorkflowError("artifact 必须位于同一工作区") from exc
    run["payload"]["artifact_paths"][args.role] = str(relative)
    if expected_type == "account_strategy":
        run["payload"]["strategy_artifact_id"] = artifact.get("artifact_id")
    if expected_type == "persona":
        strategy_id = run["payload"].get("strategy_artifact_id")
        if not strategy_id:
            raise WorkflowError("登记 persona 前必须先登记或引用 account_strategy")
        if artifact.get("payload", {}).get("strategy_artifact_id") != strategy_id:
            raise WorkflowError("persona.strategy_artifact_id 与 run 的账号战略不一致")
        run["payload"]["persona_artifact_id"] = artifact.get("artifact_id")
    if required_gate:
        run["payload"]["gate_status"][required_gate] = "approved"
    run["payload"]["current_stage"] = next_stage
    run["updated_at"] = now_iso()
    run_errors = validate_artifact(run)
    if run_errors:
        raise WorkflowError("登记后 run manifest 不合法：" + "; ".join(run_errors))
    superseded: dict[str, Any] | None = None
    superseded_path: Path | None = None
    supersedes_id = artifact.get("payload", {}).get("supersedes_artifact_id")
    if expected_type in {"account_strategy", "persona"} and supersedes_id:
        superseded_path = root / "artifacts" / artifact["account_id"] / expected_type / f"{supersedes_id}.json"
        superseded = load_json(superseded_path)
        if superseded.get("artifact_type") != expected_type or superseded.get("artifact_id") != supersedes_id:
            raise WorkflowError("supersedes_artifact_id 未解析到正确的旧 artifact")
        if superseded.get("account_id") != artifact.get("account_id"):
            raise WorkflowError("新旧 revision 的 account_id 不一致")
        old_status = superseded.get("status")
        superseded["status"] = "superseded"
        superseded["updated_at"] = now_iso()
        superseded_errors = validate_artifact(superseded)
        if superseded_errors:
            raise WorkflowError("旧 revision 无法标记 superseded：" + "; ".join(superseded_errors))
    atomic_write_json(run_path, run)
    if superseded is not None and superseded_path is not None:
        atomic_write_json(superseded_path, superseded)
        audit_event(root, superseded, args.actor, args.actor_type, "artifact_superseded", artifact["artifact_id"], old_status, "superseded")
    audit_event(root, artifact, args.actor, args.actor_type, "artifact_registered", args.role)
    print(relative)


def markdown_render(artifact: dict[str, Any]) -> str:
    lines = [
        f"# {artifact.get('artifact_type')} · {artifact.get('artifact_id')}",
        "",
        "> 本文件由 JSON artifact 确定性生成，仅用于人工审阅。JSON 才是机器事实源。",
        "",
        "| 字段 | 值 |",
        "|---|---|",
    ]
    for field in ("schema_version", "account_id", "run_id", "status", "created_at", "updated_at"):
        value = str(artifact.get(field, "")).replace("|", "\\|")
        lines.append(f"| {field} | {value} |")
    lines.extend(["", "## Payload", "", "```json", json.dumps(artifact.get("payload"), ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Provenance", ""])
    if artifact.get("provenance"):
        for source in artifact["provenance"]:
            lines.append(f"- `{source.get('source_id')}` · {source.get('kind')} · {source.get('summary')}")
    else:
        lines.append("- 无")
    lines.extend(["", "## Approvals", ""])
    if artifact.get("approvals"):
        lines.extend(["| Gate | Decision | Actor | At | Payload hash |", "|---|---|---|---|---|"])
        for approval in artifact["approvals"]:
            lines.append(
                f"| {approval.get('gate')} | {approval.get('decision')} | {approval.get('actor_id')} | "
                f"{approval.get('at')} | `{approval.get('payload_sha256', '')[:12]}…` |"
            )
    else:
        lines.append("尚无人工决定。")
    return "\n".join(lines) + "\n"


def html_render(artifact: dict[str, Any]) -> str:
    title = html.escape(f"{artifact.get('artifact_type')} · {artifact.get('artifact_id')}")
    payload = html.escape(json.dumps(artifact.get("payload"), ensure_ascii=False, indent=2))
    metadata = "".join(
        f"<tr><th>{html.escape(field)}</th><td>{html.escape(str(artifact.get(field, '')))}</td></tr>"
        for field in ("schema_version", "account_id", "run_id", "status", "created_at", "updated_at")
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:960px;margin:40px auto;padding:0 20px;color:#1f2937;background:#f8fafc}}
main{{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:28px;box-shadow:0 8px 30px rgba(15,23,42,.06)}}
table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;border-bottom:1px solid #e5e7eb;padding:10px;vertical-align:top}}th{{width:180px}}
pre{{white-space:pre-wrap;word-break:break-word;background:#0f172a;color:#e2e8f0;padding:18px;border-radius:12px;overflow:auto}}
.notice{{padding:12px 16px;background:#eff6ff;border-left:4px solid #2563eb;border-radius:8px}}
</style></head><body><main><h1>{title}</h1><p class="notice">本页由 JSON artifact 确定性生成，仅用于人工审阅。</p>
<table>{metadata}</table><h2>Payload</h2><pre>{payload}</pre></main></body></html>"""


def command_render(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    artifact = load_json(path)
    output = Path(args.output).resolve()
    rendered = markdown_render(artifact) if args.format == "markdown" else html_render(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="XHS Workflow V2.2 contract and state CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="初始化工作区或添加账号")
    init.add_argument("--root", required=True)
    init.add_argument("--account-id", required=True)
    init.add_argument("--display-name", required=True)
    init.add_argument("--actor", default="content-owner")
    init.set_defaults(func=command_init)

    new_run = sub.add_parser("new-run", help="创建本轮 manifest")
    new_run.add_argument("--root", required=True)
    new_run.add_argument("--account-id", required=True)
    new_run.add_argument("--objective", required=True)
    new_run.add_argument("--actor", required=True)
    new_run.add_argument("--run-type", choices=sorted(RUN_TYPES), default="full_cycle")
    new_run.add_argument("--strategy", help="工作区内已批准的 account_strategy JSON 绝对或相对路径")
    new_run.add_argument("--persona", help="工作区内已批准的 persona JSON 绝对或相对路径")
    new_run.add_argument("--content-sequence-no", type=int)
    new_run.add_argument("--runtime-name", help="可选的当前 Agent 运行时名称；不确定时留空")
    new_run.set_defaults(func=command_new_run)

    validate = sub.add_parser("validate", help="校验单个 artifact")
    validate.add_argument("path")
    validate.set_defaults(func=command_validate)

    validate_workspace = sub.add_parser("validate-workspace", help="校验整个工作区")
    validate_workspace.add_argument("--root", required=True)
    validate_workspace.set_defaults(func=command_validate_workspace)

    approve = sub.add_parser("approve", help="记录人工门禁决定")
    approve.add_argument("path")
    approve.add_argument("--gate", required=True, choices=sorted(GATES))
    approve.add_argument("--actor", required=True)
    approve.add_argument("--decision", choices=["approved", "rejected", "revoked"], required=True)
    approve.add_argument("--notes")
    approve.set_defaults(func=command_approve)

    transition = sub.add_parser("transition", help="改变 publication 状态")
    transition.add_argument("path")
    transition.add_argument("--to", required=True, choices=sorted(PUBLICATION_TRANSITIONS))
    transition.add_argument("--actor", required=True)
    transition.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    transition.add_argument("--reason", required=True)
    transition.add_argument("--remote-id")
    transition.add_argument("--remote-url")
    transition.add_argument("--error")
    transition.set_defaults(func=command_transition)

    register = sub.add_parser("register", help="把 artifact 路径登记到 run manifest")
    register.add_argument("--run", required=True)
    register.add_argument("--artifact", required=True)
    register.add_argument("--role", required=True)
    register.add_argument("--actor", required=True)
    register.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    register.set_defaults(func=command_register)

    render = sub.add_parser("render", help="从 JSON 生成审阅视图")
    render.add_argument("path")
    render.add_argument("--format", choices=["markdown", "html"], required=True)
    render.add_argument("--output", required=True)
    render.set_defaults(func=command_render)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
