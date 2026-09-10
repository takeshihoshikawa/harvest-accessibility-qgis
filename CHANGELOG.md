# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.1.1] - 2026-05-21
### Fixed
- Intermittent `QgsVectorLayer`/`QVariant` type error in QGIS 4.0 (PyQt6). `processing.run()` parameter dicts no longer pass `QgsVectorLayer` objects directly: memory layer outputs are registered in the context temporary store and referenced by ID, and input layers are passed as their original parameter values. This avoids the non-deterministic SIP failure converting a Python dict to `QVariantMap`.

## [0.1.0] - 2026-04-05
### Added
- Initial public release
- Processing algorithm: Harvest Accessibility (d1 straight-line distance to nearest forest road, d2 shortest network path to nearest landing)
- Support for multiple landing points (minimum d2 per grid point)
- Sample data GeoPackage (EPSG:6676) with operation area, forest roads, and landings
- Grid-based sampling with configurable spacing and network snapping tolerance

[0.1.1]: https://github.com/takeshihoshikawa/harvest-accessibility/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/takeshihoshikawa/harvest-accessibility/releases/tag/v0.1.0
