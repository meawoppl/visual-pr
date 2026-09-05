#!/usr/bin/env bash
# Cut a release: ./release.sh vX.Y.Z
#
# From a clean, up-to-date main whose CHANGELOG.md already has a "## vX.Y.Z"
# section: tags vX.Y.Z, moves the major tag vX onto it, pushes both, verifies
# the raw URLs consumers curl at vX now serve the new files, and publishes a
# GitHub release whose notes are that changelog section. See AGENTS.md.
set -euo pipefail

die() { echo "release.sh: $*" >&2; exit 1; }

ver="${1:-}"
[[ "$ver" =~ ^v([0-9]+)\.[0-9]+\.[0-9]+$ ]] || die "usage: ./release.sh vX.Y.Z"
major="v${BASH_REMATCH[1]}"
repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"

[ "$(git branch --show-current)" = main ] || die "run from main"
[ -z "$(git status --porcelain)" ] || die "working tree is not clean"
git fetch -q origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || die "main is not in sync with origin/main"
git rev-parse -q --verify "refs/tags/$ver" >/dev/null && die "$ver already exists"

grep -q "^## $ver " CHANGELOG.md || die "CHANGELOG.md has no '## $ver — date' section"
grep -q "ACTION_REF:-$major}" action.yml || die "action.yml recipe fallback is not $major"
grep -q "visual-pr@$major" README.md || die "README usage does not say @$major"
grep -q "raw.githubusercontent.com/$repo/$major/" README.md || die "README raw URLs are not on $major"

if [ -x .venv/bin/python ]; then
  echo "running the test suite..."
  XDG_CONFIG_HOME="$(mktemp -d)" .venv/bin/python -m pytest -q || die "tests failed"
fi

notes="$(awk -v h="## $ver " 'index($0,h)==1{p=1;next} p&&/^## /{exit} p' CHANGELOG.md)"
[ -n "$notes" ] || die "empty changelog section for $ver"

git tag -a "$ver" -m "$ver" && git tag -f "$major" "$ver" >/dev/null
git push -q origin "$ver" && git push -q -f origin "$major"
echo "tagged $ver; $major -> $(git rev-parse --short "$major")"

for f in check_svg.py pr_body_image.py changed_lines.py action.yml style/default.json template.svg SPEC.md; do
  want="$(sha256sum "$f" | cut -c1-64)"
  for _ in 1 2 3 4 5 6; do
    got="$(curl -fsSL "https://raw.githubusercontent.com/$repo/$major/$f?r=$RANDOM" | sha256sum | cut -c1-64)" && [ "$got" = "$want" ] && break
    sleep 5; got=""
  done
  [ "$got" = "$want" ] || die "raw URL for $f at $major does not serve the released bytes yet"
done
echo "raw URLs at $major verified"

gh release create "$ver" --title "$ver" --notes "$notes" --verify-tag >/dev/null
echo "released: https://github.com/$repo/releases/tag/$ver"
