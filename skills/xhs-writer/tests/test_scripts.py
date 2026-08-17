from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # Pillow 是可选依赖；缺失时跳过而不是让整个套件报错
    Image = None


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"

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
        blocked_modules = {"openai", "requests", "httpx", "aiohttp", "socket", "http.client", "urllib.request"}
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

    def test_analyze_material_recurses_and_hashes(self) -> None:
        nested = self.root / "materials" / "nested"
        nested.mkdir(parents=True)
        visible = nested / "note.txt"
        visible.write_text("hello", encoding="utf-8")
        hidden = nested / ".secret.txt"
        hidden.write_text("secret", encoding="utf-8")
        output = self.root / "materials.json"
        run_script("analyze_material.py", str(self.root / "materials"), "--out", str(output))
        manifest = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "2.2.0")
        self.assertEqual(len(manifest["materials"]), 1)
        self.assertEqual(
            manifest["materials"][0]["sha256"],
            hashlib.sha256(b"hello").hexdigest(),
        )
        self.assertEqual(manifest["materials"][0]["rights_status"], "pending")
        self.assertIs(manifest["materials"][0]["external_processing_approved"], False)

    @unittest.skipUnless(Image is not None, "requires Pillow (optional dependency)")
    def test_local_text_card_and_overlay_have_exact_dimensions(self) -> None:
        card = self.root / "card.png"
        run_script(
            "render_text_card.py",
            str(card),
            "--text",
            "A clear title",
            "--size",
            "300x400",
            "--font-size",
            "36",
        )
        with Image.open(card) as image:
            self.assertEqual(image.size, (300, 400))
        source = self.root / "source.png"
        Image.new("RGB", (600, 600), "navy").save(source)
        overlay = self.root / "overlay.png"
        run_script(
            "text_on_image.py",
            str(source),
            str(overlay),
            "--text",
            "Test",
            "--fit",
            "3:4",
            "--canvas-size",
            "300x400",
            "--size",
            "30",
        )
        with Image.open(overlay) as image:
            self.assertEqual(image.size, (300, 400))

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

    @unittest.skipUnless(Image is not None, "requires Pillow (optional dependency)")
    def test_native_image_job_handoff_and_local_finalization(self) -> None:
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
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["capability_requirement"]["kind"], "native_image_generation")

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

        Image.new("RGB", (300, 400), "white").save(output)
        run_script("image_job.py", "finalize", "--job", str(job_path))
        completed = json.loads(job_path.read_text(encoding="utf-8"))
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"]["width"], 300)
        self.assertEqual(completed["output"]["height"], 400)
        self.assertEqual(completed["output"]["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertEqual(completed["execution"]["capability_id"], "native:test-image")
        run_script("image_job.py", "validate", "--job", str(job_path))

    @unittest.skipUnless(Image is not None, "requires Pillow (optional dependency)")
    def test_reference_image_requires_external_processing_approval(self) -> None:
        reference = self.root / "reference.png"
        Image.new("RGB", (300, 400), "navy").save(reference)
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
