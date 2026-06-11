"""Shared damage schema — the integration contract (STRUCTURE.md §3.2).

Every damage record, from EITHER pipeline (floods or fires), conforms to this
one schema. The food-security layer and all RQ analyses consume ONLY this
schema; nothing downstream reads a pipeline's internal rasters directly.

Hard rule (STRUCTURE.md §6): the food-security layer and RQ analyses must
refuse to consume any record whose validation_status != "validated". Tier-2
outputs are human-gated — no agent/Workflow run may set validation_status to
"validated".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Phenomenon(str, Enum):
    FLOOD = "flood"
    FIRE = "fire"


class ValidationStatus(str, Enum):
    UNVALIDATED = "unvalidated"  # default for every Tier-2 artifact (§9)
    VALIDATED = "validated"      # set ONLY by a human (§6)
    REJECTED = "rejected"


@dataclass
class DamageRecord:
    """One damaged-cropland observation, keyed per STRUCTURE.md §3.2."""

    aoi_id: str                       # canonical AOI (aois/, §3.1) — never redefined here
    date: str                         # ISO 8601 (event date / observation window)
    phenomenon: Phenomenon            # flood | fire
    severity_class: str               # pipeline-defined severity bin
    source_layer: str                 # provenance of the detection (e.g. "S1_GRD", "S2_dNBR")
    damaged_cropland_ha: float        # the shared output both pipelines emit
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED

    def is_consumable(self) -> bool:
        """Downstream gate: only validated records may feed §3.4 / RQ analyses."""
        return self.validation_status is ValidationStatus.VALIDATED


# TODO(W0): finalize severity_class vocab per phenomenon; add (de)serialization
# to the canonical table format used by outputs/.
