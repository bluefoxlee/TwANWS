"""Small METAR helpers used by the AOAWS data adapter.

The ANWS JSON fields remain the primary data source.  Only values that are not
provided separately by the API (dew point and pressure), plus runway visual
range (RVR), are read from the raw METAR report.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

_RVR_RE = re.compile(
    r"^(?P<runway>R\d{2}[LCR]?)/"
    r"(?P<low>[MP]?\d{3,4})"
    r"(?:V(?P<high>[MP]?\d{3,4}))?"
    r"(?P<unit>FT|M)?"
    r"(?P<trend>[UDN])?=?$"
)
_VISIBILITY_RE = re.compile(r"^(?P<value>\d{4})(?P<direction>[NSEW]{1,2})?$")
_CLOUD_RE = re.compile(
    r"^(?P<amount>FEW|SCT|BKN|OVC)(?P<height>\d{3})(?P<type>CB|TCU)?$"
)
_VERTICAL_VISIBILITY_RE = re.compile(r"^VV(?P<height>\d{3}|///)$")
_REPORT_TIME_RE = re.compile(r"^\d{6}Z$")
_TEMPERATURE_RE = re.compile(r"^(?P<temperature>M?\d{2})/(?P<dew_point>M?\d{2})=?$")
_PRESSURE_RE = re.compile(r"^Q(?P<pressure>\d{4})=?$")
_WIND_RE = re.compile(
    r"^(?P<direction>\d{3}|VRB)"
    r"(?P<speed>P?\d{2})"
    r"(?:G(?P<gust>P?\d{2}))?"
    r"(?P<unit>KT|MPS)$"
)
_VARIABLE_WIND_RE = re.compile(r"^(?P<from>\d{3})V(?P<to>\d{3})$")
_TREND_TIME_RE = re.compile(r"^(?P<marker>FM|TL|AT)(?P<time>\d{4})$")
_TREND_WEATHER_RE = re.compile(
    r"^(?:[+-]?(?:VC)?(?:TS|SH)|"
    r"[+-]?(?:VC)?(?:MI|BC|PR|DR|BL|SH|TS|FZ)?"
    r"(?:DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PO|SQ|FC|SS|DS)"
    r"(?:DZ|RA|SN|SG|IC|PL|GR|GS|UP)?"
    r")$"
)
_TREND_CLOUD_RE = re.compile(
    r"^(?:(?:FEW|SCT|BKN|OVC)\d{3}(?:CB|TCU)?|VV(?:\d{3}|///)|NSC|NCD)$"
)
_TREND_MARKERS = {"BECMG", "TEMPO", "NOSIG", "RMK"}


@dataclass(frozen=True)
class RvrGroup:
    """One runway visual range group from a METAR/SPECI report.

    ``M`` and ``P`` are kept as qualifiers instead of being folded into the
    numeric value.  The Code Book defines them as below-minimum and
    above-maximum indicators, respectively.
    """

    runway: str
    lower: int
    upper: int | None
    lower_qualifier: str | None
    upper_qualifier: str | None
    unit: str
    trend: str | None
    raw: str

    @staticmethod
    def _to_metres(value: int, unit: str) -> int:
        if unit == "FT":
            return round(value * 0.3048)
        return value

    @property
    def lower_metres(self) -> int:
        """Return the lower RVR value in metres."""
        return self._to_metres(self.lower, self.unit)

    @property
    def upper_metres(self) -> int | None:
        """Return the upper RVR value in metres, if reported."""
        if self.upper is None:
            return None
        return self._to_metres(self.upper, self.unit)


@dataclass(frozen=True)
class ReportHeader:
    """METAR/SPECI report identity and quality flags."""

    kind: str
    station: str | None
    report_time_utc: str | None
    automated: bool
    corrected: bool
    nil: bool


@dataclass(frozen=True)
class TemperatureGroup:
    """Temperature/dew-point group from a METAR/SPECI report."""

    temperature: int
    dew_point: int
    raw: str


@dataclass(frozen=True)
class WindGroup:
    """One wind group from a METAR/SPECI report."""

    direction: int | None
    speed: int
    gust: int | None
    unit: str
    variable_from: int | None
    variable_to: int | None
    speed_qualifier: str | None
    gust_qualifier: str | None
    raw: str

    @property
    def is_calm(self) -> bool:
        """Return whether the wind group reports calm conditions."""
        return self.direction == 0 and self.speed == 0 and self.gust is None


@dataclass(frozen=True)
class VisibilityGroup:
    """Prevailing or directional visibility from a METAR/SPECI report."""

    metres: int | None
    direction: str | None
    cavok: bool
    raw: str


@dataclass(frozen=True)
class CloudGroup:
    """One cloud layer or vertical-visibility group."""

    amount: str
    height_hundreds_ft: int | None
    cloud_type: str | None
    vertical_visibility: bool
    raw: str

    @property
    def height_feet(self) -> int | None:
        """Return the reported cloud/vertical-visibility height in feet."""
        if self.height_hundreds_ft is None:
            return None
        return self.height_hundreds_ft * 100

    @property
    def is_ceiling(self) -> bool:
        """Return whether this group contributes to the operational ceiling."""
        return self.vertical_visibility or self.amount in {"BKN", "OVC"}

    @property
    def coverage_percent(self) -> int | None:
        """Return an operational sky-cover percentage for this group.

        METAR cloud amounts are reported in oktas rather than percentages.
        Home Assistant weather entities use percentages, so use the standard
        midpoint representation for FEW/SCT/BKN and 100% for OVC/VV.
        NSC/NCD explicitly report no significant cloud.
        """
        return {
            "FEW": 25,
            "SCT": 50,
            "BKN": 75,
            "OVC": 100,
            "VV": 100,
            "NSC": 0,
            "NCD": 0,
        }.get(self.amount)


@dataclass(frozen=True)
class TrendGroup:
    """One significant trend group from a METAR/SPECI report."""

    kind: str
    tokens: tuple[str, ...]
    raw: str

    @property
    def time_markers(self) -> dict[str, str]:
        """Return FM/TL/AT trend times as marker-to-UTC mappings."""
        markers: dict[str, str] = {}
        for token in self.tokens:
            match = _TREND_TIME_RE.fullmatch(token)
            if match is not None:
                markers[match.group("marker")] = match.group("time")
        return markers

    @property
    def payload_tokens(self) -> tuple[str, ...]:
        """Return trend tokens excluding FM/TL/AT time markers."""
        return tuple(
            token for token in self.tokens if _TREND_TIME_RE.fullmatch(token) is None
        )

    @property
    def visibility_tokens(self) -> tuple[str, ...]:
        """Return trend visibility tokens, including CAVOK."""
        return tuple(
            token
            for token in self.payload_tokens
            if token == "CAVOK" or re.fullmatch(r"\d{4}", token) is not None
        )

    @property
    def weather_tokens(self) -> tuple[str, ...]:
        """Return present-weather or NSW tokens from the trend group."""
        return tuple(
            token
            for token in self.payload_tokens
            if token == "NSW" or _TREND_WEATHER_RE.fullmatch(token) is not None
        )

    @property
    def cloud_tokens(self) -> tuple[str, ...]:
        """Return cloud or vertical-visibility tokens from the trend group."""
        return tuple(
            token
            for token in self.payload_tokens
            if _TREND_CLOUD_RE.fullmatch(token) is not None
        )


def current_report_tokens(report: str) -> list[str]:
    """Return tokens from the current-observation part of a METAR/SPECI."""
    tokens: list[str] = []
    for token in report.split():
        marker = token.rstrip("=")
        if marker in _TREND_MARKERS or marker.startswith("FM") and marker[2:].isdigit():
            break
        tokens.append(token)
    return tokens


def parse_report_header(report: str) -> ReportHeader | None:
    """Parse METAR/SPECI identity and AUTO/COR/NIL flags."""
    tokens = [token.rstrip("=") for token in report.split()]
    if not tokens or tokens[0] not in {"METAR", "SPECI"}:
        return None

    kind = tokens[0]
    # AUTO/COR/NIL may occur in the compact header before or after the
    # station/time fields, so inspect only the first few header tokens.
    flags = {
        token for token in tokens[1:7] if token in {"AUTO", "COR", "NIL"}
    }

    station = None
    station_index = 1
    while station_index < len(tokens):
        if (
            tokens[station_index] not in {"AUTO", "COR", "NIL"}
            and re.fullmatch(r"[A-Z]{4}", tokens[station_index])
        ):
            station = tokens[station_index]
            break
        station_index += 1

    report_time = None
    if station is not None:
        for token in tokens[station_index + 1:]:
            if _REPORT_TIME_RE.fullmatch(token) is not None:
                report_time = token
                break

    return ReportHeader(
        kind=kind,
        station=station,
        report_time_utc=report_time,
        automated="AUTO" in flags,
        corrected="COR" in flags,
        nil="NIL" in flags,
    )


def parse_trends(report: str) -> list[TrendGroup]:
    """Parse BECMG, TEMPO and NOSIG groups from a METAR/SPECI report.

    Only the current-observation section is excluded from trend groups.  The
    tokens inside each group are intentionally preserved so callers can apply
    the Code Book rules for weather, visibility, clouds and validity times
    without losing information.
    """
    tokens = [token.rstrip("=") for token in report.split()]
    trends: list[TrendGroup] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if token == "RMK":
            break
        if token in {"BECMG", "TEMPO"}:
            end = index + 1
            while end < len(tokens) and tokens[end] not in _TREND_MARKERS:
                end += 1
            trends.append(
                TrendGroup(
                    kind=token,
                    tokens=tuple(tokens[index + 1:end]),
                    raw=" ".join(tokens[index:end]),
                )
            )
            index = end
            continue
        if token == "NOSIG":
            trends.append(TrendGroup(kind="NOSIG", tokens=(), raw=token))
        index += 1

    return trends


def _signed_temperature(value: str) -> int:
    """Convert a METAR temperature such as ``05`` or ``M03`` to Celsius."""
    return -int(value[1:]) if value.startswith("M") else int(value)


def parse_temperature(report: str) -> TemperatureGroup | None:
    """Parse the current temperature/dew-point group."""
    for token in current_report_tokens(report):
        match = _TEMPERATURE_RE.fullmatch(token)
        if match is not None:
            return TemperatureGroup(
                temperature=_signed_temperature(match.group("temperature")),
                dew_point=_signed_temperature(match.group("dew_point")),
                raw=token.rstrip("="),
            )
    return None


def parse_dew_point(report: str, expected_temperature: int | None = None) -> int | None:
    """Return the dew point from the current part of a METAR report."""
    temperature_group = parse_temperature(report)
    if temperature_group is not None and (
        expected_temperature is None
        or temperature_group.temperature == expected_temperature
    ):
        return temperature_group.dew_point
    return None


def parse_pressure(report: str) -> int | None:
    """Return QNH pressure in hPa from the current part of a METAR report."""
    for token in current_report_tokens(report):
        match = _PRESSURE_RE.fullmatch(token)
        if match is not None:
            return int(match.group("pressure"))
    return None


def parse_wind(report: str) -> WindGroup | None:
    """Parse the first current-observation wind group in a report."""
    tokens = current_report_tokens(report)
    for index, token in enumerate(tokens):
        match = _WIND_RE.fullmatch(token)
        if match is None:
            continue

        variable_from = None
        variable_to = None
        raw = token.rstrip("=")
        if index + 1 < len(tokens):
            variable_match = _VARIABLE_WIND_RE.fullmatch(tokens[index + 1].rstrip("="))
            if variable_match is not None:
                variable_from = int(variable_match.group("from"))
                variable_to = int(variable_match.group("to"))
                raw = f"{raw} {tokens[index + 1].rstrip('=')}"

        speed_token = match.group("speed")
        gust_token = match.group("gust")
        return WindGroup(
            direction=(
                None
                if match.group("direction") == "VRB"
                else int(match.group("direction"))
            ),
            speed=int(speed_token.lstrip("P")),
            gust=int(gust_token.lstrip("P")) if gust_token else None,
            unit=match.group("unit"),
            variable_from=variable_from,
            variable_to=variable_to,
            speed_qualifier="P" if speed_token.startswith("P") else None,
            gust_qualifier=("P" if gust_token and gust_token.startswith("P") else None),
            raw=raw,
        )
    return None


def parse_visibility(report: str) -> VisibilityGroup | None:
    """Parse prevailing visibility, directional visibility or CAVOK."""
    for token in current_report_tokens(report):
        clean_token = token.rstrip("=")
        if clean_token == "CAVOK":
            return VisibilityGroup(
                metres=None, direction=None, cavok=True, raw=clean_token
            )

        match = _VISIBILITY_RE.fullmatch(clean_token)
        if match is not None:
            return VisibilityGroup(
                metres=int(match.group("value")),
                direction=match.group("direction"),
                cavok=False,
                raw=clean_token,
            )
    return None


def parse_present_weather(report: str) -> list[str]:
    """Return present-weather groups from the current observation section."""
    return [
        token.rstrip("=")
        for token in current_report_tokens(report)
        if _TREND_WEATHER_RE.fullmatch(token.rstrip("=")) is not None
    ]


def parse_clouds(report: str) -> list[CloudGroup]:
    """Parse cloud layers, vertical visibility and NSC/NCD groups."""
    clouds: list[CloudGroup] = []
    for token in current_report_tokens(report):
        clean_token = token.rstrip("=")
        match = _CLOUD_RE.fullmatch(clean_token)
        if match is not None:
            clouds.append(
                CloudGroup(
                    amount=match.group("amount"),
                    height_hundreds_ft=int(match.group("height")),
                    cloud_type=match.group("type"),
                    vertical_visibility=False,
                    raw=clean_token,
                )
            )
            continue

        vertical_match = _VERTICAL_VISIBILITY_RE.fullmatch(clean_token)
        if vertical_match is not None:
            raw_height = vertical_match.group("height")
            clouds.append(
                CloudGroup(
                    amount="VV",
                    height_hundreds_ft=(
                        int(raw_height) if raw_height != "///" else None
                    ),
                    cloud_type=None,
                    vertical_visibility=True,
                    raw=clean_token,
                )
            )
            continue

        if clean_token in {"NSC", "NCD"}:
            clouds.append(
                CloudGroup(
                    amount=clean_token,
                    height_hundreds_ft=None,
                    cloud_type=None,
                    vertical_visibility=False,
                    raw=clean_token,
                )
            )
    return clouds


def parse_rvr(report: str) -> list[RvrGroup]:
    """Parse RVR groups from the current observation part of a report.

    The returned records preserve runway identity, bounds, units and trend.
    The metre-suffixed form used by ANWS (for example ``R24/800M``) is
    accepted alongside standard ICAO forms.
    """
    groups: list[RvrGroup] = []
    for token in current_report_tokens(report):
        match = _RVR_RE.fullmatch(token)
        if match is None:
            continue

        low = match.group("low")
        high = match.group("high")
        lower_qualifier = low[0] if low[0] in "MP" else None
        upper_qualifier = (
            high[0] if high and high[0] in "MP" else None
        )
        unit = match.group("unit") or "M"
        groups.append(
            RvrGroup(
                runway=match.group("runway"),
                lower=int(low.lstrip("MP")),
                upper=int(high.lstrip("MP")) if high else None,
                lower_qualifier=lower_qualifier,
                upper_qualifier=upper_qualifier,
                unit=unit,
                trend=match.group("trend"),
                raw=token.rstrip("="),
            )
        )
    return groups


def parse_rvr_metres(report: str) -> list[int]:
    """Return reported RVR lower values converted to metres.

    Both ICAO forms (for example ``R06/1600U``, ``R06/P2000`` and
    ``R06/0800V1600D``) and the metre-suffixed form observed in ANWS data
    (for example ``R24/800M``) are accepted.  For a variable RVR group the
    lower value is deliberately used.
    """
    return [group.lower_metres for group in parse_rvr(report)]
