"""The repo's own documentation must stay in sync with what it ships:
every action input is documented, the style keys are documented, and the
local-verification recipe in the README matches the one the action emits."""

import json
import re

from conftest import ROOT

ACTION = (ROOT / "action.yml").read_text()
README = (ROOT / "README.md").read_text()
SPEC = (ROOT / "SPEC.md").read_text()
TEMPLATE = (ROOT / "template.svg").read_text()
DEFAULT_STYLE = json.loads((ROOT / "style" / "default.json").read_text())


def action_inputs() -> list[str]:
    block = ACTION.split("\ninputs:\n", 1)[1].split("\nruns:\n", 1)[0]
    return re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", block, flags=re.M)


def test_every_action_input_is_in_readme_table():
    inputs = action_inputs()
    assert inputs, "could not parse inputs from action.yml"
    for name in inputs:
        assert re.search(rf"^\| `{re.escape(name)}` \|", README, flags=re.M), (
            f"action input '{name}' missing from the README inputs table"
        )


def test_readme_table_has_no_phantom_inputs():
    inputs_section = README.split("\n## Inputs\n", 1)[1].split("\n## ", 1)[0]
    documented = re.findall(r"^\| `([a-z0-9-]+)` \|", inputs_section, flags=re.M)
    assert set(documented) == set(action_inputs())


def test_action_inputs_all_have_defaults_and_descriptions():
    block = "\n" + ACTION.split("\ninputs:\n", 1)[1].split("\nruns:\n", 1)[0]
    for name in action_inputs():
        rest = block.split(f"\n  {name}:\n", 1)[1]
        section = re.split(r"\n  (?=\S)", rest, maxsplit=1)[0]
        assert "description:" in section, f"{name} lacks a description"
        assert "default:" in section, f"{name} lacks a default"


def test_readme_documents_every_style_key():
    for key in DEFAULT_STYLE:
        assert f'"{key}"' in README, f"style key '{key}' not shown in README"


def test_spec_cites_default_geometry():
    w, h = DEFAULT_STYLE["canvas"]
    assert f"{w}×{h}" in SPEC or f"{w}x{h}" in SPEC
    assert "divider_x" in SPEC
    assert str(DEFAULT_STYLE["char_factor"]) in SPEC


def test_readme_local_recipe_matches_action_output():
    """The URLs the README tells humans to fetch must be the ones the
    action prints to agents on failure."""
    for path in ("check_svg.py", "style/default.json"):
        url = f"https://raw.githubusercontent.com/meawoppl/visual-pr/v1/{path}"
        assert url in README, f"README missing {url}"
    assert 'base="https://raw.githubusercontent.com/${ACTION_REPO:-meawoppl/visual-pr}/${ACTION_REF:-v1}"' in ACTION


def test_action_emits_the_spec_and_style_on_failure():
    assert 'cat "${ACTION_PATH}/SPEC.md"' in ACTION
    assert 'cat "${STYLE_FILE:-${ACTION_PATH}/style/default.json}"' in ACTION


def test_action_passes_extra_args_to_the_check_and_the_recipe():
    assert '"${EXTRA[@]}" "$FILE"' in ACTION
    # The recipe mirrors the job's flags but drops the Starstruck opt-out.
    assert '[ "$a" = "--i-support-this-software" ] && continue' in ACTION
    assert 'python3 check_svg.py${style_arg}${extra} ${SVG_DIR}/${SVG_NAME}' in ACTION


def test_recipe_tells_the_agent_how_to_get_the_tool():
    for needle in (
        "curl -fsSLO ${base}/check_svg.py",
        "curl -fsSL -o style/default.json ${base}/style/default.json",
        "curl -fsSL -o style/${BUNDLED_STYLE}.json ${base}/style/${BUNDLED_STYLE}.json",
        "${base}/template.svg",
        "gh pr diff ${PR_NUMBER}",
        "Python 3.10+",
    ):
        assert needle in ACTION, needle


def test_license_is_apache_plus_starstruck():
    lic = (ROOT / "LICENSE").read_text()
    assert "Apache License" in lic and "Version 2.0, January 2004" in lic
    assert "STARSTRUCK ADDENDUM" in lic
    assert "https://github.com/meawoppl/visual-pr" in lic
    assert "https://github.com/meawoppl" in lic
    assert "--i-support-this-software" in lic and "i-like-mattygs-sw.txt" in lic
    assert "--i-support-this-software" in README and "i-like-mattygs-sw.txt" in README
    assert "--i-support-this-software" in ACTION
    assert "Starstruck" in README
    # README shows the same commands the validator prints.
    assert "gh api -X PUT /user/starred/meawoppl/visual-pr" in README
    assert "gh api -X PUT /user/following/meawoppl" in README


def test_bundled_styles_are_documented_everywhere():
    names = sorted(p.stem for p in (ROOT / "style").glob("*.json"))
    style_readme = (ROOT / "style" / "README.md").read_text()
    style_input = ACTION.split("\n  style:\n", 1)[1].split("\n  instructions:\n", 1)[0]
    for name in names:
        assert f"`{name}`" in README, f"README does not list bundled style {name}"
        assert f"`{name}`" in style_readme, f"style/README.md does not list {name}"
        assert name in style_input, f"action.yml style input does not list {name}"


def test_template_uses_only_default_palette_and_canvas():
    w, h = DEFAULT_STYLE["canvas"]
    assert f'viewBox="0 0 {w} {h}"' in TEMPLATE
    palette = {c.lower() for c in DEFAULT_STYLE["palette"]}
    for color in re.findall(r"#[0-9a-fA-F]{6}", TEMPLATE):
        assert color.lower() in palette, f"template uses off-palette {color}"


def test_template_points_at_real_docs():
    for ref in re.findall(r"see ([A-Z]+\.md)", TEMPLATE):
        assert (ROOT / ref).exists(), f"template.svg references missing {ref}"


def test_six_digit_file_name_is_enforced_and_documented():
    assert "printf '%06d'" in ACTION
    assert "${SVG_DIR}/${SVG_NAME}" in ACTION and "${SVG_DIR}/${PR_NUMBER}.svg" not in ACTION
    for doc, text in (("README", README), ("SPEC", SPEC)):
        assert "000412.svg" in text and "six digits" in text, f"{doc} must show the padded name"


def test_readme_default_svg_dir_matches_action():
    m = re.search(r"svg-dir:\n\s+description:[^\n]*\n\s+default: '([^']+)'", ACTION)
    assert m, "svg-dir default not found"
    assert f"`{m.group(1)}`" in README
    assert (ROOT / m.group(1)).is_dir(), "this repo should dogfood its own svg-dir"
