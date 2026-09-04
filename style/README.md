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
which fonts a reviewer's browser will fall back to. So the style declares what
is safe: the default covers what every mainstream system font collection
renders — ASCII, Latin-1 and Latin Extended, Greek, Cyrillic, general
punctuation (– — … • ‹ ›), arrows (→ ↔ ⇒), mathematical operators (≤ ≥ ≠ ≈ ∑
√ ∞), box drawing and block elements, geometric shapes (■ ▲ ●), check marks
(✓ ✗) and angle brackets (⟨ ⟩). Not on the list, deliberately: emoji, icon-font
private-use glyphs, zero-width and other format characters, and everything in
the supplementary planes. Override `glyphs` in your style JSON to change it
(the key replaces the default list, so copy it and add).

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
