#!/usr/bin/env python3
"""Validate local assets and rights entries in a V2 content artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


RIGHTS_BASES = {"owned", "licensed", "permission", "public_domain", "generated"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_path(uri: str, artifact_path: Path) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme:
        return None
    candidate = Path(uri).expanduser()
    if not candidate.is_absolute():
        candidate = artifact_path.parent / candidate
    return candidate.resolve()


def validate(path: Path) -> list[str]:
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"无法读取 JSON：{exc}"]
    if not isinstance(artifact, dict) or artifact.get("artifact_type") != "content":
        return ["文件必须是 V2 content artifact"]
    payload = artifact.get("payload")
    if not isinstance(payload, dict):
        return ["payload 必须是 object"]
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return ["payload.assets 必须是 array"]

    errors: list[str] = []
    ids: set[str] = set()
    for index, asset in enumerate(assets):
        label = f"assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{label} 必须是 object")
            continue
        asset_id = asset.get("asset_id")
        if not asset_id:
            errors.append(f"{label} 缺少 asset_id")
        elif asset_id in ids:
            errors.append(f"{label} asset_id 重复：{asset_id}")
        else:
            ids.add(asset_id)
        if asset.get("rights_basis") not in RIGHTS_BASES:
            errors.append(f"{label} rights_basis 无效")
        if asset.get("rights_status") != "verified":
            errors.append(f"{label} rights_status 必须是 verified")
        if asset.get("rights_basis") in {"licensed", "permission"} and not asset.get("license_or_permission_ref"):
            errors.append(f"{label} 必须保存许可证或授权依据")
        if not isinstance(asset.get("contains_personal_data"), bool):
            errors.append(f"{label} contains_personal_data 必须是 boolean")
        if not isinstance(asset.get("external_processing_approved"), bool):
            errors.append(f"{label} external_processing_approved 必须是 boolean")
        if asset.get("rights_basis") == "generated":
            if not asset.get("generation_job_id") or not asset.get("generator_capability_id"):
                errors.append(f"{label} 生成素材必须记录 generation_job_id 和 generator_capability_id")
        uri = asset.get("uri")
        if not isinstance(uri, str) or not uri:
            errors.append(f"{label} 缺少 uri")
            continue
        resolved = local_path(uri, path)
        if resolved is None:
            errors.append(f"{label} 发布资产必须是本地或 file URI：{uri}")
            continue
        if not resolved.is_file():
            errors.append(f"{label} 文件不存在：{resolved}")
            continue
        expected = asset.get("sha256")
        actual = sha256_file(resolved)
        if expected != actual:
            errors.append(f"{label} SHA-256 不一致：{resolved}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("content_json")
    args = parser.parse_args()
    path = Path(args.content_json).resolve()
    errors = validate(path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"PASS: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
