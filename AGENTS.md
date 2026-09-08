# Working in visual-pr

This repo *is* the product: a composite GitHub Action (`action.yml`), a
dependency-free validator (`check_svg.py`), two helpers the action calls
(`changed_lines.py`, `pr_body_image.py`), a second action for the weekly
sweep (`sweep/action.yml` around `sweep_merged.py`), bundled styles, an
example matrix,
and the docs that agents read when a check fails. Consumers pin a moving major
tag (`meawoppl/visual-pr@v2`) and curl files from
`raw.githubusercontent.com/meawoppl/visual-pr/v2/...`. Every change here lands
in other repos' CI the moment a tag moves — behave accordingly.

## Everyday

```bash
python3 -m venv .venv && .venv/bin/pip install pytest shellcheck-py
.venv/bin/python -m pytest -q          # ~200 tests; hermetic (no network, no ~/.config writes)
python3 examples/build.py              # regenerate examples/ after touching src/ or style/
```

- Tests are the documentation's guard rails: `tests/test_docs.py` binds
  README, `action.yml`, `SPEC.md`, `style/`, `LICENSE` and `CHANGELOG.md`
  together. If a doc claim changes, a test tells you where else it is made.
- `tests/test_action.py` drives the composite action's shell offline with a
  fake `gh`. Change `action.yml` there first; CI's end-to-end job is the
  confirmation, not the discovery.
- Shell in `action.yml` and `release.sh` is shellchecked in CI; workflows are
  actionlinted. Run both locally before pushing (`PATH=.venv/bin:$PATH`).
- `.github/workflows/sweep.yml` runs the sweep action on this repo every
  Monday and opens a `no-visual` PR with the removals. Merge those; they are
  the weekly proof that the tool works against real GitHub. If one fails, the
  tool is broken for consumers too — fix before the next release.
- Never write the Starstruck marker from tests or tooling. `tests/conftest.py`
  points `XDG_CONFIG_HOME` at a temp dir; `examples/build.py` stubs the check.

## Pull requests here

Same rules as everyone else, because this repo runs its own action:

- Branch from `main`. Every PR ships `.0-pr-viz/<pr-number zero-padded to six
  digits>.svg`, grounded in its own diff, validated with
  `python3 check_svg.py .0-pr-viz/00000N.svg` (zero warnings is the bar we hold
  ourselves to). Show it in your portal session with `agent-portal show`.
- The PR description opens with the SHA-pinned image of that SVG. Re-pin the
  SHA when you push a new version of the SVG.
- PR titles describe the change. Commit trailers as the harness dictates.
- Merging a PR does **not** move any tag. See below.

## Release policy: bundle, then cut

`main` is always releasable and is never itself a release. Changes accumulate
on `main` and are **bundled** into a deliberate release when there is a
coherent set worth announcing, or a fix a consumer needs. Nothing reaches a
consumer until a tag moves, and tags move only through `release.sh`.

Versioning follows what a **passing PR looks like**, not the size of the diff:

| change | version | examples |
|---|---|---|
| bug fix, docs, tests, new warning, new *optional* input, new bundled style | patch / minor — moves the major tag | `v2.0.0 → v2.1.0`, `v2` follows |
| anything that turns a passing PR into a failing one | new major | directory or file-name scheme, default of `body-image`, a new hard error in the validator, a removed input |

The lesson behind the rule: `v1` was moved across three contract changes in
one day and every `@v1` consumer broke three times. A frozen major is a promise.

**Cutting a release** (from a clean, up-to-date `main`):

1. Write the section in `CHANGELOG.md`: rename `## Unreleased` to
   `## vX.Y.Z — YYYY-MM-DD`, start a fresh empty `## Unreleased` above it.
   Say what a consumer will notice, not what files changed.
2. For a new major, also bump the contract references in the same PR:
   `${ACTION_REF:-vN}` in `action.yml`, `meawoppl/visual-pr@vN` and the raw
   URLs in `README.md`, and the tests that assert them (`test_versioning_is_consistent`
   will refuse anything half-done).
3. Merge that PR, then run `./release.sh vX.Y.Z`. It checks the tree, the
   changelog section and the contract references, tags `vX.Y.Z`, moves `vN`,
   pushes both, verifies the raw URLs at `vN` serve the new files, and publishes
   a GitHub release with the changelog section as its notes.
4. Update consumers you control (agent-portal's `.github/workflows/visual-pr.yml`
   and its `AGENTS.md` conventions) in their own PR. A new major is not done
   until at least one real consumer is on it and green.

Never `git tag -f` a major by hand. Never move a major across a contract
change. If you must un-break a consumer quickly, move the major *back* to the
last commit of its contract (that is what `v1 → 77dd60e` was) and cut the new
contract as the next major.
