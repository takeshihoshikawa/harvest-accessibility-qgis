# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.0] - 2026-10-14
### Added
- **Maximum yarding distance**, as a slope distance (default 0 = no limit). Trees beyond it are
  out of range: they are kept in the per-tree layer with `in_range = 0`, left out of the means,
  and counted apart in the report. Asked for after field use of 0.2.0.
- **Trees beyond the yarding limit are marked on the map.** In the per-tree layer they are blue
  (#4575b4, apart from the grey of d1 = 0) under "集材範囲外" and no longer stretch the colour classes of the rest; they get no stem or haul
  line. The rows stay in the layer with `in_range = 0`, so the report's out-of-range row can be
  traced to them.
- **Largest d1 and d2** under the means in the report, over the same trees as the means.
- **`d1_slope`**, d1 along the ground, from the height difference of the grabbed end and the road
  point. Reported next to the horizontal mean. The heights are interpolated from the four
  surrounding DEM cells: the cell a point falls in can be half a cell out, which on a 4 m DEM and
  a 30° face is over a metre.
- **Volume per landing.** Given a volume field on the tree points, the report totals volume and
  trees per landing, with out-of-range, unreachable and unextractable trees in rows of their own
  so that the rows add up to the block. Without a volume field the table shows tree counts.

### Changed
- **d2 is computed by the plugin's own network search**, not QGIS's routing algorithm, and a
  tree's d2 now depends on that tree alone. QGIS tied all the start points into the network
  together, merging those within the gap tolerance of each other, so the answer depended on which
  other trees were in the run: neighbouring trees came out with identical values, and the answer
  moved with the set of points. The network is now built from the roads alone and searched once
  per landing, and each tree is read off from where it lies on a segment. Checked against QGIS
  routing run one tree at a time on a surveyed block: within 3 cm.
  **The mean d2 moves against 0.2.0:** on a surveyed block with individual trees from 935.6 m to
  939.2 m (+0.4%), on the same block with a lattice by under 0.1 m; on the sample data from
  between 181.5 and 181.9 m (it varied from run to run) to 151.0 m, because many lattice points
  there share a foot on the road. Runs are also 4–5 times faster (120,000 points: 84 s → 15 s).
- **The gap tolerance only joins different lines.** QGIS also merged vertices of the same line
  that were closer than the tolerance, dropping the length between them.
- **Maximum sample points** defaults to 250,000 (was 200,000), and the memory estimate in the
  log is re-measured: about 0.39 GB plus 11.5 KB per point with the felling model on and every
  output written, the heaviest case; about 8.7 KB without the felling model. The old figure,
  13 KB, was measured with the felling model off and QGIS's routing. The limit keeps roughly the
  same memory budget as before, about 3.3 GB at the default, so it rises only a little.
- The retry at a wider gap tolerance is gone. It existed because the number of unroutable points
  jumped about with the tolerance, which was the tie-in behaviour above.
- **Both algorithms sit in one group** in the Processing Toolbox. They had different group ids
  under the same name.
- **The operation area no longer has to be in a metric CRS** (#2). Distances are measured in the
  CRS of the first input that is projected in metres — operation area, forest roads, landings,
  tree points, barriers, in that order — and everything else, the operation area included, is
  reprojected into it with a warning. No CRS is derived: the answer is always in one some input
  carries. Only when no input qualifies does the run stop.
- **Fetch DEM** takes an optional **DEM CRS**. An operation area in degrees no longer stops it:
  choose a metric CRS and the DEM is written in that. Left empty, the area's own CRS is used as
  before, and a CRS that is not in metres is still refused, now with a message saying what to set.

### Fixed
- **Large tree layers in another CRS no longer exhaust memory.** Tree points in a CRS other than
  the one distances are measured in were reprojected whole before being clipped to the area. A
  prefecture's published single-tree layer (9.35 million points) would have taken about 8–9 GB.
  They are now cut to the area first, in their own CRS, and only those points reprojected: the
  same layer given whole runs in 0.7 s and 0.66 GB, with the same answer as a pre-clipped copy.
- **"Selected features only" on the road layer works with the felling model.** With a DEM and the
  box ticked, the run stopped with an error (`'NoneType' object has no attribute 'getFeatures'`,
  reproduced headless); the road layer was looked up in a way that does not accept a selection.
  The felling model and the placing of landings now use the selected roads, as routing did.
- **The same input gives the same answer on every run.** A sample point exactly as far from two
  roads got a shortest line to each, and the one kept was whichever came first -- which changed
  from run to run, and d2 with it (on the sample data, 99 m by one road and 299 m by the other).
  Every tied foot is now routed and the shorter haul is kept.
- **The sample GeoPackage matches the GeoJSON files.** It had four roads and one landing, against
  six and three. Its description, and the sample README, said some points would have no d2; none
  do, since landings are reached from the nearest point on the road.

### Removed
- **Number of candidate roads per sample point** (advanced). It was read and never used: the
  distance to the road has always been measured to the single nearest road, whatever it was set
  to. Saved models and scripts that still pass it run as before.

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

[0.3.0]: https://github.com/takeshihoshikawa/harvest-accessibility-qgis/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/takeshihoshikawa/harvest-accessibility-qgis/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/takeshihoshikawa/harvest-accessibility-qgis/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/takeshihoshikawa/harvest-accessibility-qgis/releases/tag/v0.1.0
