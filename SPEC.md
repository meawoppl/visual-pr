# Visual PR — authoring spec

Produce **one SVG** that argues the pull request's thesis visually: what was
wrong or missing before, what mechanism the PR adds, and what guarantee holds
after. Commit it on the PR branch at `<svg-dir>/<pr-number>.svg`
(default `000-pr-visualization/<pr-number>.svg` — the `000-` prefix sorts it
first in GitHub's review file list).

## Rule zero: the diagram is grounded in the code

**If you didn't read it, don't draw it.** Every box title, field name,
function, filter expression, and claim in the diagram must come from the
actual diff and the surrounding code — never from the PR description alone,
and never invented. Read the diff first (`gh pr diff <N>`, `gh pr view <N>`,
`git show <base>:<file>` for the BEFORE side). A reviewer cross-checking
symbols against the diff must find every one.

## The thesis

One or two lines of large near-white text directly under the header. It states
the **claim** of the PR — the behavioral change and its consequence — not a
description of the diff. Formula: *X used to ⟨flaw, stated concretely⟩; now
⟨mechanism⟩, so ⟨guarantee⟩.*

## Canvas and layout

Geometry comes from the style JSON (bundled default: 2000×1200; the numbers
below assume it — scale proportionally for other canvases):

- Full-bleed background (first palette color), 55px side margins.
- **Header** (y≈52): `PR #NNNN · <title>` — 24px, muted, letter-spacing 1.
- **Thesis** (y≈100, second line y≈140): 34px, near-white. Hairline under it.
- **Split**: `BEFORE` label (22px bold, letter-spacing 4, the red accent) on
  the left; `AFTER` (green accent) on the right; dashed vertical divider at
  the style's `divider_x` between them.
- **Footer** (y≈1172): one muted 22px line — the scope caveat: what the PR
  deliberately does *not* do, or its sharpest real limitation. Always present.

## Color semantics (indexes into the style palette)

The bundled default is Tokyo Night; a consuming repo may re-skin via its style
JSON, but the *semantics* hold: background, box-fill, neutral border, muted
text, body text, bright title, near-white thesis, then accents — blue for
component/type/function names, **green only for fixes/new mechanisms/
guarantees**, **red only for defects/dead-ends**, orange for caveats/gates,
purple and teal as sparing secondary accents. Unchanged structure stays
neutral so the eye is pulled only to what the PR changed.

## Archetypes — pick one per PR

- **Dataflow**: boxes = components, arrows = flow; BEFORE dead-ends in red,
  AFTER flows through a green new box to a green outcome.
- **Sequence**: lifelines + activation bars for locking/ordering/protocol
  changes.
- **Timeline**: horizontal axis for latency, retention windows, delays.
- **Checklist verdict**: red `–` items vs green `✓` items for validation
  logic.

Each panel must read top-to-bottom in one pass, and the two panels should be
structurally parallel so the reader diffs them by eye.

## Text fitting — budgets, not vibes

The validator estimates glyph width as `char_factor × font-size` (default
0.5). On the default canvas: thesis line ≤105 chars @34px; box title ≤62
chars @26px; box detail ≤71 chars @23px; footer ≤165 chars @22px. Never let
text touch a box edge (24px interior padding); split lines rather than
shrinking below 21px. Free-floating labels must not cross an arrow's path or
the center divider.

## Quality bar

- Every identifier in the diagram appears in the diff or the touched files.
- Red only where something is genuinely wrong; green only where the PR makes
  it right — a diagram that is all green is marketing, not review.
- The footer names a real limitation, not a humble-brag.
- The validator passes clean (it is the same check CI runs).
