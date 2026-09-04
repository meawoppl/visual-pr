#!/usr/bin/env python3
"""Re-skin the example PR diagrams into every bundled style and assemble the
style × PR matrix.

    python3 examples/build.py          # regenerate examples/<style>/<pr>.svg,
                                       # examples/matrix.svg, examples/README.md
    python3 examples/build.py --check  # exit 1 if the committed outputs are stale

Sources live in examples/src/<six-digit pr>.svg and are authored in the default
(Tokyo Night) palette. Because every bundled palette lists its 14 colors in
the same semantic order (see style/README.md), re-skinning is a positional
substitution of fill/stroke values. Each output is validated with
check_svg.py against its own style; any ERROR fails the build.
"""

import argparse
import filecmp
import io
import json
import pathlib
import re
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import check_svg  # noqa: E402


class _NoSnark:
    """The Starstruck nudge is irrelevant when validating generated examples,
    and must not write the marker into the developer's config dir."""

    def __init__(self, **kw):
        pass

    def report(self, out=None):
        return None


check_svg.SnarkCheck = _NoSnark

EXAMPLES = ROOT / "examples"
SRC = EXAMPLES / "src"
STYLE_DIR = ROOT / "style"
# Column order for the matrix: dark themes first, light themes last.
STYLE_ORDER = ["default", "dracula", "nord", "gruvbox-dark", "github-light", "solarized-light"]

CELL_W, CELL_H, GAP, LABEL_W, HEADER_H = 400, 240, 24, 150, 56
LABEL_COLOR = "#8a8f98"  # legible on both dark and light page backgrounds


def load_palettes() -> dict[str, list[str]]:
    pals = {p.stem: json.loads(p.read_text())["palette"] for p in STYLE_DIR.glob("*.json")}
    missing = set(pals) - set(STYLE_ORDER)
    if missing:
        sys.exit(f"add {sorted(missing)} to STYLE_ORDER in {__file__}")
    return pals


def reskin(svg_text: str, src_pal: list[str], dst_pal: list[str]) -> str:
    if len(src_pal) != len(dst_pal):
        raise ValueError("palettes must have the same length to re-skin by index")
    mapping = {a.lower(): b.lower() for a, b in zip(src_pal, dst_pal) if a.lower() != "none"}

    def swap(m: re.Match) -> str:
        return f'{m.group(1)}="{mapping.get(m.group(2).lower(), m.group(2))}"'

    return re.sub(r'(?<![\w-])(fill|stroke)="(#[0-9a-fA-F]{6})"', swap, svg_text)


def validate(path: pathlib.Path, style: str) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    argv = sys.argv
    sys.argv = ["check_svg.py", "--style", style, str(path)]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = check_svg.main()
    finally:
        sys.argv = argv
    return rc, out.getvalue() + err.getvalue()


def pr_title(svg_text: str) -> tuple[str, str]:
    m = re.search(r">PR #(\d+) · ([^<]+)</text>", svg_text)
    if not m:
        raise ValueError("example header must read 'PR #<n> · <title>'")
    return m.group(1), m.group(2)


def nested_cell(svg_text: str, key: str, x: int, y: int) -> str:
    """Embed a full example as a nested <svg>, namespacing ids so 30 copies of
    the marker defs don't collide."""
    root_tag = re.match(r"<svg\b[^>]*>", svg_text, flags=re.S).group(0)
    fam = re.search(r'font-family="([^"]*)"', root_tag)
    inner = svg_text[len(root_tag):].rsplit("</svg>", 1)[0]
    inner = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{key}-{m.group(1)}"', inner)
    inner = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{key}-{m.group(1)})", inner)
    inner = re.sub(r'href="#([^"]+)"', lambda m: f'href="#{key}-{m.group(1)}"', inner)
    fam_attr = f' font-family="{fam.group(1)}"' if fam else ""
    return (
        f'<svg x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" viewBox="0 0 2000 1200"{fam_attr}>'
        f"{inner}</svg>\n"
        f'<rect x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" fill="none" stroke="{LABEL_COLOR}" stroke-opacity="0.5"/>\n'
    )


def build(out_dir: pathlib.Path) -> list[str]:
    """Write every output under out_dir; return the log lines."""
    pals = load_palettes()
    sources = sorted(SRC.glob("*.svg"))
    if not sources:
        sys.exit(f"no sources in {SRC}")
    log: list[str] = []
    titles: dict[str, str] = {}
    cells: list[str] = []
    failed = False

    for row, src in enumerate(sources):
        text = src.read_text()
        num, title = pr_title(text)
        if not (src.stem.isdigit() and len(src.stem) == 6):
            sys.exit(f"{src.name}: example files use the six-digit PR-number name, e.g. 000412.svg")
        if int(num) != int(src.stem):
            sys.exit(f"{src.name}: header says PR #{num} but the file is {src.stem}.svg")
        num = src.stem  # outputs keep the six-digit committed name
        titles[num] = title
        for col, style in enumerate(STYLE_ORDER):
            skinned = reskin(text, pals["default"], pals[style])
            dest = out_dir / style / f"{num}.svg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(skinned)
            rc, report = validate(dest, style)
            n_warn = report.count("warning:")
            log.append(f"{style}/{num}.svg: {'ok' if rc == 0 else 'FAIL'} ({n_warn} warning(s))")
            if rc != 0:
                failed = True
                log.append(report.rstrip())
            x = LABEL_W + col * (CELL_W + GAP)
            y = HEADER_H + row * (CELL_H + GAP)
            cells.append(nested_cell(skinned, f"c{row}{col}", x, y))

    if failed:
        sys.exit("\n".join(log))

    width = LABEL_W + len(STYLE_ORDER) * (CELL_W + GAP)
    height = HEADER_H + len(sources) * (CELL_H + GAP)
    headers = "".join(
        f'<text x="{LABEL_W + i * (CELL_W + GAP) + CELL_W / 2:.0f}" y="36" font-size="24" '
        f'text-anchor="middle" fill="{LABEL_COLOR}">{s}</text>\n'
        for i, s in enumerate(STYLE_ORDER)
    )
    row_labels = "".join(
        f'<text x="{LABEL_W - GAP}" y="{HEADER_H + r * (CELL_H + GAP) + CELL_H / 2 + 8:.0f}" '
        f'font-size="24" text-anchor="end" fill="{LABEL_COLOR}">PR #{int(src.stem)}</text>\n'
        for r, src in enumerate(sources)
    )
    matrix = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'font-family="\'Segoe UI\', \'Noto Sans\', \'DejaVu Sans\', ui-sans-serif, system-ui, sans-serif">\n'
        f"<!-- generated by examples/build.py — do not edit -->\n"
        f"{headers}{row_labels}{''.join(cells)}</svg>\n"
    )
    (out_dir / "matrix.svg").write_text(matrix)

    lines = [
        "# Example matrix: PRs × bundled styles",
        "",
        "Five synthetic pull requests, one per [archetype](../SPEC.md#archetypes--pick-one-per-pr),",
        "each rendered in every bundled style. Sources are authored once in the",
        "default palette (`src/`); `build.py` re-skins them by palette index and",
        "validates every output with `check_svg.py --style <name>`.",
        "",
        "**Generated — edit `src/*.svg` or `style/*.json`, then run**",
        "`python3 examples/build.py`. CI fails if this directory is stale.",
        "",
        "![matrix](matrix.svg)",
        "",
        "| PR | " + " | ".join(f"`{s}`" for s in STYLE_ORDER) + " |",
        "|---|" + "---|" * len(STYLE_ORDER),
    ]
    for src in sources:
        n = src.stem
        cells_md = " | ".join(f"[![{s}]({s}/{n}.svg)]({s}/{n}.svg)" for s in STYLE_ORDER)
        lines.append(f"| **#{int(n)}** `{n}.svg` {titles[n]} | {cells_md} |")
    lines += [
        "",
        "Choose one with the action's `style` input (`style: nord`) or locally with",
        "`python3 check_svg.py --style nord 000-pr-visualization/000412.svg`. Own palette?",
        "Point `style` at a JSON file instead — see [`../style/README.md`](../style/README.md).",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(lines))
    return log


def check_fresh() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = pathlib.Path(tmp)
        build(tmp_dir)
        stale = []
        for fresh in sorted(tmp_dir.rglob("*")):
            if fresh.is_dir():
                continue
            committed = EXAMPLES / fresh.relative_to(tmp_dir)
            if not committed.exists() or not filecmp.cmp(fresh, committed, shallow=False):
                stale.append(str(committed.relative_to(ROOT)))
        for style in STYLE_ORDER:
            for committed in (EXAMPLES / style).glob("*.svg"):
                if not (tmp_dir / style / committed.name).exists():
                    stale.append(f"{committed.relative_to(ROOT)} (orphan)")
    if stale:
        print("examples/ is stale — run `python3 examples/build.py` and commit:", file=sys.stderr)
        for s in stale:
            print(f"  {s}", file=sys.stderr)
        return 1
    print("examples/ is up to date")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify committed outputs match a fresh build")
    args = ap.parse_args()
    if args.check:
        return check_fresh()
    for line in build(EXAMPLES):
        print(line)
    print(f"wrote {EXAMPLES / 'matrix.svg'} and {EXAMPLES / 'README.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
