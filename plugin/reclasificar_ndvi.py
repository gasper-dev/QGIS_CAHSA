from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterMatrix,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterRasterDestination,
    QgsProcessingException,
)
import processing


class ReclasificarNDVIAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    BAND = "BAND"
    TABLE = "TABLE"
    NO_DATA = "NO_DATA"
    RANGE_BOUNDARIES = "RANGE_BOUNDARIES"
    NODATA_FOR_MISSING = "NODATA_FOR_MISSING"
    OUTPUT = "OUTPUT"

    # Tabla predeterminada: mínimo, máximo, nuevo valor
    DEFAULT_TABLE = [
        -0.663717, 0.0, 1,
        0.0, 0.2, 2,
        0.2, 0.3, 3,
        0.3, 0.4, 4,
        0.4, 0.5, 5,
        0.5, 0.55, 6,
        0.55, 0.6, 7,
        0.6, 0.65, 8,
        0.65, 0.7, 9,
        0.7, 0.75, 10,
        0.75, 0.8, 11,
        0.8, 0.85, 12,
        0.85, 0.9, 13,
        0.9, 1.0, 14,
    ]

    def initAlgorithm(self, config=None):

        # ─────────────────────────────────────────────
        # RÁSTER NDVI DE ENTRADA
        # ─────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                "Ráster NDVI de entrada"
            )
        )

        # ─────────────────────────────────────────────
        # BANDA DEL RÁSTER
        # ─────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterBand(
                self.BAND,
                "Banda del ráster",
                defaultValue=1,
                parentLayerParameterName=self.INPUT
            )
        )

        # ─────────────────────────────────────────────
        # TABLA DE RECLASIFICACIÓN
        # ─────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterMatrix(
                self.TABLE,
                "Tabla de reclasificación (Mínimo, Máximo, Valor)",
                headers=["Mínimo", "Máximo", "Nuevo valor"],
                defaultValue=self.DEFAULT_TABLE
            )
        )

        # ─────────────────────────────────────────────
        # VALOR NODATA
        # ─────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterNumber(
                self.NO_DATA,
                "Valor NoData de salida",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=-9999.0
            )
        )

        # ─────────────────────────────────────────────
        # LÍMITES DE RANGO
        # ─────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterEnum(
                self.RANGE_BOUNDARIES,
                "Límites de rango",
                options=[
                    "mín < valor <= máx (0)",
                    "mín <= valor < máx (1)",
                    "mín <= valor <= máx (2)",
                    "mín < valor < máx (3)"
                ],
                defaultValue=0
            )
        )

        # ─────────────────────────────────────────────
        # TRATAMIENTO DE VALORES FUERA DE RANGO
        # ─────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.NODATA_FOR_MISSING,
                "Asignar NoData si no coincide ningún rango",
                defaultValue=True
            )
        )

        # ─────────────────────────────────────────────
        # SALIDA RECLASIFICADA
        # ─────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "Ráster reclasificado (Reclass_NDVI)"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        # Obtener parámetros
        input_layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        if input_layer is None:
            raise QgsProcessingException("No se pudo cargar el ráster de entrada.")

        band = self.parameterAsInt(parameters, self.BAND, context)
        table_param = self.parameterAsMatrix(parameters, self.TABLE, context)
        nodata = self.parameterAsDouble(parameters, self.NO_DATA, context)
        range_boundaries = self.parameterAsEnum(parameters, self.RANGE_BOUNDARIES, context)
        nodata_for_missing = self.parameterAsBoolean(parameters, self.NODATA_FOR_MISSING, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        feedback.pushInfo("==================================================")
        feedback.pushInfo("RECLASIFICACIÓN DE NDVI")
        feedback.pushInfo("==================================================")
        feedback.pushInfo(f"Ráster de entrada: {input_layer.name()}")
        feedback.pushInfo(f"Banda a procesar: {band}")

        # Normalizar matriz / tabla a lista plana de números float
        flat_table = []
        if table_param:
            if isinstance(table_param, list):
                for row in table_param:
                    if isinstance(row, (list, tuple)):
                        for val in row:
                            try:
                                flat_table.append(float(val))
                            except (ValueError, TypeError):
                                pass
                    else:
                        try:
                            flat_table.append(float(row))
                        except (ValueError, TypeError):
                            pass

        if not flat_table:
            flat_table = [float(x) for x in self.DEFAULT_TABLE]

        if len(flat_table) % 3 != 0:
            raise QgsProcessingException(
                f"La tabla de reclasificación no es válida. Debe contener filas de 3 valores (Mínimo, Máximo, Nuevo valor). Elementos encontrados: {len(flat_table)}."
            )

        feedback.pushInfo(f"Total de rangos a aplicar: {len(flat_table) // 3}")
        feedback.pushInfo("Ejecutando algoritmo 'native:reclassifybytable'...")

        resultado = processing.run(
            "native:reclassifybytable",
            {
                "INPUT_RASTER": parameters[self.INPUT],
                "RASTER_BAND": band,
                "TABLE": flat_table,
                "NO_DATA": nodata,
                "RANGE_BOUNDARIES": range_boundaries,
                "NODATA_FOR_MISSING": nodata_for_missing,
                "DATA_TYPE": 5,  # Float32
                "OUTPUT": output,
            },
            context=context,
            feedback=feedback,
        )

        output_path = resultado.get("OUTPUT", output)

        # Configurar nombre de la capa resultante en QGIS
        if context.willLoadLayerOnCompletion(self.OUTPUT):
            details = context.layerToLoadOnCompletionDetails(self.OUTPUT)
            details.name = "Reclass_NDVI"

        feedback.pushInfo("==================================================")
        feedback.pushInfo("RECLASIFICACIÓN COMPLETADA")
        feedback.pushInfo("==================================================")
        feedback.pushInfo(f"Archivo generado: {output_path}")

        return {self.OUTPUT: output_path}

    def name(self):
        return "reclasificar_ndvi"

    def displayName(self):
        return "Reclasificar NDVI"

    def group(self):
        return "Sentinel-2"

    def groupId(self):
        return "sentinel2_cahsa"

    def shortHelpString(self):
        return (
            "Reclasifica un ráster NDVI utilizando una tabla de rangos predeterminada "
            "(14 clases) o personalizada en clases discretas."
        )

    def createInstance(self):
        return ReclasificarNDVIAlgorithm()