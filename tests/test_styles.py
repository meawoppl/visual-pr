"""Every bundled style must be a drop-in re-skin: same keys as the default,
14 palette slots in the documented semantic order, valid colors."""

import json
import pathlib
import re

import pytest

from conftest import ROOT

STYLE_DIR = ROOT / "style"
STYLES = sorted(STYLE_DIR.glob("*.json"))
DEFAULT = json.loads((STYLE_DIR / "default.json").read_text())
HEX = re.compile(r"^#[0-9a-f]{6}$")


def test_there_are_several_bundled_styles():
    assert len(STYLES) >= 5
    assert (STYLE_DIR / "default.json") in STYLES


@pytest.mark.parametrize("path", STYLES, ids=lambda p: p.stem)
def test_style_shape(path: pathlib.Path):
    style = json.loads(path.read_text())
    assert set(style) == set(DEFAULT), "bundled styles must define the same keys as default"
    pal = style["palette"]
    assert len(pal) == 14, "14 semantic slots: see style/README.md"
    assert pal[-1] == "none"
    colors = pal[:-1]
    assert all(HEX.match(c) for c in colors), "6-digit lowercase hex only"
    assert len(set(colors)) == len(colors), "palette slots must be distinct colors"
    assert style["canvas"] == [2000, 1200], "examples/build.py re-skins by index and assumes shared geometry"


@pytest.mark.parametrize("path", STYLES, ids=lambda p: p.stem)
def test_light_vs_dark_contrast_direction(path: pathlib.Path):
    """Background and thesis must sit at opposite ends of the luminance range."""
    pal = json.loads(path.read_text())["palette"]

    def lum(c: str) -> float:
        r, g, b = (int(c[i : i + 2], 16) / 255 for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    bg, thesis, muted = lum(pal[0]), lum(pal[6]), lum(pal[3])
    assert abs(bg - thesis) > 0.6, "thesis text must be high-contrast against the background"
    # Muted text sits between the two.
    assert min(bg, thesis) < muted < max(bg, thesis)


@pytest.mark.parametrize("path", STYLES, ids=lambda p: p.stem)
def test_template_reskinned_by_index_validates(path: pathlib.Path, run_check, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("build", ROOT / "examples" / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)

    dst_pal = json.loads(path.read_text())["palette"]
    skinned = build.reskin((ROOT / "template.svg").read_text(), DEFAULT["palette"], dst_pal)
    f = tmp_path / "t.svg"
    f.write_text(skinned)
    r = run_check("--style", path.stem, f)
    assert r.returncode == 0, r.stderr
    assert "0 warning(s)" in r.stdout


def test_bundled_name_resolution(check_svg):
    for path in STYLES:
        assert check_svg.resolve_style(path.stem) == path
    assert check_svg.bundled_styles() == [p.stem for p in STYLES]
    with pytest.raises(FileNotFoundError, match="neither a file nor a bundled style"):
        check_svg.resolve_style("not-a-style")
    # A path-like argument never falls back to a bundled name.
    with pytest.raises(FileNotFoundError):
        check_svg.resolve_style("some/dir/nord")


def test_unknown_bundled_name_exits_2_and_lists_options(run_check):
    r = run_check("--style", "not-a-style", ROOT / "template.svg")
    assert r.returncode == 2
    assert "bundled: default, dracula" in r.stderr


def test_default_json_matches_style_readme_table():
    readme = (STYLE_DIR / "README.md").read_text()
    for i, color in enumerate(DEFAULT["palette"]):
        assert re.search(rf"^\| {i} \| .* \| `{re.escape(color)}` \|$", readme, flags=re.M), (
            f"style/README.md row {i} should show {color}"
        )


@pytest.mark.parametrize("path", STYLES, ids=lambda p: p.stem)
def test_every_style_ships_the_same_glyph_allowlist(path: pathlib.Path):
    glyphs = json.loads(path.read_text())["glyphs"]
    assert glyphs == DEFAULT["glyphs"], "bundled styles differ only in palette"
    for item in glyphs:
        assert re.fullmatch(r"[0-9A-F]{4,6}(-[0-9A-F]{4,6})?", item), item
    # ASCII + Latin-1, nothing else: arrows and math operators rendered as boxes (issue #10).
    assert glyphs == ["0020-007E", "00A0-00FF"]
