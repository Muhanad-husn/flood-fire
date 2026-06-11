"""Google Earth Engine authentication & initialization (docs/STRUCTURE.md §8).

Auth is interactive and human-run once: `earthengine authenticate`.
This module only initializes an already-authenticated session.
"""

# TODO(W0): import ee; provide init() that calls ee.Initialize() and verifies
# the project is set. Fail loudly with the `earthengine authenticate` hint.
