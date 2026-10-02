from qgis.core import QgsProcessingProvider

from .procesar_cahsa import ProcesarCAHSAAlgorithm


class ProcesarCAHSAProvider(QgsProcessingProvider):

    def loadAlgorithms(self):

        self.addAlgorithm(
            ProcesarCAHSAAlgorithm()
        )

    def id(self):
        return "procesar_cahsa"

    def name(self):
        return "Procesar CAHSA"

    def longName(self):
        return "Procesamiento Sentinel-2 · CAHSA"