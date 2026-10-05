# AeroDecode Aviation Code Reference

This reference is the vocabulary baseline for future AeroDecode dataset expansion. It is intentionally organized by report section rather than as one undifferentiated abbreviation list.

> **Source policy:** Prefer current FAA/AIM, FAA Aviation Weather Handbook, FAA Surface Weather Observing guidance, and current FAA contractions for validation. Aviation codes can be context-dependent, and NOTAM formatting is evolving toward ICAO compliance. Do not treat this list as permission to guess an unfamiliar code.

## METAR/SPECI report structure

1. Report type: `METAR`, `SPECI`
2. Station identifier: four-letter ICAO identifier
3. Date/time: `YYGGggZ`
4. Report modifier: `AUTO`, `COR`
5. Wind
6. Visibility
7. Runway Visual Range (RVR)
8. Weather / obscurations
9. Sky condition
10. Temperature/dew point
11. Altimeter
12. Remarks: `RMK`

## METAR/SPECI modifiers and wind

- `AUTO` = fully automated report
- `COR` = corrected report
- `VRB` = variable wind direction
- `00000KT` = calm
- `G` = gust
- `KT` = knots
- `V` between directions = wind direction variable between two directions

Example: `32012G22KT 280V350` = wind 320° at 12 kt gusting 22 kt, varying between 280° and 350°.

## Visibility

- `SM` = statute miles
- `P6SM` = greater than 6 statute miles
- Fractional visibility such as `1/2SM`
- `Rxx/xxxxFT` = runway visual range
- `Rxx/MxxxxFT` = RVR below the reported value
- `Rxx/PxxxxFT` = RVR above the reported value
- `Rxx/xxxxVxxxxFT` = variable RVR
- `RVRNO` = RVR system information unavailable/not reportable in the applicable context

## Weather group construction

METAR weather groups can combine:
**intensity/proximity + descriptor + precipitation + obscuration + other phenomenon**

### Intensity/proximity
- `-` = light
- no sign = moderate
- `+` = heavy
- `VC` = vicinity

### Descriptors
- `MI` = shallow
- `PR` = partial
- `BC` = patches
- `DR` = low drifting
- `BL` = blowing
- `SH` = showers
- `TS` = thunderstorm
- `FZ` = freezing

### Precipitation
- `DZ` = drizzle
- `RA` = rain
- `SN` = snow
- `SG` = snow grains
- `IC` = ice crystals
- `PL` = ice pellets
- `GR` = hail
- `GS` = small hail and/or snow pellets
- `UP` = unknown precipitation

### Obscuration / other
- `BR` = mist
- `FG` = fog
- `FU` = smoke
- `VA` = volcanic ash
- `DU` = widespread dust
- `SA` = sand
- `HZ` = haze
- `PY` = spray
- `PO` = dust/sand whirls
- `SQ` = squall
- `FC` = funnel cloud/tornado/waterspout
- `SS` = sandstorm
- `DS` = duststorm

Examples:
- `-RA` = light rain
- `+TSRA` = heavy thunderstorm with rain
- `FZDZ` = freezing drizzle
- `BLSN` = blowing snow
- `VCSH` = showers in the vicinity

## Sky condition

- `SKC` = sky clear
- `CLR` = clear below the applicable automated reporting threshold
- `FEW` = few
- `SCT` = scattered
- `BKN` = broken
- `OVC` = overcast
- `VV` = vertical visibility
- `CB` = cumulonimbus
- `TCU` = towering cumulus

Examples:
- `SCT025` = scattered at 2,500 ft AGL
- `BKN040CB` = broken cumulonimbus at 4,000 ft AGL
- `VV008` = vertical visibility 800 ft

## Temperature/dew point

- `18/16` = 18°C temperature, 16°C dew point
- `M05/02` = temperature -5°C, dew point 2°C
- `M05/M09` = temperature -5°C, dew point -9°C
- Missing values can be represented with a missing component, such as `M05/`

## Altimeter

- `A2992` = 29.92 inHg
- `A` identifies the U.S. inch-of-mercury altimeter format

## METAR remarks

`RMK` starts the remarks section. Important families include:

### Automated station
- `AO1` = automated station without a precipitation discriminator
- `AO2` = automated station with a precipitation discriminator

### Wind
- `PK WND dddff/tt` = peak wind
- `WSHFT tt` = wind shift began at the stated time
- `FROPA` = frontal passage associated with a wind shift

### Visibility
- `TWR VIS` = tower visibility
- `SFC VIS` = surface visibility
- `VIS xVx` = variable prevailing visibility
- `VIS [DIR] value` = sector visibility
- second-location visibility may be reported with a location identifier

### Lightning
Common frequency/location forms include:
- `LTG` = lightning
- `FRQ` = frequent
- `OCNL` = occasional
- `CONS` = continuous
- `DSNT` = distant
- `ALQDS` = all quadrants

### Precipitation beginning/ending
- `B` = began
- `E` = ended
- `RAB` = rain began
- `RAE` = rain ended
- `SNB` = snow began
- `SNE` = snow ended
- `TSB` = thunderstorm began
- `TSE` = thunderstorm ended

### Thunderstorm
- `TS` = thunderstorm
- `TS MOV` / directional forms = thunderstorm movement

### Hail / virga
- `GR` = hail
- `VIRGA` = precipitation evaporating before reaching the ground

### Ceiling / sky
- `CIG` = ceiling
- `CIG hhh` = ceiling height
- `CIG hhh LOC` = ceiling at a second location
- `CLR`, `SKC`, `FEW`, `SCT`, `BKN`, `OVC`, `VV` retain their standard meanings in applicable contexts

### Pressure
- `PRESRR` = pressure rising rapidly
- `PRESFR` = pressure falling rapidly
- `SLPppp` = sea-level pressure encoded in tenths of hPa
- `SLPNO` = sea-level pressure unavailable/not reportable

### Precipitation amounts
- `Pxxxx` = hourly precipitation amount in the applicable encoded format
- `6RRRR` = 3- or 6-hour precipitation amount family
- `7RRRR` = 24-hour precipitation amount family

### Snow
- `SNINCR` / `SNOINCR` = snow depth increase
- `4/xxx` = snow depth on ground family
- `933` / related groups = snow/water-equivalent families depending on exact report format

### Temperature
- `T` group = temperature/dew point in tenths of a degree Celsius
- `1` group = 6-hour maximum temperature family
- `2` group = 6-hour minimum temperature family
- `4` group = 24-hour maximum/minimum temperature family

### Sensor / maintenance status
Known status families include:
- `PWINO` = precipitation identifier information unavailable
- `FZRANO` = freezing rain sensor information unavailable
- `TSNO` = thunderstorm information unavailable
- `RVRNO` = RVR information unavailable
- `PNO` = precipitation information unavailable
- `VISNO` = visibility information unavailable
- `WINO` / `VRNO` / `SNO` appear in FAA maintenance/status contexts

### Other
- `NOSPECI` = no SPECI reports taken
- `ACFT MSHP` = aircraft mishap, not transmitted
- `LAST` and other station-specific remarks require context and must not be generalized

## TAF structure and change groups

- `TAF` = routine terminal aerodrome forecast
- `TAF AMD` = amended TAF
- `COR` = corrected communication/header designation where applicable
- `RTD` = delayed communication/header designation where applicable
- Issue time: `YYGGggZ`
- Valid period: `YYGG/YYGG`
- `FMYYGGgg` = conditions beginning at the specified time
- `TEMPO YYGG/YYGG` = temporary fluctuations during the specified period
- `BECMG YYGG/YYGG` = gradual becoming/change period
- `PROB30` = 30 percent probability group in applicable TAF usage
- `PROB40` = 40 percent probability, used in military/international contexts and not routine NWS TAFs
- `NSW` = no significant weather
- `P6SM` = greater than 6 SM
- `WSxxx/dddffKT` = low-level wind shear group
- `TX` / `TN` = maximum/minimum temperature forecast groups in applicable joint-use/military TAF formats
- `QNH` = pressure setting in applicable military/international TAF formats
- `RMK` = remarks

## NOTAM vocabulary

NOTAMs may use domestic and ICAO-style formatting. Common terms include:
- `RWY` = runway
- `TWY` = taxiway
- `CLSD` = closed
- `OPEN` = open
- `U/S` = unserviceable/out of service
- `INOP` = inoperative
- `OUT OF SERVICE` = not operational
- `WIP` = work in progress
- `CONST` = construction
- `CRANE` = crane
- `OBST` = obstacle
- `NAV` = navigation facility/service
- `ILS` = instrument landing system
- `LOC` = localizer
- `VOR` = VHF omnidirectional range
- `DME` = distance measuring equipment
- `NAVAID` = navigation aid
- `GPS` / `GNSS` = satellite navigation systems
- `TFR` = temporary flight restriction
- `AIRSPACE` = airspace restriction/information
- `AP` / `AD` = airport/aerodrome in applicable formats
- `SFC` = surface
- `AGL` = above ground level
- `AMSL` = above mean sea level
- `EST` = estimated
- `UFN` = until further notice
- `DLY` = daily
- `PERM` = permanent
- `EXC` = except
- `BTN` = between
- `AND` = and
- `WI` = within
- `BFR` = before
- `AFTR` = after
- `NOTAMN` = new NOTAM in applicable ICAO-style format
- `NOTAMR` = replacement NOTAM in applicable ICAO-style format
- `NOTAMC` = cancellation NOTAM in applicable ICAO-style format

**NOTAM rule:** Never infer an airport, effective date, facility status, altitude, or operational restriction that is not supported by the supplied NOTAM and its date context.

## Global decoding rules

1. Identify the report type before decoding.
2. Identify the expected sections for that report type.
3. Map every raw group actually present to a section.
4. Break compound groups into components before interpreting them.
5. Keep raw code, literal meaning, and operational interpretation separate.
6. Recognize optional and absent groups.
7. Do not treat an absent code as proof that a condition is absent.
8. If a code is ambiguous, obsolete, malformed, context-dependent, or unfamiliar, say so.
9. Prefer authoritative current references over memory when validating unusual codes.
10. Markdown should be used to make the answer easy to scan: headings, numbered lists, bullets, inline code, and tables as appropriate.

## Maintenance policy

This file is a living vocabulary reference. Future dataset expansion should add newly encountered or newly validated codes here rather than creating isolated definitions inside individual examples. When a code's meaning depends on report type, generation system, location, or version of the standard, record that context explicitly.
