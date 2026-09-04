"""changed_lines.py: the small-change escape's arithmetic — API file list in,
counted total out, Linguist rules applied from the BASE checkout."""

import json
import subprocess
import sys

import pytest

from conftest import ROOT

SCRIPT = ROOT / "changed_lines.py"


def run(files, *args, cwd=None, ndjson=True):
    if ndjson:
        stdin = "".join(json.dumps(f) + "\n" for f in files)
    else:
        stdin = json.dumps(files)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def f(name, add=0, dele=0):
    return {"filename": name, "additions": add, "deletions": dele, "changes": add + dele}


@pytest.fixture
def repo(tmp_path):
    """A base checkout with .gitattributes, as $GITHUB_WORKSPACE would be."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitattributes").write_text(
        "gen/** linguist-generated=true\n"
        "vendor/** linguist-vendored\n"
        "docs/api.json linguist-generated\n"
        "keep/yarn.lock linguist-generated=false\n"
    )
    return tmp_path


def test_plain_sum_and_both_input_shapes(repo):
    files = [f("src/a.py", 10, 2), f("src/b.py", 3, 0)]
    for ndjson in (True, False):
        r = run(files, "--repo-root", str(repo), ndjson=ndjson)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "15"
        assert "count     12  src/a.py" in r.stderr and "total     15" in r.stderr


def test_svg_dir_never_counts(repo):
    files = [f("src/a.py", 1), f(".0-pr-viz/000412.svg", 500), f(".0-pr-viz", 1)]
    r = run(files, "--repo-root", str(repo))
    assert r.stdout.strip() == "1"
    assert "(visual summary)" in r.stderr
    r = run(files, "--repo-root", str(repo), "--svg-dir", "pics")
    assert r.stdout.strip() == "502"


def test_gitattributes_from_the_base_checkout_are_honored(repo):
    files = [f("gen/schema.ts", 900), f("vendor/lib.js", 400), f("docs/api.json", 50), f("src/a.py", 7)]
    r = run(files, "--repo-root", str(repo))
    assert r.stdout.strip() == "7", r.stderr
    assert "(linguist-generated)" in r.stderr and "(linguist-vendored)" in r.stderr


def test_builtin_lockfiles_are_generated_unless_repo_says_otherwise(repo):
    files = [f("package-lock.json", 3000), f("web/yarn.lock", 200), f("dist/app.min.js", 5000),
             f("api/v1_pb2.py", 800), f("keep/yarn.lock", 20), f("src/a.py", 1)]
    r = run(files, "--repo-root", str(repo))
    assert r.stdout.strip() == "21", r.stderr  # keep/yarn.lock is explicitly counted
    assert r.stderr.count("built-in Linguist rule") == 4


def test_count_everything_ignores_all_rules(repo):
    files = [f("gen/schema.ts", 900), f("package-lock.json", 3000), f(".0-pr-viz/000001.svg", 10)]
    r = run(files, "--repo-root", str(repo), "--count-everything")
    assert r.stdout.strip() == "3900"  # svg-dir is still excluded


def test_outside_a_git_repo_only_builtin_rules_apply(tmp_path):
    files = [f("gen/schema.ts", 900), f("package-lock.json", 3000), f("src/a.py", 1)]
    r = run(files, "--repo-root", str(tmp_path / "nowhere"))
    assert r.returncode == 0
    assert r.stdout.strip() == "901"


def test_missing_changes_field_falls_back_to_additions_plus_deletions(repo):
    r = run([{"filename": "a", "additions": 4, "deletions": 6}], "--repo-root", str(repo))
    assert r.stdout.strip() == "10"


def test_empty_input_is_zero_and_bad_json_is_exit_2(repo):
    r = subprocess.run([sys.executable, str(SCRIPT)], input="", capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "0"
    r = subprocess.run([sys.executable, str(SCRIPT)], input="{not json", capture_output=True, text=True)
    assert r.returncode == 2 and "could not parse" in r.stderr
