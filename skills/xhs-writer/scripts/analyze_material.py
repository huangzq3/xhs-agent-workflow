#!/usr/bin/env python3
"""Recursively inventory user-provided materials without uploading them."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


TEXT_EXT = {".txt", ".md", ".rtf", ".html", ".htm", ".json", ".csv"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in TEXT_EXT:
        return "text"
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    return "unknown"


def is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def expand_paths(raw_paths: list[str], include_unknown: bool) -> tuple[list[Path], list[dict]]:
    files: dict[str, Path] = {}
    errors: list[dict] = []
    for raw in raw_paths:
        path = Path(raw).expanduser()
        if not path.exists():
            errors.append({"path": raw, "error": "not found"})
            continue
        candidates = [path] if path.is_file() else path.rglob("*")
        for candidate in candidates:
            if not candidate.is_file() or is_hidden(candidate.relative_to(path.parent if path.is_file() else path)):
                continue
            resolved = candidate.resolve()
            if classify(resolved) == "unknown" and not include_unknown:
                continue
            files[str(resolved)] = resolved
    return [files[key] for key in sorted(files)], errors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_info(path: Path) -> dict:
    if not shutil.which("ffprobe"):
        return {"metadata_error": "ffprobe not installed"}
    try:
        output = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=width,height,codec_type",
                "-of",
                "json",
                str(path),
            ],
            stderr=subprocess.STDOUT,
        )
        data = json.loads(output)
        duration = float(data.get("format", {}).get("duration", 0))
        video = next(
            (stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"),
            {},
        )
        return {
            "duration_seconds": round(duration, 3),
            "width": video.get("width"),
            "height": video.get("height"),
        }
    except Exception as exc:
        return {"metadata_error": str(exc)}


def extract_frames(path: Path, output_dir: Path, count: int) -> list[str]:
    if not shutil.which("ffmpeg") or count <= 0:
        return []
    info = video_info(path)
    duration = info.get("duration_seconds", 0) or 0
    if duration <= 0:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[str] = []
    safe_stem = "".join(char if char.isalnum() or char in "-_" else "_" for char in path.stem)
    for index in range(count):
        timestamp = duration * (index + 0.5) / count
        output = output_dir / f"{safe_stem}_{sha256_file(path)[:8]}_f{index + 1:02d}.jpg"
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(output),
                ],
                check=True,
            )
            frames.append(str(output.resolve()))
        except subprocess.CalledProcessError:
            continue
    return frames


def text_preview(path: Path, limit: int = 400) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError as exc:
        return f"<read error: {exc}>"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--frames-dir")
    parser.add_argument("--frames-per-video", type=int, default=0)
    parser.add_argument("--include-unknown", action="store_true")
    args = parser.parse_args()

    paths, errors = expand_paths(args.paths, args.include_unknown)
    items: list[dict] = []
    frames_dir = Path(args.frames_dir).resolve() if args.frames_dir else None
    for index, path in enumerate(paths, start=1):
        kind = classify(path)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        item = {
            "asset_id": f"asset_{index:04d}",
            "uri": str(path),
            "kind": kind,
            "media_type": media_type,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "rights_basis": None,
            "rights_status": "pending",
            "license_or_permission_ref": None,
            "contains_personal_data": None,
            "external_processing_approved": False,
            "generation_job_id": None,
            "generator_capability_id": None,
            "caption": "",
            "intended_usage": "",
        }
        if kind == "image":
            item["visual_review_status"] = "pending_agent_review"
        elif kind == "video":
            item.update(video_info(path))
            if frames_dir:
                item["derived_frames"] = extract_frames(path, frames_dir, args.frames_per_video)
        elif kind == "text":
            item["preview"] = text_preview(path)
        items.append(item)

    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "2.2.0",
        "generated_at": now_iso(),
        "materials": items,
        "errors": errors,
    }
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {output} ({len(items)} files, {len(errors)} errors)")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
