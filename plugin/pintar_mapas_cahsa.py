from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterString,
    QgsProcessingException,
    QgsProject,
    QgsVectorLayer,
    QgsFeatureRequest,
    QgsFeature,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsSymbol,
    QgsGeometry
)
import processing
import random

class PintarMapasAlgorithm(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    EXCEL = 'EXCEL'
    FIELD_INPUT = 'FIELD_INPUT'
    FIELD_EXCEL = 'FIELD_EXCEL'
    FIELD_PINTAR = 'FIELD_PINTAR'
    OUTPUT_NAME = 'OUTPUT_NAME'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                "Capa vectorial (Ej: cahsa.shp)",
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.EXCEL,
                "Archivo Excel (Datos a pintar)",
                [QgsProcessing.TypeVector]
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_INPUT,
                "Campo a unir (Capa vectorial)",
                None,
                self.INPUT
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_EXCEL,
                "Campo a unir (Archivo Excel)",
                None,
                self.EXCEL
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_PINTAR,
                "Columna con valores a pintar (Excel)",
                None,
                self.EXCEL
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.OUTPUT_NAME,
                "Nombre de la capa generada",
                defaultValue="Lotes_Pintados"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source_layer = self.parameterAsSource(parameters, self.INPUT, context)
        excel_layer = self.parameterAsSource(parameters, self.EXCEL, context)
        field_input = self.parameterAsString(parameters, self.FIELD_INPUT, context)
        field_excel = self.parameterAsString(parameters, self.FIELD_EXCEL, context)
        field_pintar = self.parameterAsString(parameters, self.FIELD_PINTAR, context)
        output_name = self.parameterAsString(parameters, self.OUTPUT_NAME, context)

        if source_layer is None or excel_layer is None:
            raise QgsProcessingException("No se pudo cargar las capas.")

        feedback.pushInfo("Ejecutando unión de atributos...")

        join_result = processing.run(
            "native:joinattributestable",
            {
                'INPUT': parameters[self.INPUT],
                'FIELD': field_input,
                'INPUT_2': parameters[self.EXCEL],
                'FIELD_2': field_excel,
                'FIELDS_TO_COPY': [],
                'METHOD': 1,
                'DISCARD_NONMATCHING': False,
                'PREFIX': '',
                'OUTPUT': 'memory:'
            },
            context=context,
            feedback=feedback
        )

        joined_layer = join_result['OUTPUT']
        joined_layer.setName(output_name)

        # Apply symbology
        feedback.pushInfo("Generando simbología categorizada...")
        
        # The joined field name might have a prefix or not, we assume it's exact or we find it
        target_field_name = field_pintar
        field_idx = joined_layer.fields().indexOf(target_field_name)
        if field_idx == -1:
            # Let's try finding a field that ends with target_field_name due to prefixing
            for field in joined_layer.fields():
                if field.name().endswith(target_field_name):
                    target_field_name = field.name()
                    field_idx = joined_layer.fields().indexOf(target_field_name)
                    break
                    
        if field_idx != -1:
            unique_values = set()
            for feat in joined_layer.getFeatures():
                val = feat[target_field_name]
                if val:
                    unique_values.add(str(val))

            categories = []
            for value in unique_values:
                symbol = QgsSymbol.defaultSymbol(joined_layer.geometryType())
                # Random color
                color = random.choice(["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#ffa500", "#800080"])
                # In QGIS python, QColor can take hex string
                from qgis.PyQt.QtGui import QColor
                symbol.setColor(QColor(color))
                category = QgsRendererCategory(value, symbol, str(value))
                categories.append(category)

            renderer = QgsCategorizedSymbolRenderer(target_field_name, categories)
            joined_layer.setRenderer(renderer)
            joined_layer.triggerRepaint()
        else:
            feedback.reportError(f"No se encontró el campo a pintar: {field_pintar}")

        QgsProject.instance().addMapLayer(joined_layer)

        return {}

    def name(self):
        return "pintar_mapas"

    def displayName(self):
        return "Pintar Mapas CAHSA"

    def group(self):
        return "Sentinel-2 · CAHSA"

    def groupId(self):
        return "sentinel2_cahsa"

    def shortHelpString(self):
        return "Une una capa vectorial con un archivo Excel y aplica simbología categorizada al resultado."

    def createInstance(self):
        return PintarMapasAlgorithm()
