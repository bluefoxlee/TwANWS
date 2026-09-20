"""Focused tests for AOAWS record conversion and update recovery."""

from pathlib import Path
import importlib.util
import sys
import types
import unittest


ROOT = Path(__file__).parents[1]
PACKAGE = "aoaws_test"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / "aoaws_anws")]
sys.modules[PACKAGE] = package

homeassistant = types.ModuleType("homeassistant")
homeassistant_const = types.ModuleType("homeassistant.const")


class UnitOfLength:
    KILOMETERS = "km"


class UnitOfSpeed:
    KNOTS = "kn"
    KILOMETERS_PER_HOUR = "km/h"
    METERS_PER_SECOND = "m/s"


class UnitOfTemperature:
    CELSIUS = "°C"


homeassistant_const.UnitOfLength = UnitOfLength
homeassistant_const.UnitOfSpeed = UnitOfSpeed
homeassistant_const.UnitOfTemperature = UnitOfTemperature
sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.const"] = homeassistant_const

const = types.ModuleType(f"{PACKAGE}.const")
const.BASE_URL = "https://example.invalid"
const.HA_USER_AGENT = "test"
const.REQUEST_TIMEOUT = 1
sys.modules[f"{PACKAGE}.const"] = const

_load_module(
    f"{PACKAGE}.metar",
    ROOT / "custom_components" / "aoaws_anws" / "metar.py",
)
data_module = _load_module(
    f"{PACKAGE}.data",
    ROOT / "custom_components" / "aoaws_anws" / "data.py",
)


def _record(**changes):
    value = {
        "datatime": "2026-04-13T01:46:00Z",
        "location_en": "Kinmen",
        "REPORT": (
            "SPECI RCBS 130146Z 19006KT 0800 "
            "R24/800M R24/500M R06/600M FG 25/24 Q1011="
        ),
        "TEMP": 25,
        "VIS": 800,
        "WDIR": 190,
        "WDSD": 6,
        "WDSD_UNIT": "KT",
        "CEILING": 700,
        "WEATHER": {"CName": "霧", "EName": "Fog"},
    }
    value.update(changes)
    return value


class DataConversionTests(unittest.TestCase):
    def setUp(self):
        self.client = data_module.AnwsAoawseData(None, "Kinmen", "tw")

    def test_rvr_overrides_visibility_with_lowest_value(self):
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record()]]
        )
        self.assertEqual(observation.visibility.value, 0.5)
        self.assertEqual(observation.prevailing_visibility.value, 0.8)
        self.assertEqual(observation.rvr_min.value, 0.5)
        self.assertEqual(observation.dew_point.value, 24)
        self.assertEqual(observation.pressure.value, 1011)
        self.assertEqual(observation.wind_speed.value, 6)
        self.assertEqual(observation.wind_speed.units, "kn")
        self.assertEqual(observation.weather.text, "霧")
        self.assertEqual(
            [(group.runway, group.lower_metres) for group in observation.rvr_groups],
            [("R24", 800), ("R24", 500), ("R06", 600)],
        )

    def test_calm_wind(self):
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT="METAR RCBS 00000KT 9999 25/24 Q1011=")]]
        )
        self.assertEqual(observation.wind_speed.value, 0)

    def test_9999_visibility_means_ten_kilometres_or_more(self):
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT="METAR RCBS 19006KT 9999 25/24 Q1011=", VIS=9999)]]
        )
        self.assertEqual(observation.visibility.value, 10.0)
        self.assertEqual(observation.prevailing_visibility.value, 10.0)
        self.assertIsNone(observation.rvr_min)

    def test_missing_site_returns_none(self):
        self.assertIsNone(self.client._convert_to_observation("Kinmen", [[_record(location_en="Taipei")]]))

    def test_failed_refresh_keeps_last_valid_values(self):
        previous_now = object()
        previous_forecast = [object()]
        self.client.now = previous_now
        self.client.forecast = previous_forecast
        self.client._update_site = lambda: False

        self.client._update()

        self.assertIs(self.client.now, previous_now)
        self.assertIs(self.client.forecast, previous_forecast)

    def test_successful_refresh_replaces_values(self):
        self.client.data = [[_record()]]
        self.client._update_site = lambda: True

        self.client._update()

        self.assertEqual(self.client.now.visibility.value, 0.5)
        self.assertTrue(self.client.forecast)

    def test_observation_keeps_raw_report_and_trends(self):
        report = (
            "SPECI RCBS 291010Z 4000 SHRA 20/20 Q1011 "
            "BECMG 1500 +TSRA"
        )
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report)]]
        )

        self.assertEqual(observation.raw_report, report)
        self.assertEqual(len(observation.trends), 1)
        self.assertEqual(observation.trends[0].kind, "BECMG")
        self.assertEqual(observation.trends[0].tokens, ("1500", "+TSRA"))

    def test_observation_keeps_report_header(self):
        report = "METAR AUTO RCBS 131200Z 18005KT 9999 25/24 Q1011="
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report)]]
        )

        self.assertEqual(observation.report_header.station, "RCBS")
        self.assertTrue(observation.report_header.automated)
        self.assertEqual(observation.report_header.report_time_utc, "131200Z")

    def test_nil_report_is_skipped(self):
        observation = self.client._convert_to_observation(
            "Kinmen",
            [[_record(REPORT="METAR RCBS 131200Z NIL=")]],
        )

        self.assertIsNone(observation)

    def test_observation_report_time_is_converted_from_utc(self):
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(datatime="2026-04-13T01:46:00Z")]]
        )

        self.assertEqual(observation.date, "2026-04-13 09:46:00")

    def test_temperature_falls_back_to_metar_when_api_value_is_missing(self):
        report = "METAR RCBS 131200Z 18005KT 9999 M02/M08 Q1011="
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report, TEMP=None)]]
        )

        self.assertEqual(observation.temperature.value, -2)
        self.assertEqual(observation.dew_point.value, -8)

    def test_wind_falls_back_to_metar_and_preserves_mps(self):
        report = "METAR RCBS 131200Z VRB03MPS 9999 25/24 Q1011="
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report, WDSD=None, WDSD_UNIT="MPS", WDIR=None)]]
        )

        self.assertEqual(observation.wind_speed.value, 3)
        self.assertEqual(observation.wind_speed.units, "m/s")
        self.assertIsNone(observation.wind_direction.value)

    def test_wind_and_visibility_fall_back_when_api_keys_are_absent(self):
        report = "METAR RCBS 131200Z 27012KT 3500 25/24 Q1011="
        record = _record(REPORT=report, WDSD=None, WDIR=None, VIS=None)
        record.pop("WDSD")
        record.pop("WDIR")
        record.pop("VIS")

        observation = self.client._convert_to_observation("Kinmen", [[record]])

        self.assertEqual(observation.wind_speed.value, 12)
        self.assertEqual(observation.wind_direction.value, 270)
        self.assertEqual(observation.visibility.value, 3.5)

    def test_temperature_falls_back_when_api_field_is_absent(self):
        report = "METAR RCBS 131200Z 18005KT 9999 05/01 Q1011="
        record = _record(REPORT=report)
        record.pop("TEMP")

        observation = self.client._convert_to_observation("Kinmen", [[record]])

        self.assertEqual(observation.temperature.value, 5)
        self.assertEqual(observation.dew_point.value, 1)

    def test_observation_keeps_wind_gust_and_variable_direction(self):
        report = "METAR RCBS 010000Z 18012G25KT 140V220 9999 25/24 Q1011="
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report, WDSD=12, WDIR=180)]]
        )

        self.assertEqual(observation.wind_gust.value, 25)
        self.assertEqual(observation.wind_gust.units, "kn")
        self.assertEqual(observation.wind_variable_from, 140)
        self.assertEqual(observation.wind_variable_to, 220)

    def test_observation_keeps_report_visibility_and_weather_codes(self):
        report = "SPECI RCBS 010000Z 18005KT 4000NE SHRA BR 25/24 Q1011="
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report, VIS=4000)]]
        )

        self.assertEqual(observation.report_visibility.metres, 4000)
        self.assertEqual(observation.report_visibility.direction, "NE")
        self.assertEqual(observation.weather_codes, ["SHRA", "BR"])

    def test_observation_keeps_cloud_groups(self):
        report = "METAR RCBS 010000Z 18005KT 9999 SCT018CB BKN030 Q1011="
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report)]]
        )

        self.assertEqual(len(observation.cloud_groups), 2)
        self.assertEqual(observation.cloud_groups[0].raw, "SCT018CB")
        self.assertEqual(observation.cloud_groups[1].height_feet, 3000)

    def test_cloud_coverage_and_ceiling_fall_back_to_metar(self):
        report = "METAR RCBS 010000Z 18005KT 9999 SCT018CB BKN030 Q1011="
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report, CEILING=None)]]
        )

        self.assertEqual(observation.cloud_coverage.value, 75)
        self.assertEqual(observation.cloud_ceiling.value, 3000)

    def test_cavok_falls_back_to_zero_cloud_coverage(self):
        report = "METAR RCBS 010000Z 18005KT CAVOK 25/24 Q1011="
        observation = self.client._convert_to_observation(
            "Kinmen", [[_record(REPORT=report, CEILING=None)]]
        )

        self.assertEqual(observation.cloud_coverage.value, 0)
        self.assertEqual(observation.cloud_ceiling.value, "")


if __name__ == "__main__":
    unittest.main()
