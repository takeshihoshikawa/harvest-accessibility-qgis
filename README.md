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
| Operation area polygon | Vector polygon | — | Harvest block boundary |
| Forest road lines (also network) | Vector line | — | Road network used for both d1 snapping and d2 routing |
| Landing points | Vector point | — | One or more log landing locations |
| Grid spacing (m) | Float | 4.0 | Spacing of the sample grid in metres |
| Network snapping tolerance (m) | Float | 5.0 | Tolerance for snapping start points onto the road network |
| Split roads at intersections | Boolean | True | Split road lines at intersections before routing for better connectivity |

## Outputs

| Output | Description |
|--------|-------------|
| Result report (HTML) | Mean d1 and d2, sample point count, unreachable point count |

Enable **Debug mode** (Advanced parameters) to also load intermediate layers into the project:
`debug_p1_grid`, `debug_p2_road_snap`, `debug_routes`, `debug_summary`

## Sample Data

The `sample_data/` directory contains sample files in EPSG:6676 (JGD2011 Japan Plane Rectangular CS IX):

- `operation_area.geojson` — harvest block polygon
- `forest_roads.geojson` — connected road network (one segment intentionally disconnected to demonstrate NULL d2)
- `landings.geojson` — multiple landing points
- `avg_extraction_sample.gpkg` — GeoPackage with all of the above

Suggested parameters: grid spacing = 4 m, snapping tolerance = 5 m.

## Notes

- Points with `d2 = NULL` could not be routed to any landing. This typically means the snap
  point lies on a disconnected road segment. Increase snapping tolerance or check road network
  connectivity.
- The algorithm iterates over all landing points and assigns each sample point the minimum d2,
  so multiple landings are handled correctly.

## License

GPL-3.0 — see [LICENSE](LICENSE)

## Author

Takeshi Hoshikawa — hoshikawa.takeshi@spua.ac.jp
