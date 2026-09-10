Sample data for Average Extraction Distance plugin

CRS: EPSG:6676 (meters; JGD2011 / Japan Plane Rectangular CS IX)
Layers in GeoPackage (avg_extraction_sample.gpkg):
- operation_area (polygon)
- forest_roads (lines) - connected network with two landings; third landing is nearby but not connected (for NULL testing)
- landings (points) - multiple landings

Suggested plugin parameters:
- Grid spacing: 4
- Snapping tolerance: 5 (or 10 if needed)

Tip:
- After running, check p2 layer for d2=NULL points (unreachable from the road network).
