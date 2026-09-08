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


def inputs_block() -> str:
    return ACTION.split("\ninputs:\n", 1)[1].split("\noutputs:\n", 1)[0].split("\nruns:\n", 1)[0]


def action_inputs() -> list[str]:
    block = inputs_block()
    return re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", block, flags=re.M)


def test_every_action_input_is_in_readme_table():
    inputs = action_inputs()
    assert inputs, "could not parse inputs from action.yml"
    for name in inputs:
        assert re.search(rf"^\| `{re.escape(name)}` \|", README, flags=re.M), (
            f"action input '{name}' missing from the README inputs table"
        )


def test_readme_table_has_no_phantom_inputs():
    inputs_section = re.split(r"\n#{2,3} ", README.split("\n## Inputs\n", 1)[1], maxsplit=1)[0]
    documented = re.findall(r"^\| `([a-z0-9-]+)` \|", inputs_section, flags=re.M)
    assert set(documented) == set(action_inputs())


def test_action_inputs_all_have_defaults_and_descriptions():
    block = "\n" + inputs_block()
    for name in action_inputs():
        rest = block.split(f"\n  {name}:\n", 1)[1]
        section = re.split(r"\n  (?=\S)", rest, maxsplit=1)[0]
        assert "description:" in section, f"{name} lacks a description"
        assert "default:" in section, f"{name} lacks a default"


def test_every_action_output_is_documented():
    block = ACTION.split("\noutputs:\n", 1)[1].split("\nruns:\n", 1)[0]
    outputs = re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", block, flags=re.M)
    assert outputs == ["outcome", "svg"]
    for name in outputs:
        assert re.search(rf"^\| `{name}` \|", README, flags=re.M), f"output '{name}' missing from README"
    for value in ("passed", "skipped-label", "skipped-small-change", "missing", "invalid",
                  "body-image-missing", "bad-style", "bad-input"):
        assert f"outcome {value}" in ACTION, f"action never emits outcome {value}"
        assert f"`{value}`" in README


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
        url = f"https://raw.githubusercontent.com/meawoppl/visual-pr/v2/{path}"
        assert url in README, f"README missing {url}"
    assert 'base="https://raw.githubusercontent.com/${ACTION_REPO:-meawoppl/visual-pr}/${ACTION_REF:-v2}"' in ACTION


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


def test_quick_start_listens_for_edited_so_body_fixes_rerun():
    quick = README.split("## Quick start", 1)[1].split("\n## ", 1)[0]
    assert "types: [opened, edited, synchronize, reopened, labeled, unlabeled]" in quick
    dogfood = (ROOT / ".github" / "workflows" / "visual-pr.yml").read_text()
    assert "edited" in dogfood


def test_body_image_modes_are_documented_and_match_the_helper():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pr_body_image", ROOT / "pr_body_image.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert mod.MODES == ("first", "included", "not-required")
    for mode in mod.MODES:
        assert f"`{mode}`" in README
        assert mode in ACTION.split("\n  body-image:\n", 1)[1].split("\n  extra-args:\n", 1)[0]
    assert "first|included|not-required" in ACTION


def test_versioning_is_consistent():
    assert "@v1" not in README, "README must not point consumers at the frozen v1"
    assert "meawoppl/visual-pr@v2" in README
    assert "${ACTION_REF:-v2}" in ACTION and "${ACTION_REF:-v1}" not in ACTION
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert changelog.startswith("# Changelog") and "## v2.0.0" in changelog and "## v1" in changelog
    assert "## Unreleased" in changelog, "keep an Unreleased section for the next bundle"
    assert "[CHANGELOG.md](CHANGELOG.md)" in README


def test_repo_policy_files():
    agents = ROOT / "AGENTS.md"
    claude = ROOT / "CLAUDE.md"
    assert agents.is_file()
    assert claude.is_symlink() and claude.resolve() == agents.resolve(), "CLAUDE.md is a symlink to AGENTS.md"
    text = agents.read_text()
    for needle in ("## Release policy", "release.sh", "## Unreleased", "never move a major", "CHANGELOG.md"):
        assert needle.lower() in text.lower(), needle
    release = ROOT / "release.sh"
    assert release.is_file() and release.stat().st_mode & 0o111, "release.sh must be executable"
    for needle in ("ACTION_REF:-$major}", "visual-pr@$major", "gh release create", "git push -q -f origin \"$major\""):
        assert needle in release.read_text(), needle


def test_sweep_action_inputs_are_documented():
    sweep = (ROOT / "sweep" / "action.yml").read_text()
    block = sweep.split("\ninputs:\n", 1)[1].split("\nruns:\n", 1)[0]
    inputs = re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", block, flags=re.M)
    assert inputs, "could not parse sweep inputs"
    section = README.split("## Keeping the directory small", 1)[1].split("\n## ", 1)[0]
    for name in inputs:
        assert re.search(rf"^\| `{re.escape(name)}` \|", section, flags=re.M), f"sweep input '{name}' missing from README"
    assert "meawoppl/visual-pr/sweep@v2" in section
    assert "sweep_merged.py" in section
    assert "sweep" in (ROOT / "CHANGELOG.md").read_text().split("## v2.0.0", 1)[0], "changelog (v2.1.0) mentions the sweep"


def test_weekly_sweep_workflow_is_wired():
    wf = (ROOT / ".github" / "workflows" / "sweep.yml").read_text()
    assert "schedule:" in wf and "cron:" in wf and "workflow_dispatch:" in wf
    assert "uses: ./sweep" in wf and "tests/test_sweep.py" in wf
    assert "pull-requests: write" in wf and "contents: write" in wf
    assert "sweep.yml" in README
