# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.1.0] - 2026-04-05
### Added
- Initial public release
- Processing algorithm: Harvest Accessibility (d1 straight-line distance to nearest forest road, d2 shortest network path to nearest landing)
- Support for multiple landing points (minimum d2 per grid point)
- Sample data GeoPackage (EPSG:6676) with operation area, forest roads, and landings
- Grid-based sampling with configurable spacing and network snapping tolerance

[0.1.0]: https://github.com/takeshihoshikawa/harvest-accessibility/releases/tag/v0.1.0
