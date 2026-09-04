"""The example matrix is generated; committed outputs must be fresh and every
cell must validate against its own style."""

import importlib.util
import re
import subprocess
import sys

import pytest

from conftest import ROOT

EXAMPLES = ROOT / "examples"
SOURCES = sorted((EXAMPLES / "src").glob("*.svg"))


def load_build():
    spec = importlib.util.spec_from_file_location("build", EXAMPLES / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_five_example_prs_with_six_digit_names_and_matching_headers():
    assert len(SOURCES) == 5
    for src in SOURCES:
        assert re.fullmatch(r"\d{6}", src.stem), f"{src.name} must use the six-digit name"
        m = re.search(r">PR #(\d+) · ", src.read_text())
        assert m and int(m.group(1)) == int(src.stem), f"{src.name} header must say PR #{int(src.stem)}"


def test_committed_outputs_are_fresh():
    r = subprocess.run(
        [sys.executable, str(EXAMPLES / "build.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("style", load_build().STYLE_ORDER)
@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.stem)
def test_every_cell_validates_clean(style, src, run_check):
    out = EXAMPLES / style / src.name
    assert out.exists()
    r = run_check("--style", style, out)
    assert r.returncode == 0, r.stderr
    assert "0 warning(s)" in r.stdout, r.stdout


def test_reskin_only_touches_fill_and_stroke():
    build = load_build()
    text = '<text fill="#7aa2f7">PR #7aa2f7 · color-ish title</text><rect stroke="#16161e" data-fill="#16161e"/>'
    out = build.reskin(text, ["#7aa2f7", "#16161e", "none"], ["#000001", "#000002", "none"])
    assert out == '<text fill="#000001">PR #7aa2f7 · color-ish title</text><rect stroke="#000002" data-fill="#16161e"/>'


def test_matrix_svg_has_one_cell_per_pair_with_unique_ids():
    build = load_build()
    matrix = (EXAMPLES / "matrix.svg").read_text()
    n = len(SOURCES) * len(build.STYLE_ORDER)
    assert matrix.count('viewBox="0 0 2000 1200"') == n
    ids = re.findall(r'\bid="([^"]+)"', matrix)
    assert len(ids) == len(set(ids)), "nested example ids must be namespaced"
    for ref in re.findall(r"url\(#([^)]+)\)", matrix):
        assert ref in ids, f"dangling reference #{ref}"


def test_examples_readme_links_every_cell():
    build = load_build()
    readme = (EXAMPLES / "README.md").read_text()
    for src in SOURCES:
        for style in build.STYLE_ORDER:
            assert f"({style}/{src.name})" in readme
    assert "![matrix](matrix.svg)" in readme
