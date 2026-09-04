"""pr_body_image.py: does the PR description show the summary, and first?"""

import importlib.util
import subprocess
import sys

import pytest

from conftest import ROOT

SCRIPT = ROOT / "pr_body_image.py"
SVG = ".0-pr-viz/000412.svg"
RAW = f"https://raw.githubusercontent.com/acme/widgets/0123abcd/{SVG}"


def load():
    spec = importlib.util.spec_from_file_location("pr_body_image", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def m():
    return load()


def ok(m, body, mode="first"):
    return m.check(body, SVG, mode)[0]


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
    f"https://raw.githubusercontent.com/acme/widgets/main/{SVG}",
    f"https://raw.githubusercontent.com/acme/widgets/refs/heads/feature/x/{SVG}",
    f"https://github.com/acme/widgets/blob/0123abcd/{SVG}?raw=true",
    f"https://github.com/acme/widgets/raw/0123abcd/{SVG}#frag",
    SVG,
])
def test_any_url_ending_with_the_repo_path_counts(m, url):
    assert ok(m, f"![s]({url})")


@pytest.mark.parametrize("url", [
    "https://raw.githubusercontent.com/acme/widgets/main/.0-pr-viz/000413.svg",
    "https://raw.githubusercontent.com/acme/widgets/main/000412.svg",
    "https://example.com/000412.svg",
    "https://raw.githubusercontent.com/acme/widgets/main/x.0-pr-viz/000412.svg",
])
def test_other_images_do_not_count(m, url):
    assert not ok(m, f"![s]({url})", "included")


def test_first_mode_rejects_image_later_in_body(m):
    body = f"## Summary\n\nThings.\n\n![s]({RAW})"
    passed, why = m.check(body, SVG, "first")
    assert not passed and "does not open with it" in why
    assert ok(m, body, "included")


def test_first_mode_rejects_other_image_first(m):
    body = f"![badge](https://img.shields.io/x.svg)\n![s]({RAW})"
    assert not ok(m, body, "first")
    assert ok(m, body, "included")


def test_missing_image_fails_both_modes_and_not_required_always_passes(m):
    body = "## Summary\n\nno picture"
    passed, why = m.check(body, SVG, "first")
    assert not passed and why == f"PR description has no image of {SVG}"
    assert not ok(m, body, "included")
    assert ok(m, body, "not-required") and ok(m, "", "not-required")


def test_empty_body(m):
    assert not ok(m, "", "first") and not ok(m, "", "included")


def test_cli_exit_codes():
    def run(body, mode):
        return subprocess.run([sys.executable, str(SCRIPT), "--mode", mode, "--svg-path", SVG],
                              input=body, capture_output=True, text=True)

    r = run(f"![s]({RAW})", "first")
    assert r.returncode == 0 and "opens with an image" in r.stdout
    r = run("nothing", "first")
    assert r.returncode == 1 and "has no image" in r.stdout
    r = run("nothing", "not-required")
    assert r.returncode == 0
    r = run("x", "sometimes")
    assert r.returncode == 2
