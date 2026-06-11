"""Pipeline B — active-fire detection (docs/STRUCTURE.md §4 Pipeline B).

Window: May–July 2026 fire season; July 2025 Latakia (EMSR811) as documented
anchor. AOIs: Hasakah (cropland fires), Latakia (coastal/forest).

Primary detector: FIRMS VIIRS 375 m (NOT MODIS, §9). MODIS MCD64A1 used only
for monthly burned-area context.

GEE IDs (verify, §5): FIRMS (MODIS only on GEE; VIIRS via API),
  MODIS/061/MCD64A1, GOOGLE/DYNAMICWORLD/V1
"""

# TODO(W5): pull VIIRS hotspots (via clients/firms.py) for AOIs/windows.
