# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

# Syria 2026 Agricultural Shocks

> **Project phase:** Planning
> **Last updated:** 2026-06-12
> **Current stage:** Pre-scaffold — planning docs only; W0 (repo scaffold, env, GEE auth, schema) not yet started.

---

## Project Identity

A data-science study quantifying how the 2026 floods and crop fires reversed Syria's tentative cereal recovery, measured for food-security impact against the 2025 record-drought baseline. The analytical spine is the contrast: the baseline is drought (desertification trajectory), the shock is water (an anomaly), plus conflict-linked crop fires.

Two parallel pipelines (floods, fires) in one repo, sharing a common AOI grid, a single damage schema, and one food-security impact layer. Both emit the **same** output — `damaged_cropland_ha` per AOI per date — which is what makes this one project rather than two. Retrospective analytical research and portfolio output, not an operational tool. See `PRODUCT.md` for full intent, scope, and locked research questions.

## Developer Principles

Product intent and research questions live in `PRODUCT.md`. The following govern *how Claude works in this repo*:

- **Balance: practicality over perfectionism.** 80/20 rule. A working, validated solution beats a theoretically optimal one.
- **Don't reinvent the wheel.** Check existing tools, GEE collections, and libraries before building.
- **Measure, don't speculate.** When in doubt, prototype and measure rather than analyze indefinitely.
- **Proportionate claims.** This is a conflict zone with contested administrative control and a politically charged dam-attribution question. Keep causal claims proportionate to evidence, attribute sources, never overclaim. RQ3 control-area framing is descriptive only — never a differential or causal claim (`PRODUCT.md` §5, §9).
- **Cost-conscious.** Prefer scoped, checkpointed runs; reserve parallel/Workflow execution for rubric-eligible mechanical work only (`PRODUCT.md` §8).

---

## Document Map

Reading order for understanding the project. Claude should consult these when reasoning about any question.

### Foundational (read first)

- **`PRODUCT.md`** — intent, problem/context, goals, non-goals, the locked research questions (RQ1–RQ3), success criteria, constraints, ethics.
- **`STRUCTURE.md`** — architecture, repository layout, core contracts, pipelines, data-source table, validation tiers, work breakdown, conventions, locked decisions.

### Contracts & Schema

- **`STRUCTURE.md` §3** — core contracts (pinned, do not reopen): §3.1 AOI & cropland mask · §3.2 shared damage schema (the integration contract) · §3.3 2025 drought baseline · §3.4 food-security join.
- **`STRUCTURE.md` §5** — data-source contracts and GEE collection IDs (verify every ID against the live catalog before use).
- **`STRUCTURE.md` §6** — validation & definition of done (Tier 1 agent-verifiable, Tier 2 human-gated).

### Specifications

- **`syria-2026-agri-shocks-dossier.md`** — full data-source catalog, access methods, and caveats. *(Referenced by `PRODUCT.md`/`STRUCTURE.md`; not yet present in the repo — create or obtain before relying on it.)*

### Tracking & Design

- **`tracking/`** — `plan-sessions` output and the progress tracker live here. *(Directory not yet created; established at scaffold time.)*
- **`STRUCTURE.md` §10** — seed for the Decision & Change Log (locked decisions). A standing Decision Log does not yet exist; create it under `tracking/` when continued planning begins recording decisions.

---

## Working Rules

### Spec Drift Reconciliation

`PRODUCT.md` and `STRUCTURE.md` are the source of truth. When code, the dossier, or a later note disagrees with them, surface the conflict — do not silently resolve it. The contracts in `STRUCTURE.md` §3 and the locked decisions in §10 are pinned: do not reopen them in continued planning; fill in *within* their boundaries.

### What Claude Should Always Do

- **Before working a unit:** Read the relevant `STRUCTURE.md` §7 work-breakdown row (W0–W10) and, once it exists, the corresponding `tracking/` session plan. These name the dependencies, complexity, and parallel-eligibility — read them before fanning out context.
- **Before answering any question:** Check `PRODUCT.md` and `STRUCTURE.md` for context, constraints, and prior decisions. Cross-reference. Don't contradict what's already decided unless explicitly revisiting it.
- **When proposing a revision to a locked decision (`STRUCTURE.md` §10):** State what changes, why it's better, and what downstream impacts need updating. Reference the original decision.
- **When finding an inconsistency between documents:** Flag it clearly. Don't silently resolve it — surface it so the human can decide.
- **Verify every GEE collection ID against the live catalog before wiring it in** (IDs are versioned — `STRUCTURE.md` §5, §9).
- **Respect the validation gate:** the food-security layer and all RQ analyses consume **only** records with `validation_status == validated`. No Workflow/parallel run may set a Tier-2 output to `validated`; only a human does (`STRUCTURE.md` §6).

### What Claude Should Never Do

- Create files outside the established directory structure (`STRUCTURE.md` §2) without asking.
- Make architectural decisions without checking the locked decisions (`STRUCTURE.md` §10) for related prior choices.
- Self-certify Tier-2 outputs (flood masks, burn scars, any `damaged_cropland_ha` derived from them). Tests passing or agent convergence is **not** correctness for Tier-2 — only human comparison against named ground truth is (`STRUCTURE.md` §6).
- Train deep-learning / CV models, analyze the earthquake, or treat pre-2026 data as anything but baseline/context (`PRODUCT.md` §4).
- Use MODIS for fire *detection* (use FIRMS VIIRS 375 m; MODIS only for monthly burned-area context — `STRUCTURE.md` §9).

### Cross-Reference Discipline

- Every module consumes the canonical AOIs and cropland mask from `aois/`; no module redefines AOIs (`STRUCTURE.md` §3.1).
- Nothing downstream reads a pipeline's internal rasters directly — the food-security layer and RQ analyses read **only** the shared damage schema (`STRUCTURE.md` §3.2).
- All external pulls are cached and checkpointed (rate-limit safety + reproducibility); retry loops must never re-pull (`STRUCTURE.md` §9).

---

## Current State

Planning phase. Only `PRODUCT.md`, `STRUCTURE.md`, and this `CLAUDE.md` exist. None of the directory structure below has been created, and the companion dossier is referenced but not yet present. Next concrete step is **W0** (`STRUCTURE.md` §7): repo scaffold, environment (WSL2 or conda for the geospatial stack), GEE auth, and the shared damage schema.

---

## Directory Structure

Planned layout (`STRUCTURE.md` §2) — created at scaffold time, not yet on disk:

```
syria-agri-shocks-2026/
├── PRODUCT.md
├── STRUCTURE.md
├── CLAUDE.md
├── aois/                 # canonical AOIs + cropland mask (shared, §3.1)
│   ├── governorates.geojson
│   ├── cropland_mask.tif
│   └── control_areas.geojson      # RQ3 — indicative only, descriptive overlay
├── baseline/             # 2025 drought reference (§3.3)
│   ├── ndvi_anomaly_2025.tif
│   ├── rainfall_deficit.csv
│   └── production_baseline.csv
├── clients/              # external-source API clients (cached, §9)
│   ├── firms.py  chirps.py  acled.py  hdx.py  gee_auth.py
├── pipelines/
│   ├── floods/           # flood_mask.py  cropland_flooded.py  attribution.py
│   └── fires/            # active_fire.py  burn_severity.py  attribution.py
├── schema/               # shared damage schema (§3.2)
├── food_security/        # impact_layer.py (§3.4)
├── analysis/             # whiplash.py  control_differential.py
├── tracking/             # plan-sessions output + progress tracker
└── outputs/              # tables, masks, figures
```
