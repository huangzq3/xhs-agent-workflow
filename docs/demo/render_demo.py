#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = PACKAGE_ROOT / "skills" / "xhs-workflow" / "scripts" / "workflow_cli.py"
DEMO_FILES = {
    "account-strategy": Path(__file__).with_name("account-strategy.json"),
    "persona": Path(__file__).with_name("persona.json"),
}


def load_workflow_cli():
    spec = importlib.util.spec_from_file_location("xhs_workflow_cli", CLI_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载当前 workflow_cli.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="校验并渲染 README 的 V2.6.0 虚构演示")
    parser.add_argument("--output-dir", required=True, help="HTML 输出目录")
    args = parser.parse_args()

    workflow_cli = load_workflow_cli()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for output_name, artifact_path in DEMO_FILES.items():
        artifact = workflow_cli.load_json(artifact_path)
        errors = workflow_cli.validate_artifact(artifact)
        if errors:
            joined = "; ".join(errors)
            raise RuntimeError(f"{artifact_path.name} 校验失败：{joined}")
        output_path = output_dir / f"{output_name}.html"
        output_path.write_text(
            workflow_cli.html_render(artifact, account_display_name="示例账号（虚构）"),
            encoding="utf-8",
        )
        print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
