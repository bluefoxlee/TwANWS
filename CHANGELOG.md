# Changelog

## Unreleased

### Added

- Derive Home Assistant cloud coverage from METAR cloud amounts and fall back
  to the lowest reported BKN/OVC/VV layer for cloud ceiling when ANWS does not
  provide one.
- Treat CAVOK as zero cloud coverage when no API cloud value is available.
- Accept combined precipitation weather groups such as `RASN`, `SHRASN`, and
  `+TSRAGR`.

### Fixed

- Fall back to METAR wind direction, wind speed, and visibility when the
  corresponding ANWS JSON keys are absent, instead of treating missing values
  as zero.

## 1.0.10

### Added

- Parse METAR/SPECI report headers, including station, report time, AUTO,
  COR, and NIL flags.
- Skip NIL reports instead of treating residual fields as current conditions.
- Fall back to METAR temperature/dew point when ANWS temperature data is
  missing or invalid.
- Fall back to METAR wind data when ANWS wind fields are missing, including
  MPS and VRB handling.

## 1.0.9

### Added

- Structure RVR groups with runway, bounds, units, and trend indicators.
- Parse BECMG, TEMPO, NOSIG, FM, TL, and AT trend groups.
- Preserve raw METAR, trend groups, prevailing visibility, and minimum RVR.
- Parse wind gusts, VRB, variable direction, MPS, P99KT, CAVOK, directional
  visibility, present weather, cloud layers, and vertical visibility.

### Fixed

- Convert ANWS UTC observation timestamps explicitly to Taiwan time.

## 1.0.8

### Fixed

- Parse RVR before deciding the current visibility, so RVR can actually take effect.
- Use the lowest value when multiple runway RVR groups are present.
- Support standard, variable, bounded, metre-suffixed, and feet-based RVR groups.
- Stop RVR groups such as `R06/1600U` from entering temperature/dew point parsing.
- Parse negative METAR dew points and expose dew point and pressure as numeric values.
- Preserve knot values without the erroneous `× 1.85` conversion and handle calm wind.
- Preserve the last valid observation when a request fails or a station is temporarily absent from a successful API response.
- Return `None` instead of an empty observation when no valid record exists.
- Update weather and sensor entities to Home Assistant's native value/unit APIs.
- Stop reporting ordinary wind speed as wind gust speed.

### Changed

- Treat METAR visibility `9999` as 10 km or more (numeric value `10.0`).
- Ignore RVR groups found only in trend or remark sections.
- Remove the unused third-party `metar` requirement.
- Correct HACS, documentation, and issue links for this fork.

### Tests

- Add parser and recovery tests covering RVR, dew point, pressure, calm wind,
  visibility, missing stations, and successful/failed refresh behavior.
