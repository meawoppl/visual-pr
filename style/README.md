# Bundled styles

Six palettes, one contract. Pick a bundled style by **name** (`style: nord` in
the workflow, `--style nord` locally) or point `style` at your own JSON with
any subset of these keys. Every palette lists its 14 colors in the same
semantic order, so a diagram authored against one style re-skins to any other
by index — which is exactly how [`../examples/build.py`](../examples/build.py)
produces the [example matrix](../examples/README.md).

The semantics matter more than the hues: **green only for what the PR makes
right, red only for what was wrong**, blue for names of things, orange for
gates and caveats, neutrals for everything that didn't change.

## Keys

| key | default | meaning |
|---|---|---|
| `canvas` | `[2000, 1200]` | viewBox the SVG must declare |
| `margin` | `40` | text estimated to end closer than this to the right edge is flagged |
| `char_factor` | `0.5` | estimated glyph width as a fraction of font-size |
| `divider_x` | `1000` | x of the BEFORE/AFTER divider; small text must not straddle it |
| `divider_band` | `[190, 1140]` | y range in which the divider rule applies |
| `glyphs` | see below | allowed Unicode ranges (`"0020-007E"`) or points (`"2044"`); anything else is a hard error |
| `palette` | 14 colors | every `fill`/`stroke` must be one of these |

### Glyph allowlist

Fonts draw characters they lack as little boxes, and a validator cannot know
which fonts a reviewer's viewer will fall back to. So the style declares what
is safe, and the default is deliberately small: **ASCII plus Latin-1**
(`0020-007E`, `00A0-00FF`) - accented letters and the Latin-1 symbols
`± µ · × ÷ ° § ¶ « »`. Arrows, math operators, en/em dashes, ellipses,
bullets, curly quotes, check marks and shapes are *not* on the list: they were
admitted once and rendered as boxes on a real viewer even though the declared
font stack nominally carries them (issue #10). The validator names the ASCII
replacement when it rejects one (`->`, `<=`, `~`, `-`, `...`, `+`, `x`).
Override `glyphs` in your style JSON to widen it for viewers you have verified
(the key replaces the default list, so copy it and add). For orientation: on a
DejaVu-based stack the en/em dash, ellipsis, bullet and curly quotes
(`2010-2027`), Greek (`0370-03FF`), Cyrillic (`0400-04FF`) and Latin
Extended-A (`0100-017F`) drew correctly while arrows, math operators, check
marks and shapes did not. Treat that as a floor: put the probe SVGs in
`tests/fixtures/glyph-probe-*.svg` in front of your actual viewer before
re-adding anything.

## Palette slots

| index | role | default (Tokyo Night) |
|---|---|---|
| 0 | canvas background | `#16161e` |
| 1 | box fill | `#1e202e` |
| 2 | neutral border / hairline | `#3d4666` |
| 3 | muted text (header, footer, provenance) | `#565f89` |
| 4 | body text | `#a9b1d6` |
| 5 | bright title | `#c0caf5` |
| 6 | thesis (highest contrast) | `#e6e9f5` |
| 7 | blue — components, types, functions | `#7aa2f7` |
| 8 | green — fixes, new mechanisms, guarantees | `#9ece6a` |
| 9 | red — defects, dead-ends | `#f7768e` |
| 10 | orange — caveats, gates | `#e0af68` |
| 11 | purple — sparing secondary accent | `#bb9af7` |
| 12 | teal — sparing secondary accent | `#7dcfff` |
| 13 | `none` | `none` |

| name | mood |
|---|---|
| `default` | Tokyo Night, dark |
| `dracula` | Dracula, dark |
| `nord` | Nord, dark |
| `gruvbox-dark` | Gruvbox, dark |
| `github-light` | GitHub Primer, light |
| `solarized-light` | Solarized, light |

See [`../examples/README.md`](../examples/README.md) for every example PR
rendered in every style.
