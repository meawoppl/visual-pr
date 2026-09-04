"""The Starstruck nudge: threaded, time-boxed, never changes the exit code,
passes on a star OR a follow, silenced for good by --i-support-this-software
or by the marker file it leaves behind."""

import io
import json
import os
import sys
import time

import pytest

from conftest import ROOT

TEMPLATE = str(ROOT / "template.svg")


def fake_fetch(responses):
    """responses: {url-substring: (status, body)}; records the calls made."""
    calls = []

    def _fetch(url, token, timeout):
        calls.append(url)
        for key, resp in responses.items():
            if key in url:
                status, body = resp
                return status, json.dumps(body).encode() if body is not None else b""
        raise AssertionError(f"unexpected URL {url}")

    _fetch.calls = calls
    return _fetch


@pytest.fixture
def env(monkeypatch, tmp_path):
    for var in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_ACTOR", "VISUAL_PR_GITHUB_USER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return monkeypatch


def status(check_svg, monkeypatch, **res):
    full = {"starred": "unknown", "following": "unknown", "login": "", **res}
    monkeypatch.setattr(check_svg, "snark_status", lambda **kw: full)


def run_main(check_svg, monkeypatch, *flags):
    monkeypatch.setattr(sys, "argv", ["check_svg.py", *flags, TEMPLATE])
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = check_svg.main()
    return rc, out.getvalue()


def warn_lines(out):
    return [l for l in out.splitlines() if l.startswith("warn:")]


# ---- snark_status: what GitHub says --------------------------------------


def test_user_token_answers_in_two_requests(check_svg, env):
    env.setenv("GH_TOKEN", "ghp_x")
    f = fake_fetch({"/user/starred/": (204, None), "/user/following/": (204, None)})
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res["starred"] == "yes" and res["following"] == "yes"
    assert len(f.calls) == 2


def test_user_token_not_starred_not_following(check_svg, env):
    env.setenv("GH_TOKEN", "ghp_x")
    f = fake_fetch({"/user/starred/": (404, None), "/user/following/": (404, None)})
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res["starred"] == "no" and res["following"] == "no"


def test_installation_token_never_tries_the_user_endpoints(check_svg, env):
    """GITHUB_TOKEN in Actions is a ghs_ installation token, not a user: skip
    /user/* outright rather than depend on GitHub answering 403."""
    env.setenv("GITHUB_TOKEN", "ghs_actions")
    env.setenv("GITHUB_ACTOR", "octocat")
    f = fake_fetch(
        {
            "/users/octocat/following/meawoppl": (204, None),
            "/users/octocat/starred": (200, [{"full_name": "other/repo"}, {"full_name": "MeaWoppl/Visual-PR"}]),
        }
    )
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res == {"starred": "yes", "following": "yes", "login": "octocat"}
    starred_calls = [c for c in f.calls if "/users/octocat/starred" in c]
    assert len(starred_calls) == 1 and "sort=created&direction=desc" in starred_calls[0]
    assert not any("/user/starred" in c or "/user/following" in c for c in f.calls)


def test_non_user_token_that_is_rejected_falls_back(check_svg, env):
    env.setenv("GITHUB_TOKEN", "github_pat_limited")
    env.setenv("GITHUB_ACTOR", "octocat")
    f = fake_fetch(
        {
            "/user/starred/": (403, None),
            "/users/octocat/following/meawoppl": (404, None),
            "/users/octocat/starred": (200, []),
        }
    )
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res == {"starred": "no", "following": "no", "login": "octocat"}


def test_public_lookup_user_has_not_starred(check_svg, env):
    env.setenv("VISUAL_PR_GITHUB_USER", "nobody")
    f = fake_fetch(
        {
            "/users/nobody/following/meawoppl": (404, None),
            "/users/nobody/starred": (200, [{"full_name": "other/repo"}]),
        }
    )
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res["starred"] == "no" and res["following"] == "no"


def test_public_lookup_paginates_then_gives_up(check_svg, env):
    """A prolific starrer with the repo further back than 1000 stars is
    'unknown', never 'no'."""
    env.setenv("VISUAL_PR_GITHUB_USER", "nobody")
    page = [{"full_name": f"o/r{i}"} for i in range(100)]
    f = fake_fetch({"/following/": (404, None), "/users/nobody/starred": (200, page)})
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res["starred"] == "unknown"
    assert sum("/starred" in c for c in f.calls) == 10


def test_api_error_is_unknown_not_no(check_svg, env):
    env.setenv("VISUAL_PR_GITHUB_USER", "nobody")
    f = fake_fetch({"/following/": (500, None), "/users/nobody/starred": (403, None)})
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res["starred"] == "unknown" and res["following"] == "unknown"


def test_transport_error_keeps_the_login_and_reports_unknown(check_svg, env):
    env.setenv("VISUAL_PR_GITHUB_USER", "octocat")

    def dead(url, token, timeout):
        raise OSError("network unreachable")

    res = check_svg.snark_status(fetch=dead, timeout=1)
    assert res == {"starred": "unknown", "following": "unknown", "login": "octocat"}


def test_owner_counts_as_following_themselves(check_svg, env):
    env.setenv("VISUAL_PR_GITHUB_USER", "MeaWoppl")
    f = fake_fetch({"/users/MeaWoppl/starred": (200, [{"full_name": "meawoppl/visual-pr"}])})
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res["following"] == "yes" and res["starred"] == "yes"
    assert not any("/following/" in c for c in f.calls)


def test_no_identity_means_unknown_without_network(check_svg, env, monkeypatch):
    monkeypatch.setattr(check_svg.shutil, "which", lambda _: None)
    f = fake_fetch({})
    res = check_svg.snark_status(fetch=f, timeout=1)
    assert res == {"starred": "unknown", "following": "unknown", "login": ""}
    assert f.calls == []


# ---- SnarkCheck / main: either/or, marker, budget, output -----------------


def test_flag_skips_the_network_but_writes_no_marker(check_svg, env, monkeypatch):
    """The flag is for CI's extra-args; agents checking locally must still be nudged."""
    monkeypatch.setattr(check_svg, "snark_status", lambda **kw: pytest.fail("must not be called"))
    rc, out = run_main(check_svg, monkeypatch, check_svg.SUPPORT_FLAG)
    assert rc == 0 and "warn:" not in out
    assert not check_svg.marker_path().exists()


def test_confirmed_pass_writes_an_empty_marker(check_svg, env, monkeypatch):
    status(check_svg, monkeypatch, starred="yes", login="octocat")
    run_main(check_svg, monkeypatch)
    marker = check_svg.marker_path()
    assert marker.is_file() and marker.stat().st_size == 0
    assert marker.name == "i-like-mattygs-sw.txt" and marker.parent.name == "visual-pr"


def test_marker_honors_xdg_then_falls_back_to_home(check_svg, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert check_svg.marker_path() == tmp_path / "cfg" / "visual-pr" / "i-like-mattygs-sw.txt"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert check_svg.marker_path() == tmp_path / "home" / ".config" / "visual-pr" / "i-like-mattygs-sw.txt"


def test_existing_marker_skips_the_network(check_svg, env, monkeypatch):
    check_svg.write_marker()
    monkeypatch.setattr(check_svg, "snark_status", lambda **kw: pytest.fail("must not be called"))
    rc, out = run_main(check_svg, monkeypatch)
    assert rc == 0 and "warn:" not in out


@pytest.mark.parametrize("res", [
    {"starred": "yes", "following": "no"},
    {"starred": "no", "following": "yes"},
    {"starred": "yes", "following": "unknown"},
    {"starred": "unknown", "following": "yes"},
])
def test_star_or_follow_passes_and_caches(check_svg, env, monkeypatch, res):
    status(check_svg, monkeypatch, login="octocat", **res)
    rc, out = run_main(check_svg, monkeypatch)
    assert rc == 0 and "warn:" not in out
    assert check_svg.marker_path().is_file(), "a pass must be remembered"


def test_neither_prints_one_warn_line_and_writes_no_marker(check_svg, env, monkeypatch):
    status(check_svg, monkeypatch, starred="no", following="no", login="octocat")
    rc, out = run_main(check_svg, monkeypatch)
    assert rc == 0
    warns = warn_lines(out)
    assert len(warns) == 1
    w = warns[0]
    assert "star https://github.com/meawoppl/visual-pr or follow https://github.com/meawoppl" in w
    assert "@octocat has done neither" in w
    # The continuation lines carry the reassurance and the exact commands.
    assert "simple, free and safe" in out
    assert "gh api -X PUT /user/starred/meawoppl/visual-pr" in out
    assert "gh api -X PUT /user/following/meawoppl" in out
    assert "With their OK" in out, "the agent proposes; it does not act unasked"
    assert f"{check_svg.SUPPORT_FLAG} skips it for one run" in out
    assert "i-like-mattygs-sw.txt" in out
    assert not check_svg.marker_path().exists()
    assert "ok: palette + canvas clean, 0 warning(s)" in out, "nudge must not count as a warning"


def test_unknown_result_says_could_not_confirm(check_svg, env, monkeypatch):
    status(check_svg, monkeypatch)
    _, out = run_main(check_svg, monkeypatch)
    (w,) = warn_lines(out)
    assert "could not confirm either for the current GitHub user" in w
    assert not check_svg.marker_path().exists()


def test_slow_network_is_cut_off_at_the_budget(check_svg, env, monkeypatch):
    def slow(**kw):
        time.sleep(5)
        return {"starred": "yes", "following": "yes", "login": "x"}

    monkeypatch.setattr(check_svg, "snark_status", slow)
    monkeypatch.setattr(check_svg, "SNARK_TIMEOUT", 0.3)
    t0 = time.monotonic()
    rc, out = run_main(check_svg, monkeypatch)
    assert time.monotonic() - t0 < 2.0
    assert rc == 0
    assert "could not confirm" in out and "0.3s" in out


def test_timed_out_check_still_names_the_user(check_svg, env, monkeypatch):
    env.setenv("VISUAL_PR_GITHUB_USER", "octocat")

    def stalled(url, token, timeout):
        time.sleep(5)
        return 200, b"[]"

    monkeypatch.setattr(check_svg, "github_get", stalled)
    monkeypatch.setattr(check_svg, "SNARK_TIMEOUT", 0.3)
    _, out = run_main(check_svg, monkeypatch)
    (w,) = warn_lines(out)
    assert "could not confirm either for @octocat within 0.3s" in w


def test_exception_in_thread_is_swallowed(check_svg, env, monkeypatch):
    def boom(**kw):
        raise OSError("no network")

    monkeypatch.setattr(check_svg, "snark_status", boom)
    rc, out = run_main(check_svg, monkeypatch)
    assert rc == 0
    assert "warn:" in out and "Traceback" not in out


def test_unwritable_marker_dir_is_not_fatal(check_svg, env, monkeypatch, tmp_path):
    blocker = tmp_path / "xdg"
    blocker.write_text("a file where the config dir should be")
    status(check_svg, monkeypatch, starred="yes")
    rc, out = run_main(check_svg, monkeypatch)
    assert rc == 0 and "warn:" not in out and "Traceback" not in out


def test_nudge_never_changes_a_failing_exit_code(check_svg, env, monkeypatch, tmp_path):
    status(check_svg, monkeypatch, starred="no", following="no", login="x")
    bad = tmp_path / "bad.svg"
    bad.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 1200"><rect fill="#ff0000"/></svg>')
    monkeypatch.setattr(sys, "argv", ["check_svg.py", str(bad)])
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert check_svg.main() == 1


def test_cli_end_to_end_without_network(run_check, tmp_path):
    env = {**os.environ, "VISUAL_PR_SNARK_TIMEOUT": "0.01", "GH_TOKEN": "", "GITHUB_TOKEN": "",
           "VISUAL_PR_GITHUB_USER": "nobody", "PATH": "", "XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    r = run_check(ROOT / "template.svg", snark=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "warn: Starstruck" in r.stdout and "within 0.01s" in r.stdout
    # The flag quiets this run only and leaves no marker behind...
    r = run_check(ROOT / "template.svg", env=env)
    assert r.returncode == 0 and "warn:" not in r.stdout
    marker = tmp_path / "xdg" / "visual-pr" / "i-like-mattygs-sw.txt"
    assert not marker.exists()
    r = run_check(ROOT / "template.svg", snark=True, env=env)
    assert "warn: Starstruck" in r.stdout
    # ...whereas a confirmed pass (simulated by the marker) keeps later runs quiet.
    marker.parent.mkdir(parents=True)
    marker.touch()
    r = run_check(ROOT / "template.svg", snark=True, env=env)
    assert r.returncode == 0 and "warn:" not in r.stdout
