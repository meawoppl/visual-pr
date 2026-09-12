"""pr_body_image.py: does the PR description show the summary, first, and durably?"""

import importlib.util
import subprocess
import sys

import pytest

from conftest import ROOT

SCRIPT = ROOT / "pr_body_image.py"
SVG = ".0-pr-viz/000412.svg"
REPO = "acme/widgets"
SHA = "0123abcd" * 5  # 40 hex characters, the shape GitHub hands out
RAW = f"https://raw.githubusercontent.com/{REPO}/{SHA}/{SVG}"
BLOB = f"https://github.com/{REPO}/blob/{SHA}/{SVG}?raw=true"


def load():
    spec = importlib.util.spec_from_file_location("pr_body_image", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def m():
    return load()


def ok(m, body, mode="first", repos=()):
    return m.check(body, SVG, mode, repos)[0]


def why(m, body, mode="first", repos=()):
    return m.check(body, SVG, mode, repos)[1]


def test_image_first_passes(m):
    assert ok(m, f"![Visual summary]({RAW})\n\nSome text.")
    assert ok(m, f"\n\n  ![x]({RAW})")


def test_leading_html_comment_and_link_wrapper_are_fine(m):
    assert ok(m, f"<!-- PR template: fill me in -->\n\n[![summary]({RAW})](https://example.com)\n\nBody")
    assert ok(m, f"<!-- a --><!-- b -->\n![s]({RAW} \"title\")")


def test_html_img_counts(m):
    assert ok(m, f'<img src="{RAW}" width="800">\n\ntext')
    assert ok(m, f"<img alt='s' src='{RAW}'/>")


@pytest.mark.parametrize("url", [
    RAW,
    BLOB,
    f"https://github.com/{REPO}/blob/{SHA}/{SVG}",
    f"https://github.com/{REPO}/raw/{SHA}/{SVG}#frag",
    f"https://raw.githubusercontent.com/{REPO}/{SHA.upper()}/{SVG}",
    f"HTTPS://RAW.GITHUBUSERCONTENT.COM/{REPO}/{SHA}/{SVG}",
])
def test_permalinks_count(m, url):
    assert ok(m, f"![s]({url})")


@pytest.mark.parametrize("url", [
    # A branch ref: fine today, 404 the moment the branch is deleted at merge.
    f"https://raw.githubusercontent.com/{REPO}/main/{SVG}",
    f"https://raw.githubusercontent.com/{REPO}/refs/heads/feature/x/{SVG}",
    f"https://github.com/{REPO}/blob/main/{SVG}?raw=true",
    # A short SHA is not the permalink the action hands out.
    f"https://raw.githubusercontent.com/{REPO}/0123abcd/{SVG}",
    # Not GitHub at all, or not a URL at all.
    f"https://example.com/{REPO}/{SHA}/{SVG}",
    SVG,
    f"./{SVG}",
    # Right shape, wrong part of GitHub: no ref to pin.
    f"https://github.com/{REPO}/{SHA}/{SVG}",
])
def test_links_that_will_not_survive_are_rejected(m, url):
    assert not ok(m, f"![s]({url})", "included")
    assert not ok(m, f"![s]({url})", "first")


def test_branch_url_is_named_and_blamed(m):
    reason = why(m, f"![s](https://raw.githubusercontent.com/{REPO}/feature-x/{SVG})")
    assert "feature-x" in reason and "404s once the branch is deleted at merge" in reason


def test_blob_url_with_a_slashed_branch_is_already_broken(m):
    """GitHub cannot parse blob/<branch-with-slash>/<path>; say so, not "will rot"."""
    reason = why(m, f"![s](https://github.com/{REPO}/blob/docs/my-feature/{SVG}?raw=true)")
    assert "docs/my-feature" in reason and "404s today" in reason
    # The same branch on raw.githubusercontent.com does resolve — until the merge.
    reason = why(m, f"![s](https://raw.githubusercontent.com/{REPO}/docs/my-feature/{SVG})")
    assert "deleted at merge" in reason


def test_non_github_url_names_the_replacement(m):
    reason = why(m, f"![s](https://cdn.example.com/{SVG})")
    assert "not a GitHub permalink" in reason
    assert f"https://raw.githubusercontent.com/OWNER/REPO/<head sha>/{SVG}" in reason


def test_repo_must_match_when_given(m):
    other = f"https://raw.githubusercontent.com/evil/typo/{SHA}/{SVG}"
    assert ok(m, f"![s]({other})")                      # no --repo: any repo passes
    assert not ok(m, f"![s]({other})", repos=(REPO,))
    assert "points at evil/typo, not acme/widgets" in why(m, f"![s]({other})", repos=(REPO,))


def test_repo_match_is_case_insensitive_and_accepts_head_or_base(m):
    fork = f"https://raw.githubusercontent.com/contributor/widgets/{SHA}/{SVG}"
    assert ok(m, f"![s]({RAW})", repos=("ACME/Widgets",))
    # A fork PR: the SVG lives on the fork now and on the base after the merge.
    assert ok(m, f"![s]({fork})", repos=("contributor/widgets", REPO))
    assert ok(m, f"![s]({RAW})", repos=("contributor/widgets", REPO))


def test_empty_repo_values_are_ignored(m):
    """The action passes whatever the event gave it; blanks must not reject everything."""
    assert ok(m, f"![s]({RAW})", repos=("",))


def test_a_durable_image_elsewhere_does_not_excuse_a_rotting_first_one(m):
    body = f"![s](https://raw.githubusercontent.com/{REPO}/main/{SVG})\n\n![s]({RAW})"
    assert ok(m, body, "included")
    passed, reason = m.check(body, SVG, "first")
    assert not passed and "not a 40-character commit SHA" in reason


def test_first_mode_rejects_image_later_in_body(m):
    body = f"## Summary\n\nThings.\n\n![s]({RAW})"
    passed, reason = m.check(body, SVG, "first")
    assert not passed and "does not open with it" in reason
    assert ok(m, body, "included")


def test_first_mode_rejects_other_image_first(m):
    body = f"![badge](https://img.shields.io/x.svg)\n![s]({RAW})"
    assert not ok(m, body, "first")
    assert ok(m, body, "included")


@pytest.mark.parametrize("url", [
    f"https://raw.githubusercontent.com/{REPO}/{SHA}/.0-pr-viz/000413.svg",
    f"https://raw.githubusercontent.com/{REPO}/{SHA}/000412.svg",
    f"https://raw.githubusercontent.com/{REPO}/{SHA}/x.0-pr-viz/000412.svg",
])
def test_other_images_do_not_count(m, url):
    assert not ok(m, f"![s]({url})", "included")
    assert why(m, f"![s]({url})", "included") == f"PR description has no image of {SVG}"


def test_missing_image_fails_both_modes_and_not_required_always_passes(m):
    body = "## Summary\n\nno picture"
    passed, reason = m.check(body, SVG, "first")
    assert not passed and reason == f"PR description has no image of {SVG}"
    assert not ok(m, body, "included")
    assert ok(m, body, "not-required") and ok(m, "", "not-required")


def test_empty_body(m):
    assert not ok(m, "", "first") and not ok(m, "", "included")


def test_points_at_stays_loose_for_the_sweep(m):
    """sweep_merged.py finds rotting URLs with points_at in order to repair them."""
    assert m.points_at(f"https://raw.githubusercontent.com/{REPO}/main/{SVG}", SVG)
    assert m.points_at(f"https://github.com/{REPO}/blob/main/{SVG}?raw=true", SVG)
    assert m.points_at(SVG, SVG)
    assert not m.points_at(f"https://raw.githubusercontent.com/{REPO}/main/x{SVG}", SVG)


def test_ref_of_splits_repo_and_ref(m):
    assert m.ref_of(RAW, SVG) == ("raw.githubusercontent.com", REPO, SHA)
    assert m.ref_of(BLOB, SVG) == ("github.com", REPO, SHA)
    assert m.ref_of(f"https://github.com/{REPO}/blob/docs/x/{SVG}", SVG) == ("github.com", REPO, "docs/x")
    assert m.ref_of(f"https://example.com/{REPO}/{SHA}/{SVG}", SVG) is None


def test_cli_exit_codes():
    def run(body, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--svg-path", SVG, *args],
                              input=body, capture_output=True, text=True)

    r = run(f"![s]({RAW})", "--mode", "first")
    assert r.returncode == 0 and "opens with an image" in r.stdout
    r = run(f"![s]({RAW})", "--mode", "first", "--repo", REPO)
    assert r.returncode == 0
    r = run(f"![s]({RAW})", "--mode", "first", "--repo", "someone/else")
    assert r.returncode == 1 and "points at acme/widgets" in r.stdout
    r = run(f"![s](https://raw.githubusercontent.com/{REPO}/main/{SVG})", "--mode", "first")
    assert r.returncode == 1 and "not a 40-character commit SHA" in r.stdout
    r = run("nothing", "--mode", "first")
    assert r.returncode == 1 and "has no image" in r.stdout
    r = run("nothing", "--mode", "not-required")
    assert r.returncode == 0
    r = run("x", "--mode", "sometimes")
    assert r.returncode == 2
