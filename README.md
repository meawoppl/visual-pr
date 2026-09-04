# visual-pr

A reusable GitHub Action that makes a **committed visual summary a checked
requirement on every pull request** — and, when the check fails, teaches the
agent preparing the PR exactly how to produce and locally verify the artifact.

Each PR commits one SVG at `000-pr-visualization/<pr-number>.svg` (the `000-`
prefix sorts it first in GitHub's "Files changed" list, so review opens on the
picture). The action requires the file, validates it against a style
definition, and on failure emits a complete recipe: the [authoring
spec](SPEC.md), the effective style JSON, your repo's custom instructions, and
the exact `check_svg.py` invocation that must pass before pushing.

## Usage

```yaml
name: Visual PR
on:
  # Runs this workflow from the BASE branch, so the check reports on every
  # open PR the moment it lands on your default branch. Safe here because the
  # PR head is checked out as data only — nothing from it is executed.
  pull_request_target:
    types: [opened, synchronize, reopened, labeled, unlabeled]

permissions:
  contents: read

jobs:
  visual-pr:
    name: Visual PR attached
    runs-on: ubuntu-latest
    steps:
      # Your style/config, from the trusted base branch.
      - uses: actions/checkout@v4
        with:
          sparse-checkout: .github/visual-pr

      # The PR's SVG, from the head — data only.
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          repository: ${{ github.event.pull_request.head.repo.full_name }}
          path: pr-head
          sparse-checkout: 000-pr-visualization

      - uses: meawoppl/visual-pr@v1
        with:
          head-path: pr-head
          style: .github/visual-pr/style.json        # optional re-skin
          instructions: |                            # optional, repo-specific
            Ground every identifier in the actual diff. Use the repo's
            domain vocabulary in box titles.
```

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `pr-number` | triggering PR | Which `<n>.svg` to require |
| `svg-dir` | `000-pr-visualization` | Directory holding the SVGs |
| `head-path` | `.` | Where the PR head was checked out |
| `style` | bundled default | Style JSON overriding canvas/palette/heuristics |
| `instructions` | — | Repo-specific authoring guidance, surfaced on failure |
| `skip-label` | `no-visual` | Label that opts a PR out (the step passes) |

## Style JSON

Any subset of [`style/default.json`](style/default.json)'s keys; omitted keys
keep the bundled Tokyo-Night defaults:

```json
{
  "canvas": [2000, 1200],
  "margin": 40,
  "char_factor": 0.5,
  "divider_x": 1000,
  "divider_band": [190, 1140],
  "palette": ["#16161e", "..."]
}
```

## Local verification (what the failure output tells agents)

```bash
curl -fsSLO https://raw.githubusercontent.com/meawoppl/visual-pr/v1/check_svg.py
mkdir -p style && curl -fsSL -o style/default.json \
  https://raw.githubusercontent.com/meawoppl/visual-pr/v1/style/default.json
python3 check_svg.py [--style your-style.json] 000-pr-visualization/<n>.svg
```

`check_svg.py` is dependency-free (Python 3 stdlib). Hard failures: bad XML,
wrong canvas, off-palette colors. Warnings (non-fatal): estimated text
overflow, divider crossings, missing font sizes.
