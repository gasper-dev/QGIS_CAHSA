from pathlib import Path

import processing

from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .provider import ProcesarCAHSAProvider


class ProcesarCAHSAPlugin:

    def __init__(self, iface):

        self.iface = iface
        self.action = None
        self.provider = None

    def initGui(self):

        # Registrar proveedor
        self.provider = ProcesarCAHSAProvider()

        QgsApplication.processingRegistry().addProvider(
            self.provider
        )

        # Crear botón
        icon_path = (
            Path(__file__).parent /
            "icon.png"
        )

        self.action = QAction(
            QIcon(str(icon_path)),
            "Procesar Sentinel-2 · CAHSA",
            self.iface.mainWindow()
        )

        self.action.setToolTip(
            "Procesar Sentinel-2 · CAHSA"
        )

        self.action.triggered.connect(
            self.run
        )

        # Agregar botón
        self.iface.addToolBarIcon(
            self.action
        )

        # Agregar al menú Complementos
        self.iface.addPluginToMenu(
            "Procesar CAHSA",
            self.action
        )

    def run(self):

        algorithm_id = (
            "procesar_cahsa:procesar_cahsa"
        )

        algorithm = (
            QgsApplication
            .processingRegistry()
            .algorithmById(
                algorithm_id
            )
        )

        if algorithm is None:

            self.iface.messageBar().pushCritical(
                "Procesar CAHSA",
                "No se encontró el algoritmo."
            )

            return

        try:

            processing.execAlgorithmDialog(
                algorithm_id
            )

        except Exception as e:

            self.iface.messageBar().pushCritical(
                "Procesar CAHSA",
                f"No se pudo abrir el algoritmo: {e}"
            )

    def unload(self):

        # Quitar botón
        if self.action is not None:

            self.iface.removeToolBarIcon(
                self.action
            )

            self.iface.removePluginMenu(
                "Procesar CAHSA",
                self.action
            )

            self.action.deleteLater()

            self.action = None

        # Quitar proveedor
        if self.provider is not None:

            QgsApplication.processingRegistry().removeProvider(
                self.provider
            )

            self.provider = None