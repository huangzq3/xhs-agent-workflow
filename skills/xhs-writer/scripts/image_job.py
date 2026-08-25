#!/usr/bin/env python3
"""Create and finalize runtime-neutral native image-generation handoffs.

This module never calls a network service. The active Agent reads the JSON job,
invokes an advertised native image capability, and exports the result to the
requested local path before finalization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.1.0"
SUPPORTED_SCHEMA_VERSIONS = {"1.0.0", SCHEMA_VERSION}
ASPECT_RE = re.compile(r"^([1-9][0-9]*):([1-9][0-9]*)$")
STATUSES = {"pending", "generated_pending_export", "completed", "failed"}


class ImageJobError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_job_id() -> str:
    timestamp = datetime.now().astimezone().strftime("%Y%m%dt%H%M%S")
    return f"image_job_{timestamp}_{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_job(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ImageJobError(f"任务不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ImageJobError(f"任务 JSON 无法解析：{exc}") from exc
    if not isinstance(value, dict):
        raise ImageJobError("任务顶层必须是 object")
    errors = validate_job(value)
    if errors:
        raise ImageJobError("任务不合法：" + "; ".join(errors))
    return value


def validate_job(job: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "job_id",
        "created_at",
        "updated_at",
        "status",
        "request",
        "capability_requirement",
        "execution",
        "output",
    }
    missing = sorted(required - set(job))
    if missing:
        errors.append("缺少顶层字段：" + ", ".join(missing))
    if job.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            "schema_version 必须是 " + " 或 ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
        )
    if not isinstance(job.get("job_id"), str) or not job.get("job_id", "").startswith("image_job_"):
        errors.append("job_id 无效")
    if job.get("status") not in STATUSES:
        errors.append("status 无效")

    request = job.get("request")
    if not isinstance(request, dict):
        errors.append("request 必须是 object")
        request = {}
    references = request.get("reference_assets")
    if not isinstance(references, list):
        errors.append("request.reference_assets 必须是 array")
        references = []
    expected_operation = "edit" if references else "generate"
    if request.get("operation") != expected_operation:
        errors.append(f"当前引用图要求 operation={expected_operation}")
    if not isinstance(request.get("prompt"), str) or not request.get("prompt", "").strip():
        errors.append("request.prompt 不能为空")
    if not isinstance(request.get("aspect_ratio"), str) or not ASPECT_RE.fullmatch(request.get("aspect_ratio", "")):
        errors.append("request.aspect_ratio 必须是 W:H")
    if not isinstance(request.get("external_processing_approved"), bool):
        errors.append("request.external_processing_approved 必须是 boolean")
    if not isinstance(request.get("requested_output_path"), str) or not request.get("requested_output_path"):
        errors.append("request.requested_output_path 不能为空")
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            errors.append(f"reference_assets[{index}] 必须是 object")
            continue
        if reference.get("external_processing_approved") is not request.get("external_processing_approved"):
            errors.append(f"reference_assets[{index}] 的外部处理批准与任务不一致")
        digest = reference.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            errors.append(f"reference_assets[{index}].sha256 无效")

    requirement = job.get("capability_requirement")
    if not isinstance(requirement, dict):
        errors.append("capability_requirement 必须是 object")
        requirement = {}
    if requirement.get("kind") != "native_image_generation":
        errors.append("capability_requirement.kind 无效")
    boundary = requirement.get("processing_boundary")
    if boundary not in {"local", "external"}:
        errors.append("capability_requirement.processing_boundary 无效")
    if boundary == "external" and request.get("external_processing_approved") is not True:
        errors.append("外部处理任务必须绑定 G0 外部处理批准")
    if boundary == "local" and request.get("external_processing_approved") is not False:
        errors.append("本地处理任务不应记录外部处理批准")
    if requirement.get("supports_reference_images") is not bool(references):
        errors.append("capability_requirement.supports_reference_images 与引用图不一致")
    if requirement.get("must_return_local_file") is not True:
        errors.append("capability_requirement.must_return_local_file 必须为 true")

    execution = job.get("execution")
    if not isinstance(execution, dict):
        errors.append("execution 必须是 object")
        execution = {}
    if job.get("status") in {"generated_pending_export", "completed", "failed"} and not execution.get("capability_id"):
        errors.append("已执行任务必须记录 capability_id")
    output = job.get("output")
    if job.get("status") == "completed" and not isinstance(output, dict):
        errors.append("completed 任务必须包含 output")
    if job.get("status") != "completed" and job.get("output") is not None:
        errors.append("未完成任务的 output 必须为 null")
    if job.get("status") == "completed" and isinstance(output, dict):
        if not isinstance(output.get("uri"), str) or not output.get("uri"):
            errors.append("output.uri 不能为空")
        if not isinstance(output.get("sha256"), str) or not re.fullmatch(
            r"[a-f0-9]{64}", output.get("sha256", "")
        ):
            errors.append("output.sha256 无效")
        if not isinstance(output.get("media_type"), str) or not output.get(
            "media_type", ""
        ).startswith("image/"):
            errors.append("output.media_type 必须是 image/*")
        if job.get("schema_version") == "1.0.0":
            if not isinstance(output.get("width"), int) or output.get("width", 0) <= 0:
                errors.append("1.0.0 output.width 必须是正整数")
            if not isinstance(output.get("height"), int) or output.get("height", 0) <= 0:
                errors.append("1.0.0 output.height 必须是正整数")
            if not isinstance(output.get("aspect_ratio"), str) or not ASPECT_RE.fullmatch(
                output.get("aspect_ratio", "")
            ):
                errors.append("1.0.0 output.aspect_ratio 无效")
        else:
            if not isinstance(output.get("size_bytes"), int) or output.get("size_bytes", 0) <= 0:
                errors.append("1.1.0 output.size_bytes 必须是正整数")
            if not execution.get("result_reference"):
                errors.append("1.1.0 completed 任务必须记录 Agent 原生生图结果引用")
    if job.get("status") == "failed" and not execution.get("error"):
        errors.append("failed 任务必须记录 error")
    return errors


def command_create(args: argparse.Namespace) -> None:
    job_path = Path(args.job).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if job_path.exists():
        raise ImageJobError(f"不覆盖已有任务：{job_path}")
    if output_path.exists():
        raise ImageJobError(f"不覆盖已有图片：{output_path}")
    if not ASPECT_RE.fullmatch(args.aspect_ratio):
        raise ImageJobError("--aspect-ratio 必须是 W:H，例如 3:4")
    if args.processing_boundary == "external" and not args.external_processing_approved:
        raise ImageJobError("外部原生生图能力需要 G0 外部处理批准")
    if args.processing_boundary == "local" and args.external_processing_approved:
        raise ImageJobError("本地处理请勿标记 --external-processing-approved")
    external_processing_approved = args.processing_boundary == "external"

    references: list[dict[str, Any]] = []
    for raw_path in args.reference:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise ImageJobError(f"引用图不存在：{path}")
        references.append(
            {
                "uri": str(path),
                "sha256": sha256_file(path),
                "external_processing_approved": external_processing_approved,
            }
        )

    timestamp = now_iso()
    job = {
        "schema_version": SCHEMA_VERSION,
        "job_id": new_job_id(),
        "created_at": timestamp,
        "updated_at": timestamp,
        "status": "pending",
        "request": {
            "operation": "edit" if references else "generate",
            "prompt": args.prompt.strip(),
            "aspect_ratio": args.aspect_ratio,
            "external_processing_approved": external_processing_approved,
            "reference_assets": references,
            "requested_output_path": str(output_path),
        },
        "capability_requirement": {
            "kind": "native_image_generation",
            "processing_boundary": args.processing_boundary,
            "supports_reference_images": bool(references),
            "must_return_local_file": True,
        },
        "execution": {
            "runtime_name": None,
            "capability_id": None,
            "started_at": None,
            "completed_at": None,
            "result_reference": None,
            "error": None,
        },
        "output": None,
    }
    errors = validate_job(job)
    if errors:
        raise ImageJobError("create 产生了无效任务：" + "; ".join(errors))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(job_path, job)
    print(job_path)


def command_mark_generated(args: argparse.Namespace) -> None:
    path = Path(args.job).expanduser().resolve()
    job = load_job(path)
    if job["status"] != "pending":
        raise ImageJobError("只能将 pending 任务标记为待导出")
    timestamp = now_iso()
    job["status"] = "generated_pending_export"
    job["updated_at"] = timestamp
    job["execution"].update(
        {
            "runtime_name": args.runtime_name,
            "capability_id": args.capability_id,
            "started_at": timestamp,
            "result_reference": args.result_reference,
        }
    )
    atomic_write_json(path, job)
    print(path)


def detect_image_media_type(path: Path) -> str:
    """Identify common Agent image outputs by signature without decoding pixels."""
    with path.open("rb") as handle:
        header = handle.read(16)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"BM"):
        return "image/bmp"
    guessed = mimetypes.guess_type(path.name)[0]
    if guessed and guessed.startswith("image/"):
        raise ImageJobError(
            f"文件扩展名看似图片，但签名无法确认：{path}；请重新导出 Agent 生成结果"
        )
    raise ImageJobError(f"Agent 生成结果不是受支持的图片文件：{path}")


def command_finalize(args: argparse.Namespace) -> None:
    path = Path(args.job).expanduser().resolve()
    job = load_job(path)
    if job["status"] not in {"pending", "generated_pending_export"}:
        raise ImageJobError("只能完成 pending 或 generated_pending_export 任务")
    output_path = Path(job["request"]["requested_output_path"])
    if not output_path.is_file():
        raise ImageJobError(f"生成结果尚未导出到：{output_path}")
    capability_id = args.capability_id or job["execution"].get("capability_id")
    if not capability_id:
        raise ImageJobError("完成任务前必须记录实际 capability_id")

    size_bytes = output_path.stat().st_size
    if size_bytes <= 0:
        raise ImageJobError(f"Agent 生成结果为空文件：{output_path}")
    media_type = detect_image_media_type(output_path)
    result_reference = args.result_reference or job["execution"].get("result_reference")
    if not result_reference:
        raise ImageJobError("完成任务前必须记录 AI Agent 原生生图结果引用")

    timestamp = now_iso()
    job["status"] = "completed"
    job["updated_at"] = timestamp
    job["execution"].update(
        {
            "runtime_name": args.runtime_name or job["execution"].get("runtime_name"),
            "capability_id": capability_id,
            "started_at": job["execution"].get("started_at") or timestamp,
            "completed_at": timestamp,
            "result_reference": result_reference,
            "error": None,
        }
    )
    job["output"] = {
        "uri": str(output_path.resolve()),
        "sha256": sha256_file(output_path),
        "media_type": media_type,
        "size_bytes": size_bytes,
    }
    errors = validate_job(job)
    if errors:
        raise ImageJobError("finalize 产生了无效任务：" + "; ".join(errors))
    atomic_write_json(path, job)
    print(path)


def command_fail(args: argparse.Namespace) -> None:
    path = Path(args.job).expanduser().resolve()
    job = load_job(path)
    if job["status"] == "completed":
        raise ImageJobError("不能将已完成任务改为 failed")
    timestamp = now_iso()
    job["status"] = "failed"
    job["updated_at"] = timestamp
    job["execution"].update(
        {
            "runtime_name": args.runtime_name or job["execution"].get("runtime_name"),
            "capability_id": args.capability_id or job["execution"].get("capability_id"),
            "started_at": job["execution"].get("started_at") or timestamp,
            "completed_at": timestamp,
            "error": args.reason,
        }
    )
    if not job["execution"].get("capability_id"):
        raise ImageJobError("failed 任务仍必须记录尝试的 capability_id")
    job["output"] = None
    errors = validate_job(job)
    if errors:
        raise ImageJobError("fail 产生了无效任务：" + "; ".join(errors))
    atomic_write_json(path, job)
    print(path)


def command_validate(args: argparse.Namespace) -> None:
    path = Path(args.job).expanduser().resolve()
    load_job(path)
    print(f"PASS: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native image-generation JSON handoff; performs no network calls")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="创建待原生生图能力执行的 JSON 任务")
    create.add_argument("--job", required=True)
    create.add_argument("--output", required=True)
    create.add_argument("--prompt", required=True)
    create.add_argument("--aspect-ratio", default="3:4")
    create.add_argument("--processing-boundary", choices=["local", "external"], required=True)
    create.add_argument("--reference", action="append", default=[])
    create.add_argument("--external-processing-approved", action="store_true")
    create.set_defaults(func=command_create)

    mark = subparsers.add_parser("mark-generated", help="原生工具已生成，但结果尚未导出到本地")
    mark.add_argument("--job", required=True)
    mark.add_argument("--capability-id", required=True)
    mark.add_argument("--runtime-name")
    mark.add_argument("--result-reference", required=True)
    mark.set_defaults(func=command_mark_generated)

    finalize = subparsers.add_parser("finalize", help="登记 Agent 导出的图片文件并完成任务")
    finalize.add_argument("--job", required=True)
    finalize.add_argument("--capability-id")
    finalize.add_argument("--runtime-name")
    finalize.add_argument("--result-reference")
    finalize.set_defaults(func=command_finalize)

    fail = subparsers.add_parser("fail", help="记录原生生图失败")
    fail.add_argument("--job", required=True)
    fail.add_argument("--capability-id")
    fail.add_argument("--runtime-name")
    fail.add_argument("--reason", required=True)
    fail.set_defaults(func=command_fail)

    validate = subparsers.add_parser("validate", help="校验 image_job JSON")
    validate.add_argument("--job", required=True)
    validate.set_defaults(func=command_validate)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except ImageJobError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
