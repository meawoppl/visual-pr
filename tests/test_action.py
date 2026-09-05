"""Drive the composite action's shell script the way the runner does, with a
fake `gh` on PATH and a temp git repo as $GITHUB_WORKSPACE. This is the
contract CI's action-self-test job exercises for real; here it runs on every
pytest invocation, offline."""

import json
import os
import pathlib
import stat
import subprocess
import sys

import pytest

from conftest import ROOT

SUPPORT_FLAG = "--i-support-this-software"


def action_script() -> str:
    text = (ROOT / "action.yml").read_text()
    body = text.split("      run: |\n", 1)[1]
    return "\n".join(l[8:] if l.startswith("        ") else l for l in body.splitlines())


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    (ws / ".gitattributes").write_text("gen/** linguist-generated=true\n")
    return ws


@pytest.fixture
def fake_gh(tmp_path):
    """A `gh` that answers `gh api ... pulls/N/files --jq .[]` from a JSON file
    we control, and fails for any PR number it has no answer for."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    answers = tmp_path / "gh-answers"
    answers.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f'ANS="{answers}"\n'
        'for a in "$@"; do case "$a" in repos/*/pulls/*/files) n="${a#*/pulls/}"; n="${n%/files}";; esac; done\n'
        'echo "$*" >> "$ANS/calls.log"\n'
        '[ -n "${n:-}" ] && [ -f "$ANS/$n.ndjson" ] && { cat "$ANS/$n.ndjson"; exit 0; }\n'
        'echo "gh: HTTP 404" >&2; exit 1\n'
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)

    def set_files(pr: int, files: list[dict]):
        (answers / f"{pr}.ndjson").write_text("".join(json.dumps(f) + "\n" for f in files))

    return {"bin": bin_dir, "set_files": set_files, "log": answers / "calls.log"}


@pytest.fixture
def run_action(tmp_path, workspace, fake_gh):
    script = action_script()

    def _run(**over):
        n = len(os.listdir(tmp_path))
        summary = tmp_path / f"summary-{n}.md"
        summary.touch()
        output = tmp_path / f"output-{n}.txt"
        output.touch()
        _run.last_output = output
        env = dict(
            os.environ,
            GITHUB_OUTPUT=str(output),
            PATH=f"{fake_gh['bin']}:{os.environ['PATH']}",
            ACTION_PATH=str(ROOT),
            ACTION_REPO="",
            ACTION_REF="",
            GITHUB_WORKSPACE=str(workspace),
            GITHUB_REPOSITORY="acme/widgets",
            GITHUB_STEP_SUMMARY=str(summary),
            XDG_CONFIG_HOME=str(tmp_path / "xdg"),
            VISUAL_PR_SNARK_TIMEOUT="0.2",
            HEAD_PATH=str(ROOT),
            SVG_DIR="tests/fixtures",
            PR_NUMBER="valid",
            STYLE="",
            INSTRUCTIONS="",
            SKIP_LABEL="no-visual",
            LABELS_JSON="[]",
            EXTRA_ARGS=SUPPORT_FLAG,
            MIN_CHANGED_LINES="0",
            RESPECT_LINGUIST="true",
            BODY_IMAGE="not-required",
            PR_BODY="",
            HEAD_REPO="acme/widgets",
            HEAD_SHA="0123abcd0123abcd0123abcd0123abcd0123abcd",
        )
        env.update({k: str(v) for k, v in over.items()})
        r = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, cwd=workspace)
        return r.returncode, r.stdout + r.stderr, summary.read_text()

    return _run


def outcome(run_action) -> str:
    text = run_action.last_output.read_text()
    return dict(l.split("=", 1) for l in text.splitlines() if "=" in l).get("outcome", "")


# ---- the basics -----------------------------------------------------------


def test_valid_svg_passes(run_action):
    rc, out, summary = run_action(PR_NUMBER="valid")
    assert rc == 0 and "Visual summary present and valid" in out and summary == ""
    assert outcome(run_action) == "passed"
    assert "svg=tests/fixtures/valid.svg" in run_action.last_output.read_text()


def test_missing_svg_fails_with_the_full_recipe(run_action):
    rc, out, summary = run_action(PR_NUMBER="999999", INSTRUCTIONS="Name the migration file.")
    assert rc == 1
    assert "::error::Missing tests/fixtures/999999.svg" in out
    for needle in (
        "VISUAL PR CHECK FAILED: missing tests/fixtures/999999.svg",
        "gh pr view 999999 && gh pr diff 999999",
        "curl -fsSLO https://raw.githubusercontent.com/meawoppl/visual-pr/v2/check_svg.py",
        "python3 check_svg.py tests/fixtures/999999.svg",
        "REPO-SPECIFIC INSTRUCTIONS:\nName the migration file.",
        "AUTHORING SPEC:",
    ):
        assert needle in summary, needle
    assert SUPPORT_FLAG not in summary, "the opt-out never appears in the recipe"
    assert outcome(run_action) == "missing"


def test_invalid_svg_fails(run_action):
    rc, out, summary = run_action(PR_NUMBER="off-palette")
    assert rc == 1 and "failed validation" in summary and "off-palette" in out
    assert outcome(run_action) == "invalid"


def test_six_digit_padding(run_action):
    rc, out, summary = run_action(PR_NUMBER="412", SVG_DIR="examples/nord", STYLE="nord")
    assert rc == 0 and "examples/nord/000412.svg" in out
    rc, out, summary = run_action(PR_NUMBER="7", SVG_DIR="examples/nord")
    assert rc == 1 and "missing examples/nord/000007.svg" in summary


def test_styles_by_file_and_by_name_and_unknown(run_action):
    # `style` paths resolve against the workspace (the cwd), so pass it absolute here.
    rc, out, _ = run_action(PR_NUMBER="red-100", STYLE=str(ROOT / "tests/fixtures/style-red.json"))
    assert rc == 0, out
    rc, _, summary = run_action(PR_NUMBER="412", SVG_DIR="examples/nord", STYLE="dracula", EXTRA_ARGS=f"{SUPPORT_FLAG} --style-x")
    assert rc == 1
    assert "curl -fsSL -o style/dracula.json" in summary
    assert "python3 check_svg.py --style dracula --style-x examples/nord/000412.svg" in summary
    rc, out, _ = run_action(STYLE="not-a-style")
    assert rc == 1 and "neither a file nor a bundled style" in out
    assert outcome(run_action) == "bad-style"


def test_skip_label(run_action):
    rc, out, _ = run_action(PR_NUMBER="999999", LABELS_JSON='["bug","no-visual"]')
    assert rc == 0 and "not required" in out
    assert outcome(run_action) == "skipped-label"


# ---- the small-change escape ---------------------------------------------


def files(*specs):
    return [{"filename": n, "additions": a, "deletions": d, "changes": a + d} for n, a, d in specs]


def test_small_pr_without_svg_passes(run_action, fake_gh):
    fake_gh["set_files"](55, files(("src/a.py", 10, 5), ("README.md", 3, 0)))
    rc, out, summary = run_action(PR_NUMBER="55", MIN_CHANGED_LINES="40")
    assert rc == 0, out
    assert "PR changes 18 counted line(s), under min-changed-lines=40" in out
    assert summary == ""
    assert outcome(run_action) == "skipped-small-change"
    assert "repos/acme/widgets/pulls/55/files" in fake_gh["log"].read_text()


def test_large_pr_without_svg_still_fails(run_action, fake_gh):
    fake_gh["set_files"](56, files(("src/a.py", 30, 20)))
    rc, out, summary = run_action(PR_NUMBER="56", MIN_CHANGED_LINES="40")
    assert rc == 1
    assert "PR changes 50 counted line(s) (min-changed-lines=40); visual summary required." in out
    assert "VISUAL PR CHECK FAILED: missing tests/fixtures/000056.svg" in summary


def test_linguist_and_lockfiles_are_left_out_of_the_count(run_action, fake_gh):
    fake_gh["set_files"](57, files(("package-lock.json", 3000, 2000), ("gen/api.ts", 900, 0),
                                   ("tests/fixtures/000057.svg", 200, 0), ("src/a.py", 12, 0)))
    rc, out, _ = run_action(PR_NUMBER="57", MIN_CHANGED_LINES="40")
    assert rc == 0, out
    assert "PR changes 12 counted line(s)" in out
    # ...unless the repo turns that off.
    rc, out, _ = run_action(PR_NUMBER="57", MIN_CHANGED_LINES="40", RESPECT_LINGUIST="false")
    assert rc == 1
    assert "PR changes 5912 counted line(s)" in out


def test_api_failure_requires_the_visual(run_action, fake_gh):
    rc, out, summary = run_action(PR_NUMBER="58", MIN_CHANGED_LINES="40")
    assert rc == 1
    assert "::warning::Could not count changed lines for PR 58; requiring the visual summary." in out
    assert "VISUAL PR CHECK FAILED" in summary


def test_escape_is_off_by_default_and_never_skips_validation(run_action, fake_gh):
    fake_gh["set_files"](59, files(("src/a.py", 1, 0)))
    rc, _, _ = run_action(PR_NUMBER="59")  # MIN_CHANGED_LINES=0
    assert rc == 1
    assert not fake_gh["log"].exists(), "no API call when the escape is off"
    # A present-but-broken SVG is validated regardless of PR size.
    rc, out, _ = run_action(PR_NUMBER="off-palette", MIN_CHANGED_LINES="9999")
    assert rc == 1 and "failed validation" in out


# ---- the picture in the description ---------------------------------------

RAW_VALID = "https://raw.githubusercontent.com/acme/widgets/0123abcd0123abcd0123abcd0123abcd0123abcd/tests/fixtures/valid.svg"


def test_body_image_first_passes_when_description_opens_with_it(run_action):
    rc, out, _ = run_action(BODY_IMAGE="first", PR_BODY=f"![Visual summary]({RAW_VALID})\n\n## Summary\n...")
    assert rc == 0, out
    assert "opens with an image of tests/fixtures/valid.svg" in out
    assert outcome(run_action) == "passed"


def test_body_image_first_fails_when_image_is_not_first(run_action):
    rc, out, summary = run_action(BODY_IMAGE="first", PR_BODY=f"## Summary\n\n![s]({RAW_VALID})")
    assert rc == 1
    assert outcome(run_action) == "body-image-missing"
    assert "does not open with it" in out
    assert "The SVG itself is present and valid" in summary
    assert f"![Visual summary]({RAW_VALID})" in summary, "recipe prints the exact SHA-pinned line"
    assert "gh pr edit valid --body-file" in summary
    assert "python3 pr_body_image.py --mode first --svg-path tests/fixtures/valid.svg" in summary
    assert "curl -fsSLO https://raw.githubusercontent.com/meawoppl/visual-pr/v2/pr_body_image.py" in summary


def test_body_image_included_accepts_anywhere(run_action):
    rc, out, _ = run_action(BODY_IMAGE="included", PR_BODY=f"## Summary\n\n![s]({RAW_VALID})")
    assert rc == 0, out
    rc, out, summary = run_action(BODY_IMAGE="included", PR_BODY="## Summary\n\nno picture")
    assert rc == 1 and "has no image of tests/fixtures/valid.svg" in out
    assert "anywhere in it:" in summary


def test_body_image_not_required_skips_and_missing_svg_recipe_gets_step_5(run_action):
    rc, out, _ = run_action(BODY_IMAGE="not-required", PR_BODY="")
    assert rc == 0 and "PR description" not in out
    rc, _, summary = run_action(PR_NUMBER="999999", BODY_IMAGE="first")
    assert rc == 1
    assert "5. Put the picture in the PR description — the very first line of it:" in summary
    assert "0123abcd0123abcd0123abcd0123abcd0123abcd/tests/fixtures/999999.svg" in summary
    rc, _, summary = run_action(PR_NUMBER="999999", BODY_IMAGE="not-required")
    assert rc == 1 and "5. Put the picture" not in summary


def test_body_image_bad_value_is_bad_input(run_action):
    rc, out, _ = run_action(BODY_IMAGE="sometimes")
    assert rc == 1 and "body-image must be first, included or not-required" in out
    assert outcome(run_action) == "bad-input"
