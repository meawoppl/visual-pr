"""sweep_merged.py: retention maths, description rewriting, the archive index,
and an end-to-end run against a temp git repo with a fake `gh`."""

import datetime as dt
import importlib.util
import json
import os
import stat
import subprocess
import sys

import pytest

from conftest import ROOT

SCRIPT = ROOT / "sweep_merged.py"
REPO = "acme/widgets"
DIR = ".0-pr-viz"


def load():
    spec = importlib.util.spec_from_file_location("sweep_merged", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sw():
    return load()


NOW = dt.datetime(2026, 9, 7, 12, 0, tzinfo=dt.timezone.utc)


def pr(n, days_ago, **extra):
    merged = (NOW - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"number": n, "merged_at": merged, "merge_commit_sha": f"{n:040x}", "title": f"PR {n}", "body": "", **extra}


# ---- retention ------------------------------------------------------------


def test_keep_days_and_keep_last(sw):
    prs = [pr(1, 30), pr(2, 10), pr(3, 3), pr(4, 0.5)]
    assert [p["number"] for p in sw.select_for_sweep(prs, 7, 0, NOW)] == [2, 1], "newest first"
    assert [p["number"] for p in sw.select_for_sweep(prs, 0, 0, NOW)] == [4, 3, 2, 1]
    # keep-last protects the newest regardless of age.
    assert [p["number"] for p in sw.select_for_sweep(prs, 0, 2, NOW)] == [2, 1]
    assert sw.select_for_sweep(prs, 7, 3, NOW) == [pr(1, 30)]
    assert sw.select_for_sweep([], 7, 0, NOW) == []


def test_pr_number_from_name(sw, tmp_path):
    import pathlib
    assert sw.pr_number(pathlib.Path("000412.svg")) == 412
    assert sw.pr_number(pathlib.Path("412.svg")) == 412
    assert sw.pr_number(pathlib.Path("README.md")) is None
    assert sw.pr_number(pathlib.Path("valid.svg")) is None


# ---- description rewriting ------------------------------------------------

PATH = f"{DIR}/000412.svg"
RAW, BLOB = (
    f"https://raw.githubusercontent.com/{REPO}/{'a' * 40}/{PATH}",
    f"https://github.com/{REPO}/blob/{'a' * 40}/{PATH}",
)


def test_rewrite_points_branch_and_head_urls_at_the_merge_permalink(sw):
    body = (f"![Visual summary](https://raw.githubusercontent.com/{REPO}/feature-x/{PATH})\n\n"
            f"text <img src=\"https://github.com/{REPO}/blob/{'b' * 40}/{PATH}?raw=true\"> more")
    new, changed = sw.rewrite_body(body, PATH, RAW, BLOB)
    assert changed
    assert new.count(RAW) == 2
    assert "feature-x" not in new and "b" * 40 not in new
    assert new.startswith("![Visual summary](" + RAW + ")")


def test_rewrite_is_idempotent_and_leaves_other_images_alone(sw):
    body = f"[![s]({RAW})]({BLOB})\n\n![badge](https://img.shields.io/x.svg)\n"
    new, changed = sw.rewrite_body(body, PATH, RAW, BLOB)
    assert not changed and new == body


def test_rewrite_prepends_when_no_image(sw):
    new, changed = sw.rewrite_body("## Summary\n\nwords", PATH, RAW, BLOB)
    assert changed
    assert new.startswith(f"[![Visual summary]({RAW})]({BLOB})\n\n## Summary")
    new2, changed2 = sw.rewrite_body(None, PATH, RAW, BLOB)
    assert changed2 and new2 == f"[![Visual summary]({RAW})]({BLOB})\n"


# ---- archive index --------------------------------------------------------


def test_archive_round_trip(sw, tmp_path):
    p = tmp_path / "ARCHIVE.md"
    rows = {412: {"date": "2026-08-01", "title": "Fix | thing", "url": BLOB}, 7: {"date": "2026-07-01", "title": "Old", "url": "u"}}
    sw.write_archive(p, rows)
    text = p.read_text()
    assert text.startswith("# Archived PR visuals")
    assert text.index("| #412 |") < text.index("| #7 |"), "newest first"
    assert "[000007.svg](u)" in text and "Fix \\| thing" in text
    loaded = sw.load_archive(p)
    assert loaded[7]["url"] == "u" and loaded[412]["url"] == BLOB and loaded[412]["title"] == "Fix \\| thing"


# ---- permalink verification -----------------------------------------------


@pytest.fixture
def http_server(tmp_path):
    import http.server, threading, functools
    root = tmp_path / "www" / "o" / "r" / ("c" * 40) / DIR
    root.mkdir(parents=True)
    (root / "000410.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (root / "000411.svg").write_text("not really an image")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path / "www"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_url_ok_requires_200_and_svg_content(sw, http_server):
    base = f"{http_server}/o/r/{'c' * 40}/{DIR}"
    ok, detail = sw.url_ok(f"{base}/000410.svg")
    assert ok and detail.startswith("200"), detail
    ok, detail = sw.url_ok(f"{base}/000411.svg")
    assert not ok, "plain text is not an image"
    ok, detail = sw.url_ok(f"{base}/000999.svg")
    assert not ok and "404" in detail
    ok, detail = sw.url_ok("http://127.0.0.1:9/nothing.svg", timeout=2)
    assert not ok


def test_description_reread_must_show_the_permalink(world):
    """If the PATCH 'succeeds' but the body does not carry the permalink, keep the file."""
    gh = world["bin"] / "gh"
    gh.write_text(gh.read_text().replace('prs[n]["body"] = body; ', ""))  # fake gh forgets the edit
    r = run_sweep(world, "--mode", "none", "--keep-days", "7")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("does not show the permalink after update — kept") == 2
    assert (world["repo"] / DIR / "000410.svg").exists() and (world["repo"] / DIR / "000411.svg").exists()
    assert "nothing swept" in r.stdout


# ---- end to end with a fake gh ---------------------------------------------


@pytest.fixture
def world(tmp_path):
    """A repo checkout with three merged visuals + one open one, and a fake gh
    that serves PR metadata / file-at-sha lookups and records mutations."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    d = repo / DIR
    d.mkdir()
    for n in (410, 411, 412, 413):
        (d / f"{n:06d}.svg").write_text(f"<svg>{n}</svg>")
    (d / "README.md").write_text("# visuals\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed"], check=True)

    answers = tmp_path / "answers"
    answers.mkdir()
    prs = {
        410: pr(410, 30, body=f"![Visual summary](https://raw.githubusercontent.com/{REPO}/feat/{DIR}/000410.svg)\n\nOld PR"),
        411: pr(411, 10, body="No picture here"),
        412: pr(412, 2, body="Recent"),
        413: {"number": 413, "state": "open", "merged_at": None, "body": "", "title": "open"},
    }
    (answers / "prs.json").write_text(json.dumps({str(k): v for k, v in prs.items()}))
    # 411's file "exists" at its merge sha; 410's too. Anything else 404s.
    (answers / "exists.json").write_text(json.dumps([f"{DIR}/000410.svg@{410:040x}", f"{DIR}/000411.svg@{411:040x}", f"{DIR}/000412.svg@{412:040x}"]))

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f'''#!/usr/bin/env python3
import json, sys, pathlib, re
A = pathlib.Path({str(answers)!r})
args = sys.argv[1:]
(A / "calls.log").open("a").write(json.dumps(args) + "\\n")
prs = json.loads((A / "prs.json").read_text()); exists = set(json.loads((A / "exists.json").read_text()))
if args[:1] == ["api"]:
    if "-X" in args and "PATCH" in args:
        n = re.search(r"/pulls/(\\d+)", " ".join(args)).group(1)
        body = json.loads(pathlib.Path(args[args.index("--input") + 1]).read_text())["body"]
        (A / f"patched-{{n}}.md").write_text(body)
        prs[n]["body"] = body; (A / "prs.json").write_text(json.dumps(prs)); print("{{}}"); sys.exit(0)
    m = re.fullmatch(r"repos/[^/]+/[^/]+/pulls/(\\d+)", args[1])
    if m:
        n = m.group(1)
        if n in prs: print(json.dumps(prs[n])); sys.exit(0)
        print("gh: HTTP 404", file=sys.stderr); sys.exit(1)
    m = re.fullmatch(r"repos/[^/]+/[^/]+/contents/(.+)\\?ref=([0-9a-f]+)", args[1])
    if m:
        if f"{{m.group(1)}}@{{m.group(2)}}" in exists: print(json.dumps({{"size": 1}})); sys.exit(0)
        print("gh: HTTP 404", file=sys.stderr); sys.exit(1)
if args[:2] == ["pr", "create"]:
    (A / "pr-create.json").write_text(json.dumps(args)); print("https://github.com/{REPO}/pull/999"); sys.exit(0)
print("fake gh: unhandled " + " ".join(args), file=sys.stderr); sys.exit(1)
''')
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return {"repo": repo, "answers": answers, "bin": bin_dir}


def run_sweep(world, *args):
    env = dict(os.environ, PATH=f"{world['bin']}:{os.environ['PATH']}")
    return subprocess.run([sys.executable, str(SCRIPT), "--repo", REPO, "--no-verify-urls", *args], cwd=world["repo"],
                          env=env, capture_output=True, text=True)


def test_dry_run_changes_nothing(world):
    r = run_sweep(world, "--dry-run", "--keep-days", "7")
    assert r.returncode == 0, r.stderr
    assert "2 to sweep" in r.stdout and "dry run" in r.stdout
    assert not list(world["answers"].glob("patched-*.md"))
    assert (world["repo"] / DIR / "000410.svg").exists()


def test_sweep_rewrites_descriptions_archives_and_removes(world):
    r = run_sweep(world, "--mode", "none", "--keep-days", "7")
    assert r.returncode == 0, r.stderr + r.stdout
    d = world["repo"] / DIR
    # 410 and 411 swept; 412 too recent; 413 open; README untouched.
    assert not (d / "000410.svg").exists() and not (d / "000411.svg").exists()
    assert (d / "000412.svg").exists() and (d / "000413.svg").exists() and (d / "README.md").exists()
    # Descriptions: 410's branch URL became the merge permalink; 411 got one prepended.
    p410 = (world["answers"] / "patched-410.md").read_text()
    assert p410.startswith(f"![Visual summary](https://raw.githubusercontent.com/{REPO}/{410:040x}/{DIR}/000410.svg)")
    p411 = (world["answers"] / "patched-411.md").read_text()
    assert p411.startswith(f"[![Visual summary](https://raw.githubusercontent.com/{REPO}/{411:040x}/{DIR}/000411.svg)](https://github.com/{REPO}/blob/{411:040x}/{DIR}/000411.svg)")
    assert "No picture here" in p411
    assert not (world["answers"] / "patched-412.md").exists()
    # Archive indexes both, newest first, and is committed with the removals.
    archive = (d / "ARCHIVE.md").read_text()
    assert archive.index("| #411 |") < archive.index("| #410 |")
    assert f"https://github.com/{REPO}/blob/{410:040x}/{DIR}/000410.svg" in archive
    log = subprocess.run(["git", "-C", str(world["repo"]), "log", "-1", "--format=%s%n%b", "--stat"], capture_output=True, text=True).stdout
    assert "Sweep 2 merged PR visual(s) older than 7 day(s)" in log
    assert r.stdout.count("description confirmed") == 2
    assert "000410.svg" in log and "000411.svg" in log and "ARCHIVE.md" in log
    assert subprocess.run(["git", "-C", str(world["repo"]), "status", "--porcelain"], capture_output=True, text=True).stdout == ""


def test_sweep_is_idempotent(world):
    run_sweep(world, "--mode", "none", "--keep-days", "7")
    r = run_sweep(world, "--mode", "none", "--keep-days", "7")
    assert r.returncode == 0 and "0 to sweep" in r.stdout


def test_missing_file_at_merge_commit_is_kept(world):
    (world["answers"] / "exists.json").write_text(json.dumps([f"{DIR}/000410.svg@{410:040x}"]))
    r = run_sweep(world, "--mode", "none", "--keep-days", "7")
    assert r.returncode == 0, r.stderr
    assert "#411" in r.stdout and "not found at merge commit" in r.stdout and "nor at any pushed commit" in r.stdout
    assert (world["repo"] / DIR / "000411.svg").exists() and not (world["repo"] / DIR / "000410.svg").exists()


def test_renamed_directory_falls_back_to_newest_commit_with_the_file(world):
    """PR #1 of visual-pr: its SVG was at 000-pr-visualization/ when merged, so the
    merge commit has nothing at the current path. The newest commit that does
    (HEAD here) is still a permanent link, so sweep with that."""
    head = subprocess.run(["git", "-C", str(world["repo"]), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (world["answers"] / "exists.json").write_text(json.dumps([f"{DIR}/000410.svg@{410:040x}", f"{DIR}/000411.svg@{head}"]))
    r = run_sweep(world, "--mode", "none", "--keep-days", "7")
    assert r.returncode == 0, r.stderr + r.stdout
    assert f"using {head[:8]}, the newest commit with it" in r.stdout
    assert not (world["repo"] / DIR / "000411.svg").exists()
    p411 = (world["answers"] / "patched-411.md").read_text()
    assert f"https://raw.githubusercontent.com/{REPO}/{head}/{DIR}/000411.svg" in p411
    assert f"/blob/{head}/{DIR}/000411.svg" in (world["repo"] / DIR / "ARCHIVE.md").read_text()


def test_pr_mode_opens_a_labeled_pr_on_a_dated_branch(world):
    # Give the repo an "origin" to push to.
    remote = world["repo"].parent / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(world["repo"]), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(world["repo"]), "branch", "-M", "main"], check=True)
    r = run_sweep(world, "--mode", "pr", "--keep-days", "7", "--keep-last", "1")
    assert r.returncode == 0, r.stderr + r.stdout
    create = json.loads((world["answers"] / "pr-create.json").read_text())
    assert "--label" in create and create[create.index("--label") + 1] == "no-visual"
    assert create[create.index("--base") + 1] == "main"
    head = create[create.index("--head") + 1]
    assert head.startswith("visual-pr/sweep-")
    branches = subprocess.run(["git", "-C", str(remote), "branch"], capture_output=True, text=True).stdout
    assert head in branches
    # keep-last 1 protects only 412 (the newest merged); 411 and 410 are both past keep-days.
    assert "2 to sweep" in r.stdout


def test_keep_last_protects_newest_even_when_old(world):
    r = run_sweep(world, "--dry-run", "--keep-days", "0", "--keep-last", "2")
    assert "1 to sweep" in r.stdout and "#410" in r.stdout
