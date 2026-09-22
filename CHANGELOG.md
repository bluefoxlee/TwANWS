# Changelog

## 1.1.1 (Rolling observation trend)

### Changed

- Build local weather trends from a continuous three-hour observation window
  rather than only the previous observation.
- Wait for three valid observations before classifying a trend, reset the
  window after a 90-minute reporting gap, and expose the window start, length,
  and observation count in entity attributes.

## 1.1.0 (Observation trend preview)

### Added

- Compare consecutive valid local AOAWS observations and expose conservative
  `unknown`, `stable`, `improving`, `deteriorating`, or `mixed` trend states.
- Include trend score, reasons, confidence, summary, and observation time in
  the existing weather entity attributes without changing card layouts.
- Keep prevailing visibility and RVR comparisons separate so the lowest RVR
  does not masquerade as a change in prevailing visibility.

## 1.0.18

### Changed

- Use the official Air Navigation and Weather Services, CAA, MOTC wording for entity attribution while retaining AOAWS as the service name.

## 1.0.17

### Changed

- Align user-facing names with the official Advanced Operational Aviation Weather System (AOAWS) system name.
- Identify the data provider as Air Navigation and Weather Services, CAA, MOTC (ANWS), operated via AOAWS.

## 1.0.16 (Code Book audit)

### Added

- Accept three-digit wind speeds and validate the Code Book upper-bound forms
  `P99KT` and `P49MPS`.
- Preserve AUTO cloud groups with `///` replacements, directional visibility
  minima, unknown RVR groups, Taiwan RMK `Axxxx` altimeter data, and raw RMK
  tokens in structured report attributes.
- Expose prevailing visibility and minimum RVR as separate numeric attributes
  for future visualisations.
- Validate present-weather descriptor combinations against WMO/ICAO table
  4678 so invalid combinations are not mistaken for current weather.

### Fixed

- Do not convert missing wind or visibility groups into false calm/zero values;
  missing observations now remain unknown.

## 1.0.15

### Added

- Expose JSON-safe aviation report attributes, including report header flags,
  raw METAR, RVR groups, wind details, visibility, cloud layers, QNH, and
  trend groups on the weather entities.
- Preserve native Home Assistant cloud coverage while exposing detailed cloud
  layers and derived cloud ceiling for future card layouts.

## 1.0.14

### Added

- Distinguish `last_update` (last successful integration update) from
  `observation_time` (the station report observation time).
- Keep both timestamps available on sensor and weather entity attributes using
  timezone-aware ISO 8601 values.

## 1.0.13

### Fixed

- Show the configured-language weather text on the generic weather sensor
  instead of exposing only the internal Home Assistant condition key.
- Keep the stable condition key available as `weather_condition` and continue
  using it for weather icons.

## 1.0.12

### Added

- Localize visibility labels for the configured language while preserving the
  numeric visibility distance and a stable English `visibility_level` attribute.
- Expose configured-language weather text on both the weather sensor and the
  standard weather entity.

### Compatibility

- Keep Home Assistant condition values such as `rainy` and
  `lightning-rainy` unchanged so icons, automations, and weather cards remain
  compatible.

## 1.0.11

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
