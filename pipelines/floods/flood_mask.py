"""Pipeline A — flood-extent masks (STRUCTURE.md §4 Pipeline A).

Window: March–June 2026 (April floods/hailstorms + late-May Euphrates surge).
AOIs: Deir ez-Zor, Raqqa, Hasakah.

Sentinel-1 SAR is LOAD-BEARING (extent through cloud); optical (Sentinel-2 +
Dynamic World) is confirmatory only (§9). Subtract permanent water using JRC
Global Surface Water.

Tier-2 human-gated (§6): mask generation per sub-AOI may fan out, but
validation against GloFAS / any Copernicus EMS flood activation is sequential
and human. validation_status defaults to "unvalidated".

GEE IDs (verify against live catalog before use, §5/§9):
  COPERNICUS/S1_GRD, COPERNICUS/S2_SR_HARMONIZED, GOOGLE/DYNAMICWORLD/V1,
  JRC/GSW1_4/GlobalSurfaceWater, COPERNICUS/DEM/GLO30
"""

# TODO(W4): SAR-based flood extent per AOI/date; subtract permanent water.
