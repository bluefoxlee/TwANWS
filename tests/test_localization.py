"""Tests for display-only localization helpers."""

from pathlib import Path
import importlib.util
import sys
import unittest


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "aoaws_anws"
    / "localization.py"
)
SPEC = importlib.util.spec_from_file_location("aoaws_localization", MODULE_PATH)
LOCALIZATION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LOCALIZATION
SPEC.loader.exec_module(LOCALIZATION)


class LocalizationTests(unittest.TestCase):
    def test_visibility_labels_follow_language(self):
        self.assertEqual(
            LOCALIZATION.localized_visibility_label(0.05, "tw"), "極差"
        )
        self.assertEqual(
            LOCALIZATION.localized_visibility_label(10, "tw"), "極佳"
        )
        self.assertEqual(
            LOCALIZATION.localized_visibility_label(2, "en"), "Good"
        )

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(
            LOCALIZATION.localized_visibility_label(4, "fr"), "Very Good"
        )

    def test_missing_visibility_has_no_display_label(self):
        self.assertIsNone(LOCALIZATION.localized_visibility_label(None, "tw"))

    def test_weather_text_falls_back_when_preferred_text_is_missing(self):
        self.assertEqual(
            LOCALIZATION.localized_weather_text(
                {"CName": "", "EName": "Fog"}, "tw"
            ),
            "Fog",
        )
        self.assertEqual(
            LOCALIZATION.localized_weather_text(
                {"CName": "霧", "EName": "Fog"}, "en"
            ),
            "Fog",
        )


if __name__ == "__main__":
    unittest.main()
