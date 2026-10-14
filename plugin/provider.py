from qgis.core import QgsProcessingProvider

from .procesar_cahsa import ProcesarCAHSAAlgorithm
from .pintar_mapas_cahsa import PintarMapasAlgorithm
from .reclasificar_ndvi import ReclasificarNDVIAlgorithm

class ProcesarCAHSAProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(ProcesarCAHSAAlgorithm())
        self.addAlgorithm(PintarMapasAlgorithm())
        self.addAlgorithm(ReclasificarNDVIAlgorithm())

    def id(self):
        return "procesar_cahsa"

    def name(self):
        return "Procesar Sentinel-2"

    def longName(self):
        return "Procesar Sentinel-2"
