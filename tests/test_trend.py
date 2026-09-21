"""Tests for conservative consecutive-observation trend detection."""

from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys
import unittest


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components" / "aoaws_anws" / "trend.py"
SPEC = importlib.util.spec_from_file_location("aoaws_trend", MODULE_PATH)
TREND = importlib.util.module_from_spec(SPEC)
sys.modules["aoaws_trend"] = TREND
SPEC.loader.exec_module(TREND)


def _element(value, units=None):
    return SimpleNamespace(value=value, units=units)


def _observation(
    *,
    visibility=10.0,
    rvr=None,
    weather_codes=(),
    ceiling=None,
    wind_speed=7,
    wind_gust=None,
    observation_time="2026-09-21T12:00:00+08:00",
):
    return SimpleNamespace(
        visibility=_element(visibility, "km"),
        prevailing_visibility=_element(visibility, "km")
        if visibility is not None
        else None,
        rvr_min=_element(rvr, "km") if rvr is not None else None,
        weather_codes=tuple(weather_codes),
        weather=None,
        cloud_ceiling=_element(ceiling) if ceiling is not None else _element(""),
        cloud_groups=(),
        wind_speed=_element(wind_speed, "kn"),
        wind_gust=_element(wind_gust, "kn") if wind_gust is not None else None,
        observation_time=observation_time,
    )


class TrendTests(unittest.TestCase):
    def test_first_observation_is_unknown(self):
        result = TREND.unknown_trend("tw")

        self.assertEqual(result.state, "unknown")
        self.assertEqual(result.reasons, ("insufficient_history",))

    def test_visibility_drop_and_thunderstorm_are_deteriorating(self):
        previous = _observation(visibility=10.0, weather_codes=())
        current = _observation(
            visibility=4.0,
            weather_codes=("+TSRA",),
            observation_time="2026-09-21T12:05:00+08:00",
        )

        result = TREND.compare_observations(previous, current, "tw")

        self.assertEqual(result.state, "deteriorating")
        self.assertIn("visibility_decreasing", result.reasons)
        self.assertIn("thunderstorm_present", result.reasons)
        self.assertEqual(result.confidence, "high")

    def test_visibility_recovery_and_thunderstorm_end_are_improving(self):
        previous = _observation(visibility=4.0, weather_codes=("+TSRA",))
        current = _observation(
            visibility=10.0,
            weather_codes=(),
            observation_time="2026-09-21T12:05:00+08:00",
        )

        result = TREND.compare_observations(previous, current, "tw")

        self.assertEqual(result.state, "improving")
        self.assertIn("visibility_improving", result.reasons)
        self.assertIn("thunderstorm_ended", result.reasons)

    def test_conflicting_signals_are_mixed(self):
        previous = _observation(visibility=4.0, weather_codes=())
        current = _observation(
            visibility=10.0,
            weather_codes=("SHRA",),
            observation_time="2026-09-21T12:05:00+08:00",
        )

        result = TREND.compare_observations(previous, current, "tw")

        self.assertEqual(result.state, "mixed")

    def test_same_observation_is_stable(self):
        previous = _observation()
        current = _observation(observation_time=previous.observation_time)

        result = TREND.compare_observations(previous, current, "tw")

        self.assertEqual(result.state, "stable")
        self.assertEqual(result.score, 0)

    def test_low_ceiling_and_gust_increase_are_detected(self):
        previous = _observation(ceiling=2500, wind_speed=7)
        current = _observation(
            ceiling=1000,
            wind_speed=14,
            observation_time="2026-09-21T12:05:00+08:00",
        )

        result = TREND.compare_observations(previous, current, "tw")

        self.assertEqual(result.state, "deteriorating")
        self.assertIn("ceiling_lowering", result.reasons)
        self.assertIn("wind_increasing", result.reasons)

    def test_missing_values_do_not_create_false_trend(self):
        previous = _observation(visibility=None, ceiling=None, wind_speed=None)
        current = _observation(
            visibility=None,
            ceiling=None,
            wind_speed=None,
            observation_time="2026-09-21T12:05:00+08:00",
        )

        result = TREND.compare_observations(previous, current, "tw")

        self.assertEqual(result.state, "stable")
        self.assertEqual(result.score, 0)


if __name__ == "__main__":
    unittest.main()
