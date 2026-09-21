"""Common ANWS AOAWS Data class used by both sensor and entity."""

import logging
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from homeassistant.const import (
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
)
from .const import (
    BASE_URL,
    HA_USER_AGENT,
    REQUEST_TIMEOUT,
)
from .metar import (
    parse_altimeter_inches,
    parse_clouds,
    parse_dew_point,
    parse_present_weather,
    parse_pressure,
    parse_rmk_tokens,
    parse_report_header,
    parse_rvr,
    parse_temperature,
    parse_trends,
    parse_visibility,
    parse_wind,
)
from .localization import localized_weather_text
from .trend import TrendResult, compare_observations, unknown_trend

_LOGGER = logging.getLogger(__name__)


class Element():
    def __init__(self, field_code=None, value=None, units=None, text=None):

        self.field_code = field_code
        self.value = value
        self.units = units

        # For elements which can also have a text value
        self.text = text

    def __str__(self):
        return str(self.value) + ' ' + str(self.units)


class Observation:
    def __init__(self):
        self.name = None
        self.date = None
        self.weather = None
        self.temperature = None
        self.wind_speed = None
        self.wind_direction = None
        self.wind_gust = None
        self.wind_report = None
        self.wind_variable_from = None
        self.wind_variable_to = None
        self.report_visibility = None
        self.weather_codes = []
        self.cloud_groups = []
        self.visibility = None
        self.uv = None
        self.precipitation = None
        self.humidity = None
        self.pressure = None
        self.pressure_tendency = None
        self.dew_point = None
        self.cloud_coverage = None
        self.cloud_ceiling = None
        self.raw_report = None
        self.report_header = None
        self.observation_time = None
        self.trends = []
        self.rmk_tokens = ()
        self.rvr_groups = []
        self.prevailing_visibility = None
        self.rvr_min = None
        self.trend_result: TrendResult | None = None

    def __iter__(self):
        for attr, value in self.__dict__.items():
            yield attr, value

    def elements(self):
        """Return a list of the Elements which are not None"""
        elements = [el[1] for el in self.__dict__.items() if isinstance(el[1], Element)]

        return elements

    def report_attributes(self):
        """Return JSON-safe aviation report details for entity attributes."""
        attributes = {}

        if self.report_header:
            attributes.update(
                {
                    "report_type": self.report_header.kind,
                    "report_station": self.report_header.station,
                    "report_time_utc": self.report_header.report_time_utc,
                    "report_automated": self.report_header.automated,
                    "report_corrected": self.report_header.corrected,
                    "report_nil": self.report_header.nil,
                }
            )
        if self.raw_report:
            attributes["raw_metar"] = self.raw_report
        if self.weather_codes:
            attributes["weather_codes"] = list(self.weather_codes)
        if self.report_visibility:
            attributes["report_visibility"] = {
                "metres": self.report_visibility.metres,
                "direction": self.report_visibility.direction,
                "cavok": self.report_visibility.cavok,
                "raw": self.report_visibility.raw,
                "directional": [
                    {"metres": metres, "direction": direction}
                    for metres, direction in self.report_visibility.directional
                ],
            }
        if self.wind_report:
            attributes["wind_report"] = {
                "direction": self.wind_report.direction,
                "speed": self.wind_report.speed,
                "gust": self.wind_report.gust,
                "unit": self.wind_report.unit,
                "variable_from": self.wind_report.variable_from,
                "variable_to": self.wind_report.variable_to,
                "speed_qualifier": self.wind_report.speed_qualifier,
                "gust_qualifier": self.wind_report.gust_qualifier,
                "raw": self.wind_report.raw,
            }
        if self.rvr_groups:
            attributes["rvr"] = [
                {
                    "runway": group.runway,
                    "lower_metres": group.lower_metres,
                    "upper_metres": group.upper_metres,
                    "lower_qualifier": group.lower_qualifier,
                    "upper_qualifier": group.upper_qualifier,
                    "trend": group.trend,
                    "raw": group.raw,
                }
                for group in self.rvr_groups
            ]
        if self.prevailing_visibility:
            attributes["prevailing_visibility_km"] = self.prevailing_visibility.value
        if self.rvr_min:
            attributes["rvr_min_km"] = self.rvr_min.value
        if self.cloud_groups:
            attributes["cloud_layers"] = [
                {
                    "amount": cloud.amount,
                    "height_feet": cloud.height_feet,
                    "cloud_type": cloud.cloud_type,
                    "coverage_percent": cloud.coverage_percent,
                    "vertical_visibility": cloud.vertical_visibility,
                    "raw": cloud.raw,
                }
                for cloud in self.cloud_groups
            ]
        if self.trends:
            attributes["trends"] = [
                {
                    "kind": trend.kind,
                    "time_markers": trend.time_markers,
                    "payload_tokens": list(trend.payload_tokens),
                    "raw": trend.raw,
                }
                for trend in self.trends
            ]
        if self.cloud_coverage is not None:
            attributes["cloud_coverage_percent"] = self.cloud_coverage.value
        if self.cloud_ceiling and self.cloud_ceiling.value not in (None, ""):
            attributes["cloud_ceiling_feet"] = self.cloud_ceiling.value
        if self.pressure:
            attributes["qnh_hpa"] = self.pressure.value
        altimeter_inches = parse_altimeter_inches(self.raw_report or "")
        if altimeter_inches is not None:
            attributes["altimeter_inhg"] = altimeter_inches
        if self.rmk_tokens:
            attributes["rmk_tokens"] = list(self.rmk_tokens)
        if self.trend_result:
            attributes.update(self.trend_result.as_attributes())
        return attributes


class AnwsAoawseData:
    """Get current AOAWS from ANWS.

    Use API calls have had to be wrapped with the standard hassio helper
    async_add_executor_job.
    """

    def __init__(self, hass, site_name, language):
        """Initialize the data object."""
        self._hass = hass
        self._site = site_name

        # Holds the current data from the ANWS AOAWS
        self.data = None
        self.site_name = None
        self.language = language
        self.now = None
        self.forecast = None
        self.last_update = None
        self.trend_result = None
        self.uri = BASE_URL

    async def async_update_site(self):
        """Async wrapper for getting the update."""
        return await self._hass.async_add_executor_job(self._update_site)

    def get_observation_for_site(self, site, data):
        """ return observation """
        return self._convert_to_observation(site, data)

    def get_observations_for_site(self, site, data):
        """ return observations """
        return self._convert_to_observations(site, data)

    def _convert_to_observation(self, site, data):
        """Convert the newest valid record for a site to an observation."""
        records = list(self._site_records(site, data))
        for record in reversed(records):
            try:
                return self._record_to_observation(record, use_rvr=True)
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.warning(
                    "Skipping invalid current observation for %s: %s", site, err
                )
        return None

    def _convert_to_observations(self, site, data):
        """Convert all valid records for a site to observations."""
        observations = []
        for record in self._site_records(site, data):
            try:
                observations.append(
                    self._record_to_observation(record, use_rvr=False)
                )
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.warning(
                    "Skipping invalid observation for %s: %s", site, err
                )
        return observations

    @staticmethod
    def _site_records(site, data):
        """Yield records belonging to a site from the nested ANWS response."""
        if not isinstance(data, list):
            return
        for group in data:
            if not isinstance(group, list):
                continue
            for record in group:
                if isinstance(record, dict) and record.get("location_en") == site:
                    yield record

    def _record_to_observation(self, record, use_rvr):
        """Convert one ANWS JSON record to an Observation."""
        observation = Observation()

        obs_datetime = datetime.strptime(
            record["datatime"].strip(), "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        observation.date = obs_datetime.astimezone(
            timezone(timedelta(hours=8))
        ).strftime("%Y-%m-%d %H:%M:%S")
        observation.observation_time = obs_datetime.astimezone(
            timezone(timedelta(hours=8))
        ).isoformat(timespec="seconds")

        weather = record.get("WEATHER") or {}
        weather_en = "".join(
            character
            for character in str(weather.get("EName", ""))
            if character.isalpha() or character.isspace()
        ).strip()
        weather_text = localized_weather_text(weather, self.language)
        observation.weather = Element(
            "W", value=weather_en, text=weather_text or weather_en
        )

        report = str(record.get("REPORT") or "")
        try:
            temperature = int(record["TEMP"])
        except (KeyError, TypeError, ValueError):
            temperature_group = parse_temperature(report)
            if temperature_group is None:
                raise
            temperature = temperature_group.temperature
        observation.temperature = Element(
            "T", value=temperature, units=UnitOfTemperature.CELSIUS
        )

        observation.raw_report = report
        observation.rmk_tokens = parse_rmk_tokens(report)
        observation.report_header = parse_report_header(report)
        if observation.report_header and observation.report_header.nil:
            raise ValueError("METAR/SPECI report is NIL")
        observation.trends = parse_trends(report)
        observation.rvr_groups = parse_rvr(report)
        observation.wind_report = parse_wind(report)
        observation.report_visibility = parse_visibility(report)
        observation.weather_codes = parse_present_weather(report)
        observation.cloud_groups = parse_clouds(report)
        cloud_coverages = [
            cloud.coverage_percent
            for cloud in observation.cloud_groups
            if cloud.coverage_percent is not None
        ]
        if cloud_coverages:
            observation.cloud_coverage = Element(
                "CC", value=max(cloud_coverages)
            )
        elif observation.report_visibility and observation.report_visibility.cavok:
            # CAVOK includes no significant cloud below the applicable
            # aerodrome minimum; expose that as clear sky coverage.
            observation.cloud_coverage = Element("CC", value=0)
        if observation.wind_report is not None:
            observation.wind_variable_from = observation.wind_report.variable_from
            observation.wind_variable_to = observation.wind_report.variable_to
        wind_speed_value = record.get("WDSD")
        try:
            if wind_speed_value in (None, ""):
                raise ValueError
            wind_speed = int(wind_speed_value)
        except (TypeError, ValueError):
            wind_speed = (
                observation.wind_report.speed
                if observation.wind_report is not None
                else None
            )
        if "00000KT" in report or "CALM" in report.upper() or "靜風" in report:
            wind_speed = 0
        wind_unit = str(record.get("WDSD_UNIT") or "")
        wind_unit_upper = wind_unit.upper()
        if "浬/時" in wind_unit or "KT" in wind_unit_upper:
            unit = UnitOfSpeed.KNOTS
        elif "MPS" in wind_unit_upper or "M/S" in wind_unit_upper:
            unit = UnitOfSpeed.METERS_PER_SECOND
        elif observation.wind_report and observation.wind_report.unit == "MPS":
            unit = UnitOfSpeed.METERS_PER_SECOND
        else:
            unit = UnitOfSpeed.KILOMETERS_PER_HOUR
        observation.wind_speed = Element("W", value=wind_speed, units=unit)

        if observation.wind_report and observation.wind_report.gust is not None:
            gust_unit = (
                UnitOfSpeed.KNOTS
                if observation.wind_report.unit == "KT"
                else UnitOfSpeed.METERS_PER_SECOND
            )
            observation.wind_gust = Element(
                "WG", value=observation.wind_report.gust, units=gust_unit
            )

        wind_direction_value = record.get("WDIR")
        try:
            if wind_direction_value in (None, ""):
                raise ValueError
            wind_direction = int(wind_direction_value)
        except (TypeError, ValueError):
            wind_direction = (
                observation.wind_report.direction
                if observation.wind_report is not None
                else None
            )
        if observation.wind_report and observation.wind_report.direction is None:
            wind_direction = None
        observation.wind_direction = Element("W", value=wind_direction)

        dew_point = parse_dew_point(report, temperature)
        if dew_point is not None:
            observation.dew_point = Element(
                "T", value=dew_point, units=UnitOfTemperature.CELSIUS
            )

        pressure = parse_pressure(report)
        if pressure is not None:
            observation.pressure = Element("P", value=pressure)

        visibility_value = record.get("VIS")
        try:
            if visibility_value in (None, ""):
                raise ValueError
            visibility_metres = int(visibility_value)
        except (TypeError, ValueError):
            if observation.report_visibility and observation.report_visibility.metres is not None:
                visibility_metres = observation.report_visibility.metres
            elif observation.report_visibility and observation.report_visibility.cavok:
                visibility_metres = 9999
            else:
                visibility_metres = None
        if visibility_metres is None:
            prevailing_visibility_km = None
        elif visibility_metres >= 9999:
            prevailing_visibility_km = 10.0
        else:
            prevailing_visibility_km = visibility_metres / 1000
        observation.prevailing_visibility = Element(
            "VIS", value=prevailing_visibility_km, units=UnitOfLength.KILOMETERS
        )

        rvr_values = [
            group.lower_metres
            for group in observation.rvr_groups
            if group.lower_metres is not None
        ]
        visibility_km = prevailing_visibility_km
        if rvr_values:
            rvr_min_km = min(rvr_values) / 1000
            observation.rvr_min = Element(
                "RVR", value=rvr_min_km, units=UnitOfLength.KILOMETERS
            )
            if use_rvr:
                visibility_km = rvr_min_km
        observation.visibility = Element(
            "W", value=visibility_km, units=UnitOfLength.KILOMETERS
        )

        ceiling_value = record.get("CEILING")
        if ceiling_value in (None, ""):
            parsed_ceilings = [
                cloud.height_feet
                for cloud in observation.cloud_groups
                if cloud.is_ceiling and cloud.height_feet is not None
            ]
            if parsed_ceilings:
                ceiling_value = min(parsed_ceilings)
        if ceiling_value is None:
            ceiling_value = ""
        observation.cloud_ceiling = Element("W", value=ceiling_value)
        return observation


    def _parser_json(self, data):
        if "airport_list" not in data:
            _LOGGER.error("There is no airport_list")
            return []
        if "Taiwan" not in data["airport_list"]:
            _LOGGER.error("There is no Taiwan in airport_list")
            return []

        return data["airport_list"]["Taiwan"]


    def _update_site(self):
        """Fetch data and return whether the configured site is present."""

        # Suppress the InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'User-Agent': HA_USER_AGENT
        }

        try:
            response = requests.post(
                self.uri,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                verify=False)

        except requests.exceptions.RequestException as err:
            _LOGGER.warning("Failed fetching data for %s: %s", self._site, err)
            return False

        if response.status_code != HTTPStatus.OK:
            _LOGGER.warning(
                "Received HTTP %s from ANWS AOAWS for %s",
                response.status_code,
                self._site,
            )
            return False

        try:
            new_data = self._parser_json(response.json())
        except (TypeError, ValueError) as err:
            _LOGGER.warning("Received invalid ANWS AOAWS data: %s", err)
            return False

        if not any(self._site_records(self._site, new_data)):
            _LOGGER.warning("ANWS AOAWS response has no data for %s", self._site)
            return False

        self.data = new_data
        self.site_name = self._site
        return True

    async def async_update(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        """Get the latest data from AOAWS."""
        _LOGGER.debug("ANWS update triggered for %s", self._site)

        try:
            if not self._update_site():
                return

            observation = self.get_observation_for_site(self._site, self.data)
            if observation is None:
                _LOGGER.warning("No valid current observation for %s", self._site)
                return

            forecast = self.get_observations_for_site(self._site, self.data)
            if self.now is None:
                trend_result = unknown_trend(self.language, observation.observation_time)
            elif observation.observation_time == self.now.observation_time:
                trend_result = self.trend_result or unknown_trend(
                    self.language, observation.observation_time
                )
            else:
                trend_result = compare_observations(
                    self.now, observation, self.language
                )
            observation.trend_result = trend_result
            self.trend_result = trend_result
            self.now = observation
            if forecast:
                self.forecast = forecast
            self.last_update = datetime.now(
                timezone(timedelta(hours=8))
            ).isoformat(timespec="seconds")
        except (KeyError, TypeError, ValueError) as err:
            # Keep the last valid values; the next coordinator poll retries.
            _LOGGER.warning("ANWS AOAWS update failed for %s: %s", self._site, err)
