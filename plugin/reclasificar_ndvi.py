import csv
import os
import tempfile

from osgeo import gdal
import numpy as np
import processing

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterFileDestination,
)


class ReclasificarNDVIAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    TABLE = "TABLE"

    def name(self):
        return "reclasificar_ndvi"

    def displayName(self):
        return "Reclasificar NDVI con tabla de atributos"

    def group(self):
        return "Sentinel-2"

    def groupId(self):
        return "sentinel2_cahsa"

    def shortHelpString(self):
        return (
            "Reclasifica un ráster NDVI en 14 clases, genera un ráster entero "
            "y crea una tabla con OBJECTID, Value y Count (formato CSV e integrada "
            "en el GeoTIFF como tabla de atributos RAT)."
        )

    def createInstance(self):
        return ReclasificarNDVIAlgorithm()

    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                "Ráster NDVI de entrada"
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "Ráster reclasificado de salida (Reclass_NDVI)"
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.TABLE,
                "Tabla de atributos CSV (Opcional)",
                "CSV files (*.csv)",
                optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        raster = self.parameterAsRasterLayer(
            parameters, self.INPUT, context
        )

        output_path = self.parameterAsOutputLayer(
            parameters, self.OUTPUT, context
        )

        csv_path = self.parameterAsFileOutput(
            parameters, self.TABLE, context
        )

        if raster is None:
            raise QgsProcessingException(
                "No se pudo cargar el ráster NDVI de entrada."
            )

        # Intervalos de reclasificación:
        # [mínimo, máximo, valor asignado]
        tabla = [
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
            0.9, 1.0, 14
        ]

        feedback.pushInfo("Iniciando reclasificación NDVI...")

        # Reclasificar el ráster
        processing.run(
            "native:reclassifybytable",
            {
                "INPUT_RASTER": raster,
                "RASTER_BAND": 1,
                "TABLE": tabla,
                "NO_DATA": -9999,
                "RANGE_BOUNDARIES": 0,
                "NODATA_FOR_MISSING": True,
                "DATA_TYPE": 1,  # Int16
                "OUTPUT": output_path,
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )

        feedback.pushInfo(
            "Reclasificación terminada. Calculando frecuencias..."
        )

        # Abrir el ráster de salida para leerlo y cerrarlo inmediatamente
        dataset = gdal.Open(output_path, gdal.GA_ReadOnly)

        if dataset is None:
            raise QgsProcessingException(
                f"No se pudo abrir el ráster reclasificado: {output_path}"
            )

        try:
            band = dataset.GetRasterBand(1)
            array = band.ReadAsArray()
            nodata = band.GetNoDataValue()
        finally:
            band = None
            dataset = None

        # Excluir NoData, -9999 y valores no finitos
        valid = np.isfinite(array)

        if nodata is not None:
            valid &= (array != nodata)

        valid &= (array != -9999)

        values = array[valid]

        if values.size == 0:
            raise QgsProcessingException(
                "El ráster no contiene píxeles válidos clasificados. "
                "Verifica los valores NDVI de entrada y los intervalos."
            )

        # Obtener los valores existentes y su frecuencia
        unique_values, pixel_counts = np.unique(
            values.astype(np.int64),
            return_counts=True
        )

        counts_by_class = {
            int(value): int(count)
            for value, count in zip(unique_values, pixel_counts)
        }

        feedback.pushInfo(
            "Valores encontrados: "
            + str(unique_values[:30].tolist())
        )

        # Preparar las 15 filas: Value de 0 a 14
        rows = []

        for value in range(15):
            rows.append(
                (
                    value + 1,                    # OBJECTID: 1–15
                    value,                        # Value: 0–14
                    counts_by_class.get(value, 0) # Count
                )
            )

        # Si no se especificó ruta para el CSV, generarla automáticamente
        if not csv_path:
            if output_path and output_path != "TEMPORARY_OUTPUT":
                base, _ = os.path.splitext(output_path)
                csv_path = base + "_tabla.csv"
            else:
                csv_path = os.path.join(tempfile.gettempdir(), "Reclass_NDVI_tabla.csv")

        csv_directory = os.path.dirname(csv_path)
        if csv_directory:
            os.makedirs(csv_directory, exist_ok=True)

        with open(
            csv_path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([
                "OBJECTID",
                "Value",
                "Count"
            ])
            writer.writerows(rows)

        feedback.pushInfo(
            "Tabla CSV creada: " + csv_path
        )

        # Intentar guardar la tabla de atributos dentro del GeoTIFF
        update_dataset = gdal.Open(
            output_path,
            gdal.GA_Update
        )

        if update_dataset is None:
            feedback.pushWarning(
                "No se pudo abrir el GeoTIFF para escribir la tabla "
                "de atributos. El CSV sí se ha generado."
            )
        else:
            output_band = None
            try:
                output_band = update_dataset.GetRasterBand(1)

                rat = gdal.RasterAttributeTable()

                rat.CreateColumn(
                    "OBJECTID",
                    gdal.GFT_Integer,
                    gdal.GFU_Generic
                )

                rat.CreateColumn(
                    "Value",
                    gdal.GFT_Integer,
                    gdal.GFU_Generic
                )

                rat.CreateColumn(
                    "Count",
                    gdal.GFT_Integer,
                    gdal.GFU_PixelCount
                )

                rat.SetRowCount(15)

                for row_index, (objectid, value, count) in enumerate(rows):
                    rat.SetValueAsInt(row_index, 0, objectid)
                    rat.SetValueAsInt(row_index, 1, value)
                    rat.SetValueAsInt(row_index, 2, count)

                output_band.SetDefaultRAT(rat)
                output_band.FlushCache()
                update_dataset.FlushCache()

                feedback.pushInfo(
                    "Tabla de atributos integrada en el GeoTIFF."
                )

            except Exception as error:
                feedback.pushWarning(
                    "No se pudo integrar la tabla de atributos: "
                    + str(error)
                    + ". El CSV permanece disponible."
                )

            finally:
                output_band = None
                update_dataset = None

        # Asignar nombre a la capa de salida cuando se cargue en QGIS
        if context.willLoadLayerOnCompletion(self.OUTPUT):
            details = context.layerToLoadOnCompletionDetails(self.OUTPUT)
            details.name = "Reclass_NDVI"

        feedback.pushInfo(
            "Proceso terminado correctamente."
        )

        return {
            self.OUTPUT: output_path,
            self.TABLE: csv_path
        }


# Alias de clase para compatibilidad
ReclassNDVI = ReclasificarNDVIAlgorithm
