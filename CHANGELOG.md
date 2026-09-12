# Changelog

Major tags (`v1`, `v2`) move with fixes; point tags (`v2.0.0`) are exact.
A new major is cut whenever a passing PR would look different. Releases are
cut with `./release.sh vX.Y.Z` — see AGENTS.md for the policy.

## Unreleased

**Contract change — cut this as v4.** The PR description's image of the summary
must now be a GitHub *permalink*: a full 40-character commit SHA, naming the
PR's head or base repository, on `raw.githubusercontent.com/OWNER/REPO/<sha>/...`
or `github.com/OWNER/REPO/{blob,raw}/<sha>/...`. A branch ref is a hard failure.
It used to pass, and the resulting link 404s the moment the branch is deleted at
merge — the moment the description becomes the PR's only record of the picture,
because the sweep has taken the file out of the working tree. A
`blob/<branch>/...` URL whose branch name contains a slash never resolved at
all: GitHub cannot tell where the ref ends and the path begins. Both hosts are
accepted because on a private repository only a `github.com` URL carries the
reader's session. Only PRs opened after the tag moves feel this; merged
descriptions are never re-checked.

- The failure now names what is wrong with the URL you wrote — the branch it is
  pinned to, the repository it points at, or that it is not a GitHub URL — and
  says whether the link is already broken or merely about to be.
- `pr_body_image.py` takes a repeatable `--repo OWNER/REPO`; the action passes
  the PR's head and base, so a fork's permalink is accepted before the merge and
  the base's after it. Omit it and any repository passes.
- The sweep is unchanged: it still recognises branch-pinned images in merged
  descriptions, which is how it repairs them.
- Tests: `tests/test_sweep.py` anchored "now" to a date literal while the code
  under test reads the real clock, so the suite turned red on an untouched
  `main` once enough days had passed. The anchor is relative now.

## v3.0.0 — 2026-09-09

**Contract change:** the default glyph allowlist is now ASCII + Latin-1 only
(`0020-007E`, `00A0-00FF`). Arrows (`→`), math operators (`− ≤ ≥ ≠ ≈`),
en/em dashes, ellipses, bullets, curly quotes, check marks and shapes are hard
errors; the validator names the ASCII replacement (`->`, `<=`, `~`, `-`,
`...`, `+`, `x`). They were admitted by v2 and rendered as missing-glyph boxes
on a real reviewer's viewer even though the declared font stack nominally
carries them ([#10](https://github.com/meawoppl/visual-pr/issues/10)). A
repo whose viewers are verified can widen `glyphs` in its own style JSON.
Template, examples and SPEC are rewritten to the new set. Merged visuals are
never re-checked; only new PRs feel this. Everything else is v2.1.0 plus the
items below.

- Docs: the quick start grants `pull-requests: read`, which `min-changed-lines`
  needs to read the PR's file list once a `permissions:` block is present.
- Sweep: before deleting, fetch the permalink (200 + SVG bytes) and re-read
  the PR description from the API to confirm it carries the permalink; keep
  the file otherwise. `--no-verify-urls` skips the fetch for offline tests.
  This repo now runs the sweep on itself weekly (`.github/workflows/sweep.yml`).
- Sweep: when GitHub refuses to let Actions open the PR, say which setting
  to flip (or to pass a PAT / use `mode: push`) instead of a bare GraphQL error.

## v2.1.0 — 2026-09-07

- `meawoppl/visual-pr/sweep@v2` (and `sweep_merged.py`): a weekly janitor
  that rewrites each merged PR's description to the permalink of its SVG at
  the merge commit, indexes it in `<svg-dir>/ARCHIVE.md`, and deletes the file
  from the working tree so shallow checkouts stay small. Additive; no change
  to what a passing PR looks like.

## v2.0.0 — 2026-09-04

The contract:

- SVG lives at `.0-pr-viz/<pr-number zero-padded to six digits>.svg`
  (`000412.svg`). `.0` sorts ahead of `.github/` and every letter in
  "Files changed"; six digits keep the files in PR order.
- The PR description opens with an image of that SVG (`body-image: first`;
  `included` and `not-required` available). Listen for the `edited` pull
  request event so fixing the description re-runs the check.
- `style` accepts a bundled name (`default`, `dracula`, `nord`,
  `gruvbox-dark`, `github-light`, `solarized-light`) or a path. All six share
  one 14-slot palette order; `examples/` renders five PRs in every style.
- Validator hard errors: malformed XML, wrong canvas, off-palette color, and
  characters outside the style's `glyphs` allowlist (what fonts would draw as
  missing-glyph boxes). Warnings: canvas overflow, divider crossing, text
  overrunning its box, missing font size, numeric file name not six digits.
- Escapes: the `skip-label` (default `no-visual`) and `min-changed-lines`
  with `respect-linguist` (files marked linguist-generated/-vendored in the
  base branch's `.gitattributes`, and common lockfiles, do not count).
- Outputs `outcome` and `svg`.
- On failure the recipe walks the agent through reading the diff, fetching
  the validator and style, the exact local command, and the exact
  description line to add.
- License: Apache-2.0 plus the Starstruck addendum. `check_svg.py` runs a
  time-boxed star/follow lookup and prints one `warn:` with the `gh` commands
  if neither is confirmed; a confirmed pass is cached under the config dir;
  `--i-support-this-software` skips it for one run.

## v1 — 2026-09-04

Original release: a single validator and composite action requiring
`000-pr-visualization/<n>.svg` (unpadded), Tokyo Night only, no description
check. Frozen; `v1` stays on this commit.
