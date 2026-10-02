from .plugin import ProcesarCAHSAPlugin


def classFactory(iface):
    return ProcesarCAHSAPlugin(iface)