#!/usr/bin/env python3
"""Does the pull request description show the visual summary, durably?

    gh pr view N --json body --jq .body \\
      | python3 pr_body_image.py --mode first --svg-path .0-pr-viz/000123.svg \\
          --repo OWNER/REPO

Reads the PR body on stdin. An "image of the summary" is a Markdown image
(`![alt](url)`, optionally wrapped in a link) or an HTML `<img src=...>` whose
URL points at the SVG's repo path. The URL must be a GitHub **permalink**:

    https://raw.githubusercontent.com/OWNER/REPO/<40-char sha>/<svg-path>
    https://github.com/OWNER/REPO/blob/<40-char sha>/<svg-path>
    https://github.com/OWNER/REPO/raw/<40-char sha>/<svg-path>

A branch ref is rejected: it 404s the moment the branch is deleted at merge,
which is exactly when the description becomes the only record of the PR. Both
hosts are accepted because on a private repository only a `github.com` URL
carries the reader's session.

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

GITHUB_HOSTS = ("raw.githubusercontent.com", "github.com")
SHA = re.compile(r"^[0-9a-fA-F]{40}$")
ABS_URL = re.compile(r"^https?://([^/]+)(/.*)?$", re.IGNORECASE)


def url_of(match: re.Match) -> str:
    return match.group("md") or match.group("html") or ""


def points_at(url: str, svg_path: str) -> bool:
    """Is this URL *about* the summary, however badly written?

    Deliberately loose: the sweep uses it to find the images worth repairing,
    and the check uses it to tell "no picture at all" apart from "a picture
    linked in a way that will rot".
    """
    bare = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    svg_path = svg_path.strip("/")
    return bare == svg_path or bare.endswith("/" + svg_path)


def ref_of(url: str, svg_path: str) -> tuple[str, str, str] | None:
    """(host, repo, ref) for a GitHub URL serving svg_path, else None.

    The ref keeps its slashes, so a branch like 'docs/x' comes back whole and
    can be named in the diagnosis — and so `blob/docs/x/...`, which GitHub
    itself cannot disambiguate, is never mistaken for a pinned ref.
    """
    m = ABS_URL.match(url.split("#", 1)[0].split("?", 1)[0])
    if not m or m.group(1).lower() not in GITHUB_HOSTS:
        return None
    host = m.group(1).lower()
    segments = [s for s in (m.group(2) or "").split("/") if s]
    wanted = [s for s in svg_path.strip("/").split("/") if s]
    if not wanted or segments[len(segments) - len(wanted):] != wanted:
        return None
    head = segments[: len(segments) - len(wanted)]
    if host == "github.com":
        # OWNER/REPO/{blob,raw}/REF/... — drop the verb to match the raw shape.
        if len(head) < 4 or head[2] not in ("blob", "raw"):
            return None
        head = head[:2] + head[3:]
    if len(head) < 3:
        return None
    return host, "/".join(head[:2]), "/".join(head[2:])


def pin_problem(url: str, svg_path: str, repos: tuple[str, ...] = ()) -> str | None:
    """Why this URL will not still show the summary tomorrow, or None."""
    found = ref_of(url, svg_path)
    if found is None:
        return (
            f"PR description image is not a GitHub permalink to {svg_path}: {url} "
            f"(use https://raw.githubusercontent.com/OWNER/REPO/<head sha>/{svg_path})"
        )
    host, repo, ref = found
    if not SHA.match(ref):
        # A slash in a /blob/ or /raw/ ref is already fatal: GitHub cannot tell
        # where the branch name ends and the file path begins, so the URL has
        # never resolved. Everything else is live now and dead after the merge.
        rot = ("GitHub cannot tell where that ref ends and the path begins, so it 404s today"
               if host == "github.com" and "/" in ref
               else "that URL 404s once the branch is deleted at merge")
        return (
            f"PR description image is pinned to '{ref}', not a 40-character commit SHA: "
            f"{url} ({rot})"
        )
    known = {r.lower() for r in repos if r}
    if known and repo.lower() not in known:
        return (
            f"PR description image points at {repo}, not "
            f"{' or '.join(sorted(set(r for r in repos if r)))}: {url}"
        )
    return None


def find_images(body: str) -> list[re.Match]:
    return list(IMAGE.finditer(body))


def check(body: str, svg_path: str, mode: str, repos: tuple[str, ...] = ()) -> tuple[bool, str]:
    if mode == "not-required":
        return True, "PR description image not required"
    candidates = [m for m in find_images(body) if points_at(url_of(m), svg_path)]
    if not candidates:
        return False, f"PR description has no image of {svg_path}"
    if not any(pin_problem(url_of(m), svg_path, repos) is None for m in candidates):
        return False, pin_problem(url_of(candidates[0]), svg_path, repos)
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
        problem = pin_problem(url_of(first), svg_path, repos)
        return (False, problem) if problem else (True, f"PR description opens with an image of {svg_path}")
    return False, (
        f"PR description contains an image of {svg_path} but does not open with it "
        f"(mode 'first'); move it to the very first line"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg-path", required=True, help="repo path of the summary, e.g. .0-pr-viz/000123.svg")
    ap.add_argument("--mode", choices=MODES, default="first")
    ap.add_argument("--repo", action="append", default=[], metavar="OWNER/REPO",
                    help="repository the permalink must name; repeatable (head and base). "
                         "Omit to accept any repository.")
    args = ap.parse_args()
    ok, why = check(sys.stdin.read(), args.svg_path, args.mode, tuple(args.repo))
    print(why)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
