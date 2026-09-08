#!/usr/bin/env python3
"""Sweep merged PR visuals out of the working tree without losing them.

    python3 sweep_merged.py [--repo OWNER/REPO] [--svg-dir .0-pr-viz]
                            [--keep-days 7] [--keep-last 0]
                            [--mode pr|push|none] [--skip-label no-visual]
                            [--dry-run]

Every merged PR's SVG stays in git history forever at its merge commit, so
the working tree does not need to carry it. For each `<svg-dir>/<n>.svg` in
the checkout whose PR is merged and older than --keep-days (and not among the
--keep-last most recently merged):

1. Rewrite the PR description so its image points at the permalink of the
   file *as merged*: raw.githubusercontent.com/OWNER/REPO/<merge sha>/<path>,
   linked to the matching github.com/.../blob/<merge sha>/<path>. If the file
   is not at that path in the merge commit (the directory was renamed later,
   say), the newest commit on the current branch that has it is used instead
   — still permanent. A body with no image gets one prepended.
   Already-permalinked bodies are left alone.
2. Record the PR in `<svg-dir>/ARCHIVE.md` (number, merge date, title,
   permalink) so the pictures stay one click away.
3. `git rm` the file.

Then, per --mode: `pr` commits on a branch, pushes, and opens a PR labeled
--skip-label (the sweep is exactly the kind of PR that needs no diagram);
`push` commits straight onto the current branch and pushes; `none` leaves
the commit for you. Needs `gh` authenticated with pull-requests write to edit
descriptions (and contents write for push/pr). Run it weekly; shallow
checkouts stay small and the review history stays intact.
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pr_body_image  # noqa: E402  (same directory)

ARCHIVE_NAME = "ARCHIVE.md"
ARCHIVE_HEADER = (
    "# Archived PR visuals\n\n"
    "Swept from the working tree by `sweep_merged.py`; each image lives on at its\n"
    "merge commit and the PR description shows it. Newest first.\n\n"
    "| PR | merged | title | image |\n|---|---|---|---|\n"
)
ROW = re.compile(r"^\| #(?P<n>\d+) \| (?P<date>[^|]*) \| (?P<title>.*) \| \[[^\]]*\]\((?P<url>[^)]*)\) \|$")


# ------------------------------------------------------------------ helpers


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def gh_json(args: list[str]):
    r = run(["gh", "api", *args])
    if r.returncode != 0:
        raise RuntimeError(f"gh api {' '.join(args)}: {r.stderr.strip()}")
    return json.loads(r.stdout or "null")


def pr_number(path: pathlib.Path) -> int | None:
    return int(path.stem) if path.suffix == ".svg" and path.stem.isdigit() else None


def parse_time(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def select_for_sweep(prs: list[dict], keep_days: float, keep_last: int, now: dt.datetime) -> list[dict]:
    """prs: dicts with number, merged_at (ISO) — merged only. Returns the ones
    to sweep: not among the keep_last most recent, and merged > keep_days ago."""
    merged = sorted(prs, key=lambda p: parse_time(p["merged_at"]), reverse=True)
    candidates = merged[keep_last:] if keep_last > 0 else merged
    cutoff = now - dt.timedelta(days=keep_days)
    return [p for p in candidates if parse_time(p["merged_at"]) <= cutoff]


def file_exists_at(repo: str, sha: str, path: str) -> bool:
    try:
        gh_json([f"repos/{repo}/contents/{path}?ref={sha}"])
        return True
    except RuntimeError:
        return False


def permalink_sha(repo: str, merge_sha: str, path: str) -> tuple[str | None, str]:
    """The merge commit when the file is there; otherwise the newest commit on
    the current branch touching the path (HEAD in a shallow clone), if GitHub
    has it. Returns (sha or None, note)."""
    if file_exists_at(repo, merge_sha, path):
        return merge_sha, ""
    newest = run(["git", "rev-list", "-1", "HEAD", "--", path]).stdout.strip()
    if newest and file_exists_at(repo, newest, path):
        return newest, f"(not at merge commit {merge_sha[:8]}; using {newest[:8]}, the newest commit with it)"
    return None, f"not found at merge commit {merge_sha[:8]} nor at any pushed commit on this branch"


def permalinks(repo: str, sha: str, path: str) -> tuple[str, str]:
    return (
        f"https://raw.githubusercontent.com/{repo}/{sha}/{path}",
        f"https://github.com/{repo}/blob/{sha}/{path}",
    )


def rewrite_body(body: str, svg_path: str, raw_url: str, blob_url: str) -> tuple[str, bool]:
    """Point every image of svg_path at raw_url. No image → prepend a linked one."""
    body = body or ""
    changed = False
    out = []
    last = 0
    for m in pr_body_image.find_images(body):
        url = pr_body_image.url_of(m)
        if not pr_body_image.points_at(url, svg_path) or url == raw_url:
            continue
        # Replace just the URL inside this match.
        start = m.start() + m.group(0).index(url)
        out.append(body[last:start])
        out.append(raw_url)
        last = start + len(url)
        changed = True
    out.append(body[last:])
    new = "".join(out)
    if not any(pr_body_image.points_at(pr_body_image.url_of(m), svg_path) for m in pr_body_image.find_images(new)):
        new = f"[![Visual summary]({raw_url})]({blob_url})\n\n{new}".rstrip() + "\n"
        changed = True
    return new, changed


def load_archive(path: pathlib.Path) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            m = ROW.match(line)
            if m:
                rows[int(m["n"])] = {"date": m["date"], "title": m["title"], "url": m["url"]}
    return rows


def write_archive(path: pathlib.Path, rows: dict[int, dict]) -> None:
    lines = [ARCHIVE_HEADER]
    for n in sorted(rows, reverse=True):
        r = rows[n]
        title = r["title"].replace("|", "\\|")
        lines.append(f"| #{n} | {r['date']} | {title} | [{n:06d}.svg]({r['url']}) |\n")
    path.write_text("".join(lines))


# --------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY") or None, help="OWNER/REPO (default: $GITHUB_REPOSITORY or gh repo view)")
    ap.add_argument("--svg-dir", default=".0-pr-viz")
    ap.add_argument("--keep-days", type=float, default=7, help="only sweep PRs merged at least this many days ago")
    ap.add_argument("--keep-last", type=int, default=0, help="always keep the N most recently merged")
    ap.add_argument("--mode", choices=("pr", "push", "none"), default="pr")
    ap.add_argument("--skip-label", default="no-visual", help="label for the sweep PR so the visual check skips it")
    ap.add_argument("--branch-prefix", default="visual-pr/sweep")
    ap.add_argument("--dry-run", action="store_true", help="report what would happen; change nothing")
    args = ap.parse_args()

    repo = args.repo
    if not repo:
        r = run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
        repo = r.stdout.strip()
    if not repo:
        print("ERROR: could not determine the repository; pass --repo OWNER/REPO", file=sys.stderr)
        return 2

    svg_dir = pathlib.Path(args.svg_dir)
    if not svg_dir.is_dir():
        print(f"nothing to do: {svg_dir} does not exist")
        return 0

    now = dt.datetime.now(dt.timezone.utc)
    files = {n: p for p in sorted(svg_dir.glob("*.svg")) if (n := pr_number(p)) is not None}
    print(f"{len(files)} PR visual(s) in {svg_dir}/")

    merged: list[dict] = []
    for n in sorted(files):
        try:
            pr = gh_json([f"repos/{repo}/pulls/{n}"])
        except RuntimeError as e:
            print(f"  #{n}: skip — {e}")
            continue
        if not pr.get("merged_at"):
            print(f"  #{n}: {pr.get('state')} and not merged — kept")
            continue
        merged.append(pr)

    sweep = select_for_sweep(merged, args.keep_days, args.keep_last, now)
    kept = len(merged) - len(sweep)
    print(f"{len(merged)} merged; {kept} within keep-days/keep-last; {len(sweep)} to sweep")
    if not sweep:
        return 0

    archive_path = svg_dir / ARCHIVE_NAME
    rows = load_archive(archive_path)
    removed: list[pathlib.Path] = []
    edited = 0
    for pr in sorted(sweep, key=lambda p: p["number"]):
        n, sha = pr["number"], pr["merge_commit_sha"]
        path = f"{svg_dir.as_posix()}/{files[n].name}"
        # The permalink must resolve before we delete anything.
        sha, note = permalink_sha(repo, sha, path)
        if sha is None:
            print(f"  #{n}: {path} {note} — kept")
            continue
        raw_url, blob_url = permalinks(repo, sha, path)
        new_body, changed = rewrite_body(pr.get("body") or "", path, raw_url, blob_url)
        date = parse_time(pr["merged_at"]).date().isoformat()
        print(f"  #{n}: merged {date} → {blob_url} {note}".rstrip() + ("" if changed else " (description already permalinked)"))
        if args.dry_run:
            continue
        if changed:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump({"body": new_body}, f)
            r = run(["gh", "api", "-X", "PATCH", f"repos/{repo}/pulls/{n}", "--input", f.name])
            os.unlink(f.name)
            if r.returncode != 0:
                print(f"  #{n}: could not update the description ({r.stderr.strip()}) — kept")
                continue
            edited += 1
        rows[n] = {"date": date, "title": pr.get("title", ""), "url": blob_url}
        run(["git", "rm", "-q", str(files[n])])
        removed.append(files[n])

    if args.dry_run:
        print(f"dry run: would edit descriptions, archive and remove {len(sweep)} file(s)")
        return 0
    if not removed:
        print("nothing swept")
        return 0

    write_archive(archive_path, rows)
    run(["git", "add", str(archive_path)])
    summary = f"Sweep {len(removed)} merged PR visual(s) older than {args.keep_days:g} day(s)"
    body_lines = [
        "Each image now lives at its merge-commit permalink, and the merged PR's",
        "description points there. `ARCHIVE.md` indexes them.",
        "",
        *[f"- #{pr_number(p)} → https://github.com/{repo}/blob/{rows[pr_number(p)]['url'].split('/blob/')[1]}" for p in removed],
    ]
    git_id = ["-c", "user.name=visual-pr sweep", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com"]
    if run(["git", "config", "user.email"]).stdout.strip():
        git_id = []
    print(f"{edited} description(s) updated; {len(removed)} file(s) removed")

    if args.mode == "none":
        run(["git", *git_id, "commit", "-q", "-m", summary, "-m", "\n".join(body_lines)])
        print("committed locally (mode none); nothing pushed")
        return 0
    if args.mode == "push":
        branch = run(["git", "branch", "--show-current"]).stdout.strip()
        run(["git", *git_id, "commit", "-q", "-m", summary, "-m", "\n".join(body_lines)])
        r = run(["git", "push", "-q", "origin", f"HEAD:{branch}"])
        if r.returncode != 0:
            print(f"ERROR: push failed: {r.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"pushed to {branch}")
        return 0
    branch = f"{args.branch_prefix}-{now.date().isoformat()}"
    base = run(["git", "branch", "--show-current"]).stdout.strip() or "main"
    run(["git", "checkout", "-q", "-B", branch])
    run(["git", *git_id, "commit", "-q", "-m", summary, "-m", "\n".join(body_lines)])
    r = run(["git", "push", "-q", "-f", "-u", "origin", branch])
    if r.returncode != 0:
        print(f"ERROR: push failed: {r.stderr.strip()}", file=sys.stderr)
        return 1
    r = run(["gh", "pr", "create", "--repo", repo, "--base", base, "--head", branch, "--title", summary,
             "--body", "\n".join(body_lines), "--label", args.skip_label])
    if r.returncode != 0:
        print(f"ERROR: could not open the sweep PR: {r.stderr.strip()}", file=sys.stderr)
        return 1
    print(r.stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
