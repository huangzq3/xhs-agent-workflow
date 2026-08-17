#!/usr/bin/env python3
"""Deterministic account-strategy, inventory, publishing-policy, and long-tail operations."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import workflow_cli as core


def parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise core.WorkflowError(f"不是有效的 ISO 8601 时间：{value}") from exc


def workspace_relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError as exc:
        raise core.WorkflowError(f"文件不在当前工作区：{path}") from exc


def load_typed(path: Path, expected_type: str) -> dict[str, Any]:
    artifact = core.load_json(path)
    errors = core.validate_artifact(artifact)
    if errors:
        raise core.WorkflowError(f"{path} 未通过校验：" + "; ".join(errors))
    if artifact.get("artifact_type") != expected_type:
        raise core.WorkflowError(f"{path} 必须是 {expected_type}")
    return artifact


def require_same_account(*artifacts: dict[str, Any]) -> str:
    account_ids = {item.get("account_id") for item in artifacts}
    if len(account_ids) != 1:
        raise core.WorkflowError("所有 artifact 必须属于同一 account_id")
    return str(next(iter(account_ids)))


def require_effective_g1(artifact: dict[str, Any], label: str) -> None:
    if artifact.get("status") != "approved":
        raise core.WorkflowError(f"{label} 必须是 approved，不能使用 {artifact.get('status')} revision")
    if not core.effective_approval(artifact, "G1"):
        raise core.WorkflowError(f"{label} 必须具有当前 payload 对应的有效 G1 批准")


def artifact_path(root: Path, account_id: str, artifact_type: str, artifact_id: str) -> Path:
    return root / "artifacts" / account_id / artifact_type / f"{artifact_id}.json"


def command_new_strategy(args: argparse.Namespace) -> None:
    run_path = Path(args.run).resolve()
    run = load_typed(run_path, "run_manifest")
    if not core.effective_approval(run, "G0"):
        raise core.WorkflowError("创建账号战略前需要 run manifest 的有效 G0 批准")
    if run.get("payload", {}).get("current_stage") != "strategy":
        raise core.WorkflowError("只有 current_stage=strategy 的 run 可以创建账号战略")
    root = core.find_workspace(run_path)
    supersedes: dict[str, Any] | None = None
    if args.supersedes:
        supersedes = load_typed(Path(args.supersedes).resolve(), "account_strategy")
        require_same_account(run, supersedes)
        require_effective_g1(supersedes, "被修订的账号战略")
    timestamp = core.now_iso()
    strategy_id = core.new_id("account_strategy")
    old_payload = supersedes.get("payload", {}) if supersedes else {}
    artifact = {
        "schema_version": core.SCHEMA_VERSION,
        "artifact_type": "account_strategy",
        "artifact_id": strategy_id,
        "account_id": run["account_id"],
        "run_id": run["run_id"],
        "created_at": timestamp,
        "updated_at": timestamp,
        "status": "review_required",
        "provenance": [
            {
                "source_id": core.new_id("source"),
                "kind": "derived" if supersedes else "user_input",
                "captured_at": timestamp,
                "summary": "创建账号战略修订草案" if supersedes else "创建首版账号战略草案",
            }
        ],
        "approvals": [],
        "payload": {
            "revision": int(old_payload.get("revision", 0)) + 1,
            "supersedes_artifact_id": supersedes.get("artifact_id") if supersedes else None,
            "lifecycle_stage": args.lifecycle_stage,
            "stage_confidence": args.stage_confidence,
            "persona_mode": args.persona_mode,
            "play_mode": args.play_mode,
            "transition": {
                "from_stage": old_payload.get("lifecycle_stage") if supersedes else None,
                "rationale": "",
                "evidence_refs": [],
                "alternative_explanations": [],
            },
            "stage_evidence": [],
            "content_objectives": [],
            "publishing_policy": {
                "modification_policy": "human_review_required",
                "deletion_policy": "human_review_required",
                "minimum_observation_hours": None,
                "same_topic_cooldown_hours": None,
                "breakout_hold_hours": None,
                "threshold_basis": "unset",
                "exceptions_require_human": True,
            },
            "inventory_policy": {
                "target_coverage_days": None,
                "target_ready_items": None,
                "threshold_basis": "unset",
            },
            "measurement_policy": {
                "trust_metrics": [],
                "long_tail_checkpoints_days": [],
                "qualitative_rubric_refs": [],
            },
            "experience_seed_refs": [],
            "limitations": [],
        },
    }
    errors = core.validate_artifact(artifact)
    if errors:
        raise core.WorkflowError("无法创建账号战略草案：" + "; ".join(errors))
    path = artifact_path(root, run["account_id"], "account_strategy", strategy_id)
    core.atomic_write_json(path, artifact)
    core.audit_event(root, artifact, args.actor, "human", "account_strategy_created", "建立待填充、待 G1 批准的账号战略草案")
    print(path)


def command_new_inventory(args: argparse.Namespace) -> None:
    run_path = Path(args.run).resolve()
    strategy_path = Path(args.strategy).resolve()
    persona_path = Path(args.persona).resolve()
    run = load_typed(run_path, "run_manifest")
    strategy = load_typed(strategy_path, "account_strategy")
    persona = load_typed(persona_path, "persona")
    account_id = require_same_account(run, strategy, persona)
    if not core.effective_approval(run, "G0"):
        raise core.WorkflowError("创建库存前需要 run manifest 的有效 G0 批准")
    require_effective_g1(strategy, "账号战略")
    require_effective_g1(persona, "画像")
    if persona.get("payload", {}).get("strategy_artifact_id") != strategy.get("artifact_id"):
        raise core.WorkflowError("persona.strategy_artifact_id 与账号战略不一致")
    root = core.find_workspace(run_path)
    workspace_relative(root, strategy_path)
    workspace_relative(root, persona_path)
    timestamp = core.now_iso()
    inventory_id = core.new_id("inventory_item")
    artifact = {
        "schema_version": core.SCHEMA_VERSION,
        "artifact_type": "inventory_item",
        "artifact_id": inventory_id,
        "account_id": account_id,
        "run_id": run["run_id"],
        "created_at": timestamp,
        "updated_at": timestamp,
        "status": "idea",
        "provenance": [{"source_id": core.new_id("source"), "kind": "user_input", "captured_at": timestamp, "summary": f"由 {args.actor} 创建内容库存项"}],
        "approvals": [],
        "payload": {
            "revision": 1,
            "strategy_artifact_id": strategy["artifact_id"],
            "persona_artifact_id": persona["artifact_id"],
            "topic_report_artifact_id": args.topic_report_id,
            "topic_id": args.topic_id,
            "content_artifact_id": None,
            "content_artifact_path": None,
            "publication_artifact_id": None,
            "publication_artifact_path": None,
            "content_sequence_no": args.content_sequence_no,
            "content_objective": args.objective,
            "format": args.format,
            "working_title": args.working_title,
            "same_topic_key": args.same_topic_key,
            "state": "idea",
            "planned_publish_at": None,
            "hold_reason": None,
            "policy_check": None,
            "measurement_schedule": [],
            "history": [{"from": None, "to": "idea", "at": timestamp, "actor_id": args.actor, "actor_type": args.actor_type, "reason": "创建库存项"}],
        },
    }
    errors = core.validate_artifact(artifact)
    if errors:
        raise core.WorkflowError("无法创建库存项：" + "; ".join(errors))
    path = artifact_path(root, account_id, "inventory_item", inventory_id)
    core.atomic_write_json(path, artifact)
    core.audit_event(root, artifact, args.actor, args.actor_type, "inventory_created", args.working_title, None, "idea")
    print(path)


def resolve_content(root: Path, inventory: dict[str, Any], explicit_path: str | None) -> tuple[dict[str, Any], Path]:
    raw_path = explicit_path or inventory.get("payload", {}).get("content_artifact_path")
    if not raw_path:
        raise core.WorkflowError("进入 review_ready/ready/scheduled 前必须提供本地 content artifact")
    candidate = Path(raw_path)
    path = (candidate if candidate.is_absolute() else root / candidate).resolve()
    content = load_typed(path, "content")
    require_same_account(inventory, content)
    payload = inventory["payload"]
    if content.get("payload", {}).get("strategy_artifact_id") != payload.get("strategy_artifact_id"):
        raise core.WorkflowError("content.strategy_artifact_id 与库存项不一致")
    if content.get("payload", {}).get("persona_artifact_id") != payload.get("persona_artifact_id"):
        raise core.WorkflowError("content.persona_artifact_id 与库存项不一致")
    return content, path


def schedule_long_tail(root: Path, inventory: dict[str, Any], publication: dict[str, Any]) -> list[dict[str, Any]]:
    strategy_id = inventory["payload"]["strategy_artifact_id"]
    strategy_path = artifact_path(root, inventory["account_id"], "account_strategy", strategy_id)
    strategy = load_typed(strategy_path, "account_strategy")
    published_at = publication.get("payload", {}).get("published_at")
    if not published_at:
        raise core.WorkflowError("生成长尾计划前 publication 必须记录 published_at")
    baseline = parse_iso(published_at)
    checkpoints = strategy.get("payload", {}).get("measurement_policy", {}).get("long_tail_checkpoints_days", [])
    return [
        {
            "checkpoint_days": day,
            "due_at": (baseline + timedelta(days=day)).isoformat(timespec="seconds"),
            "status": "pending",
            "snapshot_artifact_id": None,
            "completed_at": None,
        }
        for day in sorted(checkpoints)
    ]


def command_transition_inventory(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    inventory = load_typed(path, "inventory_item")
    root = core.find_workspace(path)
    payload = inventory["payload"]
    current = payload["state"]
    target = args.to
    if target not in core.INVENTORY_TRANSITIONS.get(current, set()):
        raise core.WorkflowError(f"不允许的库存状态变化：{current} -> {target}")
    content: dict[str, Any] | None = None
    content_path: Path | None = None
    if target in {"review_ready", "ready", "scheduled"}:
        content, content_path = resolve_content(root, inventory, args.content)
    if target in {"ready", "scheduled"} and content and not core.effective_approval(content, "G3"):
        raise core.WorkflowError("库存进入 ready/scheduled 前需要 content 的有效 G3 批准")
    if target == "scheduled" and not args.planned_at:
        raise core.WorkflowError("进入 scheduled 必须提供 --planned-at")
    if target == "held" and not args.reason.strip():
        raise core.WorkflowError("进入 held 必须说明原因")
    publication: dict[str, Any] | None = None
    publication_path: Path | None = None
    if target == "published":
        if not args.publication:
            raise core.WorkflowError("库存进入 published 必须提供 --publication")
        publication_path = Path(args.publication).resolve()
        publication = load_typed(publication_path, "publication")
        require_same_account(inventory, publication)
        if publication.get("status") != "published":
            raise core.WorkflowError("关联 publication 必须已经是 published")
        publication_payload = publication.get("payload", {})
        if publication_payload.get("inventory_item_artifact_id") != inventory.get("artifact_id"):
            raise core.WorkflowError("publication.inventory_item_artifact_id 与库存项不一致")
        if publication_payload.get("strategy_artifact_id") != payload.get("strategy_artifact_id"):
            raise core.WorkflowError("publication.strategy_artifact_id 与库存项不一致")
        content, content_path = resolve_content(root, inventory, None)
        if not core.effective_approval(content, "G3"):
            raise core.WorkflowError("库存进入 published 前关联 content 的 G3 必须仍然有效")
    timestamp = core.now_iso()
    before_status = inventory["status"]
    if content and content_path:
        payload["content_artifact_id"] = content["artifact_id"]
        payload["content_artifact_path"] = workspace_relative(root, content_path)
    if target == "scheduled":
        parse_iso(args.planned_at)
        payload["planned_publish_at"] = args.planned_at
    elif target in {"draft", "review_ready", "ready"}:
        payload["planned_publish_at"] = None
    payload["hold_reason"] = args.reason if target == "held" else None
    if publication and publication_path:
        payload["publication_artifact_id"] = publication["artifact_id"]
        payload["publication_artifact_path"] = workspace_relative(root, publication_path)
        payload["measurement_schedule"] = schedule_long_tail(root, inventory, publication)
    payload["state"] = target
    payload.setdefault("history", []).append({"from": current, "to": target, "at": timestamp, "actor_id": args.actor, "actor_type": args.actor_type, "reason": args.reason})
    inventory["status"] = target
    inventory["updated_at"] = timestamp
    errors = core.validate_artifact(inventory)
    if errors:
        raise core.WorkflowError("库存状态变化后不合法：" + "; ".join(errors))
    core.atomic_write_json(path, inventory)
    core.audit_event(root, inventory, args.actor, args.actor_type, "inventory_transition", args.reason, before_status, target)
    print(f"{current} -> {target}: {path}")


def latest_published_at(root: Path, inventory: dict[str, Any]) -> datetime | None:
    key = inventory.get("payload", {}).get("same_topic_key")
    if not key:
        return None
    timestamps: list[datetime] = []
    folder = root / "artifacts" / inventory["account_id"] / "inventory_item"
    for candidate in sorted(folder.glob("*.json")):
        other = core.load_json(candidate)
        if other.get("artifact_id") == inventory.get("artifact_id"):
            continue
        other_payload = other.get("payload", {})
        if other_payload.get("state") != "published" or other_payload.get("same_topic_key") != key:
            continue
        publication_path = other_payload.get("publication_artifact_path")
        if not publication_path:
            continue
        publication = core.load_json(root / publication_path)
        published_at = publication.get("payload", {}).get("published_at")
        if published_at:
            timestamps.append(parse_iso(published_at))
    return max(timestamps) if timestamps else None


def policy_decision(strategy: dict[str, Any], inventory: dict[str, Any], action: str, root: Path, checked_at: datetime) -> tuple[str, list[str]]:
    policy = strategy["payload"]["publishing_policy"]
    reasons: list[str] = []
    if action in {"modify", "delete"}:
        rule = policy[f"{'modification' if action == 'modify' else 'deletion'}_policy"]
        if rule == "prohibited":
            return "blocked", [f"账号战略将 {action} 设为 prohibited"]
        reasons.append(f"账号战略要求 {action} 由人工审阅")
        minimum = policy.get("minimum_observation_hours")
        publication_path = inventory.get("payload", {}).get("publication_artifact_path")
        if minimum is not None and publication_path:
            publication = core.load_json(root / publication_path)
            published_at = publication.get("payload", {}).get("published_at")
            if published_at:
                elapsed = (checked_at - parse_iso(published_at)).total_seconds() / 3600
                if elapsed < minimum:
                    reasons.append(f"尚未达到配置的 minimum_observation_hours={minimum}")
        return "needs_human", reasons
    if policy.get("threshold_basis") == "unset":
        reasons.append("发布阈值来源尚未配置")
    cooldown = policy.get("same_topic_cooldown_hours")
    previous = latest_published_at(root, inventory)
    if cooldown is None and inventory.get("payload", {}).get("same_topic_key"):
        reasons.append("同主题冷却时长尚未配置")
    elif cooldown is not None and previous is not None:
        elapsed = (checked_at - previous).total_seconds() / 3600
        if elapsed < cooldown:
            reasons.append(f"同主题距上次发布 {elapsed:.2f} 小时，低于配置值 {cooldown}")
    if policy.get("breakout_hold_hours") is not None:
        reasons.append("breakout_hold_hours 已配置；爆款状态需以经审阅证据确认")
    return ("needs_human", reasons) if reasons else ("allowed", ["未发现违反当前账号战略的条件"])


def command_check_policy(args: argparse.Namespace) -> None:
    strategy_path = Path(args.strategy).resolve()
    inventory_path = Path(args.inventory).resolve()
    strategy = load_typed(strategy_path, "account_strategy")
    inventory = load_typed(inventory_path, "inventory_item")
    require_same_account(strategy, inventory)
    require_effective_g1(strategy, "账号战略")
    if inventory.get("payload", {}).get("strategy_artifact_id") != strategy.get("artifact_id"):
        raise core.WorkflowError("库存项引用的账号战略与 --strategy 不一致")
    root = core.find_workspace(inventory_path)
    checked_at = parse_iso(args.at) if args.at else parse_iso(core.now_iso())
    decision, reasons = policy_decision(strategy, inventory, args.action, root, checked_at)
    check = {"checked_at": checked_at.isoformat(timespec="seconds"), "strategy_artifact_id": strategy["artifact_id"], "action": args.action, "decision": decision, "reasons": reasons}
    inventory["payload"]["policy_check"] = check
    inventory["updated_at"] = core.now_iso()
    errors = core.validate_artifact(inventory)
    if errors:
        raise core.WorkflowError("写入策略检查后库存项不合法：" + "; ".join(errors))
    publication_path: Path | None = None
    publication: dict[str, Any] | None = None
    if args.publication:
        if args.action != "publish":
            raise core.WorkflowError("--publication 只用于同步发布前 action=publish 检查；发布后动作使用 record-post-publish")
        publication_path = Path(args.publication).resolve()
        publication = load_typed(publication_path, "publication")
        require_same_account(strategy, inventory, publication)
        if publication.get("payload", {}).get("state") not in {"draft", "review_required"}:
            raise core.WorkflowError("策略检查只能同步到 draft 或 review_required publication")
        if publication.get("payload", {}).get("inventory_item_artifact_id") != inventory.get("artifact_id"):
            raise core.WorkflowError("publication 与库存项不一致")
        publication["payload"]["policy_check"] = check
        publication["updated_at"] = core.now_iso()
        publication_errors = core.validate_artifact(publication)
        if publication_errors:
            raise core.WorkflowError("写入策略检查后 publication 不合法：" + "; ".join(publication_errors))
    core.atomic_write_json(inventory_path, inventory)
    if publication is not None and publication_path is not None:
        core.atomic_write_json(publication_path, publication)
    core.audit_event(root, inventory, args.actor, args.actor_type, "publishing_policy_checked", f"{args.action}: {decision}")
    print(json.dumps(check, ensure_ascii=False, indent=2))


def command_record_post_publish(args: argparse.Namespace) -> None:
    publication_path = Path(args.publication).resolve()
    strategy = load_typed(Path(args.strategy).resolve(), "account_strategy")
    publication = load_typed(publication_path, "publication")
    require_same_account(strategy, publication)
    require_effective_g1(strategy, "账号战略")
    if publication.get("status") != "published":
        raise core.WorkflowError("只有 published publication 可以记录发布后动作")
    policy = strategy["payload"]["publishing_policy"]
    rule = policy[f"{'modification' if args.action == 'modify' else 'deletion'}_policy"]
    if args.decision == "approved" and rule == "prohibited":
        raise core.WorkflowError(f"账号战略禁止 {args.action}，不能记录为 approved")
    timestamp = core.now_iso()
    publication["payload"].setdefault("post_publish_actions", []).append({"action": args.action, "requested_at": timestamp, "actor_id": args.actor, "actor_type": "human", "decision": args.decision, "reasons": [args.reason]})
    publication["updated_at"] = timestamp
    errors = core.validate_artifact(publication)
    if errors:
        raise core.WorkflowError("记录发布后动作后 publication 不合法：" + "; ".join(errors))
    core.atomic_write_json(publication_path, publication)
    root = core.find_workspace(publication_path)
    core.audit_event(root, publication, args.actor, "human", "post_publish_action_decided", f"{args.action}: {args.decision}; {args.reason}")
    print(publication_path)


def command_long_tail_due(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    core.load_json(root / "workspace.json")
    as_of = parse_iso(args.as_of) if args.as_of else parse_iso(core.now_iso())
    due: list[dict[str, Any]] = []
    for path in sorted((root / "artifacts").glob("*/inventory_item/*.json")):
        inventory = load_typed(path, "inventory_item")
        for item in inventory.get("payload", {}).get("measurement_schedule", []):
            if item.get("status") == "pending" and parse_iso(item["due_at"]) <= as_of:
                due.append({"account_id": inventory["account_id"], "inventory_item_artifact_id": inventory["artifact_id"], "inventory_path": workspace_relative(root, path), "checkpoint_days": item["checkpoint_days"], "due_at": item["due_at"]})
    due.sort(key=lambda item: (item["due_at"], item["account_id"], item["inventory_item_artifact_id"]))
    print(json.dumps(due, ensure_ascii=False, indent=2))


def command_complete_long_tail(args: argparse.Namespace) -> None:
    inventory_path = Path(args.inventory).resolve()
    snapshot_path = Path(args.snapshot).resolve()
    inventory = load_typed(inventory_path, "inventory_item")
    snapshot = load_typed(snapshot_path, "metrics_snapshot")
    require_same_account(inventory, snapshot)
    snapshot_payload = snapshot["payload"]
    if snapshot.get("status") != "ready" or snapshot_payload.get("measurement_kind") != "long_tail":
        raise core.WorkflowError("长尾完成凭据必须是 ready 的 long_tail metrics_snapshot")
    if snapshot_payload.get("checkpoint_days") != args.checkpoint_days:
        raise core.WorkflowError("snapshot.checkpoint_days 与指定 checkpoint 不一致")
    if snapshot_payload.get("publication_artifact_id") != inventory.get("payload", {}).get("publication_artifact_id"):
        raise core.WorkflowError("snapshot.publication_artifact_id 与库存项不一致")
    matched = False
    timestamp = core.now_iso()
    for item in inventory["payload"]["measurement_schedule"]:
        if item.get("checkpoint_days") == args.checkpoint_days:
            if item.get("status") != "pending":
                raise core.WorkflowError("该长尾检查点已处理")
            item.update({"status": "completed", "snapshot_artifact_id": snapshot["artifact_id"], "completed_at": timestamp})
            matched = True
            break
    if not matched:
        raise core.WorkflowError("库存项不存在指定的长尾检查点")
    inventory["updated_at"] = timestamp
    errors = core.validate_artifact(inventory)
    if errors:
        raise core.WorkflowError("完成长尾检查后库存项不合法：" + "; ".join(errors))
    core.atomic_write_json(inventory_path, inventory)
    root = core.find_workspace(inventory_path)
    core.audit_event(root, inventory, args.actor, args.actor_type, "long_tail_checkpoint_completed", f"day {args.checkpoint_days}: {snapshot['artifact_id']}")
    print(inventory_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="XHS Workflow V2.2 portfolio operations")
    sub = parser.add_subparsers(dest="command", required=True)

    new_strategy = sub.add_parser("new-strategy", help="创建账号战略草案")
    new_strategy.add_argument("--run", required=True)
    new_strategy.add_argument("--lifecycle-stage", choices=sorted(core.LIFECYCLE_STAGES), required=True)
    new_strategy.add_argument("--stage-confidence", choices=["low", "medium", "high"], required=True)
    new_strategy.add_argument("--persona-mode", choices=["assumed", "validated"], required=True)
    new_strategy.add_argument("--play-mode", choices=["trend", "ip", "hybrid", "undecided"], required=True)
    new_strategy.add_argument("--supersedes")
    new_strategy.add_argument("--actor", required=True)
    new_strategy.set_defaults(func=command_new_strategy)

    new_inventory = sub.add_parser("new-inventory", help="创建内容库存项")
    new_inventory.add_argument("--run", required=True)
    new_inventory.add_argument("--strategy", required=True)
    new_inventory.add_argument("--persona", required=True)
    new_inventory.add_argument("--objective", choices=sorted(core.CONTENT_OBJECTIVES), required=True)
    new_inventory.add_argument("--format", choices=["image", "video", "text"], required=True)
    new_inventory.add_argument("--working-title", required=True)
    new_inventory.add_argument("--content-sequence-no", type=int)
    new_inventory.add_argument("--topic-report-id")
    new_inventory.add_argument("--topic-id")
    new_inventory.add_argument("--same-topic-key")
    new_inventory.add_argument("--actor", required=True)
    new_inventory.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    new_inventory.set_defaults(func=command_new_inventory)

    transition = sub.add_parser("transition-inventory", help="改变库存项状态")
    transition.add_argument("path")
    transition.add_argument("--to", choices=sorted(core.INVENTORY_STATES), required=True)
    transition.add_argument("--content")
    transition.add_argument("--planned-at")
    transition.add_argument("--publication")
    transition.add_argument("--actor", required=True)
    transition.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    transition.add_argument("--reason", required=True)
    transition.set_defaults(func=command_transition_inventory)

    check = sub.add_parser("check-policy", help="按账号战略检查发布或发布后动作")
    check.add_argument("--strategy", required=True)
    check.add_argument("--inventory", required=True)
    check.add_argument("--publication")
    check.add_argument("--action", choices=["publish", "modify", "delete"], required=True)
    check.add_argument("--at", help="测试或回放用检查时间；默认当前时间")
    check.add_argument("--actor", required=True)
    check.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    check.set_defaults(func=command_check_policy)

    post = sub.add_parser("record-post-publish", help="记录人工发布后修改/删除决定")
    post.add_argument("--publication", required=True)
    post.add_argument("--strategy", required=True)
    post.add_argument("--action", choices=["modify", "delete"], required=True)
    post.add_argument("--decision", choices=["approved", "rejected"], required=True)
    post.add_argument("--actor", required=True)
    post.add_argument("--reason", required=True)
    post.set_defaults(func=command_record_post_publish)

    due = sub.add_parser("long-tail-due", help="列出到期的长尾检查点")
    due.add_argument("--root", required=True)
    due.add_argument("--as-of")
    due.set_defaults(func=command_long_tail_due)

    complete = sub.add_parser("complete-long-tail", help="用指标快照完成长尾检查点")
    complete.add_argument("--inventory", required=True)
    complete.add_argument("--checkpoint-days", type=int, required=True)
    complete.add_argument("--snapshot", required=True)
    complete.add_argument("--actor", required=True)
    complete.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    complete.set_defaults(func=command_complete_long_tail)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except core.WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
