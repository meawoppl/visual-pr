#!/usr/bin/env python3
"""Validate a visual-PR SVG against a style definition.

Usage: check_svg.py [--style style.json] <file.svg>

The style JSON (see style/default.json for the bundled Tokyo-Night default)
defines the canvas size, allowed palette, text-fit heuristics, and the
BEFORE/AFTER divider position. Consuming repos point the action's `style`
input at their own JSON to re-skin the frame; omitted keys fall back to the
default style's values.

Hard errors (exit 1): unparseable XML, wrong canvas, off-palette color.
Warnings (exit 0): text that looks like it overflows the canvas or crosses
the panel divider, missing font-size. Overflow estimates use
char_factor × font-size per character — eyeball anything flagged.
"""

import argparse
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

DEFAULT_STYLE = pathlib.Path(__file__).parent / "style" / "default.json"

errors: list[str] = []
warnings: list[str] = []


def load_style(path: str | None) -> dict:
    style = json.loads(DEFAULT_STYLE.read_text())
    if path:
        style.update(json.loads(pathlib.Path(path).read_text()))
    style["palette"] = {c.lower() for c in style["palette"]}
    return style


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def check_colors(elem: ET.Element, palette: set[str]) -> None:
    for attr in ("fill", "stroke"):
        val = elem.get(attr)
        if val is None:
            continue
        v = val.strip().lower()
        if v.startswith("url(") or v in ("currentcolor", "inherit"):
            continue
        if v not in palette:
            errors.append(
                f"<{strip_ns(elem.tag)}> {attr}='{val}' is off-palette "
                f"(allowed colors come from the style JSON)"
            )


def text_content(elem: ET.Element) -> str:
    return "".join(elem.itertext()).strip()


def check_text(elem: ET.Element, style: dict, inherited_size: float) -> None:
    size = elem.get("font-size")
    if size is None and strip_ns(elem.tag) == "text":
        warnings.append(f"<text> '{text_content(elem)[:40]}' has no font-size")
    fs = float(re.sub(r"[a-z%]+$", "", size)) if size else inherited_size

    content = text_content(elem)
    if not content:
        return
    x = elem.get("x")
    if x is None:
        return
    try:
        x = float(x)
    except ValueError:
        return

    canvas_w = style["canvas"][0]
    est_w = len(content) * fs * style["char_factor"]
    anchor = elem.get("text-anchor", "start")
    if anchor == "middle":
        left, right = x - est_w / 2, x + est_w / 2
    elif anchor == "end":
        left, right = x - est_w, x
    else:
        left, right = x, x + est_w

    if right > canvas_w - style["margin"] or left < 0:
        warnings.append(
            f"text likely overflows canvas (est {left:.0f}..{right:.0f}): "
            f"'{content[:60]}'"
        )
    # Panel-divider crossing: text starting in one panel shouldn't cross it.
    # Full-width text (thesis, footer) is exempt via the size/band gates.
    divider = style.get("divider_x")
    if divider and left < divider - 10 and right > divider + 10 and fs < 30:
        y = elem.get("y")
        yv = float(y) if y and re.fullmatch(r"[\d.]+", y) else 0.0
        band = style.get("divider_band", [0, style["canvas"][1]])
        if band[0] < yv < band[1]:
            warnings.append(
                f"text crosses the BEFORE/AFTER divider (est {left:.0f}..{right:.0f}): "
                f"'{content[:60]}'"
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("svg", help="SVG file to validate")
    ap.add_argument("--style", help="style JSON overriding the bundled default")
    args = ap.parse_args()

    try:
        style = load_style(args.style)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not load style: {e}", file=sys.stderr)
        return 2

    try:
        tree = ET.parse(args.svg)
    except (ET.ParseError, OSError) as e:
        print(f"ERROR: not well-formed XML: {e}", file=sys.stderr)
        return 1

    root = tree.getroot()
    canvas_w, canvas_h = style["canvas"]
    viewbox = (root.get("viewBox") or "").split()
    if viewbox != ["0", "0", str(canvas_w), str(canvas_h)]:
        errors.append(
            f"viewBox is '{root.get('viewBox')}', style requires '0 0 {canvas_w} {canvas_h}'"
        )

    for elem in root.iter():
        check_colors(elem, style["palette"])
        if strip_ns(elem.tag) in ("text", "tspan"):
            check_text(elem, style, inherited_size=23.0)

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)

    if errors:
        return 1
    print(f"ok: palette + canvas clean, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
