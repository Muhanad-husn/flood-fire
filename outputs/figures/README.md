# outputs/figures/ — rendered figures

Static figures (PNG/SVG) written by `viz.save_figure()` and the plot functions in
`analysis/`, `food_security/`, and `pipelines/*/attribution.py`, then embedded in
the Quarto report (`report/`).

PNG/JPG here are **gitignored** (`.gitignore`) — figures are regenerated from code
and the validated damage tables, never the source of truth. Re-render with
`quarto render report/` or by re-running the owning module.
