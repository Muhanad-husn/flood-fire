"""FIRMS active-fire client — VIIRS 375 m, NOT MODIS (docs/STRUCTURE.md §9).

Access: API + free MAP_KEY. Rate limit: 5,000 requests / 10 min (§9).
All pulls are cached and checkpointed so retry loops never re-pull.
MODIS is used only for monthly burned-area context, never for detection.
"""

# TODO(W3): MAP_KEY from env; query VIIRS hotspots for fire AOIs/windows;
# cache responses; surface rate-limit headroom. Parallel-eligible (W3, §7).
