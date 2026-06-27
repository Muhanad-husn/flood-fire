"""Pipeline B driver — VIIRS detection + S2 dNBR → fire DamageRecords (W5/S7).

Builds, for each fire AOI/window:
  1. VIIRS hotspots (cached, clients/firms.py) → table + near-fire footprint.
  2. S2 dNBR severity (burn_severity.py), confirmed by VIIRS proximity (DEC-031),
     intersected with the DEC-015 cropland definition.
  3. damaged_cropland_ha per AOI/severity, under BOTH union (headline) and
     intersection (sensitivity) cropland (DEC-015).
  4. DamageRecord(phenomenon=fire, validation_status=unvalidated) — UNION headline —
     written to outputs/tables/fire_damage.{csv,parquet}; the union/intersection
     range to outputs/tables/fire_damage_sensitivity.csv.

The 2025 Latakia EMSR811 event is processed as a METHOD-VALIDATION anchor only
(pre-2026 = baseline/context, DEC-001) — it is NOT emitted as a study DamageRecord.

Run:  PYTHONPATH=. python pipelines/fires/build_fires.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from clients import gee_auth
from pipelines.fires import active_fire as af
from pipelines.fires import burn_severity as bs
from schema.damage_schema import (
    DamageRecord, Phenomenon, ValidationStatus, validate_record, write_csv, write_parquet,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_TABLES = ROOT / "outputs" / "tables"
OUT_HOTSPOTS = ROOT / "outputs" / "fire_hotspots"

# 2026 fire-season windows (S13 national re-scope). Same calendar windows for
# every governorate; dNBR is computed only over each governorate's VIIRS footprint.
# Window extended to live VIIRS NRT coverage as of 2026-06-27 (re-run update).
WINDOW_2026 = "2026-05-01/2026-06-27"   # available VIIRS NRT slice of May–Jul season
PRE_2026 = ("2026-03-15", "2026-04-30")
POST_2026 = ("2026-05-25", "2026-06-27")


def _gov_features() -> list[dict]:
    g = json.loads((ROOT / "aois" / "governorates.geojson").read_text())
    return g["features"]


def _fire_aois() -> list[str]:
    """Canonical fire AOIs = governorates tagged `fires` in governorates.geojson.

    National since S13 (every governorate with 2026 cropland fire); Latakia and
    Damascus City carry no `fires` tag (0 cropland fire) and are excluded.
    """
    return [f["properties"]["aoi_id"] for f in _gov_features()
            if "fires" in f["properties"].get("pipelines", [])]


def _jobs() -> list[tuple]:
    """(aoi, label, date_str, firms-sources, pre, post, is_study) per fire AOI."""
    jobs = [(aoi, "2026", WINDOW_2026, af.VIIRS_NRT, PRE_2026, POST_2026, True)
            for aoi in _fire_aois()]
    # Validation anchor — EMSR811 (Jul 2025 Latakia forest fire). NOT a 2026 study
    # record (pre-2026 = baseline/context, DEC-001); kept to validate the method.
    jobs.append(("latakia", "2025_emsr811", "2025-07-01/2025-07-20", af.VIIRS_SP,
                 ("2025-06-01", "2025-06-30"), ("2025-07-21", "2025-08-25"), False))
    return jobs


def _aoi_geoms():
    import ee
    return {f["properties"]["aoi_id"]: ee.Geometry(f["geometry"]) for f in _gov_features()}


def run() -> None:
    gee_auth.initialize()
    geoms = _aoi_geoms()
    union, inter = bs.cropland_masks()

    study_records: list[DamageRecord] = []
    sensitivity_rows: list[dict] = []
    anchor_rows: list[dict] = []

    for aoi, label, date_str, sources, pre, post, is_study in _jobs():
        print(f"\n=== {aoi} [{label}] {date_str} ===")
        start, end = date_str.split("/")
        rows = af.fetch(aoi, start, end, sources=sources)
        af.save_hotspots_csv(rows, OUT_HOTSPOTS / f"{aoi}_{label}_viirs.csv")
        summ = af.summary(rows)
        print(f"  VIIRS: {summ}")
        if summ["n"] == 0:
            print("  no hotspots — skipping dNBR")
            continue

        near = af.near_fire_mask(rows)
        footprint = af.footprint_geometry(rows)
        dnbr = bs.dnbr_image(geoms[aoi], pre, post)

        ha_u = bs.burned_cropland_ha(dnbr, near, union, footprint)
        ha_i = bs.burned_cropland_ha(dnbr, near, inter, footprint)
        tot_u = round(sum(ha_u.values()), 1)
        tot_i = round(sum(ha_i.values()), 1)
        print(f"  burned cropland ha — union={tot_u} intersection={tot_i}")
        print(f"    by severity (union): "
              f"{ {bs.SEVERITY_BY_CLASS[k]: round(v,1) for k,v in sorted(ha_u.items())} }")

        for cls, sev in bs.SEVERITY_BY_CLASS.items():
            hu = round(ha_u.get(cls, 0.0), 4)
            hi = round(ha_i.get(cls, 0.0), 4)
            sensitivity_rows.append({
                "aoi_id": aoi, "window": label, "date": date_str,
                "severity_class": sev, "ha_union": hu, "ha_intersection": hi,
                "is_study": is_study,
            })
            if is_study:
                rec = validate_record(DamageRecord(
                    aoi_id=aoi, date=date_str, phenomenon=Phenomenon.FIRE,
                    severity_class=sev, source_layer="S2_dNBR",
                    damaged_cropland_ha=hu,   # UNION = headline (DEC-015)
                    validation_status=ValidationStatus.UNVALIDATED,
                ))
                study_records.append(rec)
            else:
                anchor_rows.append({
                    "aoi_id": aoi, "window": label, "severity_class": sev,
                    "ha_union": hu, "ha_intersection": hi,
                })

    # --- write canonical study records (union headline) ----------------------
    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    write_csv(study_records, OUT_TABLES / "fire_damage.csv")
    write_parquet(study_records, OUT_TABLES / "fire_damage.parquet")

    # --- write union/intersection sensitivity table --------------------------
    with (OUT_TABLES / "fire_damage_sensitivity.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["aoi_id", "window", "date", "severity_class",
                                           "ha_union", "ha_intersection", "is_study"])
        w.writeheader()
        w.writerows(sensitivity_rows)

    # --- write EMSR811 validation-anchor table (not a study record) ----------
    if anchor_rows:
        with (OUT_TABLES / "fire_validation_anchor_emsr811.csv").open(
                "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["aoi_id", "window", "severity_class",
                                               "ha_union", "ha_intersection"])
            w.writeheader()
            w.writerows(anchor_rows)

    print(f"\nWROTE {len(study_records)} study DamageRecords (all UNVALIDATED) -> "
          f"{OUT_TABLES/'fire_damage.csv'}")
    print(f"      sensitivity range -> {OUT_TABLES/'fire_damage_sensitivity.csv'}")
    print(f"      EMSR811 anchor -> {OUT_TABLES/'fire_validation_anchor_emsr811.csv'}")


if __name__ == "__main__":
    run()
