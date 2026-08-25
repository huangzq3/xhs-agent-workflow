from __future__ import annotations

import ast
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SKILL_ROOT.parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

def run_script(name: str, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"{name} returncode={result.returncode}, expected={expected}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


class WriterScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_writer_has_no_direct_image_service_integration(self) -> None:
        blocked_modules = {
            "PIL", "openai", "requests", "httpx", "aiohttp", "socket",
            "http.client", "urllib.request",
        }
        for path in sorted(SCRIPTS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
            self.assertFalse(blocked_modules & imports, f"{path.name} imports a direct network/image service module")
        self.assertFalse((SCRIPTS / "image_generator.py").exists())
        self.assertFalse((SKILL_ROOT / ".env.example").exists())

    def test_writer_has_no_pillow_or_local_raster_implementation(self) -> None:
        for removed in ("render_text_card.py", "text_on_image.py", "collage_3x4.py"):
            self.assertFalse((SCRIPTS / removed).exists(), removed)
        requirements = (PACKAGE_ROOT / "requirements-optional.txt").read_text(encoding="utf-8")
        installer = (PACKAGE_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("Pillow", requirements)
        self.assertNotIn("PIL", installer)
        self.assertNotIn("Pillow", installer)

    def test_analyze_material_recurses_and_hashes(self) -> None:
        nested = self.root / "materials" / "nested"
        nested.mkdir(parents=True)
        visible = nested / "note.txt"
        visible.write_text("hello", encoding="utf-8")
        image = nested / "sample.png"
        image.write_bytes(PNG_1X1)
        hidden = nested / ".secret.txt"
        hidden.write_text("secret", encoding="utf-8")
        output = self.root / "materials.json"
        run_script("analyze_material.py", str(self.root / "materials"), "--out", str(output))
        manifest = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "2.2.0")
        self.assertEqual(len(manifest["materials"]), 2)
        text_item = next(item for item in manifest["materials"] if item["kind"] == "text")
        image_item = next(item for item in manifest["materials"] if item["kind"] == "image")
        self.assertEqual(
            text_item["sha256"],
            hashlib.sha256(b"hello").hexdigest(),
        )
        self.assertEqual(text_item["rights_status"], "pending")
        self.assertIs(text_item["external_processing_approved"], False)
        self.assertEqual(image_item["visual_review_status"], "pending_agent_review")
        self.assertNotIn("width", image_item)
        self.assertNotIn("height", image_item)

    def test_watermark_removal_is_blocked(self) -> None:
        output = self.root / "out.png"
        result = run_script(
            "crop_watermark.py",
            str(self.root / "in.png"),
            str(output),
            "--edge",
            "bottom",
            expected=2,
        )
        self.assertIn("已停用", result.stderr)
        self.assertFalse(output.exists())

    def test_native_image_job_handoff_and_agent_output_registration(self) -> None:
        job_path = self.root / "image_job.json"
        output = self.root / "generated.png"
        run_script(
            "image_job.py",
            "create",
            "--job",
            str(job_path),
            "--output",
            str(output),
            "--prompt",
            "Create a minimal vertical card",
            "--aspect-ratio",
            "3:4",
            "--processing-boundary",
            "local",
        )
        pending = json.loads(job_path.read_text(encoding="utf-8"))
        self.assertEqual(pending["schema_version"], "1.1.0")
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["capability_requirement"]["kind"], "native_image_generation")

        output.write_bytes(PNG_1X1)
        unproven = run_script(
            "image_job.py",
            "finalize",
            "--job",
            str(job_path),
            "--capability-id",
            "native:test-image",
            expected=2,
        )
        self.assertIn("Agent 原生生图结果引用", unproven.stderr)

        run_script(
            "image_job.py",
            "mark-generated",
            "--job",
            str(job_path),
            "--capability-id",
            "native:test-image",
            "--runtime-name",
            "test-runtime",
            "--result-reference",
            "attachment:test-001",
        )
        marked = json.loads(job_path.read_text(encoding="utf-8"))
        self.assertEqual(marked["status"], "generated_pending_export")

        run_script("image_job.py", "finalize", "--job", str(job_path))
        completed = json.loads(job_path.read_text(encoding="utf-8"))
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"]["media_type"], "image/png")
        self.assertEqual(completed["output"]["size_bytes"], len(PNG_1X1))
        self.assertNotIn("width", completed["output"])
        self.assertNotIn("height", completed["output"])
        self.assertEqual(completed["output"]["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertEqual(completed["execution"]["capability_id"], "native:test-image")
        run_script("image_job.py", "validate", "--job", str(job_path))

    def test_reference_image_requires_external_processing_approval(self) -> None:
        reference = self.root / "reference.png"
        reference.write_bytes(PNG_1X1)
        job_path = self.root / "edit_job.json"
        output = self.root / "edited.png"
        result = run_script(
            "image_job.py",
            "create",
            "--job",
            str(job_path),
            "--output",
            str(output),
            "--prompt",
            "Restyle the approved reference",
            "--processing-boundary",
            "external",
            "--reference",
            str(reference),
            expected=2,
        )
        self.assertIn("外部处理批准", result.stderr)
        self.assertFalse(job_path.exists())

        run_script(
            "image_job.py",
            "create",
            "--job",
            str(job_path),
            "--output",
            str(output),
            "--prompt",
            "Restyle the approved reference",
            "--processing-boundary",
            "external",
            "--reference",
            str(reference),
            "--external-processing-approved",
        )
        created = json.loads(job_path.read_text(encoding="utf-8"))
        self.assertEqual(created["request"]["operation"], "edit")
        self.assertTrue(created["request"]["reference_assets"][0]["external_processing_approved"])

    def test_legacy_image_job_10_remains_readable(self) -> None:
        output = self.root / "legacy.png"
        output.write_bytes(PNG_1X1)
        legacy = {
            "schema_version": "1.0.0",
            "job_id": "image_job_legacy_test",
            "created_at": "2026-08-25T12:00:00+08:00",
            "updated_at": "2026-08-25T12:01:00+08:00",
            "status": "completed",
            "request": {
                "operation": "generate",
                "prompt": "Legacy native image output",
                "aspect_ratio": "3:4",
                "external_processing_approved": False,
                "reference_assets": [],
                "requested_output_path": str(output),
            },
            "capability_requirement": {
                "kind": "native_image_generation",
                "processing_boundary": "local",
                "supports_reference_images": False,
                "must_return_local_file": True,
            },
            "execution": {
                "runtime_name": "legacy-runtime",
                "capability_id": "native:legacy-image",
                "started_at": "2026-08-25T12:00:00+08:00",
                "completed_at": "2026-08-25T12:01:00+08:00",
                "result_reference": None,
                "error": None,
            },
            "output": {
                "uri": str(output),
                "sha256": hashlib.sha256(PNG_1X1).hexdigest(),
                "media_type": "image/png",
                "width": 3,
                "height": 4,
                "aspect_ratio": "3:4",
            },
        }
        job_path = self.root / "legacy_image_job.json"
        job_path.write_text(json.dumps(legacy), encoding="utf-8")
        run_script("image_job.py", "validate", "--job", str(job_path))

    def test_asset_rights_validator_checks_hash(self) -> None:
        asset = self.root / "asset.txt"
        asset.write_text("owned", encoding="utf-8")
        digest = hashlib.sha256(b"owned").hexdigest()
        artifact = {
            "artifact_type": "content",
            "payload": {
                "assets": [
                    {
                        "asset_id": "asset_1",
                        "uri": str(asset),
                        "sha256": digest,
                        "rights_basis": "owned",
                        "rights_status": "verified",
                        "license_or_permission_ref": None,
                        "contains_personal_data": False,
                        "external_processing_approved": False,
                        "generation_job_id": None,
                        "generator_capability_id": None,
                    }
                ]
            },
        }
        path = self.root / "content.json"
        path.write_text(json.dumps(artifact), encoding="utf-8")
        run_script("validate_asset_rights.py", str(path))
        artifact["payload"]["assets"][0]["sha256"] = "0" * 64
        path.write_text(json.dumps(artifact), encoding="utf-8")
        run_script("validate_asset_rights.py", str(path), expected=2)


if __name__ == "__main__":
    unittest.main()
