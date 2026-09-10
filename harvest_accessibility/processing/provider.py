import os
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon
from .harvest_accessibility_alg import HarvestAccessibilityAlg


class HarvestAccessibilityProvider(QgsProcessingProvider):
    def id(self):
        return "harvestaccessibility"

    def name(self):
        return "Harvest Accessibility"

    def longName(self):
        return "Harvest Accessibility — Forestry Road Network Analysis"

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "..", "icon.png")
        return QIcon(icon_path)

    def loadAlgorithms(self):
        self.addAlgorithm(HarvestAccessibilityAlg())
