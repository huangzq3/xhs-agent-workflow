from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / "scripts" / "workflow_cli.py"
PORTFOLIO_CLI = SKILL_ROOT / "scripts" / "portfolio_cli.py"
SCHEMA = SKILL_ROOT / "references" / "schemas" / "artifact.schema.json"
INSTALLER = SKILL_ROOT.parents[1] / "install.sh"
SPEC = importlib.util.spec_from_file_location("workflow_cli", CLI)
assert SPEC and SPEC.loader
workflow_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow_cli)


def run_script(script: Path, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([sys.executable, str(script), *args], text=True, capture_output=True, check=False)
    if result.returncode != expected:
        raise AssertionError(
            f"returncode={result.returncode}, expected={expected}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def run_cli(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    return run_script(CLI, *args, expected=expected)


def run_portfolio(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    return run_script(PORTFOLIO_CLI, *args, expected=expected)


class WorkflowCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "workspace"
        run_cli("init", "--root", str(self.root), "--account-id", "demo_account", "--display-name", "Demo", "--actor", "owner")
        result = run_cli("new-run", "--root", str(self.root), "--account-id", "demo_account", "--objective", "测试完整闭环", "--actor", "owner")
        self.run_path = Path(result.stdout.strip())
        self.run = json.loads(self.run_path.read_text(encoding="utf-8"))
        self.run_id = self.run["run_id"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def configure_runtime(self, run_path: Path | None = None) -> None:
        path = run_path or self.run_path
        run = json.loads(path.read_text(encoding="utf-8"))
        runtime = run["payload"]["runtime_capabilities"]
        runtime.update({"runtime_name": "test-runtime", "captured_at": workflow_cli.now_iso(), "capability_source": "runtime_advertised", "discovery_status": "complete", "execution_mode": "full", "limitations": []})
        for name, entry in runtime["capabilities"].items():
            entry.update({"status": "unavailable", "capability_id": None, "notes": []})
            if name == "native_image_generation":
                entry.update({"processing_boundary": "unknown", "supports_reference_images": False, "returns_local_file": False})
        for name in ("local_json_storage", "append_audit_log", "human_approval"):
            runtime["capabilities"][name].update({"status": "available", "capability_id": f"test:{name}"})
        run["payload"]["data_scope"]["allowed_sources"] = ["user_input"]
        workflow_cli.atomic_write_json(path, run)

    def approve_g0(self, run_path: Path | None = None) -> None:
        path = run_path or self.run_path
        self.configure_runtime(path)
        run_cli("approve", str(path), "--gate", "G0", "--actor", "owner", "--decision", "approved")

    def write_artifact(self, kind: str, artifact_id: str, payload: dict, *, status: str = "review_required", run_id: str | None = None) -> Path:
        timestamp = workflow_cli.now_iso()
        artifact = {
            "schema_version": "2.2.0", "artifact_type": kind, "artifact_id": artifact_id,
            "account_id": "demo_account", "run_id": run_id or self.run_id,
            "created_at": timestamp, "updated_at": timestamp, "status": status,
            "provenance": [], "approvals": [], "payload": payload,
        }
        path = self.root / "artifacts" / "demo_account" / kind / f"{artifact_id}.json"
        workflow_cli.atomic_write_json(path, artifact)
        return path

    def strategy_payload(self, *, deletion_policy: str = "human_review_required", cooldown: float | None = 72, checkpoints: list[int] | None = None) -> dict:
        return {
            "revision": 1,
            "supersedes_artifact_id": None,
            "lifecycle_stage": "trial",
            "stage_confidence": "medium",
            "persona_mode": "assumed",
            "play_mode": "hybrid",
            "transition": {"from_stage": None, "rationale": "新账号从试运营开始", "evidence_refs": ["source_owner"], "alternative_explanations": ["历史数据尚少"]},
            "stage_evidence": [{"signal_id": "stage_1", "observation": "尚无稳定内容基线", "evidence_refs": ["source_owner"], "confidence": "medium"}],
            "content_objectives": [
                {"objective": "acquisition", "target_share": 0.4, "rationale": "验证入口", "seed_ref": None},
                {"objective": "trust", "target_share": 0.4, "rationale": "验证信任", "seed_ref": None},
                {"objective": "tag_strengthening", "target_share": 0.2, "rationale": "验证标签", "seed_ref": None},
            ],
            "publishing_policy": {
                "modification_policy": "human_review_required", "deletion_policy": deletion_policy,
                "minimum_observation_hours": 24, "same_topic_cooldown_hours": cooldown,
                "breakout_hold_hours": None, "threshold_basis": "manual", "exceptions_require_human": True,
            },
            "inventory_policy": {"target_coverage_days": 7, "target_ready_items": 3, "threshold_basis": "manual"},
            "measurement_policy": {"trust_metrics": ["profile_visit_rate", "follow_rate"], "long_tail_checkpoints_days": checkpoints if checkpoints is not None else [7, 30], "qualitative_rubric_refs": ["rubric/trust-v1"]},
            "experience_seed_refs": [],
            "limitations": ["阈值为账号负责人当前手工设定，尚待账号基线校准"],
        }

    def make_strategy(self, artifact_id: str = "account_strategy_demo01", **kwargs: object) -> Path:
        path = self.write_artifact("account_strategy", artifact_id, self.strategy_payload(**kwargs))
        run_cli("approve", str(path), "--gate", "G1", "--actor", "owner", "--decision", "approved")
        return path

    def persona_payload(self, strategy_id: str, *, mode: str = "assumed") -> dict:
        return {
            "revision": 1, "supersedes_artifact_id": None, "strategy_artifact_id": strategy_id, "mode": mode,
            "hypotheses": [{"hypothesis_id": "persona_h1", "statement": "新手需要可复现步骤", "status": "pending" if mode == "assumed" else "supported", "evidence_refs": []}],
            "validation_plan": {"sample_target": 6, "diversity_dimensions": ["内容目标", "题材"], "success_signals": ["信任指标持续改善"], "stop_conditions": ["连续样本反驳核心假设"]},
            "identity": {"display_name": "Demo", "positioning_statement": "帮助新手验证工作流"},
            "niche": {"primary": "工作流", "subtopics": ["自动化"], "formats": ["text"]},
            "audience": [{"segment_id": "audience_1", "name": "新手"}],
            "differentiation": {"value_proposition": "可核验", "proof": [], "non_goals": []},
            "content_pillars": [{"pillar_id": "pillar_1", "name": "验证", "purpose": "提供证据"}],
            "voice": {"traits": ["清晰"]}, "visual": {}, "boundaries": ["不伪造经历"],
        }

    def make_persona(self, strategy_path: Path, artifact_id: str = "persona_demo001", *, mode: str = "assumed") -> Path:
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        path = self.write_artifact("persona", artifact_id, self.persona_payload(strategy["artifact_id"], mode=mode))
        run_cli("approve", str(path), "--gate", "G1", "--actor", "owner", "--decision", "approved")
        return path

    def content_payload(self, strategy_id: str, persona_id: str, *, sequence: int = 1) -> dict:
        return {
            "revision": 1, "strategy_artifact_id": strategy_id, "persona_artifact_id": persona_id,
            "topic_report_artifact_id": "topic_report_demo01", "topic_id": "topic_1",
            "content_objective": "trust", "content_sequence_no": sequence, "format": "text",
            "title": "如何验证工作流", "caption": "从契约开始。", "hashtags": ["工作流"],
            "claims": [{"claim_id": "claim_1", "text": "建议先验证契约", "kind": "opinion", "source_refs": [], "verification_status": "not_applicable"}],
            "personal_experiences": [], "assets": [], "change_summary": ["初稿"], "safety_notes": [],
        }

    def make_content(self, strategy_path: Path, persona_path: Path, artifact_id: str = "content_demo001", *, approve: bool = True) -> Path:
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        persona = json.loads(persona_path.read_text(encoding="utf-8"))
        path = self.write_artifact("content", artifact_id, self.content_payload(strategy["artifact_id"], persona["artifact_id"]))
        if approve:
            run_cli("approve", str(path), "--gate", "G3", "--actor", "owner", "--decision", "approved")
        return path

    def publication_payload(self, strategy_id: str, inventory_id: str, content_id: str, *, state: str = "draft", decision: str = "allowed") -> dict:
        return {
            "strategy_artifact_id": strategy_id, "inventory_item_artifact_id": inventory_id,
            "content_artifact_id": content_id, "target_account_id": "demo_account", "platform": "xiaohongshu",
            "state": state, "visibility": "public", "scheduled_at": None, "asset_order": [], "preview_sha256": None,
            "policy_check": {"checked_at": workflow_cli.now_iso(), "strategy_artifact_id": strategy_id, "action": "publish", "decision": decision, "reasons": ["test"]},
            "post_publish_actions": [], "attempts": [], "remote_id": "remote_1" if state == "published" else None,
            "remote_url": None, "published_at": workflow_cli.now_iso() if state == "published" else None, "last_error": None,
        }

    def make_ready_inventory(self, strategy_path: Path, persona_path: Path, content_path: Path, artifact_id: str = "inventory_demo01", *, same_topic_key: str | None = None) -> Path:
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        persona = json.loads(persona_path.read_text(encoding="utf-8"))
        content = json.loads(content_path.read_text(encoding="utf-8"))
        relative_content = str(content_path.relative_to(self.root))
        payload = {
            "revision": 1, "strategy_artifact_id": strategy["artifact_id"], "persona_artifact_id": persona["artifact_id"],
            "topic_report_artifact_id": "topic_report_demo01", "topic_id": "topic_1",
            "content_artifact_id": content["artifact_id"], "content_artifact_path": relative_content,
            "publication_artifact_id": None, "publication_artifact_path": None,
            "content_sequence_no": 1, "content_objective": "trust", "format": "text", "working_title": "待发布内容",
            "same_topic_key": same_topic_key, "state": "ready", "planned_publish_at": None, "hold_reason": None,
            "policy_check": None, "measurement_schedule": [],
            "history": [{"from": "review_ready", "to": "ready", "at": workflow_cli.now_iso(), "actor_id": "owner", "actor_type": "human", "reason": "G3 后入库"}],
        }
        return self.write_artifact("inventory_item", artifact_id, payload, status="ready")

    def snapshot_payload(self, publication_id: str, *, kind: str = "initial", checkpoint: int | None = None, prior: str | None = None) -> dict:
        return {
            "content_artifact_id": "content_demo001", "publication_artifact_id": publication_id, "format": "text",
            "captured_at": workflow_cli.now_iso(), "window": "7d" if kind == "long_tail" else "24h",
            "measurement_kind": kind, "checkpoint_days": checkpoint, "prior_snapshot_artifact_id": prior,
            "stock_metrics": {"views": 10}, "flow_metrics": {"new_views": 10}, "derived_metrics": {"interaction_rate": None},
            "trust_metrics": {"profile_visit_rate": 0.1, "follow_rate": 0.05},
            "qualitative_metrics": [{"metric": "comment_trust", "value": "medium", "rubric_ref": "rubric/trust-v1", "evidence_refs": ["comment_1"], "assessed_by": "human"}],
            "missing_fields": [], "source": {"kind": "manual"},
        }

    def test_schema_and_installer_are_agent_neutral(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], "2.2.0")
        self.assertIn("accountStrategyPayload", schema["$defs"])
        self.assertIn("inventoryItemPayload", schema["$defs"])
        installer = INSTALLER.read_text(encoding="utf-8").lower()
        self.assertIn("--target", installer)
        self.assertNotIn(".trae/", installer)

    def test_g0_advances_full_cycle_to_strategy(self) -> None:
        rejected = run_cli("approve", str(self.run_path), "--gate", "G0", "--actor", "owner", "--decision", "approved", expected=2)
        self.assertIn("G0 批准前", rejected.stderr)
        self.approve_g0()
        run = json.loads(self.run_path.read_text(encoding="utf-8"))
        self.assertEqual(run["payload"]["current_stage"], "strategy")
        self.assertTrue(workflow_cli.effective_approval(run, "G0"))

    def test_strategy_scaffold_has_no_hardcoded_numeric_thresholds(self) -> None:
        self.approve_g0()
        result = run_portfolio("new-strategy", "--run", str(self.run_path), "--lifecycle-stage", "trial", "--stage-confidence", "low", "--persona-mode", "assumed", "--play-mode", "undecided", "--actor", "owner")
        path = Path(result.stdout.strip())
        strategy = json.loads(path.read_text(encoding="utf-8"))
        policy = strategy["payload"]["publishing_policy"]
        self.assertIsNone(policy["minimum_observation_hours"])
        self.assertIsNone(policy["same_topic_cooldown_hours"])
        self.assertEqual(policy["threshold_basis"], "unset")
        blocked = run_cli("approve", str(path), "--gate", "G1", "--actor", "owner", "--decision", "approved", expected=2)
        self.assertIn("stage_evidence", blocked.stderr)

    def test_strategy_and_assumed_persona_have_separate_g1_decisions(self) -> None:
        self.approve_g0()
        strategy_path = self.make_strategy()
        run_cli("register", "--run", str(self.run_path), "--artifact", str(strategy_path), "--role", "account_strategy", "--actor", "agent")
        run = json.loads(self.run_path.read_text(encoding="utf-8"))
        self.assertEqual(run["payload"]["current_stage"], "persona")
        persona_path = self.make_persona(strategy_path)
        run_cli("register", "--run", str(self.run_path), "--artifact", str(persona_path), "--role", "persona", "--actor", "agent")
        run = json.loads(self.run_path.read_text(encoding="utf-8"))
        self.assertEqual(run["payload"]["current_stage"], "topics")
        self.assertTrue(workflow_cli.effective_approval(run, "G0"))
        self.assertEqual(len(json.loads(strategy_path.read_text(encoding="utf-8"))["approvals"]), 1)
        self.assertEqual(len(json.loads(persona_path.read_text(encoding="utf-8"))["approvals"]), 1)

    def test_registering_strategy_revision_supersedes_exact_predecessor(self) -> None:
        self.approve_g0()
        old_path = self.make_strategy("account_strategy_old001")
        old_persona_path = self.make_persona(old_path, "persona_old001")
        old = json.loads(old_path.read_text(encoding="utf-8"))
        payload = self.strategy_payload()
        payload.update({"revision": 2, "supersedes_artifact_id": old["artifact_id"], "lifecycle_stage": "scale"})
        payload["transition"] = {"from_stage": "trial", "rationale": "多轮证据支持扩展", "evidence_refs": ["review_1"], "alternative_explanations": ["季节波动"]}
        new_path = self.write_artifact("account_strategy", "account_strategy_new001", payload)
        run_cli("approve", str(new_path), "--gate", "G1", "--actor", "owner", "--decision", "approved")
        run_cli("register", "--run", str(self.run_path), "--artifact", str(new_path), "--role", "account_strategy", "--actor", "agent")
        self.assertEqual(json.loads(old_path.read_text(encoding="utf-8"))["status"], "superseded")
        denied = run_cli("new-run", "--root", str(self.root), "--account-id", "demo_account", "--objective", "不得使用旧战略", "--actor", "owner", "--run-type", "content_production", "--strategy", str(old_path), "--persona", str(old_persona_path), expected=2)
        self.assertIn("superseded", denied.stderr)

    def test_trial_run_requires_approved_assumed_strategy_and_persona(self) -> None:
        strategy_path = self.make_strategy()
        persona_path = self.make_persona(strategy_path)
        missing = run_cli("new-run", "--root", str(self.root), "--account-id", "demo_account", "--objective", "试运营第 1 篇", "--actor", "owner", "--run-type", "trial_content", expected=2)
        self.assertIn("--strategy", missing.stderr)
        result = run_cli("new-run", "--root", str(self.root), "--account-id", "demo_account", "--objective", "试运营第 1 篇", "--actor", "owner", "--run-type", "trial_content", "--strategy", str(strategy_path), "--persona", str(persona_path), "--content-sequence-no", "1")
        trial_path = Path(result.stdout.strip())
        self.approve_g0(trial_path)
        trial = json.loads(trial_path.read_text(encoding="utf-8"))
        self.assertEqual(trial["payload"]["current_stage"], "topics")
        self.assertEqual(trial["payload"]["content_sequence_no"], 1)
        self.assertEqual(trial["payload"]["gate_status"]["G1"], "approved")

    def test_inventory_ready_requires_effective_g3(self) -> None:
        self.approve_g0()
        strategy_path = self.make_strategy()
        persona_path = self.make_persona(strategy_path)
        content_path = self.make_content(strategy_path, persona_path, approve=False)
        result = run_portfolio("new-inventory", "--run", str(self.run_path), "--strategy", str(strategy_path), "--persona", str(persona_path), "--objective", "trust", "--format", "text", "--working-title", "库存测试", "--content-sequence-no", "1", "--actor", "agent")
        inventory_path = Path(result.stdout.strip())
        run_portfolio("transition-inventory", str(inventory_path), "--to", "draft", "--actor", "agent", "--reason", "开始创作")
        run_portfolio("transition-inventory", str(inventory_path), "--to", "review_ready", "--content", str(content_path), "--actor", "agent", "--reason", "初稿完成")
        denied = run_portfolio("transition-inventory", str(inventory_path), "--to", "ready", "--actor", "agent", "--reason", "尝试入库", expected=2)
        self.assertIn("有效 G3", denied.stderr)
        run_cli("approve", str(content_path), "--gate", "G3", "--actor", "owner", "--decision", "approved")
        run_portfolio("transition-inventory", str(inventory_path), "--to", "ready", "--actor", "agent", "--reason", "G3 已批准")
        self.assertEqual(json.loads(inventory_path.read_text(encoding="utf-8"))["status"], "ready")

    def test_g4_blocks_prohibited_policy_and_unknown_needs_human(self) -> None:
        self.approve_g0()
        strategy_path = self.make_strategy()
        persona_path = self.make_persona(strategy_path)
        content_path = self.make_content(strategy_path, persona_path)
        inventory_path = self.make_ready_inventory(strategy_path, persona_path, content_path)
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        content = json.loads(content_path.read_text(encoding="utf-8"))
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        blocked_payload = self.publication_payload(strategy["artifact_id"], "inventory_demo01", "content_demo001", decision="blocked")
        blocked_path = self.write_artifact("publication", "publication_block01", blocked_payload, status="review_required")
        denied = run_cli("approve", str(blocked_path), "--gate", "G4", "--actor", "owner", "--decision", "approved", expected=2)
        self.assertIn("blocked", denied.stderr)

        allowed_payload = self.publication_payload(strategy["artifact_id"], inventory["artifact_id"], content["artifact_id"])
        allowed_path = self.write_artifact("publication", "publication_demo001", allowed_payload)
        run_cli("transition", str(allowed_path), "--to", "review_required", "--actor", "agent", "--reason", "预览完成")
        run_cli("approve", str(allowed_path), "--gate", "G4", "--actor", "owner", "--decision", "approved")
        run_cli("transition", str(allowed_path), "--to", "publishing", "--actor", "agent", "--reason", "消费一次批准")
        run_cli("transition", str(allowed_path), "--to", "unknown", "--actor", "agent", "--reason", "远端超时", "--error", "timeout")
        denied = run_cli("transition", str(allowed_path), "--to", "failed", "--actor", "agent", "--reason", "自动猜测", expected=2)
        self.assertIn("人工", denied.stderr)
        run_cli("transition", str(allowed_path), "--to", "published", "--actor", "owner", "--actor-type", "human", "--reason", "人工核对远端", "--remote-id", "remote_1")

    def test_g5_requires_trust_metrics_and_snapshot_window(self) -> None:
        self.approve_g0()
        run = json.loads(self.run_path.read_text(encoding="utf-8"))
        denied = run_cli("approve", str(self.run_path), "--gate", "G5", "--actor", "owner", "--decision", "approved", expected=2)
        self.assertIn("snapshot_window", denied.stderr)
        run["payload"]["measurement_plan"].update({"snapshot_windows": ["24h"], "trust_metrics": ["follow_rate"]})
        workflow_cli.atomic_write_json(self.run_path, run)
        run_cli("approve", str(self.run_path), "--gate", "G5", "--actor", "owner", "--decision", "approved")
        updated = json.loads(self.run_path.read_text(encoding="utf-8"))
        self.assertTrue(workflow_cli.effective_approval(updated, "G0"))
        self.assertTrue(workflow_cli.effective_approval(updated, "G5"))

    def test_same_topic_cooldown_uses_strategy_value(self) -> None:
        self.approve_g0()
        strategy_path = self.make_strategy(cooldown=10)
        persona_path = self.make_persona(strategy_path)
        content_path = self.make_content(strategy_path, persona_path)
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        content = json.loads(content_path.read_text(encoding="utf-8"))
        previous_inventory_path = self.make_ready_inventory(strategy_path, persona_path, content_path, "inventory_previous01", same_topic_key="workflow")
        previous = json.loads(previous_inventory_path.read_text(encoding="utf-8"))
        previous_publication_payload = self.publication_payload(strategy["artifact_id"], previous["artifact_id"], content["artifact_id"], state="published")
        previous_publication_payload["published_at"] = "2026-08-17T08:00:00+08:00"
        previous_publication_path = self.write_artifact("publication", "publication_previous01", previous_publication_payload, status="published")
        previous["status"] = "published"
        previous["payload"].update({"state": "published", "publication_artifact_id": "publication_previous01", "publication_artifact_path": str(previous_publication_path.relative_to(self.root))})
        previous["payload"]["history"].append({"from": "scheduled", "to": "published", "at": "2026-08-17T08:00:00+08:00", "actor_id": "owner", "actor_type": "human", "reason": "已发布"})
        workflow_cli.atomic_write_json(previous_inventory_path, previous)
        current_inventory_path = self.make_ready_inventory(strategy_path, persona_path, content_path, "inventory_current01", same_topic_key="workflow")
        result = run_portfolio("check-policy", "--strategy", str(strategy_path), "--inventory", str(current_inventory_path), "--action", "publish", "--at", "2026-08-17T12:00:00+08:00", "--actor", "agent")
        check = json.loads(result.stdout)
        self.assertEqual(check["decision"], "needs_human")
        self.assertTrue(any("配置值 10" in reason for reason in check["reasons"]))

    def test_long_tail_schedule_due_and_completion(self) -> None:
        self.approve_g0()
        strategy_path = self.make_strategy(checkpoints=[7, 30], cooldown=None)
        persona_path = self.make_persona(strategy_path)
        content_path = self.make_content(strategy_path, persona_path)
        inventory_result = run_portfolio("new-inventory", "--run", str(self.run_path), "--strategy", str(strategy_path), "--persona", str(persona_path), "--objective", "trust", "--format", "text", "--working-title", "长尾测试", "--same-topic-key", "workflow", "--actor", "agent")
        inventory_path = Path(inventory_result.stdout.strip())
        for target, extra in (("draft", []), ("review_ready", ["--content", str(content_path)]), ("ready", []), ("scheduled", ["--planned-at", "2026-08-17T12:00:00+08:00"])):
            run_portfolio("transition-inventory", str(inventory_path), "--to", target, *extra, "--actor", "agent", "--reason", f"进入 {target}")
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        content = json.loads(content_path.read_text(encoding="utf-8"))
        publication_path = self.write_artifact("publication", "publication_longtail01", self.publication_payload(strategy["artifact_id"], inventory["artifact_id"], content["artifact_id"], state="published"), status="published")
        run_portfolio("transition-inventory", str(inventory_path), "--to", "published", "--publication", str(publication_path), "--actor", "agent", "--reason", "发布完成")
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        self.assertEqual([item["checkpoint_days"] for item in inventory["payload"]["measurement_schedule"]], [7, 30])
        due = run_portfolio("long-tail-due", "--root", str(self.root), "--as-of", "2099-01-01T00:00:00+08:00")
        self.assertEqual(len(json.loads(due.stdout)), 2)
        snapshot_path = self.write_artifact("metrics_snapshot", "metrics_longtail07", self.snapshot_payload("publication_longtail01", kind="long_tail", checkpoint=7, prior="metrics_initial01"), status="ready")
        run_portfolio("complete-long-tail", "--inventory", str(inventory_path), "--checkpoint-days", "7", "--snapshot", str(snapshot_path), "--actor", "agent")
        remaining = run_portfolio("long-tail-due", "--root", str(self.root), "--as-of", "2099-01-01T00:00:00+08:00")
        self.assertEqual([item["checkpoint_days"] for item in json.loads(remaining.stdout)], [30])

    def test_post_publish_delete_respects_human_policy(self) -> None:
        strategy_path = self.make_strategy(deletion_policy="prohibited")
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        publication_path = self.write_artifact("publication", "publication_delete01", self.publication_payload(strategy["artifact_id"], "inventory_delete01", "content_demo001", state="published"), status="published")
        denied = run_portfolio("record-post-publish", "--publication", str(publication_path), "--strategy", str(strategy_path), "--action", "delete", "--decision", "approved", "--actor", "owner", "--reason", "想删除", expected=2)
        self.assertIn("禁止", denied.stderr)
        run_portfolio("record-post-publish", "--publication", str(publication_path), "--strategy", str(strategy_path), "--action", "delete", "--decision", "rejected", "--actor", "owner", "--reason", "遵循账号战略")
        publication = json.loads(publication_path.read_text(encoding="utf-8"))
        self.assertEqual(publication["payload"]["post_publish_actions"][0]["actor_type"], "human")

    def test_all_ten_artifact_contracts_validate(self) -> None:
        strategy_payload = self.strategy_payload()
        persona_payload = self.persona_payload("account_strategy_demo01")
        topic_payload = {
            "objective": "选择可测试主题", "strategy_artifact_id": "account_strategy_demo01", "persona_artifact_id": "persona_demo001", "research_mode": "trial_diversification", "requested_topics": ["验证工作流"],
            "evidence": [{"evidence_id": "evidence_1", "kind": "user_input", "source_ref": "source_1", "captured_at": workflow_cli.now_iso(), "observation": "需要验证", "quote": None, "quote_verified": False, "metrics": {}, "limitations": []}],
            "candidates": [{"topic_id": "topic_1", "premise": "演示验证", "audience_need": "理解方法", "evidence_refs": ["evidence_1"], "scores": {"relevance": 90}, "confidence": "medium", "content_angles": [], "risks": [], "decision": "selected"}], "selected_topic_ids": ["topic_1"], "limitations": [],
        }
        content_payload = self.content_payload("account_strategy_demo01", "persona_demo001")
        inventory_payload = {"revision": 1, "strategy_artifact_id": "account_strategy_demo01", "persona_artifact_id": "persona_demo001", "topic_report_artifact_id": "topic_report_demo01", "topic_id": "topic_1", "content_artifact_id": None, "content_artifact_path": None, "publication_artifact_id": None, "publication_artifact_path": None, "content_sequence_no": 1, "content_objective": "trust", "format": "text", "working_title": "验证", "same_topic_key": None, "state": "idea", "planned_publish_at": None, "hold_reason": None, "policy_check": None, "measurement_schedule": [], "history": [{"from": None, "to": "idea", "at": workflow_cli.now_iso(), "actor_id": "agent", "actor_type": "agent", "reason": "创建"}]}
        publication_payload = self.publication_payload("account_strategy_demo01", "inventory_demo01", "content_demo001")
        metrics_payload = self.snapshot_payload("publication_demo001")
        review_payload = {
            "strategy_artifact_id": "account_strategy_demo01", "content_artifact_id": "content_demo001", "snapshot_artifact_ids": ["metrics_initial01"], "baseline": {"type": "none"}, "observations": [],
            "hypotheses": [{"hypothesis_id": "hyp_1", "statement": "样本不足", "evidence_refs": [], "alternative_explanations": [], "confidence": "low"}], "diagnoses": [], "recommended_interventions": [{"type": "creative", "action": "继续采样"}],
            "lifecycle_assessment": {"current_stage": "trial", "proposed_stage": None, "confidence": "low", "evidence_refs": [], "alternative_explanations": [], "requires_human_confirmation": True},
            "persona_validation": {"persona_mode": "assumed", "hypothesis_results": [], "revision_recommended": False, "evidence_refs": []}, "trust_observations": [], "long_tail_observations": [], "limitations": ["样本不足"],
        }
        experiment_payload = {"review_artifact_id": "review_demo001", "hypothesis": "标题影响点击", "intervention_type": "creative", "independent_variable": "标题", "control": "正文不变", "target_metric": {"name": "click_rate"}, "guardrails": [], "observation_window": "72h", "sample_size_plan": "四个样本", "stop_rule": "达到样本数", "state": "proposed", "result": None, "persona_change_proposal": None, "strategy_change_proposal": None}
        fixtures = [
            json.loads(self.run_path.read_text(encoding="utf-8")),
            json.loads(self.write_artifact("account_strategy", "account_strategy_contract01", strategy_payload).read_text(encoding="utf-8")),
            json.loads(self.write_artifact("persona", "persona_contract01", persona_payload).read_text(encoding="utf-8")),
            json.loads(self.write_artifact("topic_report", "topic_report_contract01", topic_payload).read_text(encoding="utf-8")),
            json.loads(self.write_artifact("content", "content_contract01", content_payload).read_text(encoding="utf-8")),
            json.loads(self.write_artifact("inventory_item", "inventory_contract01", inventory_payload, status="idea").read_text(encoding="utf-8")),
            json.loads(self.write_artifact("publication", "publication_contract01", publication_payload, status="draft").read_text(encoding="utf-8")),
            json.loads(self.write_artifact("metrics_snapshot", "metrics_contract01", metrics_payload, status="ready").read_text(encoding="utf-8")),
            json.loads(self.write_artifact("review", "review_contract01", review_payload, status="ready").read_text(encoding="utf-8")),
            json.loads(self.write_artifact("experiment", "experiment_contract01", experiment_payload).read_text(encoding="utf-8")),
        ]
        for fixture in fixtures:
            with self.subTest(artifact_type=fixture["artifact_type"]):
                self.assertEqual(workflow_cli.validate_artifact(fixture), [])

    def test_render_escapes_untrusted_html(self) -> None:
        strategy = self.make_strategy()
        strategy_data = json.loads(strategy.read_text(encoding="utf-8"))
        payload = self.publication_payload(strategy_data["artifact_id"], "inventory_demo01", "content_demo001")
        payload["visibility"] = "<script>alert(1)</script>"
        path = self.write_artifact("publication", "publication_render01", payload, status="draft")
        output = self.root / "renders" / "demo.html"
        run_cli("render", str(path), "--format", "html", "--output", str(output))
        rendered = output.read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)


if __name__ == "__main__":
    unittest.main()
