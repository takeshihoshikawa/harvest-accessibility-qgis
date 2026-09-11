# Harvest Accessibility — QGIS Plugin

A QGIS Processing plugin for forestry operations that computes harvest accessibility
using a two-stage distance model: straight-line skidding distance to the nearest forest
road (d1) and shortest network path along the road to the nearest landing point (d2).

## What It Does

Given an operation area polygon, a forest road network, and one or more landing points,
the plugin places a regular grid of sample points across the area and computes:

- **d1** — straight-line (skidding) distance from each sample point to the nearest forest road
- **d2** — shortest network path along the road from the road snap point to the nearest landing

Summary statistics (mean d1, mean d2) are reported in an HTML result report.

Two optional inputs change what is measured:

- Supply **individual tree points** (e.g. from ALS) and they are used as the sample points
  instead of the grid. Extraction distance is a per-tree quantity, so real stem positions beat
  a regular lattice, and stand density is reflected instead of being averaged away.
- Supply a **DEM** — or let the algorithm download one — and d1 switches from the standing tree
  to the felled stem: the tree is felled in a permitted direction and the near end (top or butt)
  is winched, so d1 becomes the distance from the road to that end.
  See [Felling model](#felling-model).

## Requirements

- QGIS 3.22 or later
- Input layers must use a **projected CRS in metres** (e.g. EPSG:6676 for Japan)

## Installation

1. Download the latest release ZIP from the [Releases](../../releases) page
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**
3. Select the downloaded ZIP and click **Install Plugin**
4. The algorithm appears in **Processing Toolbox → Harvest Accessibility**

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| Operation area (polygon) | Vector polygon | — | Harvest block boundary. Its CRS is the one everything else is brought into |
| Forest roads (lines; also the haul network) | Vector line | — | The same layer serves both the distance to the road (d1) and the route to the landing (d2) |
| Landings (points; more than one is fine) | Vector point | — | A landing away from the road is routed from the nearest point on it |
| Barriers (rivers, cliffs; lines or polygons) | Vector line/polygon | — | Optional. Neither a felled stem nor a haul may cross one |
| Keep felling and hauling inside the operation area | Boolean | off | Treats everything outside the block as a barrier. Strict: a road outside the boundary cannot be used either |
| Individual trees (points; measured tree by tree) | Vector point | — | Optional. Real stem positions are used in place of the lattice |
| Tree height (field of the tree layer) | Field | — | Optional. Falls back to the value below |
| Tree height (m, when no field is given) | Float | 20.0 | Applied to every tree |

Inputs in a different CRS to the operation area are reprojected, with a warning.

Advanced parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| Gap bridged in the road network (m) | Float | 2.0 | How wide a gap between road lines may be treated as connected. Only that — landings no longer depend on it |
| Tree spacing (m) | Float | 10.0 | Spacing of the lattice, when no tree points are given |
| DEM download | Enum | Auto | Auto tries each source finest first. If none covers the area the run continues without the felling model |
| DEM file (used instead of downloading) | Raster | — | Optional. For a block outside the tile coverage, or a machine with no network |
| Felling sector half-angle (deg) | Float | 105.0 | Directions allowed, measured from straight downslope |
| Slope allowing any direction (deg) | Float | 10.0 | At or below this slope the tree can be felled any way |
| Direct grapple reach (m) | Float | 3.0 | Within this distance of the road nothing is winched |
| Slope/aspect smoothing window (m) | Float | 5.0 | Cell size the DEM is resampled to before slope and aspect |
| Candidate roads per sample point | Integer | 10 | How many nearby roads are considered |
| Maximum sample points | Integer | 200000 | Stops before processing rather than running out of memory part way. Memory is roughly 0.42 GB plus 13 KB per sample point. 0 disables the check |
| Split roads at intersections | Boolean | True | Split road lines at intersections before routing |

## Outputs

| Output | Description |
|--------|-------------|
| Result report (HTML) | Mean d1 and d2, sample point count, unreachable point count |
| Sample points with distances | One point per tree or grid node: `d1`, `d2`, `d_total`, the landing it feeds, and — with the felling model — the felling azimuth and stem reach |
| Hauling lines | From the end that gets grabbed to the point on the road. Only where something is actually winched |
| Felled stems | Butt to top, as felled. Needs the felling model |

The map layers are optional — leave a field empty and that layer is not produced. They are
styled as they load: distances are graduated, and zero gets its own class, because with a third
of the points at zero folding them into the ramp flattens everything else.

On a grid the stems are hypothetical trees at each node, and at 4 m spacing 20 m stems overlap
into a solid mass. They are meant for real tree points.

Enable **Debug mode** (Advanced parameters) to also load intermediate layers into the project:
`debug_p1_grid`, `debug_p2_road_snap`, `debug_routes`, `debug_summary`

## Felling model

With a DEM supplied, d1 stops being a purely geometric quantity and becomes a model of the
work. The tree is felled, and the end nearest the road is what gets pulled.

- Felling is allowed within a sector centred on straight downslope (default ±105°). On gentle
  ground (default ≤10°) any direction is allowed.
- The stem's **horizontal** reach is `L·cos(slope in the felling direction)`, so felling across
  the contour reaches further horizontally than felling straight down a steep face.
- Blocking the road is accepted: if the stem reaches the road, d1 is 0 and the haul starts at
  the crossing point.
- A direction whose stem would cross a **barrier** is not available — a stem thrown over a
  river cannot be pulled back across it.
- Within grapple reach of the road, d1 is 0.

The report states the assumptions used (height, sector, grapple reach, smoothing) alongside
both the geometric and the modelled mean d1, because the model's numbers only mean something
next to the assumptions that produced them.

Direction choice clamps the bearing to the road into the allowed sector. That is exact for a
straight road and an approximation for a curved or branching network.

## Getting a DEM

The main algorithm fetches elevation itself by default: **DEM download** is set to *Auto*, which
tries each source finest first. Pick a named source to pin one, or *Do not download* to switch the
felling model off. If no source covers the area the run says so and continues without the model,
rather than failing — a machine in the field with no network still gets the geometric answer. The result is cached, so re-running while you tune
parameters does not download the same tiles again.

| Source | Resolution | Coverage |
|--------|-----------|----------|
| VIRTUAL SHIZUOKA | ~0.5 m | Shizuoka Prefecture |
| GSI DEM5A | ~4 m | Where surveyed |
| GSI DEM10B | ~8 m | Nationwide |

**Processing Toolbox → Harvest Accessibility → Fetch DEM from elevation tiles** writes the same
DEM to a file. Use it when the file itself is what you want: to reuse one DEM across runs or
projects, to inspect or edit it, or to prepare one for a machine with no network access.

Either way the DEM is reprojected out of web mercator first. This is not cosmetic — slope
computed on mercator pixels comes out roughly 20% too gentle at Japanese latitudes, and the
felling model branches on a slope threshold.

At this site the source resolution made little difference to the mean d1 (15.89 m / 15.90 m /
15.99 m for ~0.5 m / ~4 m / ~8 m), because the smoothing window coarsens the DEM anyway. It
moved the count of stems reaching the road by about 8%, so it matters per tree more than in
aggregate.

Tiles are served by 産業技術総合研究所 シームレス標高タイル, carrying 静岡県 VIRTUAL SHIZUOKA
(CC BY 4.0) and 国土地理院 基盤地図情報数値標高モデル. Credit the source when publishing
results.

## Sample Data

The `data/sample/` directory contains sample files in EPSG:6676 (JGD2011 Japan Plane Rectangular CS VIII):

- `operation_area.geojson` — harvest block polygon
- `forest_roads.geojson` — connected road network (one segment intentionally disconnected to demonstrate NULL d2)
- `landings.geojson` — multiple landing points
- `avg_extraction_sample.gpkg` — GeoPackage with all of the above

The defaults suit it: tree spacing 10 m, gap bridged 2 m. The third landing is deliberately off the network, so some points come back with `d2 = NULL`.

## Notes

- Points with `d2 = NULL` could not be routed to any landing, which usually means a break in the
  road network. The gap tolerance is not a threshold — the count of unroutable points moves around
  with it, because it decides how a point ties into the routing graph — so the run retries at a few
  nearby values on its own and reports the one it used. If points remain, check the network itself.
- Points with `d1 = NULL` cannot be extracted at all: no felling direction leaves a stem that can be
  pulled to a road it can reach. They are left out of both means and counted in the report.
- The algorithm iterates over all landing points and assigns each sample point the minimum d2,
  so multiple landings are handled correctly.

## Contributing

This repository is a read-only snapshot published from a private development repository.
Each release is exported as a single commit, so it carries no development history and
**pull requests cannot be merged** — any commit pushed here is replaced by the next release.

Bug reports and feature requests are very welcome: please open an
[issue](https://github.com/takeshihoshikawa/harvest-accessibility-qgis/issues).

## License

GPL-3.0 — see [LICENSE](LICENSE)

## Author

Takeshi Hoshikawa — hoshikawa.takeshi@spua.ac.jp
