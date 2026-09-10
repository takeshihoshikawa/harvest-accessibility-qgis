import os

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QTranslator, QCoreApplication
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .processing.provider import HarvestAccessibilityProvider


def tr(string):
    return QCoreApplication.translate("HarvestAccessibilityPlugin", string)


class HarvestAccessibilityPlugin:
    """QGIS plugin entry point.

    Registers a Processing provider and adds a menu entry and toolbar icon.
    """

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.translator = None
        self._load_translation()

    def _load_translation(self):
        locale = QgsApplication.locale()[:2]  # e.g. "ja"
        locale_path = os.path.join(
            os.path.dirname(__file__), "i18n",
            f"harvest_accessibility_{locale}.qm"
        )
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        self.provider = HarvestAccessibilityProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) \
            else QgsApplication.getThemeIcon("/processingAlgorithm.svg")

        self.action = QAction(icon, tr("Run…"), self.iface.mainWindow())
        self.action.triggered.connect(self._open_dialog)

        self.iface.addPluginToMenu(tr("Harvest Accessibility"), self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu(tr("Harvest Accessibility"), self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        if self.translator is not None:
            QCoreApplication.removeTranslator(self.translator)

    def _open_dialog(self):
        from qgis import processing
        processing.execAlgorithmDialog("harvestaccessibility:harvest_accessibility")
