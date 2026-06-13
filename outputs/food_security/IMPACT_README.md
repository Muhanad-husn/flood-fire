# W6 — Food-security impact layer (docs/STRUCTURE.md §3.4)
Translates **human-validated** flood & fire `damaged_cropland_ha` records (§3.2, §6) into estimated cereal-production loss and an indicative food-security pressure, referenced to the 2025 drought baseline (§3.3).
## Headline (study AOIs, combined flood + fire)
- **Estimated cereal-production loss:** ~**24,412 t** (headline) — range **2,651–38,432 t** (cropland-definition × temporal-aggregation sensitivity).
- That is **4.49%** of the four study AOIs' combined 2025 baseline (543,958 t), and 2.03% of the national ~1.2 Mt 2025 cereal floor.
- Indicative food-security pressure (study total): **moderate incremental stress** — *not* an IPC phase (see caveats).

## Method (DEC-033)
1. **Validated-only gate (§6).** Only `is_consumable()` records are read; a non-validated record makes the layer refuse (`gate_records`, strict). No agent set any `validation_status` — the floods (S6) and fires (S7) Tier-2 gates were closed by a human.
2. **One cropland convention.** UNION cropland (DEC-015) is the headline, INTERSECTION the conservative low bound. The flood two-row encoding (DEC-024) and the fire union-headline + sensitivity-table encoding (DEC-032) are normalised onto union-headline here — so flood rows are **not** double-counted across cropland definitions.
3. **No temporal double-count (floods).** Flood records are per event-date; a `persistent` pixel recurs across dates. Headline flood-affected cropland per AOI = the **peak single event-date** extent (transient+persistent) — a clean snapshot, conservative lower bound. A season-distinct reference (Σ transient + peak persistent) is the upper bracket. Fires = one window, disjoint severity → exact.
4. **Loss = ha × 2025 baseline yield** (per-AOI `cereal_production_2025_t / cropland_ha`, DEC-019 — a uniform ~0.223 t/ha drought-floor yield). Applying the drought-year yield to 2026 damaged area makes the loss a **conservative lower bound**: 2026 was a tentative recovery (PRODUCT §2), so expected yields on the lost hectares were higher.

## Confidence & caveats (proportionate claims, §9)
- **Not an IPC classification.** The `food_security_pressure_indicative` label is a qualitative band from production-loss-as-%-of-baseline, **not** an IPC phase. A real phase needs the full IPC protocol (consumption, livelihoods, nutrition, mortality). **GIEWS / FEWS NET / IPC** are the authoritative sources; this layer is a production-shock signal that feeds, not replaces, such an assessment. Syria's 2025 baseline was already a record-drought Crisis-level food-security context (PRODUCT §2) — the 2026 shock is **incremental** pressure on top of that.
- **Loss is a lower bound** on two counts: conservative drought-floor yield, and the peak-date (not season-union) flood aggregation. The reported range brackets the cropland-definition and temporal-aggregation uncertainty; it does **not** add yield-recovery uncertainty.
- **Damage hectares inherit the pipeline caveats:** flood extent is open-water riverine inundation (flooded vegetation / pluvial upland under-detected, DEC-023); burned cropland is VIIRS-confirmed dNBR, a conservative lower bound (DEC-031). Latakia 2026 fire ≈ 1 ha because the July fire peak is in the simulated future (S7) — a data-availability gap, not absence of risk.

## Outputs
- `impact_by_aoi.csv` — per AOI × phenomenon: damaged ha (headline/low/season), yield, loss (t), loss % of baseline.
- `impact_national.csv` — per-AOI combined + study total vs the 2025 floor + indicative pressure.
- `outputs/figures/w6_food_security_production_loss.png` — headline loss by AOI & phenomenon.
