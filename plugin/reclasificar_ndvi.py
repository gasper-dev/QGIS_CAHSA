import os
import csv
import processing

from osgeo import gdal

from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterRasterDestination,
    QgsProcessingException,
    QgsProcessingLayerPostProcessorInterface,
    QgsColorRampShader,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsUnitTypes,
)


class NDVIPostProcessor(QgsProcessingLayerPostProcessorInterface):

    def __init__(self, classes, colors):
        super().__init__()
        self.classes = classes
        self.colors = colors

    def postProcessLayer(self, layer, context, feedback):
        if not layer.isValid():
            return

        shader = QgsRasterShader()
        color_shader = QgsColorRampShader()
        color_shader.setColorRampType(
            QgsColorRampShader.Discrete
        )

        items = []

        for index, (_, _, value) in enumerate(self.classes):
            items.append(
                QgsColorRampShader.ColorRampItem(
                    float(value),
                    QColor(self.colors[index]),
                    f"Clase {value}"
                )
            )

        color_shader.setColorRampItemList(items)
        shader.setRasterShaderFunction(color_shader)

        renderer = QgsSingleBandPseudoColorRenderer(
            layer.dataProvider(), 1, shader
        )

        layer.setRenderer(renderer)
        layer.triggerRepaint()


class ReclasificarNDVIAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    BAND = "BAND"
    OUTPUT = "OUTPUT"

    CLASSES = [
        (-0.663717, 0.0, 1),
        (0.0, 0.2, 2),
        (0.2, 0.3, 3),
        (0.3, 0.4, 4),
        (0.4, 0.5, 5),
        (0.5, 0.55, 6),
        (0.55, 0.6, 7),
        (0.6, 0.65, 8),
        (0.65, 0.7, 9),
        (0.7, 0.75, 10),
        (0.75, 0.8, 11),
        (0.8, 0.85, 12),
        (0.85, 0.9, 13),
        (0.9, 1.0, 14),
    ]

    COLORS = [
        "#8c510a",
        "#d8b365",
        "#f6e8c3",
        "#c7eae5",
        "#80cdc1",
        "#5ab4ac",
        "#35978f",
        "#01665e",
        "#1a9850",
        "#66bd63",
        "#a6d96a",
        "#d9ef8b",
        "#4dac26",
        "#006837",
    ]

    def name(self):
        return "reclasificar_ndvi"

    def displayName(self):
        return "Reclasificar NDVI + tabla de clases"

    def group(self):
        return "Sentinel-2"

    def groupId(self):
        return "sentinel2_cahsa"

    def shortHelpString(self):
        return (
            "Reclasifica un NDVI en 14 clases, aplica simbología "
            "y genera estadísticas por clase en CSV y una RAT "
            "cuando el formato de salida lo permite."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                "Ráster NDVI de entrada"
            )
        )

        self.addParameter(
            QgsProcessingParameterBand(
                self.BAND,
                "Banda del ráster",
                defaultValue=1,
                parentLayerParameterName=self.INPUT
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "Ráster reclasificado"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        raster = self.parameterAsRasterLayer(
            parameters, self.INPUT, context
        )
        band = self.parameterAsInt(
            parameters, self.BAND, context
        )
        output = self.parameterAsOutputLayer(
            parameters, self.OUTPUT, context
        )

        if raster is None or not raster.isValid():
            raise QgsProcessingException(
                "El ráster de entrada no es válido."
            )

        # 1. Reclasificar el NDVI.
        feedback.pushInfo("1/4 Reclasificando NDVI...")

        table = [
            value
            for minimum, maximum, category in self.CLASSES
            for value in (minimum, maximum, category)
        ]

        result = processing.run(
            "native:reclassifybytable",
            {
                "INPUT_RASTER": raster,
                "RASTER_BAND": band,
                "TABLE": table,
                "NO_DATA": -9999,
                "RANGE_BOUNDARIES": 0,
                "NODATA_FOR_MISSING": True,
                "DATA_TYPE": 1,
                "OUTPUT": output,
            },
            context=context,
            feedback=feedback,
        )

        output_path = result["OUTPUT"]

        # 2. Leer el ráster y calcular estadísticas.
        feedback.pushInfo("2/4 Calculando estadísticas...")

        dataset = gdal.Open(output_path, gdal.GA_Update)

        if dataset is None:
            raise QgsProcessingException(
                "No se pudo abrir el ráster de salida."
            )

        raster_band = dataset.GetRasterBand(1)
        array = raster_band.ReadAsArray()
        nodata = raster_band.GetNoDataValue()

        valid = array >= 1
        valid &= array <= 14

        if nodata is not None:
            valid &= array != nodata

        values = array[valid]
        total_pixels = int(values.size)

        if total_pixels == 0:
            dataset = None
            raise QgsProcessingException(
                "No hay píxeles clasificados entre 1 y 14."
            )

        unique, counts = __import__("numpy").unique(
            values, return_counts=True
        )

        counts_by_class = {
            int(value): int(count)
            for value, count in zip(unique, counts)
        }

        # Área del píxel usando el determinante de la transformación.
        transform = dataset.GetGeoTransform()

        pixel_area = abs(
            transform[1] * transform[5]
            - transform[2] * transform[4]
        )

        # Compatible con QGIS 4: comprobar unidades, no isProjected().
        crs = raster.crs()
        area_factor = None

        if crs.isValid():
            units = crs.mapUnits()

            supported_units = (
                QgsUnitTypes.DistanceMeters,
                QgsUnitTypes.DistanceFeet,
                QgsUnitTypes.DistanceYards,
                QgsUnitTypes.DistanceMiles,
            )

            if units in supported_units:
                factor = QgsUnitTypes.fromUnitToUnitFactor(
                    units,
                    QgsUnitTypes.DistanceMeters
                )

                area_factor = pixel_area * factor**2 / 10000

        # 3. Crear tabla CSV.
        feedback.pushInfo("3/4 Generando tabla CSV...")

        csv_path = (
            os.path.splitext(output_path)[0]
            + "_tabla.csv"
        )

        headers = [
            "Clase",
            "NDVI_minimo",
            "NDVI_maximo",
            "Pixeles",
            "Area_ha",
            "Porcentaje",
        ]

        with open(
            csv_path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=headers
            )
            writer.writeheader()

            for minimum, maximum, category in self.CLASSES:
                count = counts_by_class.get(category, 0)

                area_ha = (
                    round(count * area_factor, 6)
                    if area_factor is not None
                    else ""
                )

                writer.writerow({
                    "Clase": category,
                    "NDVI_minimo": minimum,
                    "NDVI_maximo": maximum,
                    "Pixeles": count,
                    "Area_ha": area_ha,
                    "Porcentaje": round(
                        count * 100 / total_pixels, 4
                    ),
                })

        # 4. Guardar tabla de atributos raster (RAT).
        feedback.pushInfo("4/4 Guardando tabla RAT...")

        try:
            rat = gdal.RasterAttributeTable()

            rat.CreateColumn(
                "Clase", gdal.GFT_Integer, gdal.GFU_MinMax
            )
            rat.CreateColumn(
                "NDVI_minimo", gdal.GFT_Real, gdal.GFU_Min
            )
            rat.CreateColumn(
                "NDVI_maximo", gdal.GFT_Real, gdal.GFU_Max
            )
            rat.CreateColumn(
                "Pixeles", gdal.GFT_Integer, gdal.GFU_PixelCount
            )
            rat.CreateColumn(
                "Area_ha", gdal.GFT_Real, gdal.GFU_Generic
            )
            rat.CreateColumn(
                "Porcentaje", gdal.GFT_Real, gdal.GFU_Generic
            )
            rat.CreateColumn(
                "Red", gdal.GFT_Integer, gdal.GFU_Red
            )
            rat.CreateColumn(
                "Green", gdal.GFT_Integer, gdal.GFU_Green
            )
            rat.CreateColumn(
                "Blue", gdal.GFT_Integer, gdal.GFU_Blue
            )

            rat.SetRowCount(len(self.CLASSES))

            for row, (minimum, maximum, category) in enumerate(
                self.CLASSES
            ):
                count = counts_by_class.get(category, 0)
                color = QColor(self.COLORS[row])

                rat.SetValueAsInt(row, 0, category)
                rat.SetValueAsDouble(row, 1, minimum)
                rat.SetValueAsDouble(row, 2, maximum)
                rat.SetValueAsInt(row, 3, count)

                if area_factor is not None:
                    rat.SetValueAsDouble(
                        row, 4, count * area_factor
                    )

                rat.SetValueAsDouble(
                    row, 5, count * 100 / total_pixels
                )

                rat.SetValueAsInt(row, 6, color.red())
                rat.SetValueAsInt(row, 7, color.green())
                rat.SetValueAsInt(row, 8, color.blue())

            raster_band.SetDefaultRAT(rat)
            raster_band.FlushCache()

        except Exception as error:
            feedback.pushWarning(
                "No se pudo guardar la RAT dentro del GeoTIFF: "
                f"{error}. La tabla CSV sí se generó."
            )

        dataset = None

        # Aplicar simbología a la capa que cargue Processing.
        if context.willLoadLayerOnCompletion(self.OUTPUT):
            details = context.layerToLoadOnCompletionDetails(
                self.OUTPUT
            )
            details.name = "Reclass_NDVI"
            details.setPostProcessor(
                NDVIPostProcessor(
                    self.CLASSES,
                    self.COLORS
                )
            )

        feedback.pushInfo(f"Ráster generado: {output_path}")
        feedback.pushInfo(f"Tabla generada: {csv_path}")

        if area_factor is None:
            feedback.pushWarning(
                "No se calcularon hectáreas: unidades CRS no compatibles."
            )

        return {self.OUTPUT: output_path}

    def createInstance(self):
        return ReclasificarNDVIAlgorithm()