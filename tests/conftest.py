import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
CHECK = ROOT / "check_svg.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_svg", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def check_svg():
    """Fresh import of check_svg.py per test so the module-level
    errors/warnings lists start empty."""
    mod = _load_module()
    yield mod
    sys.modules.pop("check_svg", None)


@pytest.fixture
def run_check(tmp_path):
    """Run check_svg.py as a subprocess, the way the action and users do.

    Hermetic by default: XDG_CONFIG_HOME points at a temp dir (so the
    Starstruck marker never lands in the developer's ~/.config) and the
    nudge is pre-satisfied unless a test opts in with snark=True."""
    import os
    import subprocess

    def _run(*args: str, snark: bool = False, env: dict | None = None):
        base = dict(os.environ if env is None else env)
        base.setdefault("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        quiet = [] if snark else ["--i-support-this-software"]
        return subprocess.run(
            [sys.executable, str(CHECK), *quiet, *map(str, args)],
            capture_output=True,
            text=True,
            env=base,
        )

    return _run
