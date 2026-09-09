"""Behavioral tests for check_svg.py: exit codes, error/warning routing,
style overrides, and the text-fit heuristics."""

import json
import xml.etree.ElementTree as ET

import pytest

from conftest import FIXTURES, ROOT

SVG_NS = "http://www.w3.org/2000/svg"


def svg(body: str, viewbox: str = "0 0 2000 1200") -> str:
    return f'<svg xmlns="{SVG_NS}" viewBox="{viewbox}">{body}</svg>'


# --------------------------------------------------------------------------
# CLI contract: exit codes and stream routing
# --------------------------------------------------------------------------


def test_bundled_template_passes_clean(run_check):
    r = run_check(ROOT / "template.svg")
    assert r.returncode == 0, r.stderr
    assert "ok: palette + canvas clean, 0 warning(s)" in r.stdout
    assert r.stderr == ""


def test_valid_fixture_passes(run_check):
    r = run_check(FIXTURES / "valid.svg")
    assert r.returncode == 0, r.stderr


def test_off_palette_color_is_hard_error(run_check):
    r = run_check(FIXTURES / "off-palette.svg")
    assert r.returncode == 1
    assert "fill='#ff0000' is off-palette" in r.stderr
    assert "stroke='#00ff00' is off-palette" in r.stderr
    assert "ok:" not in r.stdout


def test_wrong_canvas_is_hard_error(run_check):
    r = run_check(FIXTURES / "wrong-canvas.svg")
    assert r.returncode == 1
    assert "viewBox is '0 0 1920 1080', style requires '0 0 2000 1200'" in r.stderr


def test_missing_viewbox_is_hard_error(run_check, tmp_path):
    f = tmp_path / "x.svg"
    f.write_text(f'<svg xmlns="{SVG_NS}"><rect fill="#16161e"/></svg>')
    r = run_check(f)
    assert r.returncode == 1
    assert "viewBox is 'None'" in r.stderr


def test_malformed_xml_is_hard_error(run_check):
    r = run_check(FIXTURES / "malformed.svg")
    assert r.returncode == 1
    assert "not well-formed XML" in r.stderr


def test_missing_file_is_hard_error(run_check, tmp_path):
    r = run_check(tmp_path / "does-not-exist.svg")
    assert r.returncode == 1
    assert "not well-formed XML" in r.stderr


def test_warnings_go_to_stdout_and_do_not_fail(run_check):
    r = run_check(FIXTURES / "warnings-only.svg")
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""
    assert "warning: text likely overflows canvas" in r.stdout
    assert "warning: text crosses the BEFORE/AFTER divider" in r.stdout
    assert "warning: <text> 'no size here' has no font-size" in r.stdout
    assert "ok: palette + canvas clean, 3 warning(s)" in r.stdout


def test_errors_and_warnings_both_reported_but_errors_win(run_check, tmp_path):
    f = tmp_path / "x.svg"
    f.write_text(
        svg('<rect fill="#ff0000"/><text x="55" y="300" fill="#c0caf5">hi</text>')
    )
    r = run_check(f)
    assert r.returncode == 1
    assert "warning:" in r.stdout
    assert "ERROR:" in r.stderr


# --------------------------------------------------------------------------
# Style overrides
# --------------------------------------------------------------------------


def test_style_override_changes_contract(run_check):
    r = run_check("--style", FIXTURES / "style-red.json", FIXTURES / "red-100.svg")
    assert r.returncode == 0, r.stderr
    # Without the override the same file fails on both canvas and palette.
    r = run_check(FIXTURES / "red-100.svg")
    assert r.returncode == 1
    assert "off-palette" in r.stderr
    assert "viewBox" in r.stderr


def test_style_override_merges_with_defaults(check_svg, tmp_path):
    s = tmp_path / "s.json"
    s.write_text(json.dumps({"palette": ["#ABCDEF"]}))
    style = check_svg.load_style(str(s))
    # Overridden key replaces; palette is lower-cased.
    assert style["palette"] == {"#abcdef"}
    # Omitted keys keep the bundled defaults.
    default = json.loads((ROOT / "style" / "default.json").read_text())
    for key in ("canvas", "margin", "char_factor", "divider_x", "divider_band"):
        assert style[key] == default[key]


def test_default_style_palette_is_lowercased(check_svg):
    style = check_svg.load_style(None)
    assert all(c == c.lower() for c in style["palette"])
    assert "none" in style["palette"]


def test_unreadable_style_exits_2(run_check, tmp_path):
    missing = tmp_path / "nope.json"
    r = run_check("--style", missing, ROOT / "template.svg")
    assert r.returncode == 2
    assert "could not load style" in r.stderr

    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    r = run_check("--style", bad, ROOT / "template.svg")
    assert r.returncode == 2
    assert "could not load style" in r.stderr


# --------------------------------------------------------------------------
# check_colors
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["#7AA2F7", " #7aa2f7 ", "none", "NONE"])
def test_palette_match_is_case_and_whitespace_insensitive(check_svg, value):
    style = check_svg.load_style(None)
    check_svg.check_colors(ET.fromstring(f'<rect fill="{value}"/>'), style["palette"])
    assert check_svg.errors == []


@pytest.mark.parametrize("value", ["url(#grad)", "currentColor", "inherit"])
def test_palette_exempts_references_and_keywords(check_svg, value):
    style = check_svg.load_style(None)
    check_svg.check_colors(ET.fromstring(f'<path stroke="{value}"/>'), style["palette"])
    assert check_svg.errors == []


def test_off_palette_error_names_element_and_attr(check_svg):
    style = check_svg.load_style(None)
    elem = ET.fromstring(f'<path xmlns="{SVG_NS}" stroke="#123456"/>')
    check_svg.check_colors(elem, style["palette"])
    assert check_svg.errors == [
        "<path> stroke='#123456' is off-palette (allowed colors come from the style JSON)"
    ]


def test_missing_fill_and_stroke_are_fine(check_svg):
    style = check_svg.load_style(None)
    check_svg.check_colors(ET.fromstring("<g/>"), style["palette"])
    assert check_svg.errors == []


# --------------------------------------------------------------------------
# check_text — the fit heuristics documented in SPEC.md
# --------------------------------------------------------------------------


def _text(check_svg, markup: str):
    style = check_svg.load_style(None)
    check_svg.check_text(ET.fromstring(markup), style, inherited_size=23.0)
    return check_svg.warnings


def test_thesis_budget_from_spec_fits(check_svg):
    # SPEC: thesis line <=105 chars @34px on the default canvas.
    line = "x" * 105
    assert _text(check_svg, f'<text x="55" y="100" font-size="34">{line}</text>') == []


def test_thesis_over_budget_warns(check_svg):
    line = "x" * 120
    w = _text(check_svg, f'<text x="55" y="100" font-size="34">{line}</text>')
    assert len(w) == 1 and "likely overflows canvas" in w[0]


def test_footer_budget_from_spec_fits(check_svg):
    # SPEC: footer <=165 chars @22px.
    line = "x" * 165
    assert _text(check_svg, f'<text x="55" y="1172" font-size="22">{line}</text>') == []


def test_left_overflow_warns(check_svg):
    w = _text(check_svg, '<text x="10" y="300" font-size="23" text-anchor="end">hello</text>')
    assert len(w) == 1 and "likely overflows canvas" in w[0]


def test_text_anchor_middle_is_centered(check_svg):
    # 40 chars @ 23px * 0.5 = 460 wide, centered at 500 -> 270..730: fits.
    ok = _text(check_svg, f'<text x="500" y="300" font-size="23" text-anchor="middle">{"x" * 40}</text>')
    assert ok == []


def test_text_anchor_middle_crossing_divider_warns(check_svg):
    w = _text(check_svg, f'<text x="1000" y="600" font-size="23" text-anchor="middle">{"x" * 40}</text>')
    assert len(w) == 1 and "crosses the BEFORE/AFTER divider" in w[0]


def test_large_text_is_exempt_from_divider_check(check_svg):
    # Thesis-sized text (>=30px) legitimately spans both panels.
    assert _text(check_svg, f'<text x="55" y="100" font-size="34">{"x" * 100}</text>') == []


def test_text_outside_divider_band_is_exempt(check_svg):
    # Header (y=52) and footer (y=1172) sit outside divider_band [190, 1140].
    assert _text(check_svg, f'<text x="800" y="52" font-size="23">{"x" * 40}</text>') == []
    assert _text(check_svg, f'<text x="800" y="1172" font-size="23">{"x" * 40}</text>') == []


def test_units_on_font_size_are_stripped(check_svg):
    assert _text(check_svg, '<text x="55" y="300" font-size="23px">short</text>') == []


def test_tspan_without_font_size_inherits_and_does_not_warn(check_svg):
    style = check_svg.load_style(None)
    elem = ET.fromstring('<tspan x="55" y="300">short</tspan>')
    check_svg.check_text(elem, style, inherited_size=23.0)
    assert check_svg.warnings == []


def test_text_without_font_size_warns_once(check_svg):
    w = _text(check_svg, '<text x="55" y="300">short</text>')
    assert w == ["<text> 'short' has no font-size"]


def test_empty_text_and_non_numeric_x_are_skipped(check_svg):
    assert _text(check_svg, '<text x="55" y="300" font-size="23"></text>') == []
    assert _text(check_svg, f'<text x="10%" y="300" font-size="23">{"x" * 500}</text>') == []
    assert _text(check_svg, f'<text y="300" font-size="23">{"x" * 500}</text>') == []


def test_nested_tspans_are_measured_as_a_whole(check_svg):
    w = _text(
        check_svg,
        f'<text x="1100" y="300" font-size="23"><tspan>{"a" * 60}</tspan><tspan>{"b" * 60}</tspan></text>',
    )
    assert len(w) == 1 and "likely overflows canvas" in w[0]


def test_strip_ns(check_svg):
    assert check_svg.strip_ns(f"{{{SVG_NS}}}text") == "text"
    assert check_svg.strip_ns("text") == "text"


# --------------------------------------------------------------------------
# check_glyphs — characters the font stack would draw as missing-glyph boxes
# --------------------------------------------------------------------------


def test_tofu_fixture_is_a_hard_error_naming_each_character(run_check):
    r = run_check(FIXTURES / "tofu.svg")
    assert r.returncode == 1
    assert "U+1F680 '🚀' (ROCKET)" in r.stderr
    assert "U+E0B0" in r.stderr and "private-use" in r.stderr
    assert "U+200B '' (ZERO WIDTH SPACE)" in r.stderr
    assert "missing-glyph box" in r.stderr
    assert r.stderr.count("ERROR:") == 3


def test_latin1_is_allowed_and_beyond_is_not(check_svg):
    style = check_svg.load_style(None)
    ranges = check_svg.glyph_ranges(style)
    ok = "± µ · × ÷ ° § ¶ « » ¼ ½ ¾ ¡ ¿ © ® é ñ ü ß Ø å <- -> <= >= != ~ ... + x"
    e = ET.Element("text"); e.text = ok  # .text, so '<' needs no XML escaping here
    check_svg.check_glyphs(e, ranges)
    assert check_svg.errors == []
    # Everything that passed v2 and drew as boxes on a real viewer (issue #10).
    bad = "→ − ≈ — – … ✓ ≤ λ Я Ł"
    e = ET.Element("text"); e.text = bad
    check_svg.check_glyphs(e, ranges)
    assert len(check_svg.errors) == len(bad.split())


def test_glyph_error_suggests_the_ascii_replacement(check_svg):
    style = check_svg.load_style(None)
    ranges = check_svg.glyph_ranges(style)
    check_svg.check_glyphs(ET.fromstring("<text>a → b ≤ c — d</text>"), ranges)
    msgs = "\n".join(check_svg.errors)
    assert "U+2192 '→' (RIGHTWARDS ARROW), outside the style's glyph allowlist" in msgs
    assert "write '->' instead" in msgs and "write '<=' instead" in msgs and "write ' - ' instead" in msgs


def test_whitespace_and_each_offender_reported_once(check_svg):
    style = check_svg.load_style(None)
    ranges = check_svg.glyph_ranges(style)
    check_svg.check_glyphs(ET.fromstring("<text>a\tb\nc 🚀🚀 🚀</text>"), ranges)
    assert len(check_svg.errors) == 1


def test_glyph_check_sees_tspans_through_the_parent_text(run_check, tmp_path):
    f = tmp_path / "x.svg"
    f.write_text(svg('<text x="55" y="300" font-size="23" fill="#c0caf5"><tspan>ok</tspan><tspan>🙂</tspan></text>'))
    r = run_check(f)
    assert r.returncode == 1 and r.stderr.count("ERROR:") == 1


def test_style_can_extend_or_replace_the_allowlist(run_check, tmp_path):
    f = tmp_path / "x.svg"
    f.write_text(svg('<text x="55" y="300" font-size="23" fill="#c0caf5">🙂</text>'))
    s = tmp_path / "s.json"
    s.write_text(json.dumps({"glyphs": ["0020-007E", "1F642"]}))
    r = run_check("--style", s, f)
    assert r.returncode == 0, r.stderr
    # An empty allowlist disables the check entirely.
    s.write_text(json.dumps({"glyphs": []}))
    r = run_check("--style", s, f)
    assert r.returncode == 0, r.stderr


def test_glyph_ranges_parse_points_and_ranges(check_svg):
    assert check_svg.glyph_ranges({"glyphs": ["0020-007E", "2044"]}) == [(0x20, 0x7E), (0x2044, 0x2044)]
    assert check_svg.glyph_ranges({}) == []


def test_template_and_examples_use_only_allowed_glyphs(run_check):
    for f in [ROOT / "template.svg", *sorted((ROOT / "examples" / "src").glob("*.svg"))]:
        r = run_check(f)
        assert r.returncode == 0, f"{f.name}: {r.stderr}"


# --------------------------------------------------------------------------
# check_box_fit — text must stay inside the <g><rect/><text/></g> it belongs to
# --------------------------------------------------------------------------


def _box(check_svg, inner: str):
    style = check_svg.load_style(None)
    check_svg.check_box_fit(ET.fromstring(f"<g>{inner}</g>"), style)
    return check_svg.warnings


RECT = '<rect x="80" y="250" width="480" height="150"/>'


def test_text_that_fits_its_box_is_silent(check_svg):
    # 432px interior at 23px*0.5 -> 37 chars fits comfortably.
    assert _box(check_svg, RECT + f'<text x="104" y="290" font-size="23">{"x" * 30}</text>') == []


def test_text_running_past_the_right_edge_warns(check_svg):
    w = _box(check_svg, RECT + f'<text x="104" y="290" font-size="23">{"x" * 45}</text>')
    assert len(w) == 1 and "overruns its box" in w[0] and "shorten or split" in w[0]


def test_text_anchor_end_and_middle_are_measured_from_the_anchor(check_svg):
    assert _box(check_svg, RECT + f'<text x="540" y="290" font-size="23" text-anchor="end">{"x" * 30}</text>') == []
    assert _box(check_svg, RECT + f'<text x="320" y="290" font-size="23" text-anchor="middle">{"x" * 30}</text>') == []
    w = _box(check_svg, RECT + f'<text x="320" y="290" font-size="23" text-anchor="middle">{"x" * 45}</text>')
    assert len(w) == 1


def test_text_below_the_box_warns(check_svg):
    w = _box(check_svg, RECT + '<text x="104" y="420" font-size="23">late</text>')
    assert len(w) == 1 and "outside its box" in w[0]


def test_groups_without_exactly_one_rect_are_not_boxes(check_svg):
    long = f'<text x="104" y="290" font-size="23">{"x" * 80}</text>'
    assert _box(check_svg, long) == []
    assert _box(check_svg, RECT + RECT + long) == []


def test_box_fit_runs_from_main(run_check, tmp_path):
    f = tmp_path / "x.svg"
    f.write_text(svg(
        '<g><rect x="80" y="250" width="480" height="150" fill="#1e202e" stroke="#3d4666"/>'
        f'<text x="104" y="290" font-size="23" fill="#a9b1d6">{"x" * 45}</text></g>'
    ))
    r = run_check(f)
    assert r.returncode == 0
    assert "warning: text likely overruns its box" in r.stdout


def test_template_and_examples_have_no_box_overruns(run_check):
    for f in [ROOT / "template.svg", *sorted((ROOT / "examples" / "src").glob("*.svg"))]:
        r = run_check(f)
        assert "0 warning(s)" in r.stdout, f"{f.name}: {r.stdout}"
