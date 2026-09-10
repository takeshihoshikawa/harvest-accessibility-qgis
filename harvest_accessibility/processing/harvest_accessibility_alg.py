import os
import tempfile

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingException,
    QgsProcessingOutputHtml,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsFeature,
    QgsFields,
    QgsField,
    QgsUnitTypes,
    QgsWkbTypes
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis import processing


class HarvestAccessibilityAlg(QgsProcessingAlgorithm):
    POLY = "POLY"
    ROADS = "ROADS"
    LANDING = "LANDING"
    GRID = "GRID"
    SNAP_TOL = "SNAP_TOL"
    HTML_OUT = "HTML_OUT"
    DEBUG = "DEBUG"
    SPLIT_ROADS = "SPLIT_ROADS"

    def tr(self, string):
        return QCoreApplication.translate("HarvestAccessibilityAlg", string)

    def name(self):
        return "harvest_accessibility"

    def displayName(self):
        return self.tr("Harvest Accessibility")

    def group(self):
        return self.tr("Harvest Accessibility")

    def groupId(self):
        return "harvest_accessibility"

    def shortHelpString(self):
        return self.tr(
            "Inputs: operation polygon, forest road lines (also used as network), "
            "landing points (multiple OK).\n"
            "1) Create grid points within polygon (p1)\n"
            "2) Shortest straight line to road -> d1, endpoint on road -> p2\n"
            "3) Shortest path on road network from p2 to the nearest landing -> d2 (NULL if unreachable)\n"
            "4) HTML result report.\n"
            "NOTE: Use a projected CRS in metres.\n\n"
            "Advanced: enable debug mode to load intermediate layers into the project."
        )

    def createInstance(self):
        return HarvestAccessibilityAlg()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POLY,
            self.tr("Operation area polygon"),
            [QgsProcessing.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.ROADS,
            self.tr("Forest road lines (also network)"),
            [QgsProcessing.TypeVectorLine]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LANDING,
            self.tr("Landing points (multiple OK)"),
            [QgsProcessing.TypeVectorPoint]
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.GRID,
            self.tr("Grid spacing (m)"),
            QgsProcessingParameterNumber.Double,
            defaultValue=4.0,
            minValue=0.1
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.SNAP_TOL,
            self.tr("Network snapping tolerance (m)"),
            QgsProcessingParameterNumber.Double,
            defaultValue=5.0,
            minValue=0.0
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.SPLIT_ROADS,
            self.tr("Split roads at intersections before routing"),
            defaultValue=True
        ))

        self.addOutput(QgsProcessingOutputHtml(self.HTML_OUT, self.tr("Result report")))

        debug_param = QgsProcessingParameterBoolean(
            self.DEBUG,
            self.tr("Debug mode (add intermediate layers to project)"),
            defaultValue=False
        )
        debug_param.setFlags(
            debug_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(debug_param)

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback):
        poly = self.parameterAsSource(parameters, self.POLY, context)
        roads = self.parameterAsSource(parameters, self.ROADS, context)
        landing = self.parameterAsSource(parameters, self.LANDING, context)
        grid = float(self.parameterAsDouble(parameters, self.GRID, context))
        snap_tol = float(self.parameterAsDouble(parameters, self.SNAP_TOL, context))
        split_roads = self.parameterAsBool(parameters, self.SPLIT_ROADS, context)
        debug = self.parameterAsBool(parameters, self.DEBUG, context)

        if poly is None or roads is None or landing is None:
            raise QgsProcessingException(self.tr("Invalid input layers."))

        if poly.featureCount() == 0:
            raise QgsProcessingException(self.tr("Operation area polygon has no features."))
        if roads.featureCount() == 0:
            raise QgsProcessingException(self.tr("Forest roads layer has no features."))

        crs = poly.sourceCrs()
        if crs.isGeographic():
            raise QgsProcessingException(self.tr(
                "Polygon CRS is geographic (degrees). Reproject to a projected CRS in metres."
            ))

        if crs.mapUnits() != QgsUnitTypes.DistanceMeters:
            unit_name = QgsUnitTypes.encodeUnit(crs.mapUnits())
            raise QgsProcessingException(self.tr(
                "Polygon CRS unit is '{}', not metres. "
                "Grid spacing and distances will be incorrect. Reproject to a metric CRS."
            ).format(unit_name))

        roads_crs = roads.sourceCrs()
        landing_crs = landing.sourceCrs()
        if roads_crs != crs:
            raise QgsProcessingException(self.tr(
                "Road layer CRS ({}) differs from polygon CRS ({}). "
                "Reproject all layers to the same CRS."
            ).format(roads_crs.authid(), crs.authid()))
        if landing_crs != crs:
            raise QgsProcessingException(self.tr(
                "Landing layer CRS ({}) differs from polygon CRS ({}). "
                "Reproject all layers to the same CRS."
            ).format(landing_crs.authid(), crs.authid()))

        try:
            # 1) Create grid points and clip to polygon
            feedback.pushInfo(self.tr("1) Creating grid points (p1)..."))
            grid_layer = processing.run(
                "native:creategrid",
                {
                    "TYPE": 0,  # point
                    "EXTENT": poly.sourceExtent(),
                    "HSPACING": grid,
                    "VSPACING": grid,
                    "HOVERLAY": 0,
                    "VOVERLAY": 0,
                    "CRS": crs,
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            p1 = processing.run(
                "native:extractbylocation",
                {
                    "INPUT": grid_layer,
                    "PREDICATE": [0],  # intersects
                    "INTERSECT": self.parameterAsLayer(parameters, self.POLY, context),
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            if p1.featureCount() == 0:
                raise QgsProcessingException(self.tr(
                    "No grid points fall within the operation polygon. "
                    "Try a smaller grid spacing."
                ))

            p1 = processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": p1,
                    "FIELD_NAME": "tree_id",
                    "FIELD_TYPE": 1,  # int
                    "FIELD_LENGTH": 10,
                    "FIELD_PRECISION": 0,
                    "FORMULA": "@row_number",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            # 2) Shortest line to roads -> d1, nearest point on road -> p2
            feedback.pushInfo(self.tr("2) Computing shortest lines to roads (d1) and nearest points (p2)..."))
            shortest_lines = processing.run(
                "native:shortestline",
                {
                    "SOURCE": p1,
                    "DESTINATION": self.parameterAsLayer(parameters, self.ROADS, context),
                    "METHOD": 0,
                    "NEIGHBORS": 1,
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            shortest_lines = processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": shortest_lines,
                    "FIELD_NAME": "d1",
                    "FIELD_TYPE": 0,  # float
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "FORMULA": "$length",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            p2 = processing.run(
                "native:extractspecificvertices",
                {
                    "INPUT": shortest_lines,
                    "VERTICES": "-1",  # last vertex = nearest point on road
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            # 3) Shortest path to nearest landing along road network
            # NOTE: QGIS 'native:shortestpathpointtolayer' expects a SINGLE START_POINT (coordinate),
            # so for multiple start points we use 'native:shortestpathlayertopoint' and run it
            # for each landing, then take the minimum cost per start point.
            feedback.pushInfo(self.tr("3) Computing shortest path along road network to nearest landing (d2)..."))

            landing_layer = self.parameterAsLayer(parameters, self.LANDING, context)
            if landing_layer.featureCount() == 0:
                raise QgsProcessingException(self.tr("Landing layer has no features."))

            roads_layer = self.parameterAsLayer(parameters, self.ROADS, context)
            if split_roads:
                feedback.pushInfo(self.tr("3a) Splitting roads at intersections..."))
                roads_layer = processing.run(
                    "native:splitwithlines",
                    {
                        "INPUT": roads_layer,
                        "LINES": roads_layer,
                        "OUTPUT": "memory:"
                    },
                    context=context, feedback=feedback
                )["OUTPUT"]
                feedback.pushInfo(self.tr("    -> {} segments after split.").format(roads_layer.featureCount()))

            routes_list = []
            authid = crs.authid()

            for lf in landing_layer.getFeatures():
                if feedback.isCanceled():
                    raise QgsProcessingException(self.tr("Processing cancelled by user."))
                geom = lf.geometry()
                if geom is None or geom.isEmpty():
                    continue
                pt = geom.asPoint()
                end_point = f"{pt.x()},{pt.y()} [{authid}]"

                out = processing.run(
                    "native:shortestpathlayertopoint",
                    {
                        "INPUT": roads_layer,
                        "START_POINTS": p2,
                        "END_POINT": end_point,
                        "STRATEGY": 0,  # shortest distance
                        "DEFAULT_DIRECTION": 2,
                        "TOLERANCE": snap_tol,
                        "OUTPUT": "memory:",
                        "OUTPUT_NON_ROUTABLE": "memory:"
                    },
                    context=context, feedback=feedback
                )

                r = out["OUTPUT"]
                r = processing.run(
                    "native:fieldcalculator",
                    {
                        "INPUT": r,
                        "FIELD_NAME": "landing_fid",
                        "FIELD_TYPE": 1,  # int
                        "FIELD_LENGTH": 20,
                        "FIELD_PRECISION": 0,
                        "FORMULA": str(lf.id()),
                        "OUTPUT": "memory:"
                    },
                    context=context, feedback=feedback
                )["OUTPUT"]

                routes_list.append(r)

            if not routes_list:
                raise QgsProcessingException(self.tr(
                    "No valid landing points were found (all geometries empty?)."
                ))

            merged_routes = processing.run(
                "native:mergevectorlayers",
                {"LAYERS": routes_list, "CRS": crs, "OUTPUT": "memory:"},
                context=context, feedback=feedback
            )["OUTPUT"]

            cost_field = "cost" if merged_routes.fields().indexFromName("cost") != -1 else None
            if cost_field is None:
                feedback.pushInfo(self.tr(
                    "Note: routing output has no 'cost' field; using geometry length for d2."
                ))
            routes = processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": merged_routes,
                    "FIELD_NAME": "d2",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "FORMULA": f"\"{cost_field}\"" if cost_field else "$length",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            if routes.fields().indexFromName("tree_id") == -1:
                raise QgsProcessingException(self.tr(
                    "Routing output has no 'tree_id' field. Ensure p2 has 'tree_id' attribute."
                ))

            routes = processing.run(
                "native:extractbyexpression",
                {"INPUT": routes, "EXPRESSION": "\"d2\" IS NOT NULL", "OUTPUT": "memory:"},
                context=context, feedback=feedback
            )["OUTPUT"]

            if routes.featureCount() == 0:
                raise QgsProcessingException(self.tr(
                    "All grid points are unreachable from all landings. "
                    "Check that the road network is connected, "
                    "landing points are on or near the road, "
                    "and the snapping tolerance is sufficient."
                ))

            stats = processing.run(
                "qgis:statisticsbycategories",
                {
                    "INPUT": routes,
                    "CATEGORIES_FIELD_NAME": ["tree_id"],
                    "VALUES_FIELD_NAME": "d2",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            if stats.fields().indexFromName("min") == -1:
                raise QgsProcessingException(self.tr("Unexpected statistics output (no 'min' field)."))

            p2_tmp = processing.run(
                "native:joinattributestable",
                {
                    "INPUT": p2,
                    "FIELD": "tree_id",
                    "INPUT_2": stats,
                    "FIELD_2": "tree_id",
                    "FIELDS_TO_COPY": ["min"],
                    "METHOD": 1,
                    "DISCARD_NONMATCHING": False,
                    "PREFIX": "",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            p2_with = processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": p2_tmp,
                    "FIELD_NAME": "d2",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "FORMULA": "\"min\"",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"]

            # 4) Summary statistics
            feedback.pushInfo(self.tr("4) Computing summary statistics..."))
            d1_vals, d2_vals = [], []
            null_d2 = 0
            total = 0
            field_names = p2_with.fields().names()

            for f in p2_with.getFeatures():
                total += 1
                if f["d1"] is not None:
                    d1_vals.append(float(f["d1"]))
                d2 = f["d2"] if "d2" in field_names else None
                if d2 is None:
                    null_d2 += 1
                else:
                    d2_vals.append(float(d2))

            d1_mean = (sum(d1_vals) / len(d1_vals)) if d1_vals else None
            d2_mean = (sum(d2_vals) / len(d2_vals)) if d2_vals else None

            if d2_mean is None:
                feedback.reportError(self.tr(
                    "WARNING: d2_mean is None — no grid points could be routed to any landing. "
                    "Check that the road network is connected and the snapping tolerance is sufficient."
                ), fatalError=False)

            def fmt(val, unit="m"):
                return f"{val:.1f} {unit}" if val is not None else "N/A"

            html_path = os.path.join(
                tempfile.gettempdir(),
                f"harvest_accessibility_{os.getpid()}.html"
            )
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; margin: 2em; color: #333; }}
  h2 {{ color: #2e6b2e; }}
  table {{ border-collapse: collapse; margin-top: 1em; }}
  td {{ padding: 0.5em 1.2em 0.5em 0; }}
  .val {{ font-size: 1.6em; font-weight: bold; color: #2e6b2e; }}
  .label {{ color: #555; font-size: 0.9em; }}
  .note {{ color: #888; font-size: 0.85em; margin-top: 1.5em; }}
</style>
</head>
<body>
<h2>Harvest Accessibility — Result</h2>
<table>
  <tr>
    <td><span class="label">平均木寄せ距離 (d1)</span><br>
        <span class="val">{fmt(d1_mean)}</span></td>
    <td><span class="label">平均運材距離 (d2)</span><br>
        <span class="val">{fmt(d2_mean)}</span></td>
  </tr>
</table>
<p class="note">
  サンプル点数: {total} 点 ／ d2 未到達: {null_d2} 点
  {"<br><b style='color:#c00'>⚠ 全点が土場に到達できませんでした。林道の接続とスナップ許容誤差を確認してください。</b>" if d2_mean is None else ""}
</p>
</body>
</html>""")

            feedback.pushInfo(
                f"Done. d1_mean={d1_mean:.3f}m, d2_mean={d2_mean:.3f}m, "
                f"points={total}, d2_null={null_d2}"
                if d1_mean is not None and d2_mean is not None
                else f"Done. d1_mean={d1_mean}, d2_mean={d2_mean}, points={total}, d2_null={null_d2}"
            )

            if debug:
                project = context.project()
                if project is not None:
                    for layer, name in [
                        (p1,      "debug_p1_grid"),
                        (p2_with, "debug_p2_road_snap"),
                        (routes,  "debug_routes"),
                    ]:
                        context.addLayerToLoadOnCompletion(
                            layer.id(),
                            QgsProcessingContext.LayerDetails(name, project)
                        )

                    summary_fields = QgsFields()
                    summary_fields.append(QgsField("n_points", QVariant.Int))
                    summary_fields.append(QgsField("n_d2_null", QVariant.Int))
                    summary_fields.append(QgsField("d1_mean", QVariant.Double))
                    summary_fields.append(QgsField("d2_mean", QVariant.Double))
                    from qgis.core import QgsVectorLayer, QgsProject
                    summary_layer = QgsVectorLayer("NoGeometry", "debug_summary", "memory")
                    summary_layer.dataProvider().addAttributes(summary_fields.toList())
                    summary_layer.updateFields()
                    sf = QgsFeature(summary_layer.fields())
                    sf["n_points"] = total
                    sf["n_d2_null"] = null_d2
                    sf["d1_mean"] = d1_mean
                    sf["d2_mean"] = d2_mean
                    summary_layer.dataProvider().addFeatures([sf])
                    QgsProject.instance().addMapLayer(summary_layer)
                else:
                    feedback.pushInfo(self.tr("Debug: no project context, skipping layer output."))

            return {self.HTML_OUT: html_path}

        except QgsProcessingException:
            raise
        except Exception as e:
            raise QgsProcessingException(
                self.tr("Unexpected error during processing: {}").format(e)
            ) from e
