def classFactory(iface):
    from .plugin import HarvestAccessibilityPlugin
    return HarvestAccessibilityPlugin(iface)
