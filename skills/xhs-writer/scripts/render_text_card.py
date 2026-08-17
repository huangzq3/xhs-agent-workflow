#!/usr/bin/env python3
"""Render a local pure-text card without any external image service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow required (python3 -m pip install Pillow)", file=sys.stderr)
    raise SystemExit(2)

from text_on_image import load_font, parse_color, wrap_cjk


def parse_size(value: str) -> tuple[int, int]:
    try:
        width, height = map(int, value.lower().split("x"))
    except (TypeError, ValueError) as exc:
        raise ValueError("size must be WIDTHxHEIGHT") from exc
    if width <= 0 or height <= 0:
        raise ValueError("size must be positive")
    return width, height


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--text", required=True)
    parser.add_argument("--eyebrow", default="")
    parser.add_argument("--size", default="900x1200")
    parser.add_argument("--font")
    parser.add_argument("--font-size", type=int, default=86)
    parser.add_argument("--background", default="#F7F3EA")
    parser.add_argument("--foreground", default="#171717")
    parser.add_argument("--accent", default="#E5484D")
    parser.add_argument("--padding", type=int, default=72)
    args = parser.parse_args()

    width, height = parse_size(args.size)
    if args.padding * 2 >= width:
        print("ERROR: padding too large", file=sys.stderr)
        return 2
    image = Image.new("RGBA", (width, height), parse_color(args.background))
    draw = ImageDraw.Draw(image)
    title_font = load_font(args.font, args.font_size)
    small_font = load_font(args.font, max(24, args.font_size // 3))
    foreground = parse_color(args.foreground)
    accent = parse_color(args.accent)

    top = args.padding
    if args.eyebrow:
        draw.text((args.padding, top), args.eyebrow, font=small_font, fill=accent)
        top += args.font_size
    draw.rounded_rectangle(
        (args.padding, top, args.padding + 96, top + 12),
        radius=6,
        fill=accent,
    )
    top += 72
    lines = wrap_cjk(args.text, title_font, width - 2 * args.padding, draw)
    line_height = round(args.font_size * 1.35)
    block_height = len(lines) * line_height
    if top + block_height > height - args.padding:
        print("ERROR: text does not fit; reduce --font-size or content length", file=sys.stderr)
        return 2
    for index, line in enumerate(lines):
        draw.text((args.padding, top + index * line_height), line, font=title_font, fill=foreground)

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, quality=92)
    print(f"OK: {output} ({width}x{height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
