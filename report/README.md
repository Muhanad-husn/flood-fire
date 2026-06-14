# Report — the presentation layer

A static, reproducible [Quarto](https://quarto.org) website (DEC-008) presenting the
study's findings. It is the project's portfolio output, not a dashboard.

Pages:

- `index.qmd` — overview, findings-first; the loss map, the drought→recovery→shock
  spine, headline figures.
- `brief.qmd` — one-page executive brief (the forwardable artifact); print/save-as-PDF.
- `food_security.qmd` — the primary question: production loss and indicative
  food-security pressure, per governorate, plus the loss map and the
  headline-excluding-flagged-hectares robustness check.
- `rq.qmd` — research-questions index; `rq1.qmd` / `rq2.qmd` / `rq3.qmd` — the three.
- `glossary.qmd` — plain-language meaning of the `DEC-NNN` / `§` method codes; the
  narrative pages link their codes here to keep prose readable.

Shared bits: `styles.css` (confidence pills, key-findings/footer blocks, print CSS),
`_footer.qmd` (the citation/provenance block, `{{< include >}}`d on every page).

Maps are drawn by `viz.choropleth` straight from `aois/governorates.geojson` with
matplotlib + stdlib `json` only — **no geopandas** — so the render env stays light
(see `requirements.txt`). A governorate-loss map makes no comparative claim (the
DEC-005 concern is the control-zone overlay only). Figures default to SVG for crisp
mobile rendering; the choropleth cells override to PNG.

## The contract every figure honours

Each claim-bearing figure is built **only from human-validated (Tier-2) damage
records** — the validation gate (`docs/STRUCTURE.md` §6) is enforced in code via
`viz.consumable_records()`. Figures are rebuilt **in-cell from the committed
validated output tables** (`outputs/**/*.csv`); they never pull from Google Earth
Engine and never read a pipeline's internal rasters. PNG figures are gitignored
(DEC-008) and regenerated at render time.

Because of this, rendering needs only a light toolchain — **not** the full geo
analysis env (`f_f`): the report cells import `pandas`, `matplotlib`, `seaborn`, and
the local pure-Python `schema` / `viz` packages, and read CSVs. See
`report/requirements.txt`.

## Render locally

With [Quarto installed](https://quarto.org/docs/get-started/) and a Python with the
render deps:

```bash
pip install -r report/requirements.txt     # or: use the existing f_f conda env
quarto render report                        # writes report/_site/
quarto preview report                       # live preview while editing
```

`_quarto.yml` sets `freeze: auto`, so cached cells are not re-executed unless their
code changes. The build dirs (`_site/`, `_freeze/`, `.quarto/`, `*_files/`) are
gitignored.

> No Quarto on the machine? You can still smoke-test that every page's Python cells
> execute against the committed tables without rendering HTML — extract the
> ` ```{python} ` blocks and run them (an Agg backend makes `plt.show()` a no-op).
> This is what was used to verify the pages on a Quarto-less Windows box.

## Publish to GitHub Pages (automated)

`.github/workflows/publish-report.yml` renders the report and deploys
`report/_site/` to GitHub Pages on every push to `main` that touches `report/`,
`outputs/`, `viz/`, or `schema/` (and on manual `workflow_dispatch`).

**One-time setup (repo owner, in the GitHub UI):**

1. **Settings → Pages → Build and deployment → Source: _GitHub Actions_.**
2. Push to `main` (or run the workflow manually from the **Actions** tab).

The site then publishes at:

```
https://muhanad-husn.github.io/flood-fire/
```

The workflow uses the official `actions/deploy-pages` flow (OIDC, no `gh-pages`
branch needed). If you prefer a manual one-off publish instead of CI, you can run
`quarto publish gh-pages report` locally.
