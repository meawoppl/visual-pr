#!/usr/bin/env python3
"""Does the pull request description show the visual summary?

    gh pr view N --json body --jq .body \\
      | python3 pr_body_image.py --mode first --svg-path .0-pr-viz/000123.svg

Reads the PR body on stdin. An "image of the summary" is a Markdown image
(`![alt](url)`, optionally wrapped in a link) or an HTML `<img src=...>` whose
URL, minus any query string or fragment, ends with the SVG's repo path — so
raw.githubusercontent.com URLs pinned to a SHA or a branch, and
github.com/.../blob/...?raw=true, all count.

Modes:
  first         the image must be the first thing in the body (leading blank
                lines and HTML comments, e.g. a PR template's, are skipped)
  included      the image may appear anywhere in the body
  not-required  always satisfied

Exit 0 when satisfied, 1 when not (with a one-line reason on stdout),
2 on bad arguments.
"""

import argparse
import re
import sys

MODES = ("first", "included", "not-required")

MD_IMAGE = r"!\[[^\]]*\]\(\s*<?(?P<md>[^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)"
HTML_IMAGE = r"<img\b[^>]*?\bsrc\s*=\s*[\"'](?P<html>[^\"']+)[\"'][^>]*>"
IMAGE = re.compile(f"(?:{MD_IMAGE})|(?:{HTML_IMAGE})", re.IGNORECASE)
LEADING_NOISE = re.compile(r"^(?:\s|<!--.*?-->)*", re.DOTALL)


def url_of(match: re.Match) -> str:
    return match.group("md") or match.group("html") or ""


def points_at(url: str, svg_path: str) -> bool:
    bare = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    svg_path = svg_path.strip("/")
    return bare == svg_path or bare.endswith("/" + svg_path)


def find_images(body: str) -> list[re.Match]:
    return list(IMAGE.finditer(body))


def check(body: str, svg_path: str, mode: str) -> tuple[bool, str]:
    if mode == "not-required":
        return True, "PR description image not required"
    images = [m for m in find_images(body) if points_at(url_of(m), svg_path)]
    if not images:
        return False, f"PR description has no image of {svg_path}"
    if mode == "included":
        return True, f"PR description includes an image of {svg_path}"
    # first: after leading whitespace / HTML comments, optionally a link
    # wrapper "[", the very next thing must be that image.
    start = LEADING_NOISE.match(body).end()
    if body[start : start + 1] == "[":
        start += 1
        start += len(body[start:]) - len(body[start:].lstrip())
    first = IMAGE.match(body, start)
    if first and points_at(url_of(first), svg_path):
        return True, f"PR description opens with an image of {svg_path}"
    return False, (
        f"PR description contains an image of {svg_path} but does not open with it "
        f"(mode 'first'); move it to the very first line"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg-path", required=True, help="repo path of the summary, e.g. .0-pr-viz/000123.svg")
    ap.add_argument("--mode", choices=MODES, default="first")
    args = ap.parse_args()
    ok, why = check(sys.stdin.read(), args.svg_path, args.mode)
    print(why)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
