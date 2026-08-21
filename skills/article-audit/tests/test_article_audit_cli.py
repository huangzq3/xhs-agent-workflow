from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "article_audit_cli.py"
SCHEMA = SKILL_ROOT / "references" / "article-audit.schema.json"
SPEC = importlib.util.spec_from_file_location("article_audit_cli", SCRIPT)
assert SPEC and SPEC.loader
audit_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_cli)


class ArticleAuditContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.content = {
            "schema_version": "2.2.0",
            "artifact_type": "content",
            "artifact_id": "content_demo001",
            "account_id": "demo_account",
            "run_id": "run_demo001",
            "created_at": "2026-08-21T12:00:00+08:00",
            "updated_at": "2026-08-21T12:00:00+08:00",
            "status": "review_required",
            "provenance": [],
            "approvals": [],
            "payload": {
                "revision": 1,
                "format": "text",
                "title": "如何验证一篇文章",
                "caption": "先核对事实，再判断表达。",
                "hashtags": ["文章审计"],
                "claims": [],
                "personal_experiences": [],
                "assets": [],
                "change_summary": ["初稿"],
                "authorship": {
                    "actor_type": "agent",
                    "actor_id": "writer_agent_001",
                    "context_id": "writer_context_001",
                    "model_id": "model-a",
                },
                "article_audit_ref": None,
            },
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_audit(self) -> dict:
        return {
            "schema_version": "2.2.0",
            "artifact_type": "article_audit",
            "artifact_id": "article_audit_demo001",
            "account_id": "demo_account",
            "run_id": "run_demo001",
            "created_at": "2026-08-21T12:05:00+08:00",
            "updated_at": "2026-08-21T12:05:00+08:00",
            "status": "ready",
            "provenance": [],
            "approvals": [],
            "payload": {
                "contract_version": "1.0.0",
                "content_artifact_id": "content_demo001",
                "content_revision": 1,
                "target_uri": "artifacts/demo_account/content/content_demo001.json",
                "content_sha256": audit_cli.auditable_content_hash(self.content),
                "hash_mode": "canonical_json",
                "author": copy.deepcopy(self.content["payload"]["authorship"]),
                "reviewer": {
                    "actor_type": "agent",
                    "actor_id": "audit_agent_001",
                    "context_id": "audit_context_001",
                    "model_id": "model-b",
                },
                "independence": {
                    "separate_agent": True,
                    "separate_context": True,
                    "read_only": True,
                    "prompt_injection_treated_as_data": True,
                    "evidence": ["由编排器创建全新只读审计上下文"],
                },
                "ruleset": {
                    "ruleset_id": "article-audit-core",
                    "version": "1.0.0",
                    "core_dimensions": sorted(audit_cli.CORE_DIMENSIONS),
                    "custom_profile_refs": [],
                },
                "scope": {
                    "surface_paths": ["payload.title", "payload.caption", "payload.hashtags"],
                    "evidence_refs": [],
                    "limitations": [],
                },
                "risk": {"level": "low", "reasons": [], "model_diversity_used": False},
                "claim_inventory": {
                    "method": "independent_full_text_review",
                    "coverage_notes": ["完整阅读所有最终呈现表面"],
                    "claims": [
                        {
                            "claim_id": "claim_audit_1",
                            "text": "建议先核对事实",
                            "kind": "opinion",
                            "materiality": "non_material",
                            "surface_path": "payload.caption",
                            "source_refs": [],
                            "verification_status": "not_applicable",
                        }
                    ],
                },
                "findings": [],
                "summary": {
                    "verdict": "passed",
                    "counts": {"P0": 0, "P1": 0, "P2": 0},
                    "limitations": [],
                },
            },
        }

    def test_valid_independent_audit_passes(self) -> None:
        audit = self.make_audit()
        self.assertEqual(audit_cli.validate_audit_document(audit, content=self.content), [])

    def test_content_hash_ignores_only_audit_link(self) -> None:
        baseline = audit_cli.auditable_content_hash(self.content)
        linked = copy.deepcopy(self.content)
        linked["payload"]["article_audit_ref"] = {
            "artifact_id": "article_audit_demo001",
            "artifact_path": "artifacts/demo_account/article_audit/article_audit_demo001.json",
            "payload_sha256": "0" * 64,
            "content_sha256": baseline,
        }
        self.assertEqual(audit_cli.auditable_content_hash(linked), baseline)
        linked["payload"]["caption"] = "正文已经变化。"
        self.assertNotEqual(audit_cli.auditable_content_hash(linked), baseline)
        evidence_changed = copy.deepcopy(self.content)
        evidence_changed["provenance"].append({"kind": "web_source", "summary": "来源已更换"})
        self.assertNotEqual(audit_cli.auditable_content_hash(evidence_changed), baseline)

    def test_same_agent_or_context_is_rejected(self) -> None:
        audit = self.make_audit()
        audit["payload"]["reviewer"]["actor_id"] = "writer_agent_001"
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("actor_id 必须不同" in error for error in errors))

        audit = self.make_audit()
        audit["payload"]["reviewer"]["context_id"] = "writer_context_001"
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("context_id 必须不同" in error for error in errors))

    def test_prompt_injection_boundary_and_read_only_are_required(self) -> None:
        audit = self.make_audit()
        audit["payload"]["independence"]["read_only"] = False
        audit["payload"]["independence"]["prompt_injection_treated_as_data"] = False
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("read_only 必须为 true" in error for error in errors))
        self.assertTrue(any("prompt_injection_treated_as_data 必须为 true" in error for error in errors))

    def test_final_cards_and_assets_must_be_in_scope(self) -> None:
        content = copy.deepcopy(self.content)
        content["payload"].update({
            "format": "image",
            "cards": [{"card_id": "card_1", "text": "最终卡片文字"}],
            "assets": [{"asset_id": "asset_1", "uri": "cover.png"}],
        })
        audit = self.make_audit()
        audit["payload"]["content_sha256"] = audit_cli.auditable_content_hash(content)
        audit["payload"]["scope"]["surface_paths"].append("payload.cards")
        errors = audit_cli.validate_audit_document(audit, content=content)
        self.assertTrue(any("审计未覆盖最终呈现表面：payload.assets" in error for error in errors))

    def test_material_unverified_fact_requires_open_p0_and_failed_verdict(self) -> None:
        audit = self.make_audit()
        audit["payload"]["claim_inventory"]["claims"] = [
            {
                "claim_id": "claim_fact_1",
                "text": "成功率提高三倍",
                "kind": "fact",
                "materiality": "material",
                "surface_path": "payload.caption",
                "source_refs": [],
                "verification_status": "unverified",
            }
        ]
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("开放 P0" in error for error in errors))

        audit["payload"]["findings"] = [
            {
                "finding_id": "finding_1",
                "severity": "P0",
                "dimension": "fact_and_source",
                "surface_path": "payload.caption",
                "locator": "caption 第 1 句",
                "excerpt": "成功率提高三倍",
                "issue": "关键数据没有来源",
                "claim_refs": ["claim_fact_1"],
                "evidence_refs": [],
                "recommendation": "删除或补充可核对来源",
                "status": "open",
            }
        ]
        audit["payload"]["summary"] = {
            "verdict": "audit_failed",
            "counts": {"P0": 1, "P1": 0, "P2": 0},
            "limitations": ["没有可用来源"],
        }
        self.assertEqual(audit_cli.validate_audit_document(audit, content=self.content), [])

    def test_verified_fact_must_reference_a_registered_source(self) -> None:
        audit = self.make_audit()
        audit["payload"]["claim_inventory"]["claims"] = [{
            "claim_id": "claim_fact_1",
            "text": "某项研究已经发布",
            "kind": "fact",
            "materiality": "non_material",
            "surface_path": "payload.caption",
            "source_refs": ["source_missing"],
            "verification_status": "verified",
        }]
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("引用未登记来源：source_missing" in error for error in errors))

        audit["provenance"] = [{
            "source_id": "source_missing",
            "kind": "web_source",
            "captured_at": "2026-08-21T12:01:00+08:00",
            "summary": "可核对的原始来源",
            "url": "https://example.com/source",
        }]
        self.assertEqual(audit_cli.validate_audit_document(audit, content=self.content), [])

    def test_malformed_list_items_report_errors_instead_of_crashing(self) -> None:
        audit = self.make_audit()
        audit["payload"]["ruleset"]["core_dimensions"][0] = {"bad": "value"}
        audit["payload"]["findings"] = [{
            "finding_id": "finding_badrefs",
            "severity": "P2",
            "dimension": "language_and_terminology",
            "surface_path": "payload.caption",
            "locator": "正文",
            "excerpt": "",
            "issue": "用词可优化",
            "claim_refs": [{"bad": "ref"}],
            "evidence_refs": [],
            "recommendation": "核对用词",
            "status": "open",
        }]
        audit["payload"]["summary"]["counts"]["P2"] = 1
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("core_dimensions 必须是字符串" in error for error in errors))
        self.assertTrue(any("claim_refs 必须是非空字符串" in error for error in errors))

    def test_high_risk_same_model_cannot_pass(self) -> None:
        audit = self.make_audit()
        audit["payload"]["reviewer"]["model_id"] = "model-a"
        audit["payload"]["risk"] = {
            "level": "high",
            "reasons": ["高风险专业主张"],
            "model_diversity_used": False,
        }
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("不能 verdict=passed" in error for error in errors))
        audit["payload"]["summary"]["verdict"] = "human_decision_required"
        audit["payload"]["summary"]["limitations"] = ["未使用不同模型复核"]
        self.assertEqual(audit_cli.validate_audit_document(audit, content=self.content), [])

    def test_coverage_and_high_risk_reason_cannot_be_empty(self) -> None:
        audit = self.make_audit()
        audit["payload"]["claim_inventory"]["coverage_notes"] = []
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("coverage_notes 至少需要" in error for error in errors))

        audit = self.make_audit()
        audit["payload"]["risk"] = {
            "level": "high",
            "reasons": [],
            "model_diversity_used": True,
        }
        errors = audit_cli.validate_audit_document(audit, content=self.content)
        self.assertTrue(any("level=high 时必须记录风险原因" in error for error in errors))

    def test_schema_and_cli_validate_same_fixture(self) -> None:
        audit = self.make_audit()
        content_path = self.root / "content.json"
        audit_path = self.root / "audit.json"
        content_path.write_text(json.dumps(self.content, ensure_ascii=False), encoding="utf-8")
        audit_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", str(audit_path), "--content", str(content_path)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)

        try:
            import jsonschema
        except ImportError:
            return
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(audit)

    def test_generic_markdown_target_uses_raw_bytes_without_xhs_envelope(self) -> None:
        target_path = self.root / "article.md"
        target_path.write_text("# 标题\n\n这是一篇通用文章。\n", encoding="utf-8")
        digest, mode = audit_cli.content_hash_from_path(target_path)
        self.assertEqual(mode, "raw_bytes")

        audit = self.make_audit()
        audit.update({
            "schema_version": "article-audit/1.0.0",
            "account_id": None,
            "run_id": None,
        })
        audit["payload"].update({
            "content_artifact_id": "document_article001",
            "content_revision": None,
            "target_uri": str(target_path),
            "content_sha256": digest,
            "hash_mode": mode,
            "author": {
                "actor_type": "human",
                "actor_id": "author_001",
                "context_id": None,
                "model_id": None,
            },
            "scope": {
                "surface_paths": ["title", "body"],
                "evidence_refs": [],
                "limitations": [],
            },
        })
        audit["payload"]["claim_inventory"]["claims"][0].update({
            "text": "这是一篇通用文章",
            "surface_path": "body",
        })
        audit_path = self.root / "generic-audit.json"
        audit_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", str(audit_path), "--target", str(target_path)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(audit_cli.validate_audit_target(audit, target_path), [])

        try:
            import jsonschema
        except ImportError:
            return
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(audit)


if __name__ == "__main__":
    unittest.main()
