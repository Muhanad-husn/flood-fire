"""Shared damage schema — the integration contract (docs/STRUCTURE.md §3.2).

Every damage record, from EITHER pipeline (floods or fires), conforms to this
one schema. The food-security layer and all RQ analyses consume ONLY this
schema; nothing downstream reads a pipeline's internal rasters directly.

Hard rule (docs/STRUCTURE.md §6): the food-security layer and RQ analyses must
refuse to consume any record whose validation_status != "validated". Tier-2
outputs are human-gated — no agent/Workflow run may set validation_status to
"validated".

W0 finalization (this module):
  * severity_class vocabulary defined PER PHENOMENON (flood depth/persistence
    bins vs fire dNBR severity bins) — see SEVERITY_CLASSES + validate_record().
  * (de)serialization to the canonical outputs/ table format (CSV via stdlib,
    Parquet via pandas) with a lossless round-trip — see to_rows()/from_rows()
    and the read_/write_ helpers.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence


class Phenomenon(str, Enum):
    FLOOD = "flood"
    FIRE = "fire"


class ValidationStatus(str, Enum):
    UNVALIDATED = "unvalidated"  # default for every Tier-2 artifact (§9)
    VALIDATED = "validated"      # set ONLY by a human (§6)
    REJECTED = "rejected"


# --- severity_class vocabulary, per phenomenon (docs/STRUCTURE.md §4) ----------
#
# Each pipeline emits the SAME schema but its own severity bins. The vocab is
# pinned here so the schema is the single source of truth and downstream layers
# can group/weight by severity without knowing pipeline internals.
#
# Floods (Pipeline A): bins describe inundation confidence/persistence derived
#   from Sentinel-1 SAR (load-bearing) confirmed by optical. "transient" = a
#   single-date SAR detection; "persistent" = multi-date standing water;
#   "permanent_excluded" is NOT a damage class — it is the JRC GSW permanent
#   river that is subtracted out (kept in the vocab only to name the exclusion).
# Fires (Pipeline B): bins follow the conventional Sentinel-2 dNBR severity
#   thresholds (Key & Benson / USGS FIREMON), low→high burn severity.
SEVERITY_CLASSES: dict[Phenomenon, tuple[str, ...]] = {
    Phenomenon.FLOOD: (
        "transient",          # single-date SAR inundation over cropland
        "persistent",         # multi-date standing water over cropland
        "permanent_excluded", # JRC GSW permanent water — subtracted, not damage
    ),
    Phenomenon.FIRE: (
        "unburned",        # dNBR < 0.10        — not counted as damage
        "low",             # 0.10 <= dNBR < 0.27
        "moderate_low",    # 0.27 <= dNBR < 0.44
        "moderate_high",   # 0.44 <= dNBR < 0.66
        "high",            # dNBR >= 0.66
    ),
}

# Bins that name an exclusion/zero-damage class rather than actual damage.
# damaged_cropland_ha for these is expected to be 0.0 (asserted in validation).
_NON_DAMAGE_CLASSES: dict[Phenomenon, frozenset[str]] = {
    Phenomenon.FLOOD: frozenset({"permanent_excluded"}),
    Phenomenon.FIRE: frozenset({"unburned"}),
}


@dataclass
class DamageRecord:
    """One damaged-cropland observation, keyed per docs/STRUCTURE.md §3.2."""

    aoi_id: str                       # canonical AOI (aois/, §3.1) — never redefined here
    date: str                         # ISO 8601 (event date / observation window)
    phenomenon: Phenomenon            # flood | fire
    severity_class: str               # pipeline-defined severity bin (SEVERITY_CLASSES)
    source_layer: str                 # provenance of the detection (e.g. "S1_GRD", "S2_dNBR")
    damaged_cropland_ha: float        # the shared output both pipelines emit
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED

    def __post_init__(self) -> None:
        # Coerce string inputs (e.g. from a CSV read) into the enums so a
        # round-tripped record is `==` to the original.
        if not isinstance(self.phenomenon, Phenomenon):
            self.phenomenon = Phenomenon(self.phenomenon)
        if not isinstance(self.validation_status, ValidationStatus):
            self.validation_status = ValidationStatus(self.validation_status)
        self.damaged_cropland_ha = float(self.damaged_cropland_ha)

    def is_consumable(self) -> bool:
        """Downstream gate: only validated records may feed §3.4 / RQ analyses."""
        return self.validation_status is ValidationStatus.VALIDATED


# --- validation ---------------------------------------------------------------

class SchemaError(ValueError):
    """A DamageRecord violates the §3.2 schema contract."""


def validate_record(rec: DamageRecord) -> DamageRecord:
    """Assert a record obeys the schema's semantic rules; return it unchanged.

    Tier-1 (agent-verifiable): structural conformance only. Does NOT and CANNOT
    confer validation_status == validated — that is the human Tier-2 gate (§6).
    """
    allowed = SEVERITY_CLASSES[rec.phenomenon]
    if rec.severity_class not in allowed:
        raise SchemaError(
            f"severity_class {rec.severity_class!r} not valid for "
            f"{rec.phenomenon.value}; allowed: {allowed}"
        )
    if rec.damaged_cropland_ha < 0:
        raise SchemaError(
            f"damaged_cropland_ha must be >= 0, got {rec.damaged_cropland_ha}"
        )
    if rec.severity_class in _NON_DAMAGE_CLASSES[rec.phenomenon] and rec.damaged_cropland_ha != 0.0:
        raise SchemaError(
            f"severity_class {rec.severity_class!r} is a non-damage class for "
            f"{rec.phenomenon.value}; damaged_cropland_ha must be 0.0, got "
            f"{rec.damaged_cropland_ha}"
        )
    if not rec.aoi_id:
        raise SchemaError("aoi_id is required")
    if not rec.date:
        raise SchemaError("date is required")
    return rec


# --- canonical (de)serialization ----------------------------------------------
#
# Canonical table = one row per DamageRecord, columns in FIELDNAMES order, enums
# stored as their .value strings. CSV is the human-/git-friendly interchange;
# Parquet is the typed, compact form for the outputs/ pipeline. Both round-trip
# losslessly through to_rows()/from_rows().

FIELDNAMES: tuple[str, ...] = tuple(f.name for f in fields(DamageRecord))


def to_row(rec: DamageRecord) -> dict[str, object]:
    """One record -> a flat dict of primitives (enums as .value strings)."""
    row = asdict(rec)
    row["phenomenon"] = rec.phenomenon.value
    row["validation_status"] = rec.validation_status.value
    return row


def from_row(row: dict[str, object]) -> DamageRecord:
    """A flat dict (e.g. a CSV/Parquet row) -> a validated DamageRecord."""
    rec = DamageRecord(
        aoi_id=str(row["aoi_id"]),
        date=str(row["date"]),
        phenomenon=Phenomenon(str(row["phenomenon"])),
        severity_class=str(row["severity_class"]),
        source_layer=str(row["source_layer"]),
        damaged_cropland_ha=float(row["damaged_cropland_ha"]),
        validation_status=ValidationStatus(str(row["validation_status"])),
    )
    return validate_record(rec)


def to_rows(records: Iterable[DamageRecord]) -> list[dict[str, object]]:
    return [to_row(r) for r in records]


def from_rows(rows: Iterable[dict[str, object]]) -> list[DamageRecord]:
    return [from_row(r) for r in rows]


def write_csv(records: Sequence[DamageRecord], path: str | Path) -> Path:
    """Write records to the canonical CSV table (stdlib only)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        for rec in records:
            writer.writerow(to_row(rec))
    return path


def read_csv(path: str | Path) -> list[DamageRecord]:
    """Read the canonical CSV table back into validated DamageRecords."""
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return from_rows(csv.DictReader(fh))


def write_parquet(records: Sequence[DamageRecord], path: str | Path) -> Path:
    """Write records to the canonical Parquet table (requires pandas/pyarrow)."""
    import pandas as pd  # local import: schema core stays dependency-free

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(to_rows(records), columns=list(FIELDNAMES))
    df.to_parquet(path, index=False)
    return path


def read_parquet(path: str | Path) -> list[DamageRecord]:
    """Read the canonical Parquet table back into validated DamageRecords."""
    import pandas as pd

    df = pd.read_parquet(path)
    return from_rows(df.to_dict(orient="records"))
