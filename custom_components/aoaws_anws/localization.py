"""Display-only localization helpers for AOAWS entities.

The values returned here are presentation labels. METAR values, Home
Assistant condition constants, and numeric measurements remain unchanged.
"""

from __future__ import annotations


VISIBILITY_LEVELS = (
    ("Very Poor", 0.1),
    ("Poor", 0.4),
    ("Moderate", 1),
    ("Good", 2),
    ("Very Good", 4),
    ("Excellent", 8),
    ("Extreme Excellent", 10),
)

VISIBILITY_LABELS = {
    "en": {
        "Very Poor": "Very Poor",
        "Poor": "Poor",
        "Moderate": "Moderate",
        "Good": "Good",
        "Very Good": "Very Good",
        "Excellent": "Excellent",
        "Extreme Excellent": "Extreme Excellent",
    },
    "tw": {
        "Very Poor": "極差",
        "Poor": "差",
        "Moderate": "中等",
        "Good": "良好",
        "Very Good": "很好",
        "Excellent": "優良",
        "Extreme Excellent": "極佳",
    },
}


def visibility_level(distance_km: float | None) -> str | None:
    """Return the stable English visibility level for a distance."""
    if distance_km is None:
        return None
    for level, threshold in VISIBILITY_LEVELS:
        if distance_km <= threshold:
            return level
    return VISIBILITY_LEVELS[-1][0]


def localized_visibility_label(distance_km: float | None, language: str) -> str | None:
    """Return a display label without changing the underlying distance."""
    level = visibility_level(distance_km)
    if level is None:
        return None
    labels = VISIBILITY_LABELS.get(language, VISIBILITY_LABELS["en"])
    return labels.get(level, level)


def localized_weather_text(weather: dict, language: str) -> str:
    """Return the configured-language weather description for display."""
    english = str(weather.get("EName") or "").strip()
    chinese = str(weather.get("CName") or "").strip()
    if language == "tw" and chinese:
        return chinese
    return english or chinese
