# Example matrix: PRs × bundled styles

Five synthetic pull requests, one per [archetype](../SPEC.md#archetypes--pick-one-per-pr),
each rendered in every bundled style. Sources are authored once in the
default palette (`src/`); `build.py` re-skins them by palette index and
validates every output with `check_svg.py --style <name>`.

**Generated — edit `src/*.svg` or `style/*.json`, then run**
`python3 examples/build.py`. CI fails if this directory is stale.

![matrix](matrix.svg)

| PR | `default` | `dracula` | `nord` | `gruvbox-dark` | `github-light` | `solarized-light` |
|---|---|---|---|---|---|---|
| **#412** `000412.svg` Retry failed webhook deliveries with exponential backoff | [![default](default/000412.svg)](default/000412.svg) | [![dracula](dracula/000412.svg)](dracula/000412.svg) | [![nord](nord/000412.svg)](nord/000412.svg) | [![gruvbox-dark](gruvbox-dark/000412.svg)](gruvbox-dark/000412.svg) | [![github-light](github-light/000412.svg)](github-light/000412.svg) | [![solarized-light](solarized-light/000412.svg)](solarized-light/000412.svg) |
| **#418** `000418.svg` Acquire the cache lock before invalidating | [![default](default/000418.svg)](default/000418.svg) | [![dracula](dracula/000418.svg)](dracula/000418.svg) | [![nord](nord/000418.svg)](nord/000418.svg) | [![gruvbox-dark](gruvbox-dark/000418.svg)](gruvbox-dark/000418.svg) | [![github-light](github-light/000418.svg)](github-light/000418.svg) | [![solarized-light](solarized-light/000418.svg)](solarized-light/000418.svg) |
| **#423** `000423.svg` Shorten session TTL to 24 h with sliding refresh | [![default](default/000423.svg)](default/000423.svg) | [![dracula](dracula/000423.svg)](dracula/000423.svg) | [![nord](nord/000423.svg)](nord/000423.svg) | [![gruvbox-dark](gruvbox-dark/000423.svg)](gruvbox-dark/000423.svg) | [![github-light](github-light/000423.svg)](github-light/000423.svg) | [![solarized-light](solarized-light/000423.svg)](solarized-light/000423.svg) |
| **#431** `000431.svg` Validate upload manifests before enqueueing | [![default](default/000431.svg)](default/000431.svg) | [![dracula](dracula/000431.svg)](dracula/000431.svg) | [![nord](nord/000431.svg)](nord/000431.svg) | [![gruvbox-dark](gruvbox-dark/000431.svg)](gruvbox-dark/000431.svg) | [![github-light](github-light/000431.svg)](github-light/000431.svg) | [![solarized-light](solarized-light/000431.svg)](solarized-light/000431.svg) |
| **#437** `000437.svg` Stream CSV exports instead of buffering them in memory | [![default](default/000437.svg)](default/000437.svg) | [![dracula](dracula/000437.svg)](dracula/000437.svg) | [![nord](nord/000437.svg)](nord/000437.svg) | [![gruvbox-dark](gruvbox-dark/000437.svg)](gruvbox-dark/000437.svg) | [![github-light](github-light/000437.svg)](github-light/000437.svg) | [![solarized-light](solarized-light/000437.svg)](solarized-light/000437.svg) |

Choose one with the action's `style` input (`style: nord`) or locally with
`python3 check_svg.py --style nord .0-pr-viz/000412.svg`. Own palette?
Point `style` at a JSON file instead — see [`../style/README.md`](../style/README.md).
