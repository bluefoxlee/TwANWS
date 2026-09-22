"""Conservative rolling-window trend detection for AOAWS observations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any


TREND_UNKNOWN = "unknown"
TREND_STABLE = "stable"
TREND_IMPROVING = "improving"
TREND_DETERIORATING = "deteriorating"
TREND_MIXED = "mixed"

TREND_WINDOW = timedelta(hours=3)
TREND_MAX_GAP = timedelta(minutes=90)
TREND_MIN_OBSERVATIONS = 3


_REASON_LABELS = {
    "visibility_decreasing": ("能見度下降", "visibility decreasing"),
    "visibility_improving": ("能見度改善", "visibility improving"),
    "rvr_decreasing": ("RVR 下降", "RVR decreasing"),
    "rvr_improving": ("RVR 改善", "RVR improving"),
    "weather_intensifying": ("天氣現象增強", "weather intensifying"),
    "weather_easing": ("天氣現象減弱", "weather easing"),
    "thunderstorm_present": ("出現雷雨", "thunderstorm present"),
    "thunderstorm_ended": ("雷雨消退", "thunderstorm ended"),
    "ceiling_lowering": ("雲幕降低", "ceiling lowering"),
    "ceiling_rising": ("雲幕升高", "ceiling rising"),
    "wind_increasing": ("風勢增強", "wind increasing"),
    "wind_decreasing": ("風勢減弱", "wind decreasing"),
    "insufficient_history": ("等待更多觀測", "waiting for more observations"),
}


@dataclass(frozen=True)
class TrendResult:
    """A JSON-safe result for the current observation trend."""

    state: str
    score: int | None
    reasons: tuple[str, ...]
    summary: str
    confidence: str
    since: str | None = None
    observation_count: int | None = None
    window_minutes: int | None = None

    def as_attributes(self) -> dict[str, Any]:
        """Return attributes suitable for Home Assistant state data."""
        attributes: dict[str, Any] = {
            "trend_state": self.state,
            "trend_score": self.score,
            "trend_reasons": list(self.reasons),
            "trend_summary": self.summary,
            "trend_confidence": self.confidence,
        }
        if self.since:
            attributes["trend_since"] = self.since
        if self.observation_count is not None:
            attributes["trend_observation_count"] = self.observation_count
        if self.window_minutes is not None:
            attributes["trend_window_minutes"] = self.window_minutes
        return attributes


def unknown_trend(
    language: str = "tw",
    since: str | None = None,
    observation_count: int | None = None,
    window_minutes: int | None = None,
) -> TrendResult:
    """Return a result for the first observation or incomplete history."""
    return TrendResult(
        state=TREND_UNKNOWN,
        score=None,
        reasons=("insufficient_history",),
        summary=_summary(TREND_UNKNOWN, ("insufficient_history",), language),
        confidence="low",
        since=since,
        observation_count=observation_count,
        window_minutes=window_minutes,
    )


def append_observation_history(history: list[Any], observation: Any) -> list[Any]:
    """Keep a continuous three-hour observation window.

    A long reporting gap starts a new window so an evening METAR is never
    compared with the next morning's first report.
    """
    current_time = _observation_datetime(observation)
    if current_time is None:
        return [observation]

    ordered_history = _ordered_observations(history)
    if ordered_history:
        previous_time = _observation_datetime(ordered_history[-1])
        if (
            previous_time is None
            or current_time <= previous_time
            or current_time - previous_time > TREND_MAX_GAP
        ):
            return [observation]

    cutoff = current_time - TREND_WINDOW
    return [
        item
        for item in ordered_history
        if (item_time := _observation_datetime(item)) is not None and item_time >= cutoff
    ] + [observation]


def analyze_observation_history(
    history: list[Any], language: str = "tw"
) -> TrendResult:
    """Describe the net change across a continuous three-hour window."""
    observations = _ordered_observations(history)
    if not observations:
        return unknown_trend(language)

    first = observations[0]
    current = observations[-1]
    start_time = _observation_time(first)
    duration = _window_minutes(first, current)
    count = len(observations)
    if count < TREND_MIN_OBSERVATIONS:
        return unknown_trend(
            language,
            since=start_time,
            observation_count=count,
            window_minutes=duration,
        )

    result = compare_observations(first, current, language)
    return replace(
        result,
        since=start_time,
        observation_count=count,
        window_minutes=duration,
    )


def compare_observations(
    previous: Any,
    current: Any,
    language: str = "tw",
) -> TrendResult:
    """Compare two observations without treating small noise as a trend.

    The result is intentionally conservative: a single weak signal stays
    stable, while a severe weather onset or multiple independent signals can
    produce a meaningful trend.
    """
    if previous is None or current is None:
        return unknown_trend(language, _observation_time(current))

    signals: list[tuple[str, int]] = []
    # Compare prevailing visibility separately from RVR. The public
    # ``visibility`` element may be overridden by the lowest RVR value.
    previous_visibility = _element_value(previous, "prevailing_visibility")
    current_visibility = _element_value(current, "prevailing_visibility")
    _append_bucket_signal(
        signals,
        previous_visibility,
        current_visibility,
        "visibility_decreasing",
        "visibility_improving",
        weight=3,
    )

    previous_rvr = _element_value(previous, "rvr_min")
    current_rvr = _element_value(current, "rvr_min")
    _append_bucket_signal(
        signals,
        previous_rvr,
        current_rvr,
        "rvr_decreasing",
        "rvr_improving",
        weight=3,
    )

    previous_weather = _weather_profile(previous)
    current_weather = _weather_profile(current)
    if current_weather["level"] > previous_weather["level"]:
        signals.append(("weather_intensifying", _weather_weight(current_weather["level"])))
    elif current_weather["level"] < previous_weather["level"]:
        signals.append(("weather_easing", -_weather_weight(previous_weather["level"])))
    if current_weather["thunderstorm"] and not previous_weather["thunderstorm"]:
        signals.append(("thunderstorm_present", 4))
    elif previous_weather["thunderstorm"] and not current_weather["thunderstorm"]:
        signals.append(("thunderstorm_ended", -4))

    previous_ceiling = _ceiling_value(previous)
    current_ceiling = _ceiling_value(current)
    if previous_ceiling is not None and current_ceiling is not None:
        if current_ceiling <= previous_ceiling - 500:
            signals.append(("ceiling_lowering", 3))
        elif current_ceiling >= previous_ceiling + 500:
            signals.append(("ceiling_rising", -3))

    previous_wind = _wind_knots(previous)
    current_wind = _wind_knots(current)
    if previous_wind is not None and current_wind is not None:
        if current_wind >= previous_wind + 5:
            signals.append(("wind_increasing", 1))
        elif current_wind <= previous_wind - 5:
            signals.append(("wind_decreasing", -1))

    reasons = _unique_reasons(reason for reason, _score in signals)
    worsening = sum(max(score, 0) for _reason, score in signals)
    improving = sum(max(-score, 0) for _reason, score in signals)
    if worsening >= 4 and worsening >= improving + 2:
        state = TREND_DETERIORATING
    elif improving >= 4 and improving >= worsening + 2:
        state = TREND_IMPROVING
    elif worsening and improving:
        state = TREND_MIXED
    else:
        state = TREND_STABLE

    score = worsening - improving
    confidence = _confidence(signals, state)
    return TrendResult(
        state=state,
        score=score,
        reasons=reasons,
        summary=_summary(state, reasons, language),
        confidence=confidence,
        since=_observation_time(current),
    )


def _element_value(observation: Any, name: str) -> float | None:
    """Read an Element-like value while tolerating missing data."""
    element = getattr(observation, name, None)
    value = getattr(element, "value", element)
    try:
        if value in (None, "", "N/A"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _observation_time(observation: Any) -> str | None:
    return getattr(observation, "observation_time", None) if observation else None


def _observation_datetime(observation: Any) -> datetime | None:
    value = _observation_time(observation)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _ordered_observations(history: list[Any]) -> list[Any]:
    """Order valid observations and keep the last copy of each timestamp."""
    deduplicated: dict[datetime, Any] = {}
    for observation in history:
        timestamp = _observation_datetime(observation)
        if timestamp is not None:
            deduplicated[timestamp] = observation
    return [deduplicated[timestamp] for timestamp in sorted(deduplicated)]


def _window_minutes(first: Any, current: Any) -> int | None:
    first_time = _observation_datetime(first)
    current_time = _observation_datetime(current)
    if first_time is None or current_time is None:
        return None
    return max(0, int((current_time - first_time).total_seconds() // 60))


def _visibility_bucket(value: float | None) -> int | None:
    if value is None:
        return None
    if value >= 10:
        return 4
    if value >= 5:
        return 3
    if value >= 1:
        return 2
    return 1


def _append_bucket_signal(
    signals: list[tuple[str, int]],
    previous: float | None,
    current: float | None,
    decreasing_reason: str,
    improving_reason: str,
    weight: int,
) -> None:
    previous_bucket = _visibility_bucket(previous)
    current_bucket = _visibility_bucket(current)
    if previous_bucket is None or current_bucket is None:
        return
    if current_bucket < previous_bucket:
        signals.append((decreasing_reason, weight))
    elif current_bucket > previous_bucket:
        signals.append((improving_reason, -weight))


def _weather_profile(observation: Any) -> dict[str, Any]:
    codes = [str(code).upper() for code in getattr(observation, "weather_codes", ())]
    if not codes:
        weather = getattr(observation, "weather", None)
        value = getattr(weather, "value", weather)
        if value:
            codes = [str(value).upper()]

    level = 0
    thunderstorm = False
    for code in codes:
        token = code.lstrip("+-")
        if "TS" in token:
            thunderstorm = True
            level = max(level, 5)
        elif "FG" in token or token in {"DS", "SS"}:
            level = max(level, 4)
        elif any(phenomenon in token for phenomenon in ("SN", "SG", "GR", "GS", "PL")):
            level = max(level, 3)
        elif "SH" in token:
            level = max(level, 2)
        elif any(phenomenon in token for phenomenon in ("RA", "DZ", "BR", "UP")):
            level = max(level, 1)
    return {"level": level, "thunderstorm": thunderstorm}


def _weather_weight(level: int) -> int:
    return 4 if level >= 4 else 2


def _ceiling_value(observation: Any) -> float | None:
    value = _element_value(observation, "cloud_ceiling")
    if value is not None:
        return value
    ceilings = [
        cloud.height_feet
        for cloud in getattr(observation, "cloud_groups", ())
        if getattr(cloud, "is_ceiling", False)
        and getattr(cloud, "height_feet", None) is not None
    ]
    return min(ceilings) if ceilings else None


def _wind_knots(observation: Any) -> float | None:
    element = getattr(observation, "wind_gust", None) or getattr(observation, "wind_speed", None)
    value = getattr(element, "value", element)
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    units = str(getattr(element, "units", "kn")).lower()
    if units in {"m/s", "mps"}:
        return value * 1.94384
    if units in {"km/h", "kph"}:
        return value * 0.539957
    return value


def _unique_reasons(reasons) -> tuple[str, ...]:
    return tuple(dict.fromkeys(reasons))


def _confidence(signals: list[tuple[str, int]], state: str) -> str:
    nonzero = [score for _reason, score in signals if score]
    if state in {TREND_DETERIORATING, TREND_IMPROVING} and (
        len(nonzero) >= 2 or max(abs(score) for score in nonzero) >= 4
    ):
        return "high"
    if nonzero:
        return "medium"
    return "low"


def _summary(state: str, reasons: tuple[str, ...], language: str) -> str:
    if str(language).lower().startswith("en"):
        labels = [_REASON_LABELS.get(reason, (reason, reason))[1] for reason in reasons]
        return {
            TREND_UNKNOWN: "Waiting for more observations",
            TREND_STABLE: "No significant recent change",
            TREND_MIXED: "Weather indicators are mixed",
        }.get(state, ", ".join(labels[:3]) or "Weather trend changing")

    labels = [_REASON_LABELS.get(reason, (reason, reason))[0] for reason in reasons]
    return {
        TREND_UNKNOWN: "等待更多有效觀測",
        TREND_STABLE: "近期沒有明顯變化",
        TREND_MIXED: "不同氣象指標變化方向不一致",
    }.get(state, "、".join(labels[:3]) or "天氣趨勢變化中")
