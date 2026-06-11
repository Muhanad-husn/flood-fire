"""CHIRPS daily rainfall client (STRUCTURE.md §5).

Role F/B. GEE collection: UCSB/CHG/CHIRPS/DAILY (verify against live catalog).
Feeds the RQ1 rainfall-vs-discharge decomposition and the §3.3 baseline
rainfall deficit (Nov 2024–May 2025). All pulls cached/checkpointed.
"""

# TODO(W3): pull daily precip over flood AOIs/windows via GEE; cache.
