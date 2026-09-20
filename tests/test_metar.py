"""Tests for the dependency-free METAR helpers."""

from pathlib import Path
import importlib.util
import sys
import unittest


MODULE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "aoaws_anws" / "metar.py"
)
SPEC = importlib.util.spec_from_file_location("aoaws_metar", MODULE_PATH)
METAR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = METAR
SPEC.loader.exec_module(METAR)

current_report_tokens = METAR.current_report_tokens
parse_dew_point = METAR.parse_dew_point
parse_clouds = METAR.parse_clouds
parse_pressure = METAR.parse_pressure
parse_present_weather = METAR.parse_present_weather
parse_rvr = METAR.parse_rvr
parse_rvr_metres = METAR.parse_rvr_metres
parse_report_header = METAR.parse_report_header
parse_temperature = METAR.parse_temperature
parse_trends = METAR.parse_trends
parse_visibility = METAR.parse_visibility
parse_wind = METAR.parse_wind


class MetarParserTests(unittest.TestCase):
    def test_anws_rvr_examples(self):
        report = (
            "SPECI RCBS 130146Z 19006KT 0800 "
            "R24/800M R24/500M R06/600M FG 25/24 Q1011="
        )
        self.assertEqual(parse_rvr_metres(report), [800, 500, 600])

    def test_rvr_variants_and_feet(self):
        report = "METAR TEST 010000Z R06/P2000 R24/M0050 R18/0800V1600D R09/2000FT="
        self.assertEqual(parse_rvr_metres(report), [2000, 50, 800, 610])

    def test_rvr_preserves_runway_bounds_and_trend(self):
        report = "METAR TEST 010000Z R06/P2000U R24/M0050 R18/0800V1600D="
        groups = parse_rvr(report)

        self.assertEqual(groups[0].runway, "R06")
        self.assertEqual(groups[0].lower_metres, 2000)
        self.assertEqual(groups[0].lower_qualifier, "P")
        self.assertEqual(groups[0].trend, "U")

        self.assertEqual(groups[1].lower_qualifier, "M")
        self.assertIsNone(groups[1].upper)

        self.assertEqual(groups[2].runway, "R18")
        self.assertEqual(groups[2].lower_metres, 800)
        self.assertEqual(groups[2].upper_metres, 1600)
        self.assertEqual(groups[2].trend, "D")

    def test_wind_gust_and_variable_direction(self):
        wind = parse_wind("METAR TEST 010000Z 18012G25KT 140V220 9999=")

        self.assertEqual(wind.direction, 180)
        self.assertEqual(wind.speed, 12)
        self.assertEqual(wind.gust, 25)
        self.assertEqual(wind.unit, "KT")
        self.assertEqual((wind.variable_from, wind.variable_to), (140, 220))
        self.assertEqual(wind.raw, "18012G25KT 140V220")

    def test_wind_calm_variable_and_upper_bound(self):
        calm = parse_wind("METAR TEST 010000Z 00000KT 9999=")
        self.assertTrue(calm.is_calm)

        variable = parse_wind("METAR TEST 010000Z VRB03MPS 9999=")
        self.assertIsNone(variable.direction)
        self.assertEqual(variable.speed, 3)
        self.assertEqual(variable.unit, "MPS")

        upper_bound = parse_wind("METAR TEST 010000Z 270P99KT 9999=")
        self.assertEqual(upper_bound.speed, 99)
        self.assertEqual(upper_bound.speed_qualifier, "P")

    def test_visibility_direction_and_cavok(self):
        visibility = parse_visibility("METAR TEST 010000Z 18005KT 4000NE BR=")
        self.assertEqual(visibility.metres, 4000)
        self.assertEqual(visibility.direction, "NE")
        self.assertFalse(visibility.cavok)

        cavok = parse_visibility("METAR TEST 010000Z 18005KT CAVOK=")
        self.assertTrue(cavok.cavok)
        self.assertIsNone(cavok.metres)

    def test_present_weather_stops_before_trend(self):
        report = "SPECI TEST 010000Z 18005KT 4000 SHRA BR 20/19 Q1012 BECMG +TSRA"
        self.assertEqual(parse_present_weather(report), ["SHRA", "BR"])

    def test_present_weather_accepts_combined_precipitation(self):
        report = "METAR TEST 010000Z 18005KT 4000 -RASN +TSRAGR 20/19 Q1012="
        self.assertEqual(
            parse_present_weather(report), ["-RASN", "+TSRAGR"]
        )

    def test_report_header_flags_and_time(self):
        header = parse_report_header(
            "SPECI AUTO COR RCBS 201230Z 18005KT 9999="
        )

        self.assertEqual(header.kind, "SPECI")
        self.assertEqual(header.station, "RCBS")
        self.assertEqual(header.report_time_utc, "201230Z")
        self.assertTrue(header.automated)
        self.assertTrue(header.corrected)
        self.assertFalse(header.nil)

        nil_header = parse_report_header("METAR RCBS 201230Z NIL=")
        self.assertTrue(nil_header.nil)

    def test_cloud_layers_and_vertical_visibility(self):
        report = (
            "METAR TEST 010000Z 18005KT 9999 "
            "FEW018 SCT025TCU BKN030CB VV/// NSC NCD="
        )
        clouds = parse_clouds(report)

        self.assertEqual(
            [(cloud.amount, cloud.height_feet, cloud.cloud_type) for cloud in clouds],
            [
                ("FEW", 1800, None),
                ("SCT", 2500, "TCU"),
                ("BKN", 3000, "CB"),
                ("VV", None, None),
                ("NSC", None, None),
                ("NCD", None, None),
            ],
        )
        self.assertTrue(clouds[2].is_ceiling)
        self.assertTrue(clouds[3].is_ceiling)
        self.assertEqual(
            [cloud.coverage_percent for cloud in clouds],
            [25, 50, 75, 100, 0, 0],
        )

    def test_runway_state_group_is_not_rvr(self):
        self.assertEqual(parse_rvr_metres("METAR TEST R06/290095="), [])

    def test_trend_and_remark_groups_are_ignored(self):
        report = "METAR TEST 9999 20/18 Q1012 BECMG R06/0600U RMK R24/0500D="
        self.assertEqual(parse_rvr_metres(report), [])

    def test_dew_point_does_not_treat_rvr_as_temperature(self):
        report = "SPECI RCBS 130146Z 0800 R06/1600U 25/24 Q1011="
        self.assertEqual(parse_dew_point(report, 25), 24)

    def test_negative_dew_point(self):
        self.assertEqual(parse_dew_point("METAR TEST M02/M08 Q1020=", -2), -8)

    def test_temperature_group(self):
        temperature = parse_temperature("METAR TEST M02/M08 Q1020=")

        self.assertEqual(temperature.temperature, -2)
        self.assertEqual(temperature.dew_point, -8)
        self.assertEqual(temperature.raw, "M02/M08")

    def test_temperature_mismatch_is_ignored(self):
        self.assertIsNone(parse_dew_point("METAR TEST 25/24 Q1011=", 26))

    def test_pressure(self):
        self.assertEqual(parse_pressure("METAR TEST 25/24 Q1011 NOSIG="), 1011)

    def test_current_report_tokens_stop_at_forecast(self):
        report = "SPECI RCBS 291010Z 4000 SHRA 20/20 Q1011 BECMG 1500 +TSRA"
        self.assertNotIn("+TSRA", current_report_tokens(report))

    def test_trend_weather_is_separate_from_current_weather(self):
        report = "SPECI RCBS 291010Z 4000 SHRA 20/20 Q1011 BECMG 1500 +TSRA"
        trends = parse_trends(report)

        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0].kind, "BECMG")
        self.assertEqual(trends[0].tokens, ("1500", "+TSRA"))
        self.assertEqual(trends[0].raw, "BECMG 1500 +TSRA")
        self.assertNotIn("BECMG", current_report_tokens(report))
        self.assertNotIn("+TSRA", current_report_tokens(report))

    def test_multiple_trends_and_nosig(self):
        report = (
            "METAR TEST 9999 20/18 Q1012 "
            "TEMPO FM1030 TL1130 2000 SHRA "
            "BECMG AT1200 1500 NSW NOSIG="
        )
        trends = parse_trends(report)

        self.assertEqual(
            [(trend.kind, trend.tokens) for trend in trends],
            [
                ("TEMPO", ("FM1030", "TL1130", "2000", "SHRA")),
                ("BECMG", ("AT1200", "1500", "NSW")),
                ("NOSIG", ()),
            ],
        )
        self.assertEqual(trends[0].time_markers, {"FM": "1030", "TL": "1130"})
        self.assertEqual(trends[0].payload_tokens, ("2000", "SHRA"))
        self.assertEqual(trends[0].visibility_tokens, ("2000",))
        self.assertEqual(trends[0].weather_tokens, ("SHRA",))
        self.assertEqual(trends[1].time_markers, {"AT": "1200"})
        self.assertEqual(trends[1].payload_tokens, ("1500", "NSW"))
        self.assertEqual(trends[1].visibility_tokens, ("1500",))
        self.assertEqual(trends[1].weather_tokens, ("NSW",))

    def test_trend_classifies_weather_visibility_and_clouds(self):
        report = (
            "SPECI TEST 010000Z 9999 20/18 Q1012 "
            "BECMG 1500 +TSRA BKN020CB VV///"
        )
        trend = parse_trends(report)[0]

        self.assertEqual(trend.visibility_tokens, ("1500",))
        self.assertEqual(trend.weather_tokens, ("+TSRA",))
        self.assertEqual(trend.cloud_tokens, ("BKN020CB", "VV///"))

    def test_trend_accepts_thunder_without_precipitation(self):
        trend = parse_trends(
            "SPECI TEST 010000Z 9999 20/18 Q1012 BECMG TS"
        )[0]

        self.assertEqual(trend.weather_tokens, ("TS",))

    def test_trend_parser_stops_before_remarks(self):
        report = "METAR TEST 9999 Q1012 BECMG R06/0600U RMK R24/0500D="
        trends = parse_trends(report)

        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0].tokens, ("R06/0600U",))
        self.assertNotIn("R24/0500D", trends[0].tokens)


if __name__ == "__main__":
    unittest.main()
