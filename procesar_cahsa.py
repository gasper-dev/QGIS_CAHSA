from pathlib import Path
import shutil
import tempfile

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
    QgsProcessingParameterFile,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterBoolean,
    QgsProcessingException,
    QgsRasterLayer,
    QgsProject,
)

import processing


class ProcesarCAHSAAlgorithm(QgsProcessingAlgorithm):

    MASK = "MASK"
    B02 = "B02"
    B03 = "B03"
    B04 = "B04"
    B08 = "B08"
    NDVI_STYLE = "NDVI_STYLE"
    NAME = "NAME"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    LOAD_RESULTS = "LOAD_RESULTS"

    def initAlgorithm(self, config=None):

        # ─────────────────────────────────────────────
        # MÁSCARA
        # ─────────────────────────────────────────────

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.MASK,
                "Máscara CAHSA",
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        # ─────────────────────────────────────────────
        # BANDAS
        # ─────────────────────────────────────────────

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.B02,
                "B02 · Azul"
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.B03,
                "B03 · Verde"
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.B04,
                "B04 · Rojo"
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.B08,
                "B08 · Infrarrojo cercano (NIR)"
            )
        )

        # ─────────────────────────────────────────────
        # ESTILO NDVI
        # ─────────────────────────────────────────────

        self.addParameter(
            QgsProcessingParameterFile(
                self.NDVI_STYLE,
                "Estilo NDVI (.qml)",
                behavior=QgsProcessingParameterFile.File,
                fileFilter="QGIS Layer Style (*.qml)",
                optional=True
            )
        )

        # ─────────────────────────────────────────────
        # NOMBRE
        # ─────────────────────────────────────────────

        self.addParameter(
            QgsProcessingParameterString(
                self.NAME,
                "Nombre del cuadrante",
                defaultValue="Cuadrante_01"
            )
        )

        # ─────────────────────────────────────────────
        # CARPETA DE SALIDA
        # ─────────────────────────────────────────────

        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                "Carpeta de salida"
            )
        )

        # ─────────────────────────────────────────────
        # CARGAR RESULTADOS
        # ─────────────────────────────────────────────

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.LOAD_RESULTS,
                "Cargar resultados en QGIS",
                defaultValue=True
            )
        )

    # ═════════════════════════════════════════════════
    # PROCESAMIENTO
    # ═════════════════════════════════════════════════

    def processAlgorithm(self, parameters, context, feedback):

        # ─────────────────────────────────────────────
        # OBTENER PARÁMETROS
        # ─────────────────────────────────────────────

        mask = self.parameterAsSource(
            parameters,
            self.MASK,
            context
        )

        if mask is None:
            raise QgsProcessingException(
                "No se pudo cargar la máscara CAHSA."
            )

        mask_source = self.parameterAsString(
            parameters,
            self.MASK,
            context
        )

        b02 = self.parameterAsRasterLayer(
            parameters,
            self.B02,
            context
        )

        b03 = self.parameterAsRasterLayer(
            parameters,
            self.B03,
            context
        )

        b04 = self.parameterAsRasterLayer(
            parameters,
            self.B04,
            context
        )

        b08 = self.parameterAsRasterLayer(
            parameters,
            self.B08,
            context
        )

        qml_path = self.parameterAsFile(
            parameters,
            self.NDVI_STYLE,
            context
        )

        name = self.parameterAsString(
            parameters,
            self.NAME,
            context
        ).strip()

        output_folder = self.parameterAsString(
            parameters,
            self.OUTPUT_FOLDER,
            context
        )

        load_results = self.parameterAsBoolean(
            parameters,
            self.LOAD_RESULTS,
            context
        )

        # ─────────────────────────────────────────────
        # VALIDACIONES
        # ─────────────────────────────────────────────

        if not b02:
            raise QgsProcessingException(
                "No se pudo cargar B02."
            )

        if not b03:
            raise QgsProcessingException(
                "No se pudo cargar B03."
            )

        if not b04:
            raise QgsProcessingException(
                "No se pudo cargar B04."
            )

        if not b08:
            raise QgsProcessingException(
                "No se pudo cargar B08."
            )

        if not name:
            name = "Cuadrante_01"

        # Caracteres no válidos para nombres de archivos
        invalid_chars = '<>:"/\\|?*'

        for char in invalid_chars:
            name = name.replace(char, "_")

        # ─────────────────────────────────────────────
        # CARPETAS DE SALIDA
        # ─────────────────────────────────────────────

        cahsa_folder = Path(output_folder) / "CAHSA"

        rgb_folder = cahsa_folder / "RGB"
        ndvi_folder = cahsa_folder / "NDVI"

        rgb_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        ndvi_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        rgb_output = (
            rgb_folder /
            f"RGB_{name}.tif"
        )

        ndvi_output = (
            ndvi_folder /
            f"NDVI_{name}.tif"
        )

        # ─────────────────────────────────────────────
        # DIRECTORIO TEMPORAL
        # ─────────────────────────────────────────────

        temp_dir = Path(
            tempfile.mkdtemp(
                prefix="procesar_cahsa_"
            )
        )

        try:

            # ═════════════════════════════════════════
            # 1. CORREGIR BANDAS (-1000)
            # ═════════════════════════════════════════

            feedback.pushInfo(
                "Corrigiendo bandas Sentinel-2..."
            )

            corrected = {}

            bands = {
                "B02": b02,
                "B03": b03,
                "B04": b04,
                "B08": b08,
            }

            for band_name, layer in bands.items():

                output = temp_dir / (
                    f"{band_name}_corrected.tif"
                )

                processing.run(
                    "gdal:rastercalculator",
                    {
                        "INPUT_A": layer,
                        "BAND_A": 1,
                        "INPUT_B": None,
                        "BAND_B": -1,
                        "INPUT_C": None,
                        "BAND_C": -1,
                        "INPUT_D": None,
                        "BAND_D": -1,
                        "INPUT_E": None,
                        "BAND_E": -1,
                        "INPUT_F": None,
                        "BAND_F": -1,
                        "FORMULA": "A-1000",
                        "NO_DATA": -9999,
                        "RTYPE": 5,
                        "OPTIONS": "",
                        "EXTRA": "",
                        "OUTPUT": str(output),
                    },
                    context=context,
                    feedback=feedback
                )

                corrected[band_name] = output

            # ═════════════════════════════════════════
            # 2. RECORTAR POR MÁSCARA
            # ═════════════════════════════════════════

            feedback.pushInfo(
                "Recortando bandas por máscara CAHSA..."
            )

            clipped = {}

            for band_name, raster in corrected.items():

                output = temp_dir / (
                    f"{band_name}_clipped.tif"
                )

                processing.run(
                    "gdal:cliprasterbymasklayer",
                    {
                        "INPUT": str(raster),
                        "MASK": mask_source,
                        "SOURCE_CRS": None,
                        "TARGET_CRS": None,
                        "NODATA": -9999,
                        "CROP_TO_CUTLINE": True,
                        "KEEP_RESOLUTION": True,
                        "SET_ALPHA": False,
                        "MULTITHREADING": True,
                        "OPTIONS": "",
                        "DATA_TYPE": 5,
                        "EXTRA": "",
                        "OUTPUT": str(output),
                    },
                    context=context,
                    feedback=feedback
                )

                clipped[band_name] = output

            # ═════════════════════════════════════════
            # 3. CREAR RGB COMO VRT TEMPORAL
            # ═════════════════════════════════════════

            feedback.pushInfo(
                "Construyendo RGB..."
            )

            rgb_vrt = temp_dir / "RGB_temp.vrt"

            processing.run(
                "gdal:buildvirtualraster",
                {
                    "INPUT": [
                        str(clipped["B04"]),
                        str(clipped["B03"]),
                        str(clipped["B02"]),
                    ],
                    "RESOLUTION": 0,
                    "SEPARATE": True,
                    "PROJ_DIFFERENCE": False,
                    "ADD_ALPHA": False,
                    "ASSIGN_CRS": None,
                    "RESAMPLING": 0,
                    "SRC_NODATA": "",
                    "EXTRA": "",
                    "OUTPUT": str(rgb_vrt),
                },
                context=context,
                feedback=feedback
            )

            # ═════════════════════════════════════════
            # 4. CONVERTIR RGB VRT → GEOTIFF REAL
            # ═════════════════════════════════════════

            feedback.pushInfo(
                "Generando RGB GeoTIFF..."
            )

            processing.run(
                "gdal:translate",
                {
                    "INPUT": str(rgb_vrt),
                    "TARGET_CRS": None,
                    "NODATA": None,
                    "COPY_SUBDATASETS": False,
                    "OPTIONS": (
                        "COMPRESS=LZW|"
                        "TILED=YES"
                    ),
                    "EXTRA": "",
                    "DATA_TYPE": 5,
                    "OUTPUT": str(rgb_output),
                },
                context=context,
                feedback=feedback
            )

            # ═════════════════════════════════════════
            # 5. CALCULAR NDVI
            # ═════════════════════════════════════════

            feedback.pushInfo(
                "Calculando NDVI..."
            )

            processing.run(
                "gdal:rastercalculator",
                {
                    "INPUT_A": str(clipped["B08"]),
                    "BAND_A": 1,
                    "INPUT_B": str(clipped["B04"]),
                    "BAND_B": 1,
                    "INPUT_C": None,
                    "BAND_C": -1,
                    "INPUT_D": None,
                    "BAND_D": -1,
                    "INPUT_E": None,
                    "BAND_E": -1,
                    "INPUT_F": None,
                    "BAND_F": -1,
                    "FORMULA": (
                        "where("
                        "(A+B)!=0,"
                        "(A-B)/(A+B),"
                        "-9999"
                        ")"
                    ),
                    "NO_DATA": -9999,
                    "RTYPE": 5,
                    "OPTIONS": (
                        "COMPRESS=LZW|"
                        "TILED=YES"
                    ),
                    "EXTRA": "",
                    "OUTPUT": str(ndvi_output),
                },
                context=context,
                feedback=feedback
            )

            # ═════════════════════════════════════════
            # 6. CARGAR RESULTADOS
            # ═════════════════════════════════════════

            if load_results:

                feedback.pushInfo(
                    "Cargando resultados en QGIS..."
                )

                # ─────────────────────────────────────
                # RGB
                # ─────────────────────────────────────

                rgb_layer = QgsRasterLayer(
                    str(rgb_output),
                    f"RGB_{name}",
                    "gdal"
                )

                if not rgb_layer.isValid():

                    raise QgsProcessingException(
                        "El RGB generado no es válido."
                    )

                QgsProject.instance().addMapLayer(
                    rgb_layer
                )

                # ─────────────────────────────────────
                # NDVI
                # ─────────────────────────────────────

                ndvi_layer = QgsRasterLayer(
                    str(ndvi_output),
                    f"NDVI_{name}",
                    "gdal"
                )

                if not ndvi_layer.isValid():

                    raise QgsProcessingException(
                        "El NDVI generado no es válido."
                    )

                QgsProject.instance().addMapLayer(
                    ndvi_layer
                )

                # ─────────────────────────────────────
                # APLICAR QML
                # ─────────────────────────────────────

                if qml_path:

                    qml_file = Path(qml_path)

                    if qml_file.exists():

                        feedback.pushInfo(
                            "Aplicando estilo NDVI..."
                        )

                        try:

                            ndvi_layer.loadNamedStyle(
                                str(qml_file)
                            )

                            ndvi_layer.triggerRepaint()

                            feedback.pushInfo(
                                "Estilo NDVI aplicado correctamente."
                            )

                        except Exception as e:

                            feedback.reportError(
                                "No se pudo aplicar "
                                f"el estilo NDVI: {e}"
                            )

                    else:

                        feedback.reportError(
                            "El archivo QML no existe: "
                            f"{qml_path}"
                        )

            # ═════════════════════════════════════════
            # FINAL
            # ═════════════════════════════════════════

            feedback.pushInfo("")
            feedback.pushInfo(
                "===================================="
            )
            feedback.pushInfo(
                "PROCESAMIENTO COMPLETADO"
            )
            feedback.pushInfo(
                "===================================="
            )

            feedback.pushInfo(
                f"RGB: {rgb_output}"
            )

            feedback.pushInfo(
                f"NDVI: {ndvi_output}"
            )

            return {
                "RGB": str(rgb_output),
                "NDVI": str(ndvi_output),
            }

        except Exception as e:

            raise QgsProcessingException(
                f"Error durante el procesamiento: {e}"
            )

        finally:

            # ─────────────────────────────────────────
            # ELIMINAR TEMPORALES
            # ─────────────────────────────────────────

            try:

                shutil.rmtree(
                    temp_dir,
                    ignore_errors=True
                )

            except Exception:
                pass

    # ═════════════════════════════════════════════════
    # METADATOS DEL ALGORITMO
    # ═════════════════════════════════════════════════

    def name(self):

        return "procesar_cahsa"

    def displayName(self):

        return "Procesar Sentinel-2 · CAHSA"

    def group(self):

        return "Sentinel-2 · CAHSA"

    def groupId(self):

        return "sentinel2_cahsa"

    def shortHelpString(self):

        return (
            "Procesa las bandas Sentinel-2 B02, B03, B04 y B08 "
            "utilizando la máscara CAHSA. "
            "Corrige el offset de 1000, recorta las bandas, "
            "genera un RGB GeoTIFF y calcula NDVI. "
            "Opcionalmente aplica un estilo QML al NDVI."
        )

    def createInstance(self):

        return ProcesarCAHSAAlgorithm()