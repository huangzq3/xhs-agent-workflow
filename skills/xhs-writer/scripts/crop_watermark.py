#!/usr/bin/env python3
"""Compatibility guard: watermark removal is not a rights-clearing operation."""

import sys


def main() -> int:
    print(
        "ERROR: crop_watermark.py 已停用。裁剪或移除水印不能取得版权授权。"
        "请改用自有、已许可、获明确授权、公有领域或合规生成的素材，"
        "并运行 validate_asset_rights.py。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
