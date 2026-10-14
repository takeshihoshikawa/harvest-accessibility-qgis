Sample data for the Harvest Accessibility plugin (synthetic)

CRS: EPSG:6676 (JGD2011 / Japan Plane Rectangular CS VIII)

The same three layers are provided as GeoJSON files and in one GeoPackage
(avg_extraction_sample.gpkg):
- operation_area (polygon) - a 400 m x 300 m harvest block
- forest_roads (lines) - six roads forming one connected network
- landings (points) - three landings, A, B and C, each off the road: A and B
  by 10 m, C by 60 m. Each is reached from the nearest point on the road;
  C shows how far that can be.

Suggested plugin parameters:
- The defaults suit this data (tree spacing 10 m, gap bridged 2 m).

After running:
- "Sample points with distances" has d1, d2 and the landing each point feeds.
  Every point reaches a landing, so d2 is never empty with this data.
