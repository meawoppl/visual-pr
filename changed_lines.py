#!/usr/bin/env python3
"""Count the lines a pull request really changes, for the `min-changed-lines`
escape in action.yml.

    gh api --paginate "repos/OWNER/REPO/pulls/N/files" --jq '.[]' \\
      | python3 changed_lines.py --svg-dir .0-pr-viz --repo-root .

Reads the PR's file list (one JSON object per line, or a JSON array) on
stdin and prints the counted total on stdout; a per-file report goes to
stderr. Not counted:

- anything under --svg-dir (the visual summary itself);
- unless --count-everything: files the base branch's .gitattributes marks
  `linguist-generated` or `linguist-vendored` (resolved with `git check-attr`
  from --repo-root, so nested .gitattributes work when checked out), plus
  the lockfiles and build artifacts Linguist itself treats as generated
  (package-lock.json, yarn.lock, Cargo.lock, *.min.js, ...). An explicit
  `linguist-generated=false` in .gitattributes overrides the built-in list.

Exit 0 with the total on the last stdout line; exit 2 on unreadable input.
"""

import argparse
import fnmatch
import json
import pathlib
import subprocess
import sys

# Names Linguist classifies as generated regardless of .gitattributes
# (github-linguist/linguist lib/linguist/generated.rb, the lockfile and
# minified-asset rules). Deliberately short: the escape hatch for anything
# else is .gitattributes, which the repo controls.
BUILTIN_GENERATED = [
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "bun.lock",
    "composer.lock",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
    "uv.lock",
    "pdm.lock",
    "Gemfile.lock",
    "go.sum",
    "flake.lock",
    "mix.lock",
    "pubspec.lock",
    "packages.lock.json",
    "Package.resolved",
    "*.min.js",
    "*.min.css",
    "*.js.map",
    "*.css.map",
    "*.pb.go",
    "*_pb2.py",
    "*_pb2_grpc.py",
    "*.pb.cc",
    "*.pb.h",
]

ATTRS = ("linguist-generated", "linguist-vendored")


def read_files(stream) -> list[dict]:
    text = stream.read().strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def check_attrs(repo_root: pathlib.Path, paths: list[str]) -> dict[str, dict[str, str]]:
    """{path: {attr: value}} via one batched `git check-attr`; values are
    'set', 'unset', 'unspecified', or a string. Empty when git is unusable."""
    if not paths:
        return {}
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "check-attr", "--stdin", "-z", *ATTRS],
            input="".join(p + "\0" for p in paths),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {}
    fields = out.split("\0")
    result: dict[str, dict[str, str]] = {}
    for i in range(0, len(fields) - 2, 3):
        path, attr, value = fields[i], fields[i + 1], fields[i + 2]
        result.setdefault(path, {})[attr] = value
    return result


def is_truthy(value: str | None) -> bool:
    return value in ("set", "true")


def is_falsy(value: str | None) -> bool:
    return value in ("unset", "false")


def classify(path: str, attrs: dict[str, str], svg_dir: str, count_everything: bool) -> str | None:
    """Return a reason to skip this file, or None to count it."""
    if svg_dir and (path == svg_dir or path.startswith(svg_dir.rstrip("/") + "/")):
        return "visual summary"
    if count_everything:
        return None
    for attr in ATTRS:
        if is_truthy(attrs.get(attr)):
            return attr
    if any(is_falsy(attrs.get(attr)) for attr in ATTRS):
        return None  # repo explicitly says: count this one
    name = pathlib.PurePosixPath(path).name
    if any(fnmatch.fnmatchcase(name, pat) for pat in BUILTIN_GENERATED):
        return "generated (built-in Linguist rule)"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg-dir", default=".0-pr-viz", help="directory of the visual summaries; never counted")
    ap.add_argument("--repo-root", default=".", help="checkout whose .gitattributes decide linguist-* (the BASE branch)")
    ap.add_argument("--count-everything", action="store_true", help="ignore linguist attributes and built-in generated rules")
    args = ap.parse_args()

    try:
        files = read_files(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: could not parse the PR file list: {e}", file=sys.stderr)
        return 2

    paths = [f.get("filename", "") for f in files]
    attrs = {} if args.count_everything else check_attrs(pathlib.Path(args.repo_root), paths)

    total = 0
    for f in files:
        path = f.get("filename", "")
        changed = int(f.get("changes", int(f.get("additions", 0)) + int(f.get("deletions", 0))))
        reason = classify(path, attrs.get(path, {}), args.svg_dir, args.count_everything)
        if reason:
            print(f"  skip  {changed:>6}  {path}  ({reason})", file=sys.stderr)
        else:
            total += changed
            print(f"  count {changed:>6}  {path}", file=sys.stderr)
    print(f"  total {total:>6}  counted changed lines across {len(files)} file(s)", file=sys.stderr)
    print(total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
