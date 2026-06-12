# notebooks/ — exploration & Tier-2 validation workbench

Developer-facing, **not** the deliverable. The portfolio artifact is the static
Quarto report in [`report/`](../report) (DEC-008). These notebooks are where a
human inspects candidate rasters and works the **Tier-2 human-validation gate**
(`docs/STRUCTURE.md` §6).

## Purpose

The validation gate *requires* a human to visually compare each Tier-2 output
against named ground truth before it can be marked `validated`. These interactive
`geemap` / `leafmap` notebooks are that surface:

- **`validate_floods.ipynb`** — overlay candidate Sentinel-1 flood masks on GloFAS
  and any Copernicus EMS flood activation for the window; set `validation_status`.
- **`validate_fires.ipynb`** — overlay Sentinel-2 dNBR burn scars + FIRMS/VIIRS
  hotspots on Copernicus EMS **EMSR811** (PAX Sentinel-2 methodology as precedent).

## Rules

- **Unvalidated layers may be shown here** — clearly labelled (use
  `viz.validation_palette()` for the status encoding). This is the one place that
  is allowed; the report shows validated records only.
- **Only a human sets `validation_status = validated`** — never an agent or
  Workflow run (`docs/STRUCTURE.md` §6, DEC-007).
- Interactive `geemap` maps need live GEE auth, so they are **not** embedded in the
  reproducible report. For the report, export the relevant layer to a static
  raster/PNG (via `viz.save_figure`) so it renders offline.

> Notebooks are added as W4/W5 produce masks to validate. `.ipynb_checkpoints/` is
> gitignored.
