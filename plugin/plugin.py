from pathlib import Path

import processing

from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import QAction, QDialog, QVBoxLayout, QPushButton, QLabel
from qgis.PyQt.QtGui import QIcon

from .provider import ProcesarCAHSAProvider

class SelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opciones")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout()
        label = QLabel("Seleccione la herramienta a ejecutar:")
        layout.addWidget(label)
        
        self.btn_procesar = QPushButton("Procesar Sentinel-2")
        self.btn_pintar = QPushButton("Pintar Mapas")
        
        layout.addWidget(self.btn_procesar)
        layout.addWidget(self.btn_pintar)
        self.setLayout(layout)


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
            "Procesar Sentinel-2",
            self.iface.mainWindow()
        )

        self.action.setToolTip(
            "Procesar Sentinel-2"
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
            "CAHSA",
            self.action
        )

    def run(self):

        dialog = SelectionDialog(self.iface.mainWindow())

        def run_algo(alg_id):
            dialog.accept()
            algorithm = QgsApplication.processingRegistry().algorithmById(alg_id)
            if algorithm is None:
                self.iface.messageBar().pushCritical(
                    "CAHSA",
                    f"No se encontró el algoritmo: {alg_id}"
                )
                return

            try:
                processing.execAlgorithmDialog(alg_id)
            except Exception as e:
                self.iface.messageBar().pushCritical(
                    "CAHSA",
                    f"No se pudo abrir el algoritmo: {e}"
                )

        dialog.btn_procesar.clicked.connect(
            lambda: run_algo("procesar_cahsa:procesar_cahsa")
        )
        dialog.btn_pintar.clicked.connect(
            lambda: run_algo("procesar_cahsa:pintar_mapas")
        )

        dialog.exec()

    def unload(self):

        # Quitar botón
        if self.action is not None:

            self.iface.removeToolBarIcon(
                self.action
            )

            self.iface.removePluginMenu(
                "CAHSA",
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