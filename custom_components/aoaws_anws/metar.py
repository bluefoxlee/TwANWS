"""Small METAR helpers used by the AOAWS data adapter.

The ANWS JSON fields remain the primary data source.  The helpers read the raw
METAR/SPECI for values that are missing from the API and preserve aviation
details such as RVR, weather groups, cloud layers, trends, and Taiwan RMK
supplementary data.
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
_VISIBILITY_RE = re.compile(
    r"^(?P<value>\d{4})(?P<direction>N|NE|E|SE|S|SW|W|NW)?$"
)
_CLOUD_RE = re.compile(
    r"^(?P<amount>FEW|SCT|BKN|OVC|///)"
    r"(?P<height>\d{3}|///)(?P<type>CB|TCU|///)?$"
)
_VERTICAL_VISIBILITY_RE = re.compile(r"^VV(?P<height>\d{3}|///)$")
_REPORT_TIME_RE = re.compile(r"^\d{6}Z$")
_TEMPERATURE_RE = re.compile(r"^(?P<temperature>M?\d{2})/(?P<dew_point>M?\d{2})=?$")
_PRESSURE_RE = re.compile(r"^Q(?P<pressure>\d{4})=?$")
_ALTIMETER_RE = re.compile(r"^A(?P<pressure>\d{4})=?$")
_WIND_RE = re.compile(
    r"^(?P<direction>\d{3}|VRB)"
    r"(?P<speed>P?\d{2,3})"
    r"(?:G(?P<gust>P?\d{2,3}))?"
    r"(?P<unit>KT|MPS)$"
)
_UNKNOWN_RVR_RE = re.compile(
    r"^(?P<runway>R\d{2}[LCR]?)/(?P<value>/+)(?P<trend>[UDN])?=?$"
)
_VARIABLE_WIND_RE = re.compile(r"^(?P<from>\d{3})V(?P<to>\d{3})$")
_TREND_TIME_RE = re.compile(r"^(?P<marker>FM|TL|AT)(?P<time>\d{4})$")
_WEATHER_DESCRIPTORS = {"MI", "BC", "PR", "DR", "BL", "SH", "TS", "FZ"}
_PRECIPITATION = {"DZ", "RA", "SN", "SG", "PL", "GR", "GS", "UP"}
_OTHER_WEATHER = {
    "BR", "FG", "FU", "VA", "DU", "SA", "HZ", "PO", "SQ", "FC", "SS", "DS"
}
_VC_WEATHER = {"TS", "DS", "SS", "FG", "FC", "SH", "PO", "BLDU", "BLSA", "BLSN", "VA"}
_DESCRIPTOR_PHENOMENA = {
    "MI": {"FG"},
    "BC": {"FG"},
    "PR": {"FG"},
    "DR": {"DU", "SA", "SN"},
    "BL": {"DU", "SA", "SN"},
    "SH": {"RA", "SN", "GS", "GR", "UP"},
    "TS": {"RA", "SN", "GS", "GR", "UP"},
    "FZ": {"FG", "DZ", "RA", "UP"},
}
_TREND_CLOUD_RE = re.compile(
    r"^(?:(?:FEW|SCT|BKN|OVC|///)(?:\d{3}|///)(?:CB|TCU|///)?|"
    r"VV(?:\d{3}|///)|NSC|NCD)$"
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
    lower: int | None
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
    def lower_metres(self) -> int | None:
        """Return the lower RVR value in metres."""
        if self.lower is None:
            return None
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
    directional: tuple[tuple[int, str], ...] = ()


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
            if is_valid_weather_code(token)
        )

    @property
    def cloud_tokens(self) -> tuple[str, ...]:
        """Return cloud or vertical-visibility tokens from the trend group."""
        return tuple(
            token
            for token in self.payload_tokens
            if _is_cloud_token(token)
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


def _weather_phenomena(value: str) -> tuple[str, ...] | None:
    """Split the two-letter phenomena at the end of a weather group."""
    if not value or len(value) % 2:
        return None
    phenomena = tuple(value[index:index + 2] for index in range(0, len(value), 2))
    if len(phenomena) > 2:
        return None
    if any(item not in _PRECIPITATION | _OTHER_WEATHER for item in phenomena):
        return None
    return phenomena


def is_valid_weather_code(token: str) -> bool:
    """Return whether a token follows the Code Book's 4678 weather rules.

    This deliberately validates the syntax and descriptor combinations only.
    Range-dependent rules (for example BR visibility between 1,000 and 5,000
    metres) are checked by callers that also have the visibility group.
    """
    value = token.rstrip("=")
    if value in {"NSW", "//"}:
        return value == "NSW"

    intensity = value[:1] if value[:1] in "+-" else ""
    value = value[1:] if intensity else value
    if value.startswith("VC"):
        # The Code Book treats VC as the alternative to intensity and limits
        # it to the listed nearby phenomena.  In particular, VCSH and VCTS
        # are complete groups on their own.
        if intensity:
            return False
        return value[2:] in _VC_WEATHER

    descriptor = None
    for candidate in sorted(_WEATHER_DESCRIPTORS, key=len, reverse=True):
        if value.startswith(candidate):
            descriptor = candidate
            value = value[len(candidate):]
            break

    phenomena = _weather_phenomena(value)
    if descriptor is None:
        # A precipitation combination may contain one or two precipitation
        # phenomena; a non-precipitation group contains exactly one.
        return phenomena is not None and (
            len(phenomena) == 1
            or all(item in _PRECIPITATION for item in phenomena)
        )

    if descriptor == "TS" and not value:
        # TS alone means thunder/lightning without observed precipitation.
        return not intensity
    if phenomena is None or not phenomena:
        return False
    allowed = _DESCRIPTOR_PHENOMENA[descriptor]
    return all(item in allowed for item in phenomena)


def _is_cloud_token(token: str) -> bool:
    """Return whether a token is a Code Book cloud/sky-condition group."""
    return _TREND_CLOUD_RE.fullmatch(token.rstrip("=")) is not None


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
    """Return QNH pressure in hPa from Qxxxx or Taiwan RMK Axxxx."""
    for token in current_report_tokens(report):
        match = _PRESSURE_RE.fullmatch(token)
        if match is not None:
            return int(match.group("pressure"))

    # Taiwan's local METAR/SPECI convention also reports QNH in RMK as
    # Axxxx, where the value is hundredths of an inch Hg (for example
    # A3027 = 30.27 inHg).  Keep Home Assistant's pressure unit in hPa.
    tokens = [token.rstrip("=") for token in report.split()]
    try:
        remark_start = tokens.index("RMK") + 1
    except ValueError:
        return None
    for token in tokens[remark_start:]:
        match = _ALTIMETER_RE.fullmatch(token)
        if match is not None:
            inches_hg = int(match.group("pressure")) / 100
            return round(inches_hg * 33.8638866667)
    return None


def parse_altimeter_inches(report: str) -> float | None:
    """Return the Taiwan RMK Axxxx value in inches Hg, if present."""
    tokens = [token.rstrip("=") for token in report.split()]
    try:
        remark_start = tokens.index("RMK") + 1
    except ValueError:
        return None
    for token in tokens[remark_start:]:
        match = _ALTIMETER_RE.fullmatch(token)
        if match is not None:
            return int(match.group("pressure")) / 100
    return None


def parse_rmk_tokens(report: str) -> tuple[str, ...]:
    """Return raw supplementary tokens following the RMK marker."""
    tokens = [token.rstrip("=") for token in report.split()]
    try:
        return tuple(tokens[tokens.index("RMK") + 1:])
    except ValueError:
        return ()


def _parse_wind_value(value: str, unit: str) -> tuple[int, str | None] | None:
    """Parse a regular wind value or a Code Book upper-bound value."""
    if value.startswith("P"):
        # P99KT and P49MPS are the only upper-bound forms defined by the
        # Code Book.  They intentionally retain their P qualifier elsewhere.
        expected = "99" if unit == "KT" else "49"
        if value != f"P{expected}":
            return None
        return int(expected), "P"
    if len(value) not in {2, 3} or not value.isdigit():
        return None
    return int(value), None


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
        unit = match.group("unit")
        speed_value = _parse_wind_value(speed_token, unit)
        gust_value = _parse_wind_value(gust_token, unit) if gust_token else None
        if speed_value is None or (gust_token and gust_value is None):
            continue
        return WindGroup(
            direction=(
                None
                if match.group("direction") == "VRB"
                else int(match.group("direction"))
            ),
            speed=speed_value[0],
            gust=gust_value[0] if gust_value else None,
            unit=unit,
            variable_from=variable_from,
            variable_to=variable_to,
            speed_qualifier=speed_value[1],
            gust_qualifier=gust_value[1] if gust_value else None,
            raw=raw,
        )
    return None


def parse_visibility(report: str) -> VisibilityGroup | None:
    """Parse prevailing visibility, directional visibility or CAVOK."""
    groups: list[tuple[int, str | None, str]] = []
    for token in current_report_tokens(report):
        clean_token = token.rstrip("=")
        if clean_token == "CAVOK":
            return VisibilityGroup(
                metres=None, direction=None, cavok=True, raw=clean_token
            )

        match = _VISIBILITY_RE.fullmatch(clean_token)
        if match is not None:
            groups.append(
                (int(match.group("value")), match.group("direction"), clean_token)
            )
    if not groups:
        return None

    # The first undirected value is prevailing visibility.  Keep all
    # directional minima so the raw Code Book VNVNVNVNDv information is not
    # lost, while retaining the historical single-group API for callers.
    prevailing = next((group for group in groups if group[1] is None), groups[0])
    directional = tuple(
        (metres, direction)
        for metres, direction, _raw in groups
        if direction is not None
    )
    return VisibilityGroup(
        metres=prevailing[0],
        direction=prevailing[1],
        cavok=False,
        raw=prevailing[2],
        directional=directional,
    )


def parse_present_weather(report: str) -> list[str]:
    """Return present-weather groups from the current observation section."""
    return [
        token.rstrip("=")
        for token in current_report_tokens(report)
        if is_valid_weather_code(token)
    ]


def _parse_cloud_group(clean_token: str) -> CloudGroup | None:
    """Parse a cloud group, including AUTO slash replacements."""
    match = _CLOUD_RE.fullmatch(clean_token)
    if match is not None:
        raw_height = match.group("height")
        cloud_type = match.group("type")
        return CloudGroup(
            amount=match.group("amount"),
            height_hundreds_ft=int(raw_height) if raw_height != "///" else None,
            cloud_type=cloud_type if cloud_type not in {None, "///"} else None,
            vertical_visibility=False,
            raw=clean_token,
        )

    vertical_match = _VERTICAL_VISIBILITY_RE.fullmatch(clean_token)
    if vertical_match is not None:
        raw_height = vertical_match.group("height")
        return CloudGroup(
            amount="VV",
            height_hundreds_ft=int(raw_height) if raw_height != "///" else None,
            cloud_type=None,
            vertical_visibility=True,
            raw=clean_token,
        )

    if clean_token in {"NSC", "NCD"}:
        return CloudGroup(
            amount=clean_token,
            height_hundreds_ft=None,
            cloud_type=None,
            vertical_visibility=False,
            raw=clean_token,
        )
    return None


def parse_clouds(report: str) -> list[CloudGroup]:
    """Parse cloud layers, vertical visibility and NSC/NCD groups."""
    clouds: list[CloudGroup] = []
    for token in current_report_tokens(report):
        clean_token = token.rstrip("=")
        cloud = _parse_cloud_group(clean_token)
        if cloud is not None:
            clouds.append(cloud)
    return clouds


def parse_rvr(report: str) -> list[RvrGroup]:
    """Parse RVR groups from the current observation part of a report.

    The returned records preserve runway identity, bounds, units and trend.
    The metre-suffixed form used by ANWS (for example ``R24/800M``) is
    accepted alongside standard ICAO forms.
    """
    groups: list[RvrGroup] = []
    for token in current_report_tokens(report):
        clean_token = token.rstrip("=")
        unknown_match = _UNKNOWN_RVR_RE.fullmatch(clean_token)
        if unknown_match is not None:
            groups.append(
                RvrGroup(
                    runway=unknown_match.group("runway"),
                    lower=None,
                    upper=None,
                    lower_qualifier=None,
                    upper_qualifier=None,
                    unit="M",
                    trend=unknown_match.group("trend"),
                    raw=clean_token,
                )
            )
            continue

        match = _RVR_RE.fullmatch(clean_token)
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
                raw=clean_token,
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
    return [
        value
        for group in parse_rvr(report)
        if (value := group.lower_metres) is not None
    ]
