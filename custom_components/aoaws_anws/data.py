"""Common ANWS AOAWS Data class used by both sensor and entity."""

import logging
import re
import time
from datetime import datetime, timedelta
from http import HTTPStatus
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from bs4 import BeautifulSoup
from homeassistant.const import (
    UnitOfLength,
    UnitOfTemperature,
    UnitOfSpeed
)
from .const import (
    BASE_URL,
    HA_USER_AGENT,
    REQUEST_TIMEOUT
)

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
        self.visibility = None
        self.uv = None
        self.precipitation = None
        self.humidity = None
        self.pressure = None
        self.pressure_tendency = None
        self.dew_point = None
        self.cloud_coverage = None
        self.cloud_ceiling = None

    def __iter__(self):
        for attr, value in self.__dict__.items():
            yield attr, value

    def elements(self):
        """Return a list of the Elements which are not None"""
        elements = [el[1] for el in self.__dict__.items() if isinstance(el[1], Element)]

        return elements


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
        observation = Observation()
        for i in data:
            for j in i:
                if self._site == j["location_en"]:
                    # date
                    obs_datetime = datetime.strptime(
                        j["datatime"].strip(), "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                    timestamp = int(time.mktime((obs_datetime).timetuple()))

                    observation.date = datetime.fromtimestamp(
                        timestamp).strftime('%Y-%m-%d %H:%M:%S')

                    # wether
                    value = ''.join(c for c in j["WEATHER"]["EName"] if c.isalpha() or c.isspace()).strip()
                    observation.weather = Element("W", value=value)

                    # temperature
                    value = int(j.get("TEMP", "0"))
                    unit = UnitOfTemperature.CELSIUS
                    temperature = value
                    observation.temperature = Element("T", value=value, units=unit.strip())

                    # wind speed
                    report_text = j.get("REPORT", "")
                    value = int(j.get("WDSD", "0"))
                    if "00000KT" in report_text or "CALM" in report_text.upper() or "靜風" in report_text:
                        value = 0
                    if "浬/時" in j["WDSD_UNIT"] or "KT" in j["WDSD_UNIT"]:
                        unit = UnitOfSpeed.KNOTS
                    else:
                        unit = UnitOfSpeed.KILOMETERS_PER_HOUR
                    observation.wind_speed = Element("W", value=value, units=unit)

                    # wind direction
                    value = int(j.get("WDIR", "0"))
                    observation.wind_direction = Element("W", value=value)

                    # =========================
                    # REPORT parsing（先做）
                    # =========================
                    rvr_list = []

                    for k in j.get("REPORT", "").split():

                        # RVR，例如 R24/800M / R06/1600U
                        if k.startswith("R") and "/" in k:
                            try:
                                vis_part = k.split("/")[1]
                                match = re.search(r"\d{3,4}", vis_part)
                                if match:
                                    vis = int(match.group())
                                    rvr_list.append(vis)
                            except Exception as e:
                                _LOGGER.debug(f"RVR parse failed: {k} ({e})")
                            continue

                        # dew point，例如 25/25
                        if (
                            "/" in k
                            and not k.startswith("R")
                            and k.split("/")[0].isdigit()
                            and temperature == int(k.split("/")[0])
                        ):
                            observation.dew_point = Element("T", value=k.split("/", 1)[1])

                        # pressure，例如 Q1013
                        if k.startswith("Q"):
                            observation.pressure = Element("P", value=k[1:])

                    # =========================
                    # visibility（最後才決定）
                    # =========================
                    value = int(j.get("VIS", "0")) / 1000

                    if rvr_list:
                        value = min(rvr_list) / 1000.0

                    observation.visibility = Element(
                        "W",
                        value=value,
                        units=UnitOfLength.KILOMETERS
                    )

                    # cloud ceiling
                    value = j.get("CEILING", "")
                    observation.cloud_ceiling  = Element("W", value=value)

        return observation

    def _convert_to_observations(self, site, data):
        """ converter  """
        observations = []
        for i in data:
            for j in i:
                if self._site == j["location_en"]:
                    observation = Observation()
                    # date
                    timestamp = int(time.mktime((datetime.strptime(
                        j["datatime"].strip(), "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)).timetuple()))

                    observation.date = datetime.fromtimestamp(
                        timestamp).strftime('%Y-%m-%d %H:%M:%S')

                    # wether
                    value = ''.join(c for c in j["WEATHER"]["EName"] if c.isalpha() or c.isspace()).strip()
                    observation.weather = Element("W", value=value)

                    # temperature
                    value = int(j.get("TEMP", "-1"))
                    unit = UnitOfTemperature.CELSIUS
                    temperature = value
                    observation.temperature = Element("T", value=value, units=unit.strip())

                    # wind speed
                    report_text = j.get("REPORT", "")
                    value = int(j.get("WDSD", "-1"))
                    if "00000KT" in report_text or "CALM" in report_text.upper() or "靜風" in report_text:
                        value = 0
                    if "浬/時" in j["WDSD_UNIT"] or "KT" in j["WDSD_UNIT"]:
                        unit = UnitOfSpeed.KNOTS
                    else:
                        unit = UnitOfSpeed.KILOMETERS_PER_HOUR
                    observation.wind_speed = Element("W", value=value, units=unit)

                    # wind direction
                    value = int(j.get("WDIR", "-1"))
                    observation.wind_direction = Element("W", value=value)

                    # visibility
                    value = int(j.get("VIS", "-1"))
                    observation.visibility = Element("W", value=value)

                    # cloud ceiling
                    value = j.get("CEILING", "")
                    observation.cloud_ceiling  = Element("W", value=value)

                    observations.append(observation)

        return observations


    def _parser_json(self, data):
        if "airport_list" not in data:
            _LOGGER.error(f"There is no airport_list")
            return {}
        if "Taiwan" not in data["airport_list"]:
            _LOGGER.error(f"There is no Taiwan in airport_list")
            return {}
        new_data = []
        #for i in data["airport_list"]["Taiwan"]:
        #    datatime = i["datatime"]
        #    location_en = i["location_en"]

        return data["airport_list"]["Taiwan"]


    def _update_site(self):
        """Return the nearest DataPoint Site to the held latitude/longitude."""

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

        except requests.exceptions.RequestException:
            _LOGGER.error("Failed fetching data for %s", self.site_name)
            return

        if response.status_code == HTTPStatus.OK:
            try:
                self.data = self._parser_json(response.json())
                for i in self.data:
                    for j in i:
                        if self._site == j["location_en"]:
                            self.site_name = self._site
            except Exception as e:
                _LOGGER.error(f"Received data error {e}")
        else:
            _LOGGER.error("Received error from ANWS AOAWS: %s", self.site_name)
            self.site_name = None
            self.now = None

        return self._site

    async def async_update(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        """Get the latest data from AOAWS."""

        _LOGGER.debug("ANWS update triggered")

        try:
            # 👉 每次都先嘗試更新資料（避免卡死）
            self._update_site()

            if self.site_name is None:
                _LOGGER.warning("No ANWS AOAWS observations site held after update")
                return

            # 👉 只在成功時更新資料（避免清空）
            observation = self.get_observation_for_site(
                self._site, self.data
            )

            if observation is not None:
                self.now = observation

            forecast = self.get_observations_for_site(
                self._site, self.data
            )

            if forecast is not None:
                self.forecast = forecast

        except Exception as e:
            _LOGGER.warning(f"ANWS update failed: {e}")
            return
