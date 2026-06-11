# aois/ — canonical AOIs + cropland mask (shared)

Per `STRUCTURE.md` §3.1. Every module consumes these canonical assets; **no
module redefines AOIs**.

Expected contents (produced in W1):

- `governorates.geojson` — canonical AOI boundaries.
  - Floods: Deir ez-Zor, Raqqa, Hasakah.
  - Fires: Hasakah, Latakia.
- `cropland_mask.tif` — one cropland mask, reconciled from Dynamic World and
  ESA WorldCover, **with disagreement documented** (§9).
- `control_areas.geojson` — RQ3 only. Indicative government-controlled and
  former AANES boundaries. **Indicative / contested — descriptive overlay
  only, never a causal or differential claim** (`PRODUCT.md` §5, §9).

Binary/vector data files are not stubbed here — they are generated in W1.
