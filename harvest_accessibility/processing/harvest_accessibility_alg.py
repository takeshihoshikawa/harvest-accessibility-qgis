import math
import os
import tempfile

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterFeatureSink,
    QgsProcessingLayerPostProcessorInterface,
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
    QgsWkbTypes,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
    QgsFeatureRequest,
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import QgsRasterLayer, QgsCoordinateReferenceSystem, \
    QgsCoordinateTransform, QgsProject, QgsRectangle, \
    QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol, QgsClassificationRange, \
    QgsSingleSymbolRenderer
from qgis.PyQt.QtGui import QColor
from qgis import processing

from . import network, tiles


def _azimuth(dx, dy):
    """Azimuth in degrees, clockwise from north."""
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _angle_diff(a, b):
    """Smallest signed difference a - b, in [-180, 180)."""
    return (a - b + 180.0) % 360.0 - 180.0


def _slope_along(slope_deg, phi_deg):
    """Ground slope in a direction phi degrees away from steepest descent.

    tan(theta_dir) = tan(theta_max) * cos(phi):  straight downslope keeps the
    full slope, across-slope (phi = 90) is level.
    """
    return math.degrees(math.atan(
        math.tan(math.radians(slope_deg)) * math.cos(math.radians(phi_deg))
    ))


def _candidate_directions(target_az, aspect_deg, slope_deg, sector, flat_slope):
    """Felling directions to try, best first.

    On gentle ground any direction is allowed, so aiming at the road is optimal.
    On steeper ground the direction is clamped into the sector centred on
    downslope.  The clamp is exact for a straight road; for a curved or branching
    network it is an approximation -- the direction that truly minimises the
    distance from the stem's near end to the road need not be the clamped
    bearing.  Both sector edges are offered as fallbacks so that a barrier can
    reject the first choice without losing the point.
    """
    if slope_deg <= flat_slope or abs(_angle_diff(target_az, aspect_deg)) <= sector:
        cands = [target_az]
    else:
        cands = []
    edges = [(aspect_deg + sector) % 360.0, (aspect_deg - sector) % 360.0]
    edges.sort(key=lambda az: abs(_angle_diff(target_az, az)))
    cands.extend(edges)
    cands.append(aspect_deg)  # straight downslope: always allowed by the sector
    seen, out = set(), []
    for az in cands:
        key = round(az, 3)
        if key not in seen:
            seen.add(key)
            out.append(az)
    return out


class _QuietFeedback(QgsProcessingFeedback):
    """Feedback for nested algorithms whose per-feature complaints are noise.

    The attribute join reports every point that found no landing, and the
    clip warns that the lattice has no spatial index.  On a real block that is
    thousands of lines in the log for conditions the run already summarises or
    that do not matter, and it makes a successful run look like a failed one.
    The facts still reach the user, as one line from the caller.

    Cancellation and progress are forwarded through signals rather than by
    overriding, because QgsFeedback::isCanceled and setProgress are not virtual.
    """

    def __init__(self, parent):
        super().__init__()
        self._parent = parent
        self.n_suppressed = 0
        parent.canceled.connect(self.cancel)
        self.progressChanged.connect(parent.setProgress)

    def reportError(self, error, fatalError=False):
        self.n_suppressed += 1

    def pushWarning(self, warning):
        self.n_suppressed += 1

    def pushInfo(self, info):
        pass

    def pushDebugInfo(self, info):
        pass

    def setProgressText(self, text):
        pass


class _D1Styler(QgsProcessingLayerPostProcessorInterface):
    """Graduate the loaded layer by d1, keeping zero as its own class."""

    keep = []

    def postProcessLayer(self, layer, context, feedback=None):
        try:
            # Trees beyond the yarding limit are grey and left out of the
            # ramp: their distances are not this system's work, and letting
            # them set the class breaks would flatten the colours of the rest.
            has_range = layer.fields().indexOf("in_range") >= 0
            n_out = 0
            vals = set()
            for feat in layer.getFeatures():
                if feat["d1"] is None:
                    continue
                if has_range and feat["in_range"] == 0:
                    n_out += 1
                    continue
                vals.add(float(feat["d1"]))
            values = sorted(vals)
            positive = [v for v in values if v > 0]
            if not positive:
                return
            ranges = []
            geom_type = layer.geometryType()

            def symbol(color, width=None):
                sym = QgsSymbol.defaultSymbol(geom_type)
                sym.setColor(QColor(color))
                if width is not None:
                    try:
                        sym.setWidth(width)
                    except AttributeError:
                        pass
                return sym

            if n_out:
                ranges.append(QgsRendererRange(
                    QgsClassificationRange("集材範囲外", -1.5, -0.5),
                    symbol("#4575b4", 0.3)))

            if values and values[0] <= 0:
                ranges.append(QgsRendererRange(
                    QgsClassificationRange("0 m (no winching)", -0.001, 0.001),
                    symbol("#bdbdbd", 0.3)))

            colors = ["#fee08b", "#fdae61", "#f46d43", "#d73027", "#7f0000"]
            n = len(colors)
            lower = 0.001
            for i, color in enumerate(colors):
                upper = positive[min(len(positive) - 1,
                                     int(round((i + 1) / n * (len(positive) - 1))))]
                if upper <= lower and i < n - 1:
                    continue
                if i == n - 1:
                    upper = positive[-1]
                ranges.append(QgsRendererRange(
                    QgsClassificationRange(
                        "%.0f - %.0f m" % (max(lower, 0.0), upper), lower, upper),
                    symbol(color, 0.4)))
                lower = upper
            if ranges:
                attr = ('CASE WHEN "in_range" = 0 THEN -1 ELSE "d1" END'
                        if n_out else "d1")
                layer.setRenderer(QgsGraduatedSymbolRenderer(attr, ranges))
                layer.triggerRepaint()
        except Exception:
            # Styling is a convenience; never let it fail the run.
            pass


class _HaulingStyler(QgsProcessingLayerPostProcessorInterface):
    """Thin translucent grey.

    One haul line per tree covers the map, and the distance each one stands for
    is already the colour of its point in the tree layer, so the lines should
    read as background rather than compete with it.
    """

    keep = []

    def postProcessLayer(self, layer, context, feedback=None):
        try:
            sym = QgsSymbol.defaultSymbol(layer.geometryType())
            sym.setColor(QColor(110, 110, 110, 90))
            try:
                sym.setWidth(0.15)
            except AttributeError:
                pass
            layer.setRenderer(QgsSingleSymbolRenderer(sym))
            layer.triggerRepaint()
        except Exception:
            # Styling is a convenience; never let it fail the run.
            pass


class HarvestAccessibilityAlg(QgsProcessingAlgorithm):
    POLY = "POLY"
    ROADS = "ROADS"
    LANDING = "LANDING"
    GRID = "GRID"
    SNAP_TOL = "SNAP_TOL"
    HTML_OUT = "HTML_OUT"
    OUT_TREES = "OUT_TREES"
    OUT_STEMS = "OUT_STEMS"
    OUT_HAULING = "OUT_HAULING"
    SPLIT_ROADS = "SPLIT_ROADS"
    # Felling model (all optional; absent inputs keep the plain geometric behaviour)
    DEM = "DEM"
    AUTO_DEM = "AUTO_DEM"
    TREES = "TREES"
    HEIGHT_FIELD = "HEIGHT_FIELD"
    TREE_HEIGHT = "TREE_HEIGHT"
    BARRIERS = "BARRIERS"
    FELL_SECTOR = "FELL_SECTOR"
    FLAT_SLOPE = "FLAT_SLOPE"
    GRAPPLE_REACH = "GRAPPLE_REACH"
    ASPECT_SMOOTH = "ASPECT_SMOOTH"
    MAX_POINTS = "MAX_POINTS"
    AREA_ONLY = "AREA_ONLY"
    MAX_RANGE = "MAX_RANGE"
    VOLUME_FIELD = "VOLUME_FIELD"

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
            "The distance the wood is moved: from each felled tree to the "
            "forest road, and from there along the network to the nearest "
            "landing. Computed tree by tree and reported as averages.\n\n"
            "Give it the operation area, the roads and the landings. Tree "
            "positions are used where they exist; otherwise trees are placed on "
            "a lattice.\n\n"
            "A DEM is fetched automatically. The tree is felled in a direction "
            "the slope allows, and the distance to the road is measured from "
            "whichever end of the stem -- butt or top -- lies nearer to it.\n\n"
            "Setting barriers, and whether felling and hauling may leave the "
            "operation area, brings the answer closer to what the ground allows."
        )

    def createInstance(self):
        return HarvestAccessibilityAlg()

    def initAlgorithm(self, config=None):
        # QGIS lays parameters out in the order they are added and has no
        # grouping API -- the only collapsible section is "advanced".  So the
        # order is the grouping: the three layers the run cannot happen
        # without, what limits the work, what stands for the trees, the
        # network, the outputs, and the settings that are calibration rather
        # than per-site input.

        # --- What is being harvested, and to where -----------------------
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POLY,
            self.tr("Operation area (polygon)"),
            [QgsProcessing.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.ROADS,
            self.tr("Forest roads (lines; also the haul network)"),
            [QgsProcessing.TypeVectorLine]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LANDING,
            self.tr("Landings (points; more than one is fine)"),
            [QgsProcessing.TypeVectorPoint]
        ))

        # --- What the work may not cross ---------------------------------
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.BARRIERS,
            self.tr("Barriers (rivers, cliffs; lines or polygons)"),
            [QgsProcessing.TypeVectorLine, QgsProcessing.TypeVectorPolygon],
            optional=True
        ))
        # A site policy rather than a method constant: whether the work may
        # spill onto the neighbouring ground at all.  Strict -- a road outside
        # the boundary cannot be used either.
        self.addParameter(QgsProcessingParameterBoolean(
            self.AREA_ONLY,
            self.tr("Keep felling and hauling inside the operation area"),
            defaultValue=False
        ))
        # How far the machine can pull: a winch line or a swing yarder has a
        # length, and it is laid along the ground, so the limit is a slope
        # distance.  Trees beyond it are not extracted by this system; they are
        # counted apart rather than dropped.  0 keeps every tree in range.
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_RANGE,
            self.tr("Maximum yarding distance (slope distance, m; 0 = no limit)"),
            QgsProcessingParameterNumber.Double,
            defaultValue=0.0, minValue=0.0
        ))

        # --- What stands for the trees -----------------------------------
        # Real stem positions when they exist; otherwise a lattice at the
        # spacing set under the advanced parameters.  The height field belongs
        # to the tree points, so it has to follow them.
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.TREES,
            self.tr("Individual trees (points; measured tree by tree)"),
            [QgsProcessing.TypeVectorPoint],
            optional=True
        ))
        self.addParameter(QgsProcessingParameterField(
            self.HEIGHT_FIELD,
            self.tr("Tree height (field of the tree layer)"),
            parentLayerParameterName=self.TREES,
            type=QgsProcessingParameterField.Numeric,
            optional=True
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.TREE_HEIGHT,
            self.tr("Tree height (m, when no field is given)"),
            QgsProcessingParameterNumber.Double,
            defaultValue=20.0,
            minValue=0.0
        ))
        # Computed outside, by whatever volume equation suits the stand: the
        # choice of equation is a forestry decision, not this tool's.
        self.addParameter(QgsProcessingParameterField(
            self.VOLUME_FIELD,
            self.tr("Volume (field of the tree layer, m3 per tree)"),
            parentLayerParameterName=self.TREES,
            type=QgsProcessingParameterField.Numeric,
            optional=True
        ))

        # --- Outputs ------------------------------------------------------
        self.addOutput(QgsProcessingOutputHtml(self.HTML_OUT, self.tr("Result report")))

        # Map layers, not debug side effects: they are what a per-tree result
        # looks like, and they need to be saveable and styled.
        for sink, label, gtype in (
            (self.OUT_TREES, self.tr("Sample points with distances"),
             QgsProcessing.TypeVectorPoint),
            (self.OUT_HAULING, self.tr("Hauling lines (grabbed end to road)"),
             QgsProcessing.TypeVectorLine),
            (self.OUT_STEMS, self.tr("Felled stems (butt to top)"),
             QgsProcessing.TypeVectorLine),
        ):
            # createByDefault: the layers appear as temporary layers without
            # anyone filling anything in, and the destination field is still
            # there for saving them to a file.
            param = QgsProcessingParameterFeatureSink(
                sink, label, gtype, defaultValue="TEMPORARY_OUTPUT",
                optional=True, createByDefault=True
            )
            self.addParameter(param)

        # --- Advanced -----------------------------------------------------
        # Method constants and things that are set once for a way of working
        # rather than per block.  They must stay adjustable: the result is
        # sensitive to the sector half-angle in particular.
        for param in (
            # Only one job left for this: bridging the gaps left where a
            # hand-drawn network does not quite meet.  Landings no longer rely
            # on it, so the value can stay at what those gaps actually are.
            QgsProcessingParameterNumber(
                self.SNAP_TOL,
                self.tr("Gap bridged in the road network (m)"),
                QgsProcessingParameterNumber.Double,
                defaultValue=2.0,
                minValue=0.0
            ),
            QgsProcessingParameterNumber(
                self.GRID,
                self.tr("Tree spacing (m)"),
                QgsProcessingParameterNumber.Double,
                defaultValue=10.0, minValue=0.1
            ),
            QgsProcessingParameterEnum(
                self.AUTO_DEM,
                self.tr("DEM download"),
                options=([self.tr("Auto (try each source, best first)")]
                         + [s[0] for s in tiles.SOURCES]
                         + [self.tr("Do not download")]),
                defaultValue=0
            ),
            # A DEM you already hold: for a block outside the tile coverage,
            # for a machine with no network, or to reuse one file across runs.
            QgsProcessingParameterRasterLayer(
                self.DEM,
                self.tr("DEM file (used instead of downloading)"),
                optional=True
            ),
            QgsProcessingParameterNumber(
                self.FELL_SECTOR,
                self.tr("Felling sector half-angle from downslope (deg)"),
                QgsProcessingParameterNumber.Double,
                defaultValue=105.0, minValue=0.0, maxValue=180.0
            ),
            QgsProcessingParameterNumber(
                self.FLAT_SLOPE,
                self.tr("Slope at or below which any direction is allowed (deg)"),
                QgsProcessingParameterNumber.Double,
                defaultValue=10.0, minValue=0.0, maxValue=90.0
            ),
            QgsProcessingParameterNumber(
                self.GRAPPLE_REACH,
                self.tr("Direct grapple reach from the road (m)"),
                QgsProcessingParameterNumber.Double,
                defaultValue=3.0, minValue=0.0
            ),
            QgsProcessingParameterNumber(
                self.ASPECT_SMOOTH,
                self.tr("Slope/aspect smoothing window (m)"),
                QgsProcessingParameterNumber.Double,
                defaultValue=5.0, minValue=0.0
            ),
            # A resource guard: memory grows at roughly 11.5 KB per sample
            # point, so a large area at a fine spacing can exhaust a field
            # laptop.  Stopping before any work beats being killed by the OS
            # halfway through.  250,000 points is about 3.3 GB at the heaviest
            # (felling model on, every output layer), which an 8 GB machine
            # carries.  0 disables the check.
            QgsProcessingParameterNumber(
                self.MAX_POINTS,
                self.tr("Maximum sample points (0 = no limit)"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=250000, minValue=0
            ),
            QgsProcessingParameterBoolean(
                self.SPLIT_ROADS,
                self.tr("Split roads at intersections before routing"),
                defaultValue=True
            ),
        ):
            param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(param)

    def _write_result_layers(self, parameters, context, feedback, p1, p2_with,
                             crs, modelled, in_range, volumes):
        """Write the per-tree map layers the sinks asked for.

        These carry the answer at the level it is actually used: one row per
        tree, with the distance, the landing it feeds, and -- with the felling
        model on -- the stem that was felled and the line along which it is
        pulled.
        """
        bases = {f["tree_id"]: f.geometry().asPoint() for f in p1.getFeatures()}
        rows = {}
        for f in p2_with.getFeatures():
            rows[f["tree_id"]] = f
        names = p2_with.fields().names()

        def val(feat, key, default=None):
            return feat[key] if key in names and feat[key] is not None else default

        tree_fields = QgsFields()
        tree_fields.append(QgsField("tree_id", QVariant.Int))
        tree_fields.append(QgsField("d1", QVariant.Double))
        tree_fields.append(QgsField("d2", QVariant.Double))
        tree_fields.append(QgsField("d_total", QVariant.Double))
        tree_fields.append(QgsField("landing_fid", QVariant.Int))
        tree_fields.append(QgsField("in_range", QVariant.Int))
        if volumes is not None:
            tree_fields.append(QgsField("volume", QVariant.Double))
        if modelled:
            for name in ("d1_geom", "d1_slope", "fell_az", "stem_len", "on_road",
                         "blocked"):
                tree_fields.append(QgsField(
                    name, QVariant.Int if name in ("on_road", "blocked")
                    else QVariant.Double))

        line_fields = QgsFields()
        line_fields.append(QgsField("tree_id", QVariant.Int))
        line_fields.append(QgsField("d1", QVariant.Double))
        if modelled:
            line_fields.append(QgsField("fell_az", QVariant.Double))
            line_fields.append(QgsField("stem_len", QVariant.Double))
            line_fields.append(QgsField("grab_tip", QVariant.Int))

        def make_sink(name, fields, wkb_type):
            # An unchecked optional sink has no destination; that is a choice,
            # not an error.
            try:
                sink, dest = self.parameterAsSink(
                    parameters, name, context, fields, wkb_type, crs)
            except Exception:
                return None, None
            return sink, dest

        trees_sink, trees_id = make_sink(self.OUT_TREES, tree_fields,
                                         QgsWkbTypes.Point)
        hauling_sink, hauling_id = make_sink(self.OUT_HAULING, line_fields,
                                             QgsWkbTypes.LineString)
        stems_sink = stems_id = None
        if modelled:
            stems_sink, stems_id = make_sink(self.OUT_STEMS, line_fields,
                                             QgsWkbTypes.LineString)
        else:
            feedback.pushInfo(self.tr(
                "Felled stems need the felling model; supply a DEM (or choose a "
                "download source) to get them."
            ))

        for tree_id, base in bases.items():
            row = rows.get(tree_id)
            if row is None:
                continue
            d1 = val(row, "d1")
            d2 = val(row, "d2")
            p2_pt = row.geometry().asPoint()

            if trees_sink is not None:
                feat = QgsFeature(tree_fields)
                feat["tree_id"] = tree_id
                feat["d1"] = d1
                feat["d2"] = d2
                feat["d_total"] = None if (d1 is None or d2 is None) else d1 + d2
                feat["landing_fid"] = val(row, "landing_fid")
                # Empty for a tree that cannot be extracted at all: range is
                # not the question there.
                feat["in_range"] = None if tree_id not in in_range \
                    else int(in_range[tree_id])
                if volumes is not None:
                    feat["volume"] = volumes.get(tree_id)
                if modelled:
                    feat["d1_geom"] = val(row, "d1_geom")
                    feat["d1_slope"] = val(row, "d1_slope")
                    feat["fell_az"] = val(row, "fell_az")
                    feat["stem_len"] = val(row, "stem_len")
                    feat["on_road"] = val(row, "on_road", 0)
                    feat["blocked"] = val(row, "blocked", 0)
                feat.setGeometry(QgsGeometry.fromPointXY(base))
                trees_sink.addFeature(feat)

            tip = None
            if modelled and val(row, "fell_az") is not None:
                az = float(row["fell_az"])
                reach = float(val(row, "stem_len", 0.0))
                tip = QgsPointXY(base.x() + reach * math.sin(math.radians(az)),
                                 base.y() + reach * math.cos(math.radians(az)))

            # Beyond the yarding limit nothing is felled or hauled by this
            # system; a line drawn for it would read as work that happens.
            if in_range.get(tree_id) is False:
                continue

            if stems_sink is not None and tip is not None:
                feat = QgsFeature(line_fields)
                feat["tree_id"] = tree_id
                feat["d1"] = d1
                feat["fell_az"] = row["fell_az"]
                feat["stem_len"] = val(row, "stem_len")
                feat["grab_tip"] = val(row, "grab_tip", 0)
                feat.setGeometry(QgsGeometry.fromPolylineXY([base, tip]))
                stems_sink.addFeature(feat)

            if hauling_sink is not None:
                if not d1:
                    continue  # d1 of zero means nothing is winched
                grabbed = tip if (tip is not None and val(row, "grab_tip", 0)) else base
                if grabbed == p2_pt:
                    continue
                feat = QgsFeature(line_fields)
                feat["tree_id"] = tree_id
                feat["d1"] = d1
                if modelled:
                    feat["fell_az"] = val(row, "fell_az")
                    feat["stem_len"] = val(row, "stem_len")
                    feat["grab_tip"] = val(row, "grab_tip", 0)
                feat.setGeometry(QgsGeometry.fromPolylineXY([grabbed, p2_pt]))
                hauling_sink.addFeature(feat)

        # Style on the way in: a layer of 2000 identical dots says nothing, and
        # nobody should have to build the classification by hand to see the
        # result.  Distances of zero get their own class -- with a third of the
        # points at zero, folding them into the ramp flattens everything else.
        for dest_id in (trees_id, stems_id):
            if dest_id:
                self._style_by_d1(dest_id, context)
        if hauling_id:
            self._style_by_d1(hauling_id, context, _HaulingStyler)

        return {key: dest for key, dest in (
            (self.OUT_TREES, trees_id),
            (self.OUT_HAULING, hauling_id),
            (self.OUT_STEMS, stems_id),
        ) if dest}

    @staticmethod
    def _style_by_d1(dest_id, context, styler_cls=None):
        try:
            details = context.layerToLoadOnCompletionDetails(dest_id)
        except Exception:
            return
        if details is None:
            return
        styler_cls = styler_cls or _D1Styler
        styler = styler_cls()
        styler_cls.keep.append(styler)  # the post-processor must outlive this call
        details.setPostProcessor(styler)

    def _download_dem(self, poly, crs, source_idx, feedback, margin=60.0):
        """Fetch a DEM covering the operation area and hand back a raster layer.

        Repeated runs over the same block reuse the file already fetched, so
        tuning the model does not re-download the same tiles each time.
        """
        ext = poly.sourceExtent()
        ext = QgsRectangle(ext.xMinimum() - margin, ext.yMinimum() - margin,
                           ext.xMaximum() + margin, ext.yMaximum() + margin)
        wgs = QgsCoordinateReferenceSystem("EPSG:4326")
        ll = QgsCoordinateTransform(crs, wgs, QgsProject.instance()) \
            .transformBoundingBox(ext)
        try:
            path = tiles.build_dem(
                (ll.xMinimum(), ll.yMinimum(), ll.xMaximum(), ll.yMaximum()),
                source_idx, 0, crs.toWkt(), crs.authid(),
                log=feedback.pushInfo,
                progress=feedback.setProgress,
                cancelled=feedback.isCanceled,
            )
        except tiles.TileError as exc:
            raise QgsProcessingException(str(exc))
        layer = QgsRasterLayer(path, "downloaded_dem")
        if not layer.isValid():
            raise QgsProcessingException(self.tr(
                "The downloaded DEM could not be opened: {}").format(path))
        return layer

    def _download_dem_auto(self, poly, crs, feedback):
        """Try each tile source in turn, finest first.

        Returns None if none of them yields a DEM, and that is not an error: a
        run on a field machine with no network should still produce the plain
        geometric answer rather than failing outright.  An explicitly chosen
        source is a request, so failing that one does raise.
        """
        for i, src in enumerate(tiles.SOURCES):
            try:
                return self._download_dem(poly, crs, i, feedback)
            except QgsProcessingException as exc:
                # Cancelling arrives here as a failed source.  Treating it as
                # "this one did not work, try the next" would hand back a
                # completed run measuring something the user did not ask for.
                if feedback.isCanceled():
                    raise QgsProcessingException(
                        self.tr("Processing cancelled by user."))
                feedback.pushInfo(self.tr(
                    "    {} gave no DEM here ({}); trying the next source."
                ).format(src[0], exc))
        feedback.pushWarning(self.tr(
            "No DEM could be downloaded for this area, so the felling model is "
            "off and d1 is the plain geometric distance. Give a DEM file under "
            "the advanced parameters to turn the model on."
        ))
        return None

    def _apply_felling_model(self, p1, parameters, context, feedback,
                             _reg, poly, roads_layer, roads_geom, dem_layer, barriers_source, area_only,
                             height_field,
                             tree_height, fell_sector, flat_slope, grapple_reach,
                             aspect_smooth, crs):
        """Recompute d1 and p2 from the felled stem rather than the standing tree.

        Returns (p2_layer, stats).  The returned layer keeps the contract the
        routing step depends on: one feature per sample point, carrying tree_id
        and d1.  Points are never dropped -- a point with d1 = 0 still needs a
        route to a landing.
        """
        # Slope and aspect are evaluated on a DEM resampled to the smoothing
        # window.  Reprojecting here is not optional: elevation tiles arrive in
        # web mercator, where horizontal distances are stretched by 1/cos(lat)
        # (~22% at 35N) and every slope would come out that much too gentle --
        # and the model branches on a 15 degree threshold.
        feedback.pushInfo(self.tr("2b) Preparing slope and aspect for the felling model..."))
        dem_r = processing.run(
            "gdal:warpreproject",
            {
                "INPUT": dem_layer,
                "TARGET_CRS": crs,
                "RESAMPLING": 1,  # bilinear
                "TARGET_RESOLUTION": aspect_smooth if aspect_smooth > 0 else None,
                "OUTPUT": "TEMPORARY_OUTPUT"
            },
            context=context, feedback=feedback
        )["OUTPUT"]

        slope_r = processing.run(
            "native:slope", {"INPUT": dem_r, "Z_FACTOR": 1, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context, feedback=feedback
        )["OUTPUT"]
        aspect_r = processing.run(
            "native:aspect", {"INPUT": dem_r, "Z_FACTOR": 1, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context, feedback=feedback
        )["OUTPUT"]

        # Elevation for the slope distance comes from the DEM at its own
        # resolution, not the smoothed one: the smoothing is there to steady
        # the aspect, and would only flatten the height difference.
        dem_z = processing.run(
            "gdal:warpreproject",
            {"INPUT": dem_layer, "TARGET_CRS": crs, "RESAMPLING": 1,
             "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context, feedback=feedback
        )["OUTPUT"]
        # The layer is kept by name: the provider dies with it.
        z_layer = QgsRasterLayer(dem_z, "dem_z")
        z_provider = z_layer.dataProvider()

        z_ext = z_layer.extent()
        z_rx = z_layer.rasterUnitsPerPixelX()
        z_ry = z_layer.rasterUnitsPerPixelY()

        def z_cell(x, y):
            value, ok = z_provider.sample(QgsPointXY(x, y), 1)
            if not ok or value is None or math.isnan(value):
                return None
            return value

        def z_at(pt):
            """Elevation at pt, interpolated from the four surrounding cells.

            sample() alone returns the cell the point falls in, which puts each
            end of the haul up to half a cell out in height -- on a 4 m DEM and
            a 30 degree face, over a metre.  Where a neighbour has no value
            (the edge of the DEM) the cell's own value is used instead.
            """
            fx = (pt.x() - z_ext.xMinimum()) / z_rx - 0.5
            fy = (z_ext.yMaximum() - pt.y()) / z_ry - 0.5
            i, j = math.floor(fx), math.floor(fy)
            tx, ty = fx - i, fy - j
            corners = [z_cell(z_ext.xMinimum() + (i + di + 0.5) * z_rx,
                              z_ext.yMaximum() - (j + dj + 0.5) * z_ry)
                       for dj in (0, 1) for di in (0, 1)]
            if any(c is None for c in corners):
                return z_cell(pt.x(), pt.y())
            z00, z10, z01, z11 = corners
            return ((z00 * (1 - tx) + z10 * tx) * (1 - ty)
                    + (z01 * (1 - tx) + z11 * tx) * ty)

        def slope_distance(a, b, d):
            """Length along the ground of a haul of horizontal length d from a to b.

            The winch line runs straight between its two ends, so the height
            difference of the ends is what lengthens it.  None where the DEM
            has no value at either end.
            """
            if not d:
                return 0.0
            za, zb = z_at(a), z_at(b)
            if za is None or zb is None:
                return None
            return math.hypot(d, za - zb)

        sampled = _reg(processing.run(
            "native:rastersampling",
            {"INPUT": p1.id(), "RASTERCOPY": slope_r, "COLUMN_PREFIX": "slp_",
             "OUTPUT": "memory:"},
            context=context, feedback=feedback
        )["OUTPUT"])
        sampled = _reg(processing.run(
            "native:rastersampling",
            {"INPUT": sampled.id(), "RASTERCOPY": aspect_r, "COLUMN_PREFIX": "asp_",
             "OUTPUT": "memory:"},
            context=context, feedback=feedback
        )["OUTPUT"])

        barriers_geom = None
        if barriers_source is not None:
            parts = [f.geometry() for f in barriers_source.getFeatures()
                     if not f.geometry().isEmpty()]
            if parts:
                barriers_geom = QgsGeometry.unaryUnion(parts)

        # With the option on, everything outside the block behaves like a
        # barrier -- for the stem and for the haul alike.
        area_geom = None
        if area_only:
            parts = [f.geometry() for f in poly.getFeatures()
                     if not f.geometry().isEmpty()]
            if parts:
                area_geom = QgsGeometry.unaryUnion(parts)

        def inside_area(geom):
            """Is this geometry within the block, counting its edge as inside?

            GEOS `contains` is false for anything lying on the boundary, and a
            forest road is routinely digitised *as* the block edge -- taking
            `contains` at face value there rejects every road point and reports
            the whole block as impossible to extract.  What is actually being
            asked is whether any part falls outside.
            """
            if area_geom is None:
                return True
            outside = geom.difference(area_geom)
            return outside.isEmpty() or outside.length() < 1e-9

        def haul_ok(a, b):
            """Can the grabbed end at a be pulled straight to the road at b?"""
            line = QgsGeometry.fromPolylineXY([a, b])
            if barriers_geom is not None and line.intersects(barriers_geom):
                return False
            if not inside_area(line):
                return False
            return True

        # Points along the road, used only when the nearest point on it cannot
        # be reached: then the haul goes to the nearest point that can be.
        # Built once, and only when something can actually block a haul.
        road_pts = []
        if barriers_geom is not None or area_geom is not None:
            step = 2.0
            for rf in roads_layer.getFeatures():
                g = rf.geometry()
                if g.isEmpty():
                    continue
                length = g.length()
                n = max(1, int(length / step))
                for i in range(n + 1):
                    pt = g.interpolate(length * i / n)
                    if pt.isEmpty():
                        continue
                    xy = pt.asPoint()
                    if area_geom is not None and area_geom.disjoint(pt):
                        continue  # a road outside the block is not usable
                    road_pts.append(xy)

        def nearest_reachable(a):
            """Nearest road point the haul can actually get to, or None."""
            best_pt, best_d = None, None
            for xy in road_pts:
                d = math.hypot(xy.x() - a.x(), xy.y() - a.y())
                if best_d is not None and d >= best_d:
                    continue
                if haul_ok(a, xy):
                    best_pt, best_d = xy, d
            return (best_d, QgsGeometry.fromPointXY(best_pt)) if best_pt else None

        out = QgsVectorLayer("Point?crs=" + crs.authid(), "p2_model", "memory")
        fields = QgsFields()
        fields.append(QgsField("tree_id", QVariant.Int))
        fields.append(QgsField("d1", QVariant.Double))
        fields.append(QgsField("d1_geom", QVariant.Double))   # geometric d1, for comparison
        fields.append(QgsField("d1_slope", QVariant.Double))  # d1 along the ground
        fields.append(QgsField("fell_az", QVariant.Double))
        fields.append(QgsField("stem_len", QVariant.Double))  # horizontal reach
        fields.append(QgsField("on_road", QVariant.Int))      # stem reaches the road
        fields.append(QgsField("blocked", QVariant.Int))      # no direction survived
        fields.append(QgsField("grab_tip", QVariant.Int))     # the top is the end pulled
        out.dataProvider().addAttributes(fields.toList())
        out.updateFields()

        n_on_road, n_blocked, n_grapple, n_no_terrain = 0, 0, 0, 0
        feats = []
        for f in sampled.getFeatures():
            if feedback.isCanceled():
                raise QgsProcessingException(self.tr("Processing cancelled by user."))
            base = f.geometry().asPoint()
            base_geom = QgsGeometry.fromPointXY(base)
            d_base = base_geom.distance(roads_geom)

            # Within grapple reach nothing is winched.  The tree is still
            # felled, so it keeps going through direction selection -- otherwise
            # these trees would be holes in the stem map.
            is_grapple = d_base <= grapple_reach

            slope_deg = f["slp_1"]
            aspect_deg = f["asp_1"]
            height = None
            if height_field:
                height = f[height_field]
            if height is None or height <= 0:
                height = tree_height
            if slope_deg is None or aspect_deg is None:
                # Outside the DEM: fall back to the geometric answer rather than
                # inventing a felling direction.  Not the same as blocked -- the
                # tree can be extracted, it just is not modelled here.
                foot = roads_geom.nearestPoint(base_geom)
                feats.append(self._p2_feature(out, f, d_base, d_base, None, 0.0,
                                              foot, on_road=0, blocked=0))
                n_no_terrain += 1
                continue

            foot_geom = roads_geom.nearestPoint(base_geom)
            foot_pt = foot_geom.asPoint()
            target_az = _azimuth(foot_pt.x() - base.x(), foot_pt.y() - base.y())

            best = None
            for az in _candidate_directions(target_az, aspect_deg, slope_deg,
                                            fell_sector, flat_slope):
                phi = _angle_diff(az, aspect_deg)
                reach = height * math.cos(math.radians(_slope_along(slope_deg, phi)))
                tip = QgsPointXY(base.x() + reach * math.sin(math.radians(az)),
                                 base.y() + reach * math.cos(math.radians(az)))
                stem = QgsGeometry.fromPolylineXY([base, tip])
                # A direction whose stem crosses a barrier is not available:
                # a stem thrown over the river cannot be pulled back across it.
                if barriers_geom is not None and stem.intersects(barriers_geom):
                    continue
                if not inside_area(stem):
                    continue
                if stem.intersects(roads_geom):
                    # Blocking the road is accepted, so reaching it ends the haul.
                    hit = stem.intersection(roads_geom)
                    p2_geom = hit if hit.wkbType() == QgsWkbTypes.Point \
                        else QgsGeometry.fromPointXY(
                            hit.nearestPoint(base_geom).asPoint())
                    best = (0.0, az, reach, p2_geom, 1, 1, tip)
                    break
                tip_geom = QgsGeometry.fromPointXY(tip)
                d_tip = tip_geom.distance(roads_geom)
                # Either end can be grabbed, so the near one decides.
                if d_tip < d_base:
                    grabbed = tip
                    cand = (d_tip, az, reach, roads_geom.nearestPoint(tip_geom), 0, 1,
                            grabbed)
                else:
                    grabbed = base
                    cand = (d_base, az, reach, foot_geom, 0, 0, grabbed)
                # The stem clears the obstacles, but the haul from the grabbed
                # end can still be blocked.  Then the winch goes to the nearest
                # road point it can actually reach, not the nearest one on the
                # map.  (The d1 = 0 case above needs no test: p2 lies on the
                # stem, which has already been checked.)
                if (barriers_geom is not None or area_geom is not None) \
                        and not haul_ok(grabbed, cand[3].asPoint()):
                    alt = nearest_reachable(grabbed)
                    if alt is None:
                        continue
                    cand = (alt[0], az, reach, alt[1], 0, cand[5], grabbed)
                if best is None or cand[0] < best[0]:
                    best = cand

            if best is None:
                # No direction leaves a stem that can be felled and then pulled
                # to a road it can reach.  That is not a distance of any size:
                # the tree cannot be extracted, so d1 is empty and it stays out
                # of the means rather than contributing a haul that cannot happen.
                n_blocked += 1
                feats.append(self._p2_feature(out, f, None, d_base, None, 0.0,
                                              foot_geom, on_road=0, blocked=1))
                continue

            # The direction is chosen on the horizontal d1 and the slope
            # distance taken for that choice only.  Where another direction
            # would bring a tree under the yarding limit that the chosen one
            # leaves over it, that tree is reported out of range -- rare, and
            # the cost of choosing on slope distance is sampling the DEM for
            # every candidate of every tree.
            d1_new, az, reach, p2_geom, on_road, grab_tip, grabbed = best
            if d1_new <= grapple_reach:
                d1_new = 0.0
            if is_grapple:
                # Counted here, not when the distance was measured: a tree that
                # turns out to be unextractable is reported under that heading
                # instead, so the two never cover the same tree twice.
                n_grapple += 1
            if is_grapple and (
                    (barriers_geom is None and area_geom is None)
                    or haul_ok(base, foot_geom.asPoint())):
                # The machine grabs this tree from the road it is standing next
                # to, so the haul starts at the nearest point on the road -- not
                # wherever the felled stem happens to cross it 20 m away.  The
                # felling direction is still kept, for the stem drawing.  If
                # that road cannot be used, the modelled answer stands.
                d1_new = 0.0
                p2_geom = foot_geom
                on_road = 0
                grab_tip = 0
            n_on_road += on_road
            d1_slope = slope_distance(grabbed, p2_geom.asPoint(), d1_new)
            feats.append(self._p2_feature(out, f, d1_new, d_base, az, reach,
                                          p2_geom, on_road=on_road, blocked=0,
                                          grab_tip=grab_tip, d1_slope=d1_slope))

        out.dataProvider().addFeatures(feats)
        out.updateExtents()
        _reg(out)
        stats = {"on_road": n_on_road, "blocked": n_blocked, "grapple": n_grapple,
                 "no_terrain": n_no_terrain}
        feedback.pushInfo(self.tr(
            "    -> stem reaches the road: {} / within grapple reach: {} / "
            "cannot be extracted: {} / outside the DEM: {}"
        ).format(n_on_road, n_grapple, n_blocked, n_no_terrain))
        return out, stats

    @staticmethod
    def _p2_feature(layer, src, d1, d1_geom, az, reach, geom, on_road, blocked,
                    grab_tip=0, d1_slope=None):
        feat = QgsFeature(layer.fields())
        feat["tree_id"] = src["tree_id"]
        feat["d1"] = None if d1 is None else float(d1)
        feat["d1_geom"] = float(d1_geom)
        feat["d1_slope"] = None if d1_slope is None else float(d1_slope)
        feat["fell_az"] = None if az is None else float(az)
        feat["stem_len"] = float(reach)
        feat["on_road"] = int(on_road)
        feat["blocked"] = int(blocked)
        feat["grab_tip"] = int(grab_tip)
        feat.setGeometry(geom if isinstance(geom, QgsGeometry)
                         else QgsGeometry.fromPointXY(geom))
        return feat

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback):
        poly = self.parameterAsSource(parameters, self.POLY, context)
        roads = self.parameterAsSource(parameters, self.ROADS, context)
        landing = self.parameterAsSource(parameters, self.LANDING, context)
        grid = float(self.parameterAsDouble(parameters, self.GRID, context))
        snap_tol = float(self.parameterAsDouble(parameters, self.SNAP_TOL, context))
        split_roads = self.parameterAsBool(parameters, self.SPLIT_ROADS, context)

        # Felling model inputs.  Each feature turns itself on by being supplied.
        dem_layer = self.parameterAsRasterLayer(parameters, self.DEM, context)
        auto_dem = self.parameterAsEnum(parameters, self.AUTO_DEM, context)
        trees_source = self.parameterAsSource(parameters, self.TREES, context)
        height_field = self.parameterAsString(parameters, self.HEIGHT_FIELD, context)
        barriers_source = self.parameterAsSource(parameters, self.BARRIERS, context)
        area_only = self.parameterAsBool(parameters, self.AREA_ONLY, context)
        tree_height = float(self.parameterAsDouble(parameters, self.TREE_HEIGHT, context))
        fell_sector = float(self.parameterAsDouble(parameters, self.FELL_SECTOR, context))
        flat_slope = float(self.parameterAsDouble(parameters, self.FLAT_SLOPE, context))
        grapple_reach = float(self.parameterAsDouble(parameters, self.GRAPPLE_REACH, context))
        aspect_smooth = float(self.parameterAsDouble(parameters, self.ASPECT_SMOOTH, context))
        max_points = int(self.parameterAsInt(parameters, self.MAX_POINTS, context))
        max_range = float(self.parameterAsDouble(parameters, self.MAX_RANGE, context))
        volume_field = self.parameterAsString(parameters, self.VOLUME_FIELD, context) \
            if trees_source is not None else ""

        if poly is None or roads is None or landing is None:
            raise QgsProcessingException(self.tr("Invalid input layers."))

        if poly.featureCount() == 0:
            raise QgsProcessingException(self.tr("Operation area polygon has no features."))
        if roads.featureCount() == 0:
            raise QgsProcessingException(self.tr("Forest roads layer has no features."))

        # Distances are measured in the CRS of the first input that is projected
        # in metres, the operation area first.  An area drawn over a web map in
        # WGS84 alongside survey data in a plane rectangular CRS is ordinary,
        # and the survey data already says how to measure.  No CRS is invented
        # (a UTM zone guessed from the centroid, say): the distances are always
        # in one that some input actually carries.
        crs, crs_label = None, None
        for source, label in (
                (poly, self.tr("the operation area")),
                (roads, self.tr("the forest roads")),
                (landing, self.tr("the landings")),
                (trees_source, self.tr("the individual trees")),
                (barriers_source, self.tr("the barriers"))):
            if source is None:
                continue
            cand = source.sourceCrs()
            if cand.isValid() and not cand.isGeographic() \
                    and cand.mapUnits() == QgsUnitTypes.DistanceMeters:
                crs, crs_label = cand, label
                break
        if crs is None:
            raise QgsProcessingException(self.tr(
                "None of the input layers is in a projected CRS in metres, so "
                "distances cannot be measured. Reproject one of them -- the "
                "operation area or the forest roads -- to a metric CRS such as "
                "the plane rectangular system for the site."
            ))
        if crs != poly.sourceCrs():
            feedback.pushWarning(self.tr(
                "The operation area is in {src}, which is not a projected CRS in "
                "metres, so distances are measured in {dst}, the CRS of {layer}."
            ).format(src=poly.sourceCrs().authid(), dst=crs.authid(),
                     layer=crs_label))

        try:
            # Helper: register a memory layer in the context's temporary store so it can be
            # referenced by ID in subsequent processing.run() calls.  Without this,
            # passing QgsVectorLayer objects in parameter dicts requires PyQt6/SIP to convert
            # them to QVariant, which fails intermittently in QGIS 4.0 (PyQt6).
            def _reg(lyr):
                context.temporaryLayerStore().addMapLayer(lyr)
                return lyr

            # Messages from the nested algorithms that say nothing the user can
            # act on.  One instance for the whole run: it connects to the
            # parent's cancel signal, and one per call would pile up connections.
            quiet = _QuietFeedback(feedback)

            # QGIS's own algorithms reproject silently when inputs disagree, so
            # this one does the same rather than behaving differently to
            # everything else in the toolbox.  The difference is still
            # announced: a mismatch is often a mistake even when it is handled.
            def in_area_crs(param_name, source, label):
                if source is None:
                    return None
                if source.sourceCrs() == crs:
                    return parameters[param_name]
                feedback.pushWarning(self.tr(
                    "{layer} is in {src}; it is being reprojected to {dst}, the "
                    "CRS the distances are measured in. Check that this is "
                    "intended."
                ).format(layer=label, src=source.sourceCrs().authid(),
                         dst=crs.authid()))
                return _reg(processing.run(
                    "native:reprojectlayer",
                    {"INPUT": parameters[param_name], "TARGET_CRS": crs,
                     "OUTPUT": "memory:"},
                    context=context, feedback=quiet
                )["OUTPUT"]).id()

            # The operation area goes through the same door as everything else.
            # From here on `poly` is whatever is in the measuring CRS: the
            # source as given, or the reprojected layer (a QgsVectorLayer is a
            # QgsFeatureSource too, so sourceExtent() and getFeatures() hold).
            poly_param = in_area_crs(self.POLY, poly,
                                     self.tr("Operation area"))
            if poly_param is not parameters[self.POLY]:
                poly = context.getMapLayer(poly_param)

            # 0 = auto, 1..N = a named source, N+1 = do not download.  After
            # the area is in the measuring CRS: the DEM is fetched over its
            # extent and written in that CRS.
            no_download = (auto_dem == len(tiles.SOURCES) + 1)
            if dem_layer is not None:
                if not no_download:
                    feedback.pushInfo(self.tr(
                        "A DEM layer was given, so the download option is ignored."
                    ))
            elif not no_download:
                if auto_dem == 0:
                    dem_layer = self._download_dem_auto(poly, crs, feedback)
                else:
                    dem_layer = self._download_dem(poly, crs, auto_dem - 1, feedback)

            roads_param = in_area_crs(self.ROADS, roads,
                                      self.tr("Forest road lines"))
            landing_param = in_area_crs(self.LANDING, landing,
                                        self.tr("Landing points"))
            # Tree points can be a whole prefecture's worth -- published
            # single-tree data comes by the million.  Reprojecting all of it
            # before clipping held every point in memory (9.35 million points:
            # about 8-9 GB).  So when the trees need reprojecting, cut them to
            # the area first, in their own CRS, and reproject only what is
            # left.  The area is widened by 1 m for this cut so that a point
            # on the boundary is not lost to the reprojection; the exact clip
            # is still step 1.
            trees_param = parameters.get(self.TREES)
            if trees_source is not None and trees_source.sourceCrs() != crs:
                widened = _reg(processing.run(
                    "native:buffer",
                    {"INPUT": poly_param, "DISTANCE": 1.0, "SEGMENTS": 4,
                     "DISSOLVE": True, "OUTPUT": "memory:"},
                    context=context, feedback=quiet
                )["OUTPUT"])
                near = _reg(processing.run(
                    "native:extractbylocation",
                    {"INPUT": parameters[self.TREES], "PREDICATE": [0],
                     "INTERSECT": widened.id(), "OUTPUT": "memory:"},
                    context=context, feedback=quiet
                )["OUTPUT"])
                feedback.pushWarning(self.tr(
                    "{layer} is in {src}; the {n} points near the operation area "
                    "are being reprojected to {dst}, the CRS the distances are "
                    "measured in. Check that this is intended."
                ).format(layer=self.tr("Individual tree points"),
                         src=trees_source.sourceCrs().authid(),
                         n=near.featureCount(), dst=crs.authid()))
                trees_param = _reg(processing.run(
                    "native:reprojectlayer",
                    {"INPUT": near.id(), "TARGET_CRS": crs, "OUTPUT": "memory:"},
                    context=context, feedback=quiet
                )["OUTPUT"]).id()
            barriers_param = in_area_crs(self.BARRIERS, barriers_source,
                                         self.tr("Barriers"))
            if barriers_param is not None and barriers_param is not parameters[self.BARRIERS]:
                barriers_source = context.getMapLayer(barriers_param)

            # The roads as one geometry, built once: the felling model measures
            # to it, and the landings are placed on it.  roads_param is a layer
            # id only when the layer had to be reprojected; otherwise the source
            # already in hand is used -- it honours "selected features only",
            # which the layer behind it would not.
            roads_layer = (context.getMapLayer(roads_param)
                           if isinstance(roads_param, str) else None) or roads
            roads_geom = QgsGeometry.unaryUnion(
                [f.geometry() for f in roads_layer.getFeatures()
                 if not f.geometry().isEmpty()])

            # 1) Create grid points and clip to polygon
            if trees_source is not None:
                # Individual tree points stand in for the grid: extraction distance
                # is a per-tree quantity, so real stem positions beat a regular
                # lattice.  Grid spacing has no meaning here -- say so rather than
                # letting it look like it was applied.
                feedback.pushInfo(self.tr(
                    "1) Using supplied tree points as sample points (p1); "
                    "grid spacing is ignored."
                ))
                sample_input = trees_param
            else:
                feedback.pushInfo(self.tr("1) Creating grid points (p1)..."))
                # Check before building, not after clipping.  creategrid covers
                # the whole bounding box, so a block that is a thin strip across
                # a wide extent allocates several times what survives the clip --
                # and the guard exists to stop that allocation, not to notice it
                # afterwards.
                ext = poly.sourceExtent()
                if max_points > 0 and grid > 0:
                    n_bbox = ((ext.width() / grid) + 1) * ((ext.height() / grid) + 1)
                    if n_bbox > max_points:
                        raise QgsProcessingException(self.tr(
                            "A lattice at {sp} m over this extent would be about "
                            "{n} points, past the limit of {lim}. Use a wider tree "
                            "spacing, split the operation area into parts, or raise "
                            "'Maximum sample points' in the advanced parameters."
                        ).format(sp=grid, n=int(n_bbox), lim=max_points))
                grid_layer = _reg(processing.run(
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
                )["OUTPUT"])

                # Not indexed.  Up to 0.3.0 building a spatial index here
                # changed the answer (d2_null 54 -> 64 on a real block), most
                # likely because it changed the order of the points and QGIS's
                # routing tied all start points into the graph together, so
                # order and neighbours mattered.  Routing no longer works that
                # way (network.py); the index would only silence the clip's
                # "no spatial index" warning, which is suppressed below instead.
                sample_input = grid_layer.id()

            # Both sources get clipped to the operation area the same way.
            # Quiet: the only thing this step says is that the grid has no
            # spatial index and performance "will be severely degraded", which
            # is neither true at this scale nor actionable.  The feature count
            # is checked immediately below, so a real failure still surfaces.
            p1 = _reg(processing.run(
                "native:extractbylocation",
                {
                    "INPUT": sample_input,
                    "PREDICATE": [0],  # intersects
                    "INTERSECT": poly_param,
                    "OUTPUT": "memory:"
                },
                context=context, feedback=quiet
            )["OUTPUT"])

            if p1.featureCount() == 0:
                raise QgsProcessingException(self.tr(
                    "No sample points fall within the operation polygon. "
                    "With a grid, try a smaller spacing; with tree points, check "
                    "that they overlap the operation area."
                ))

            # Measured 2026-10-09 on the sample data at 30,000, 120,000 and
            # 188,000 points, with the felling model on and every output layer
            # written -- the heaviest case: 0.39 GB is QGIS itself, and 11.5 KB
            # per sample point the rest (peak 2.53 GB at 188,000).  Without the
            # felling model it is about 8.7 KB.  The estimate is reported
            # either way so the cost is visible before the long part of the
            # run, not only when the limit is hit.
            n_points = p1.featureCount()
            est_gb = 0.39 + n_points * 11.5e-6
            feedback.pushInfo(self.tr(
                "    -> {n} sample points (estimated peak memory {gb:.1f} GB)."
            ).format(n=n_points, gb=est_gb))
            if max_points > 0 and n_points > max_points:
                raise QgsProcessingException(self.tr(
                    "{n} sample points exceeds the limit of {lim} (estimated "
                    "memory {gb:.1f} GB). Use a coarser grid spacing, split the "
                    "operation area into parts, or raise 'Maximum sample points' "
                    "in the advanced parameters."
                ).format(n=n_points, lim=max_points, gb=est_gb))

            p1 = _reg(processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": p1.id(),
                    "FIELD_NAME": "tree_id",
                    "FIELD_TYPE": 1,  # int
                    "FIELD_LENGTH": 10,
                    "FIELD_PRECISION": 0,
                    "FORMULA": "@row_number",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"])

            # 2) Shortest line to roads -> d1, nearest point on road -> p2
            feedback.pushInfo(self.tr("2) Computing shortest lines to roads (d1) and nearest points (p2)..."))
            shortest_lines = _reg(processing.run(
                "native:shortestline",
                {
                    "SOURCE": p1.id(),
                    "DESTINATION": roads_param,
                    "METHOD": 0,
                    "NEIGHBORS": 1,
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"])

            shortest_lines = _reg(processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": shortest_lines.id(),
                    "FIELD_NAME": "d1",
                    "FIELD_TYPE": 0,  # float
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "FORMULA": "$length",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"])

            p2 = _reg(processing.run(
                "native:extractspecificvertices",
                {
                    "INPUT": shortest_lines.id(),
                    "VERTICES": "-1",  # last vertex = nearest point on road
                    "OUTPUT": "memory:"
                },
                context=context, feedback=feedback
            )["OUTPUT"])

            # A point equidistant from two roads gets a shortest line to each of
            # them.  d1 is the same either way, but the haul to the landing is
            # not -- on the sample data it is 99 m by one road and 299 m by the
            # other.  Keeping whichever row happened to come first made d2
            # change from run to run.  So every tied foot is kept, each is
            # routed, and the shorter haul decides (step 3).
            n_tied = p2.featureCount() - p1.featureCount()
            if n_tied > 0:
                feedback.pushInfo(self.tr(
                    "{} sample points are equidistant from more than one road; "
                    "each is routed from all of them and the shorter haul is kept."
                ).format(n_tied))

            # 2b) Felling model.  d1 stops being "distance to the nearest road"
            # and becomes "distance from the road to the near end of the felled
            # stem", which also moves p2 -- and p2 is where routing starts.
            geometric_d1 = None
            model_stats = None
            if dem_layer is not None:
                geometric_d1 = {}
                for f in p2.getFeatures():
                    geometric_d1[f["tree_id"]] = f["d1"]
                p2, model_stats = self._apply_felling_model(
                    p1, parameters, context, feedback, _reg,
                    poly=poly,
                    roads_layer=roads_layer,
                    roads_geom=roads_geom,
                    dem_layer=dem_layer,
                    barriers_source=barriers_source,
                    area_only=area_only,
                    height_field=height_field,
                    tree_height=tree_height,
                    fell_sector=fell_sector,
                    flat_slope=flat_slope,
                    grapple_reach=grapple_reach,
                    aspect_smooth=aspect_smooth,
                    crs=crs,
                )

            # 3) Shortest path to the nearest landing along the road network.
            feedback.pushInfo(self.tr("3) Computing shortest path along road network to nearest landing (d2)..."))

            landing_layer = context.getMapLayer(landing_param) \
                if landing_param is not parameters[self.LANDING] \
                else self.parameterAsLayer(parameters, self.LANDING, context)
            if landing_layer.featureCount() == 0:
                raise QgsProcessingException(self.tr("Landing layer has no features."))

            if split_roads:
                feedback.pushInfo(self.tr("3a) Splitting roads at intersections..."))
                split_layer = _reg(processing.run(
                    "native:splitwithlines",
                    {
                        "INPUT": roads_param,
                        "LINES": roads_param,
                        "OUTPUT": "memory:"
                    },
                    context=context, feedback=feedback
                )["OUTPUT"])
                feedback.pushInfo(self.tr("    -> {} segments after split.").format(split_layer.featureCount()))
                roads_source = split_layer.id()
            else:
                roads_source = roads_param

            # The network is built from the lines routing should use: split at
            # intersections, or as drawn (where a crossing is a bridge, not a
            # junction).  Both honour "selected features only".
            if split_roads:
                routing_src = split_layer
            else:
                routing_src = (context.getMapLayer(roads_param)
                               if isinstance(roads_param, str) else None) or roads
            lines = []
            for f in routing_src.getFeatures():
                g = f.geometry()
                if g is None or g.isEmpty():
                    continue
                for part in g.constParts():
                    lines.append([(v.x(), v.y()) for v in part.vertices()])
            net = network.Network(lines, snap_tol)

            # Each tree's place on the network is found once; each landing is
            # then searched once and every tree read off from it.  A tree's d2
            # depends on that tree alone -- not, as with QGIS's routing, on
            # which other points were tied into the graph alongside it.
            # A tree that cannot be extracted has no haul and therefore no run
            # to a landing either.  Keeping it out here stops it being counted
            # as a routing failure, which is a different problem.
            unhaulable = {f["tree_id"] for f in p2.getFeatures()
                          if f["d1"] is None}
            starts = []
            for f in p2.getFeatures():
                if f["d1"] is None:
                    continue
                pt = f.geometry().asPoint()
                starts.append((f.id(), f["tree_id"], net.locate(pt.x(), pt.y())))

            best = {}                # tree_id -> (d2, landing_fid, p2 feature id)
            skipped_landings = []
            n_landings_routed = 0
            landing_moves = {}
            for lf in landing_layer.getFeatures():
                if feedback.isCanceled():
                    raise QgsProcessingException(self.tr("Processing cancelled by user."))
                geom = lf.geometry()
                if geom is None or geom.isEmpty():
                    # Silently ignoring these would quietly send every tree to
                    # the remaining landing and look like a correct answer.
                    skipped_landings.append(lf.id())
                    continue
                # A landing is an area; the point that stands for it sits in
                # the middle of that area, which is by definition off the road.
                # That is not a tolerance question -- the landing is simply
                # reached at the nearest point of the road serving it.
                pt = geom.asPoint()
                on_road = roads_geom.nearestPoint(geom)
                if not on_road.isEmpty():
                    moved = geom.distance(on_road)
                    pt = on_road.asPoint()
                    if moved > 0.01:
                        landing_moves[lf.id()] = moved
                origin = net.locate(pt.x(), pt.y())
                if origin is None:
                    continue
                dist = net.distances_from(origin)
                n_landings_routed += 1
                for fid, tid, loc in starts:
                    d2 = net.distance(dist, origin, loc)
                    if d2 is None:
                        continue
                    cur = best.get(tid)
                    # Ties go to the first landing, then to the lower-numbered
                    # foot of a tree equidistant from two roads.
                    if cur is None or d2 < cur[0] or (
                            d2 == cur[0] and lf.id() == cur[1] and fid < cur[2]):
                        best[tid] = (d2, lf.id(), fid)

            # Back to one row per tree: for a tie, the foot whose haul won; for
            # a tree no landing could be reached from, the first of its feet.
            n_trees = len({f["tree_id"] for f in p2.getFeatures()})
            if p2.featureCount() > n_trees:
                keep = {v[2] for v in best.values()}
                first = {}
                for f in p2.getFeatures():
                    if f["tree_id"] not in best:
                        first[f["tree_id"]] = min(f.id(), first.get(f["tree_id"], f.id()))
                keep.update(first.values())
                p2 = _reg(p2.materialize(QgsFeatureRequest().setFilterFids(sorted(keep))))

            for fid, moved in sorted(landing_moves.items()):
                feedback.pushInfo(self.tr(
                    "    Landing {fid} sits {d:.1f} m off the road; routed from "
                    "the nearest point on it."
                ).format(fid=fid, d=moved))

            if skipped_landings:
                # A warning, not an error: the run is valid, but the answer is
                # wrong in a way that looks right, so it must stay visible.
                feedback.pushWarning(self.tr(
                    "{} of {} landing points have no geometry and were ignored "
                    "(feature ids: {}). Every sample point will be assigned to the "
                    "remaining landings."
                ).format(len(skipped_landings), landing_layer.featureCount(),
                         ", ".join(str(i) for i in skipped_landings)))

            if n_landings_routed == 0:
                raise QgsProcessingException(self.tr(
                    "No valid landing points were found (all geometries empty?)."
                ))

            if not best:
                raise QgsProcessingException(self.tr(
                    "All grid points are unreachable from all landings. "
                    "Check that the road network is connected, "
                    "landing points are on or near the road, "
                    "and the snapping tolerance is sufficient."
                ))

            # The per-point routing errors are suppressed above, so state the
            # same fact once, with the scale of it.
            n_samples = p2.featureCount()
            n_unreachable = n_samples - len(best) - len(unhaulable)
            if unhaulable:
                feedback.pushWarning(self.tr(
                    "{n} of {total} sample points cannot be extracted: no felling "
                    "direction leaves a stem that can be pulled to a road it can "
                    "reach. Their d1 and d2 are empty and they are left out of "
                    "the means."
                ).format(n=len(unhaulable), total=n_samples))
            if n_unreachable > 0:
                feedback.pushWarning(self.tr(
                    "{n} of {total} sample points ({pct:.1f}%) could not reach any "
                    "landing along the road network; their d2 is empty. Check that "
                    "the road network is connected and that the snapping tolerance "
                    "is large enough."
                ).format(n=n_unreachable, total=n_samples,
                         pct=100.0 * n_unreachable / n_samples))

            # What the merged route layer was ever reduced to: one row per tree.
            # No geometry, so the join below costs a table the size of p2.
            best_routes = QgsVectorLayer("None", "best_routes", "memory")
            best_fields = QgsFields()
            best_fields.append(QgsField("tree_id", QVariant.Int))
            best_fields.append(QgsField("d2", QVariant.Double))
            best_fields.append(QgsField("landing_fid", QVariant.Int))
            best_routes.dataProvider().addAttributes(best_fields.toList())
            best_routes.updateFields()
            best_feats = []
            for tid, (d2, landing_fid, _key) in best.items():
                bf = QgsFeature(best_routes.fields())
                bf["tree_id"] = tid
                bf["d2"] = d2
                bf["landing_fid"] = landing_fid
                best_feats.append(bf)
            best_routes.dataProvider().addFeatures(best_feats)
            _reg(best_routes)

            copy_fields = ["d2", "landing_fid"]
            p2_with = _reg(processing.run(
                "native:joinattributestable",
                {
                    "INPUT": p2.id(),
                    "FIELD": "tree_id",
                    "INPUT_2": best_routes.id(),
                    "FIELD_2": "tree_id",
                    "FIELDS_TO_COPY": copy_fields,
                    "METHOD": 1,
                    "DISCARD_NONMATCHING": False,
                    "PREFIX": "",
                    "OUTPUT": "memory:"
                },
                context=context, feedback=quiet
            )["OUTPUT"])

            field_names = p2_with.fields().names()

            # 3b) Yarding range.  Judged on the slope distance where the felling
            # model gave one; otherwise on the horizontal d1, which is shorter
            # and so lets trees near the limit through -- said once, below.
            in_range = {}
            n_range_horizontal = 0
            for f in p2_with.getFeatures():
                d1 = f["d1"]
                if d1 is None:
                    continue  # cannot be extracted: range is not the question
                dist = f["d1_slope"] if "d1_slope" in field_names else None
                if dist is None:
                    dist = d1
                    if d1 > 0:
                        n_range_horizontal += 1
                in_range[f["tree_id"]] = max_range <= 0 or dist <= max_range
            n_out_of_range = sum(1 for v in in_range.values() if not v)
            if max_range > 0 and n_range_horizontal:
                feedback.pushWarning(self.tr(
                    "{n} trees have no slope distance (no DEM there), so the "
                    "yarding limit was applied to their horizontal distance. That "
                    "is shorter than the slope distance, so some of them may be "
                    "counted in range when they are not."
                ).format(n=n_range_horizontal))

            # Volume per tree, as supplied.  An empty or negative value is not
            # guessed at; such trees are counted so the totals can be read.
            volumes = None
            n_no_volume = 0
            if volume_field:
                volumes = {}
                for f in p1.getFeatures():
                    v = f[volume_field]
                    try:
                        v = float(v) if v is not None else None
                    except (TypeError, ValueError):
                        v = None
                    if v is None or v < 0 or math.isnan(v):
                        n_no_volume += 1
                        continue
                    volumes[f["tree_id"]] = v

            layer_outputs = self._write_result_layers(
                parameters, context, feedback, p1, p2_with, crs,
                modelled=(dem_layer is not None),
                in_range=in_range, volumes=volumes
            )

            # 4) Summary statistics.  With a yarding limit the means are over
            # the trees in range: the ones beyond it are not extracted by this
            # system, so their distances are not part of its work.
            feedback.pushInfo(self.tr("4) Computing summary statistics..."))
            d1_vals, d2_vals, d1_slope_vals = [], [], []
            null_d2 = 0
            total = 0

            # Every tree lands in exactly one row of the landing table, so the
            # rows add up to the whole block and a shortfall has a name.
            OUT, BLOCKED, UNROUTED = "out", "blocked", "unrouted"
            groups = {}

            def add_to(key, tid, d1=None, d2=None):
                g = groups.setdefault(key, {"n": 0, "vol": 0.0, "d1": [], "d2": []})
                g["n"] += 1
                if volumes is not None:
                    g["vol"] += volumes.get(tid, 0.0)
                if d1 is not None:
                    g["d1"].append(d1)
                if d2 is not None:
                    g["d2"].append(d2)

            d1_geom_vals = []
            for f in p2_with.getFeatures():
                total += 1
                tid = f["tree_id"]
                d2 = f["d2"] if "d2" in field_names else None
                # Out-of-range trees are counted in their own row, not here,
                # so this count and the table's unreachable row agree.
                if d2 is None and tid not in unhaulable \
                        and in_range.get(tid, True):
                    # A tree that cannot be extracted has no d2 by definition;
                    # counting it here would send the reader looking for a break
                    # in the road network that is not there.
                    null_d2 += 1
                if not in_range.get(tid, True):
                    add_to(OUT, tid, float(f["d1"]))
                    continue
                # The geometric mean keeps the unextractable trees, as in
                # 0.2.0: it is what the block looks like before the model.
                if "d1_geom" in field_names and f["d1_geom"] is not None:
                    d1_geom_vals.append(float(f["d1_geom"]))
                if f["d1"] is None:
                    add_to(BLOCKED, tid)
                    continue
                d1_vals.append(float(f["d1"]))
                if "d1_slope" in field_names and f["d1_slope"] is not None:
                    d1_slope_vals.append(float(f["d1_slope"]))
                if d2 is None:
                    add_to(UNROUTED, tid, float(f["d1"]))
                else:
                    d2_vals.append(float(d2))
                    add_to(f["landing_fid"], tid, float(f["d1"]), float(d2))

            d1_mean = (sum(d1_vals) / len(d1_vals)) if d1_vals else None
            d2_mean = (sum(d2_vals) / len(d2_vals)) if d2_vals else None
            d1_slope_mean = (sum(d1_slope_vals) / len(d1_slope_vals)) \
                if d1_slope_vals else None
            # Same trees as the means: in range, extractable, and for d2 reachable.
            d1_max = max(d1_vals) if d1_vals else None
            d2_max = max(d2_vals) if d2_vals else None
            # With the model on, the plain geometric d1 is reported next to it:
            # the drop is the whole point of the model and should be visible in
            # one run rather than asserted.
            d1_geom_mean = (sum(d1_geom_vals) / len(d1_geom_vals)) if d1_geom_vals else None

            if d2_mean is None:
                feedback.reportError(self.tr(
                    "WARNING: d2_mean is None — no grid points could be routed to any landing. "
                    "Check that the road network is connected and the snapping tolerance is sufficient."
                ), fatalError=False)

            def fmt(val, unit="m"):
                return f"{val:.1f} {unit}" if val is not None else "N/A"

            # State the assumptions in the report itself.  The model's numbers
            # only mean something next to the assumptions that produced them.
            if model_stats is not None:
                height_note = (f"樹高フィールド {height_field}" if height_field
                               else f"樹高 {tree_height:.0f} m")
                model_note = (
                    "<br><b>伐倒モデル適用</b>"
                    f"（{height_note}／許容扇形 下方向±{fell_sector:.0f}度／"
                    f"傾斜{flat_slope:.0f}度以下は全方向／直接把持 {grapple_reach:.0f} m／"
                    f"斜面方位の評価 {aspect_smooth:.0f} m）"
                    f"<br>伐倒前の幾何的な平均 d1: <b>{fmt(d1_geom_mean)}</b>"
                    f"　→　モデル適用後: <b>{fmt(d1_mean)}</b>"
                    f"（斜距離で <b>{fmt(d1_slope_mean)}</b>）"
                    f"<br>幹が作業道に達した点: {model_stats['on_road']} 点 ／ "
                    f"直接つかめる範囲: {model_stats['grapple']} 点 ／ "
                    f"集材できない点: {model_stats['blocked']} 点"
                    + (f" ／ DEM の外: {model_stats['no_terrain']} 点"
                       if model_stats.get("no_terrain") else "")
                    + ("<br>作業区域の外へは伐倒も集材もしない設定です。"
                       if area_only else "")
                    + (f"<br>集材できない {model_stats['blocked']} 点は d1・d2 とも空で、"
                       "平均から除いています。"
                       if model_stats['blocked'] else "")
                )
            else:
                model_note = ""

            if max_range > 0:
                out_g = groups.get(OUT, {"n": 0, "vol": 0.0})
                range_note = (
                    f"<br><b>集材範囲の上限</b> 斜距離 {max_range:.0f} m："
                    f"範囲外 {out_g['n']} 本"
                    + (f"（材積 {out_g['vol']:.1f} m³）" if volumes is not None else "")
                    + "。平均と土場別の集計は範囲内の木で計算しています。"
                    + (f"<br>斜距離が出せない {n_range_horizontal} 本は水平距離で"
                       "判定しました（斜距離より短いため、範囲内に数えすぎることがあります）。"
                       if n_range_horizontal else "")
                )
            else:
                range_note = ""

            # One row per landing, then the trees that reach none of them under
            # their own heading, so the rows add up to the block.
            def landing_row(label, g, note=False):
                cls = ' class="sub"' if note else ""
                d1m = fmt(sum(g["d1"]) / len(g["d1"])) if g["d1"] else "—"
                d2m = fmt(sum(g["d2"]) / len(g["d2"])) if g["d2"] else "—"
                vol = (f"<td>{g['vol']:.1f}</td>" if volumes is not None else "")
                return (f"<tr{cls}><td>{label}</td><td>{g['n']}</td>{vol}"
                        f"<td>{d1m}</td><td>{d2m}</td></tr>")

            rows_html = []
            for key in sorted(k for k in groups if isinstance(k, int)):
                rows_html.append(landing_row(f"土場 {key}", groups[key]))
            for key, label in ((OUT, "集材範囲外"), (UNROUTED, "土場に到達できない"),
                               (BLOCKED, "集材できない")):
                if key in groups:
                    rows_html.append(landing_row(label, groups[key], note=True))
            all_g = {"n": sum(g["n"] for g in groups.values()),
                     "vol": sum(g["vol"] for g in groups.values()),
                     "d1": [], "d2": []}
            rows_html.append(landing_row("合計", all_g).replace(
                "<tr>", '<tr class="total">', 1))
            vol_head = "<th>材積 (m³)</th>" if volumes is not None else ""
            landing_table = (
                "<h3>土場別の集材量</h3>"
                "<table class=\"grid\"><tr><th>土場</th><th>本数</th>"
                f"{vol_head}<th>平均 d1</th><th>平均 d2</th></tr>"
                + "".join(rows_html) + "</table>"
                + (f"<p class=\"note\">材積が空または負の {n_no_volume} 本は 0 m³ として"
                   "合計しています。</p>" if volumes is not None and n_no_volume else "")
                + ("" if volumes is not None else
                   "<p class=\"note\">材積は、単木ポイントに材積フィールドを"
                   "指定すると集計されます。</p>")
            )

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
  h3 {{ color: #2e6b2e; margin-top: 1.5em; }}
  table.grid {{ margin-top: 0.5em; }}
  table.grid th, table.grid td {{ border-bottom: 1px solid #ddd;
    padding: 0.3em 1.2em 0.3em 0; text-align: right; }}
  table.grid th:first-child, table.grid td:first-child {{ text-align: left; }}
  table.grid tr.sub td {{ color: #888; }}
  table.grid tr.total td {{ font-weight: bold; border-top: 2px solid #999; }}
</style>
</head>
<body>
<h2>Harvest Accessibility — Result</h2>
<table>
  <tr>
    <td><span class="label">平均木寄せ距離 (d1)</span><br>
        <span class="val">{fmt(d1_mean)}</span><br>
        <span class="label">最大 {fmt(d1_max)}</span></td>
    <td><span class="label">平均運材距離 (d2)</span><br>
        <span class="val">{fmt(d2_mean)}</span><br>
        <span class="label">最大 {fmt(d2_max)}</span></td>
  </tr>
</table>
<p class="note">
  サンプル点数: {total} 点 ／ d2 未到達: {null_d2} 点
  {model_note}
  {range_note}
  {"<br><b style='color:#c00'>⚠ 全点が土場に到達できませんでした。作業道の接続とスナップ許容誤差を確認してください。</b>" if d2_mean is None else ""}
</p>
{landing_table}
</body>
</html>""")

            if d1_geom_mean is not None and d1_mean is not None:
                feedback.pushInfo(
                    f"d1 geometric={d1_geom_mean:.3f}m -> model={d1_mean:.3f}m"
                )
            feedback.pushInfo(
                f"Done. d1_mean={d1_mean:.3f}m, d2_mean={d2_mean:.3f}m, "
                f"points={total}, d2_null={null_d2}"
                if d1_mean is not None and d2_mean is not None
                else f"Done. d1_mean={d1_mean}, d2_mean={d2_mean}, points={total}, d2_null={null_d2}"
            )

            results = {self.HTML_OUT: html_path}
            results.update(layer_outputs)
            return results

        except QgsProcessingException:
            raise
        except Exception as e:
            raise QgsProcessingException(
                self.tr("Unexpected error during processing: {}").format(e)
            ) from e
