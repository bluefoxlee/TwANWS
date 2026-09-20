"""Support for Taiwan ANWS service."""
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)

from . import device_info
from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    DOMAIN,
    ATTR_WEATHER_TEXT,
    ANWS_AOAWS_COORDINATOR,
    ANWS_AOAWS_DATA,
    ANWS_AOAWS_NAME,
)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigType, async_add_entities
) -> None:
    """Set up the Taiwan ANWS weather sensor platform."""
    hass_data = hass.data[DOMAIN][config_entry.entry_id]
    weather_coordinator = hass_data[ANWS_AOAWS_COORDINATOR]

    async_add_entities(
        [
            AnwsAoawsWeather(
                config_entry,
                hass_data,
                weather_coordinator
            )
        ],
        False,
    )


class AnwsAoawsWeather(SingleCoordinatorWeatherEntity):
    """Implementation of a Anws Aoaws weather condition."""
    _attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY

    def __init__(self, config_entry, hass_data, coordinator):
        """Initialise the platform with a data instance."""
        super().__init__(coordinator)
        self._data = hass_data[ANWS_AOAWS_DATA]
        self._coordinator = coordinator

        self._name = f"{DEFAULT_NAME} {hass_data[ANWS_AOAWS_NAME]}"
        self._unique_id = f"{self._data.site_name}"
        self._attr_device_info = device_info(config_entry)

        self.anws_aoaws_now = None
        self.anws_aoaws_forecast = None
        self.forecast_type = "hourly"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        return self._unique_id

    @property
    def condition(self):
        """Return the current condition."""
        if not self.anws_aoaws_now or not self.anws_aoaws_now.weather:
            return None
        return self._condition_for(self.anws_aoaws_now.weather.value)

    @staticmethod
    def _condition_for(value):
        """Map an ANWS weather description to a Home Assistant condition."""
        normalized = str(value).lower().strip()
        for condition, descriptions in CONDITION_CLASSES.items():
            if normalized in descriptions:
                return condition
        return None

    @property
    def cloud_coverage(self) -> float | None:
        """Return the Cloud coverage in %."""
        return (
            self.anws_aoaws_now.cloud_coverage.value
            if self.anws_aoaws_now and self.anws_aoaws_now.cloud_coverage
            else None
        )

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return (
            self.anws_aoaws_now.temperature.value
            if self.anws_aoaws_now and self.anws_aoaws_now.temperature
            else None
        )

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return (
            self.anws_aoaws_now.temperature.value
            if self.anws_aoaws_now and self.anws_aoaws_now.temperature
            else None
        )

    @property
    def native_temperature_unit(self) -> str:
        """Return the native temperature unit."""
        if self.anws_aoaws_now and self.anws_aoaws_now.temperature:
            return self.anws_aoaws_now.temperature.units
        return UnitOfTemperature.CELSIUS

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return (
            self.anws_aoaws_now.pressure.value
            if self.anws_aoaws_now and self.anws_aoaws_now.pressure
            else None
        )

    @property
    def native_pressure_unit(self) -> str:
        """Return the native pressure unit."""
        return UnitOfPressure.HPA

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return (
            self.anws_aoaws_now.humidity.value
            if self.anws_aoaws_now and self.anws_aoaws_now.humidity
            else None
        )

    @property
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return (
            self.anws_aoaws_now.dew_point.value
            if self.anws_aoaws_now and self.anws_aoaws_now.dew_point
            else None
        )

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        return (
            self.anws_aoaws_now.wind_gust.value
            if self.anws_aoaws_now and self.anws_aoaws_now.wind_gust
            else None
        )

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return (
            self.anws_aoaws_now.wind_speed.value
            if self.anws_aoaws_now and self.anws_aoaws_now.wind_speed
            else None
        )

    @property
    def native_wind_speed_unit(self) -> str:
        """Return the native wind speed unit."""
        if self.anws_aoaws_now and self.anws_aoaws_now.wind_speed:
            return self.anws_aoaws_now.wind_speed.units
        return UnitOfSpeed.KILOMETERS_PER_HOUR

    @property
    def native_visibility(self) -> float | None:
        """Return visibility in the native unit."""
        return (
            self.anws_aoaws_now.visibility.value
            if self.anws_aoaws_now and self.anws_aoaws_now.visibility
            else None
        )

    @property
    def native_visibility_unit(self) -> str:
        """Return the native visibility unit."""
        return UnitOfLength.KILOMETERS

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return (
            self.anws_aoaws_now.wind_direction.value
            if self.anws_aoaws_now and self.anws_aoaws_now.wind_direction
            else None
        )

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def extra_state_attributes(self):
        """Return localized weather text without changing the HA condition."""
        if self.anws_aoaws_now and self.anws_aoaws_now.weather:
            return {ATTR_WEATHER_TEXT: self.anws_aoaws_now.weather.text}
        return {}

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_callback)
        )
        self._update_callback()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self.anws_aoaws_now = self._data.now
        self.anws_aoaws_forecast = self._data.forecast
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False

    @property
    def available(self):
        """Return if state is available."""
        return self.anws_aoaws_now is not None

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""

        if self.anws_aoaws_forecast:
            forecast_data: list[Forecast] = []
            for item in self.anws_aoaws_forecast:
                forecast_data.append(
                    {
                        ATTR_FORECAST_TIME: item.date,
                        ATTR_FORECAST_NATIVE_TEMP: item.temperature.value,
                        ATTR_FORECAST_NATIVE_WIND_SPEED: item.wind_speed.value,
                        ATTR_FORECAST_CONDITION: self._condition_for(item.weather.value),
                        ATTR_FORECAST_WIND_BEARING: item.wind_direction.value
                    }
                )
            return forecast_data
        return None
