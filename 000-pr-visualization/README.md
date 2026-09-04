# PR visual summaries

One SVG per pull request, named by PR number zero-padded to six digits:
`000412.svg`. This is the same requirement visual-pr enforces on the repos
that use it — here it is enforced on visual-pr itself by
[`.github/workflows/visual-pr.yml`](../.github/workflows/visual-pr.yml).

How to author one: [SPEC.md](../SPEC.md). How to check it before pushing:

```bash
python3 check_svg.py 000-pr-visualization/000412.svg
```
