"""Write a DEM for an operation area to a file, from published elevation tiles.

The main algorithm can fetch its own DEM, so this exists for the cases where a
file is what you want: reusing one DEM across many runs or projects, inspecting
or editing it, or preparing one for a machine that has no network access.
"""

import math
import urllib.error
import urllib.request

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterEnum,
    QgsProcessingParameterCrs,
    QgsProcessingParameterNumber,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterRasterDestination,
    QgsProcessingException,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis import processing

from . import tiles


class FetchDemAlg(QgsProcessingAlgorithm):
    EXTENT_SOURCE = "EXTENT_SOURCE"
    SOURCE = "SOURCE"
    ZOOM = "ZOOM"
    MARGIN = "MARGIN"
    RESOLUTION = "RESOLUTION"
    TARGET_CRS = "TARGET_CRS"
    OUTPUT = "OUTPUT"

    def tr(self, string):
        return QCoreApplication.translate("FetchDemAlg", string)

    def name(self):
        return "fetch_dem"

    def displayName(self):
        return self.tr("Fetch DEM from elevation tiles")

    def group(self):
        return self.tr("Harvest Accessibility")

    def groupId(self):
        return "harvest_accessibility"

    def createInstance(self):
        return FetchDemAlg()

    def shortHelpString(self):
        return self.tr(
            "Downloads published elevation tiles covering an operation area and "
            "writes a DEM in the layer's own CRS, or in the CRS you choose. An "
            "area drawn in degrees needs one chosen -- the CRS of the survey "
            "data, for instance -- because the margin and the resolution are "
            "in metres.\n\n"
            "The main algorithm can fetch its own DEM, so use this when you want "
            "the file itself: to reuse one DEM across runs, to inspect or edit "
            "it, or to prepare one for a machine without network access.\n\n"
            "The DEM is reprojected out of web mercator before being written. "
            "That is not cosmetic -- slope computed on mercator tiles comes out "
            "roughly 20% too gentle at these latitudes.\n\n"
            "Sources: 静岡県 VIRTUAL SHIZUOKA / 産業技術総合研究所 シームレス標高タイル "
            "(CC BY 4.0). Credit the source when you publish results."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.EXTENT_SOURCE,
            self.tr("Operation area (extent to cover)"),
            [QgsProcessing.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.SOURCE,
            self.tr("Tile source"),
            options=[s[0] for s in tiles.SOURCES],
            defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr("Output resolution (m; 0 = the tile's own resolution)"),
            QgsProcessingParameterNumber.Double,
            defaultValue=0.0, minValue=0.0
        ))
        # Only needed when the area is not already in metres.  Chosen by the
        # user rather than guessed: a UTM zone worked out from the centroid
        # would give a DEM in a CRS nobody asked for.
        self.addParameter(QgsProcessingParameterCrs(
            self.TARGET_CRS,
            self.tr("DEM CRS (empty = the operation area's own)"),
            optional=True
        ))
        margin = QgsProcessingParameterNumber(
            self.MARGIN,
            self.tr("Margin around the area (m)"),
            QgsProcessingParameterNumber.Double,
            defaultValue=60.0, minValue=0.0
        )
        zoom = QgsProcessingParameterNumber(
            self.ZOOM,
            self.tr("Zoom level (0 = use the source maximum)"),
            QgsProcessingParameterNumber.Integer,
            defaultValue=0, minValue=0, maxValue=20
        )
        for param in (margin, zoom):
            param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(param)

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, self.tr("DEM")
        ))

    def processAlgorithm(self, parameters, context: QgsProcessingContext,
                         feedback: QgsProcessingFeedback):
        source = self.parameterAsSource(parameters, self.EXTENT_SOURCE, context)
        if source is None:
            raise QgsProcessingException(self.tr("Invalid extent layer."))
        idx = self.parameterAsEnum(parameters, self.SOURCE, context)
        zoom = self.parameterAsInt(parameters, self.ZOOM, context)
        margin = self.parameterAsDouble(parameters, self.MARGIN, context)
        res = self.parameterAsDouble(parameters, self.RESOLUTION, context)
        out_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        src_crs = source.sourceCrs()
        dem_crs = self.parameterAsCrs(parameters, self.TARGET_CRS, context)
        if not dem_crs.isValid():
            dem_crs = src_crs
        if dem_crs.isGeographic() or dem_crs.mapUnits() != QgsUnitTypes.DistanceMeters:
            raise QgsProcessingException(self.tr(
                "The DEM would be written in {crs}, which is not a projected CRS "
                "in metres, so the margin and the resolution would not mean "
                "metres. Set 'DEM CRS' to one that is -- the CRS of the survey "
                "data or of the forest roads, for instance."
            ).format(crs=dem_crs.authid()))

        # The margin is added in the DEM's CRS, where it is metres.
        ext = source.sourceExtent()
        if dem_crs != src_crs:
            ext = QgsCoordinateTransform(src_crs, dem_crs, QgsProject.instance()) \
                .transformBoundingBox(ext)
        ext = QgsRectangle(ext.xMinimum() - margin, ext.yMinimum() - margin,
                           ext.xMaximum() + margin, ext.yMaximum() + margin)
        wgs = QgsCoordinateReferenceSystem("EPSG:4326")
        ll = QgsCoordinateTransform(dem_crs, wgs, QgsProject.instance()) \
            .transformBoundingBox(ext)

        try:
            path = tiles.build_dem(
                (ll.xMinimum(), ll.yMinimum(), ll.xMaximum(), ll.yMaximum()),
                idx, zoom, dem_crs.toWkt(), dem_crs.authid(),
                resolution=res, out_path=out_path, use_cache=False,
                log=feedback.pushInfo,
                progress=feedback.setProgress,
                cancelled=feedback.isCanceled,
            )
        except tiles.TileError as exc:
            raise QgsProcessingException(str(exc))
        return {self.OUTPUT: path}
