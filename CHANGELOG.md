# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.2.0] - 2026-09-11
### Added
- **Felling model.** With a DEM supplied, d1 stops being the distance from the standing tree
  and becomes the distance from the road to the near end of the felled stem. Felling is
  confined to a sector centred on straight downslope (default ±105°), any direction is allowed
  on gentle ground (default ≤10°), and reaching the road ends the haul there. Both the
  geometric and the modelled mean d1 are reported, so the effect of the model is visible in
  one run.
- **Barrier layer** (rivers etc.). A felling direction whose stem would cross a barrier is not
  available: a stem thrown over a river cannot be pulled back across it.
- **Individual tree points** can be supplied and are used as the sample points instead of the
  grid, with an optional per-tree height field. Extraction distance is a per-tree quantity, so
  real stem positions beat a regular lattice and stand density is no longer averaged away.
- **Fetch DEM from elevation tiles**, a second algorithm that builds a DEM for an area from
  published elevation tiles. Intended to be run once in the office so the field work stays
  offline. The main algorithm can also invoke it directly.
- **Per-tree output layers**: sample points with distances, hauling lines, and felled stems.
- **Maximum sample points** (advanced, default 200000). The run stops before any processing if
  the sample is larger, instead of exhausting memory part way through.
- **Keep felling and hauling inside the operation area** (off by default). Everything outside the
  block behaves as a barrier, for the stem and the haul alike. Strict: a road outside the boundary
  cannot be used either.
- The DEM download offers **Auto**, which tries each source finest first and is now the default. If
  no source covers the area the run says so and continues without the felling model, rather than
  failing — a machine in the field with no network still gets the geometric answer.
  **Note for saved models and scripts:** the option list gained *Auto* at the front and moved *Do
  not download* to the end, so a stored value of `0` now means "download" where it used to mean
  "do not". Named sources keep their positions.

### Changed
- Messages from nested algorithms that the user cannot act on are no longer shown. Sample
  points that cannot reach a landing were reported one line each, per landing — thousands of
  red lines on a real block, for a successful run. They are now summarised once, with a count
  and a percentage.
- Landing points with empty geometry are reported as a warning rather than an error. They are
  still reported: ignoring them silently sends every sample point to the remaining landings and
  looks like a correct answer.
- The Processing provider registers without the GUI, so the plugin can be run under
  `qgis_process`.
- The new output layers default to temporary layers. Hauling lines draw as thin translucent grey:
  one line per tree covers the map, and the distance each stands for is already the colour of its
  point in the tree layer.
- Inputs in a different CRS to the operation area are **reprojected** rather than rejected, with a
  warning. QGIS's own algorithms reproject silently; behaving differently to the rest of the toolbox
  is a source of mistakes.
- **The snapping tolerance was doing two unrelated jobs.** A landing is an area, so the point that
  stands for it is off the road by construction — that is now handled by routing from the nearest
  point on the road, with no parameter to set. What remains is bridging gaps in a hand-drawn
  network, renamed **Gap bridged in the road network** and defaulted to 2 m rather than 5 m. The
  value is not a threshold: on real data the count of unroutable points jumps around with it, so
  the run now retries at a few nearby values and reports the one it used.
- Grid spacing became **Tree spacing**, moved to the advanced parameters, and defaults to 10 m. It
  is decided once for a way of working rather than per block.
- Parameters are ordered by what they are for: the layers the run needs, what limits the work, what
  stands for the trees, then the outputs, with method constants behind the advanced flag.
- **Debug mode was removed.** Three of its four layers duplicated the ordinary outputs or the
  report, and the fourth — the routes to the landing — belongs in a proper output layer if it is
  wanted at all.

### Fixed
- Sample points equidistant from more than one road were counted twice in every mean.
- Landing points with empty geometry were silently ignored.
- Trees within grapple reach of the road started their haul from the wrong point.
- **A haul could cross a barrier.** Only the stem was tested against barriers, never the line from
  the grabbed end to the road, so wood was hauled over rivers. The haul now goes to the nearest road
  point it can actually reach; a tree with no reachable road is reported as not extractable and left
  out of the means, rather than contributing a distance for work that cannot happen.
- Sample points outside the DEM were counted as "blocked". They are not — they are simply not
  modelled, and they are now counted separately.
- The Japanese warning about landings with no geometry printed its two counts the wrong way round.

### Performance
- Routes are folded into the running best per landing instead of being merged, sorted and
  de-duplicated as one pile. At 120,000 sample points: 182.5 s / 3.5 GB before, 61.4 s / 2.0 GB
  after, with identical output.


## [0.1.1] - 2026-05-21
### Fixed
- Intermittent `QgsVectorLayer`/`QVariant` type error in QGIS 4.0 (PyQt6). `processing.run()` parameter dicts no longer pass `QgsVectorLayer` objects directly: memory layer outputs are registered in the context temporary store and referenced by ID, and input layers are passed as their original parameter values. This avoids the non-deterministic SIP failure converting a Python dict to `QVariantMap`.

## [0.1.0] - 2026-04-05
### Added
- Initial public release
- Processing algorithm: Harvest Accessibility (d1 straight-line distance to nearest forest road, d2 shortest network path to nearest landing)
- Support for multiple landing points (minimum d2 per grid point)
- Sample data GeoPackage (EPSG:6676) with operation area, forest roads, and landings
- Grid-based sampling with configurable spacing and network snapping tolerance

[0.2.0]: https://github.com/takeshihoshikawa/harvest-accessibility-qgis/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/takeshihoshikawa/harvest-accessibility-qgis/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/takeshihoshikawa/harvest-accessibility-qgis/releases/tag/v0.1.0
