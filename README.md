<a href="https://www.buymeacoffee.com/tsunglung" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="30" width="120"></a>

Home Assistant support for [Taiwan ANWS](https://aoaws.anws.gov.tw/). [The readme in Traditional Chinese](https://github.com/bluefoxlee/TwANWS/blob/master/README_zh-tw.md).


This integration is based on MetOffice to develop.

This integration is forked from [tsunglung](https://github.com/tsunglung/TwANWS)'s excellent work.

As aviation weather integrations are relatively niche, I maintain this fork with a few minor modifications tailored to my personal use, with some assistance from AI.

## Install

You can install the component with a [HACS](https://hacs.xyz/) custom repository: HACS > Integrations > three-dot menu > Custom repositories > URL: `https://github.com/bluefoxlee/TwANWS` > Category: Integration.

Or manually copy `aoaws_anws` folder to `custom_components` folder in your config folder.

Then restart Home Assistant.

## Config

**Please use the config flow of Home Assistant**


1. With GUI. Configuration > Integration > Add Integration > Taiwan Navigation Weather Services (NWS)
   1. If the integration didn't show up in the list please REFRESH the page
   2. If the integration is still not in the list, you need to clear the browser cache.
2. Select Site Name.
3. Select the Language

## Reliability fixes in this fork

- Keeps wind values reported in knots as knots and handles calm wind.
- Prevents runway visual range groups from being mistaken for temperature/dew point groups.
- Parses common RVR forms and uses the lowest runway value when RVR is present.
- Preserves structured RVR, trend, wind, visibility, weather, cloud, and report-header data for later diagnostics.
- Handles METAR/SPECI `BECMG`, `TEMPO`, `NOSIG`, `AUTO`, `COR`, and `NIL` groups.
- Falls back to METAR temperature, wind, and visibility groups when ANWS JSON fields are missing or invalid.
- Derives cloud coverage and ceiling from METAR cloud groups when needed, including `CAVOK`, `NSC`, `NCD`, and combined precipitation phenomena.
- Localizes visibility labels and weather text according to the integration language while preserving standard Home Assistant condition values.
- Exposes separate integration update and station observation timestamps to distinguish a stale airport report from a failed HA update.
- Exposes JSON-safe report header, raw METAR, RVR, wind, visibility, cloud-layer, and trend attributes for future cards.
- Keeps the last valid observation during temporary API or overnight station outages and retries on the next five-minute poll.
- Uses Home Assistant's native weather and sensor value/unit interfaces.

## Versioning and maintenance

This repository is an independently maintained fork of the original TwANWS project. Version numbers and release tags in this fork are maintained independently from upstream, while the original project remains credited above. Release-specific changes are documented in [CHANGELOG.md](CHANGELOG.md).

Version 1.0.16 includes a Code Book audit covering ICAO/WMO Table 4678 present-weather combinations, wind limits, RVR formats, AUTO cloud groups, and Taiwan RMK pressure data.

See [CHANGELOG.md](CHANGELOG.md) for release details.

Buy Me A Coffee

|  LINE Pay | LINE Bank | JKao Pay |
| :------------: | :------------: | :------------: |
| <img src="https://github.com/tsunglung/TwANWS/blob/master/linepay.jpg" alt="Line Pay" height="200" width="200">  | <img src="https://github.com/tsunglung/TwANWS/blob/master/linebank.jpg" alt="Line Bank" height="200" width="200">  | <img src="https://github.com/tsunglung/TwANWS/blob/master/jkopay.jpg" alt="JKo Pay" height="200" width="200">  |
