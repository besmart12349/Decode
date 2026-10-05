"""Deterministic METAR/SPECI decoder used to generate and validate Decode training records.

Output follows the 12-field Decode format. Conventions (match existing dataset):
- Airport = identifier exactly as supplied (no invented airport names).
- Date = day of month only (never an invented calendar date).
- Station Type = "Not provided." (AO1/AO2 are explained in Remarks).
"""
import re

FIELDS = ["Airport", "Date", "Time", "Wind", "Visibility", "Weather", "Clouds",
          "Temperature", "Dew Point", "Altimeter", "Remarks", "Station Type"]
NP = "Not provided."

INTENSITY = {"-": "light", "+": "heavy", "VC": "in the vicinity: "}
DESCR = {"MI": "shallow", "PR": "partial", "BC": "patches of", "DR": "low drifting",
         "BL": "blowing", "SH": "showers of", "TS": "thunderstorm", "FZ": "freezing"}
PHEN = {"DZ": "drizzle", "RA": "rain", "SN": "snow", "SG": "snow grains", "IC": "ice crystals",
        "PL": "ice pellets", "GR": "hail", "GS": "small hail/snow pellets", "UP": "unknown precipitation",
        "BR": "mist", "FG": "fog", "FU": "smoke", "VA": "volcanic ash", "DU": "widespread dust",
        "SA": "sand", "HZ": "haze", "PY": "spray", "PO": "dust/sand whirls", "SQ": "squalls",
        "FC": "funnel cloud/tornado/waterspout", "SS": "sandstorm", "DS": "duststorm"}
COVER = {"SKC": "sky clear", "CLR": "clear below 12,000 ft (automated)", "FEW": "few", "SCT": "scattered",
         "BKN": "broken", "OVC": "overcast"}

WX_RE = re.compile(r"^(VC|[-+])?(MI|PR|BC|DR|BL|SH|TS|FZ)?((?:DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS)+)$")
WX_DESC_ONLY = re.compile(r"^(VC)?(TS|SH|FZ|BL|DR)$")
SKY_RE = re.compile(r"^(FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?$")
VIS_RE = re.compile(r"^(M?\d+/\d+|\d+)SM$|^P6SM$")


def _num(n):
    return f"{int(n):,}"


def decode_weather(tok):
    if tok in ("TS", "VCTS"):
        return "thunderstorm" if tok == "TS" else "thunderstorm in the vicinity"
    m = WX_RE.match(tok)
    if not m:
        return None
    inten, desc, phen = m.groups()
    parts = [PHEN[phen[i:i + 2]] for i in range(0, len(phen), 2)]
    text = " and ".join(parts)
    if desc == "TS":
        text = "thunderstorm with " + text
    elif desc:
        text = f"{DESCR[desc]} {text}"
    if inten == "-":
        text = "light " + text
    elif inten == "+":
        text = "heavy " + text
    elif inten == "VC":
        text += " in the vicinity"
    return text


def decode_wind(tok):
    m = re.match(r"^(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT$", tok)
    if not m:
        return None
    d, s, g = m.groups()
    if d == "000" and int(s) == 0:
        return "calm"
    if d == "VRB":
        out = f"variable direction at {int(s)} kt"
    else:
        out = f"from {d}° at {int(s)} kt"
    if g:
        out += f", gusting to {int(g)} kt"
    return out


def decode_temp(tok):
    m = re.match(r"^(M?\d{2})/(M?\d{2})?$", tok)
    if not m:
        return None
    f = lambda s: None if s is None else (-int(s[1:]) if s.startswith("M") else int(s))
    return f(m.group(1)), f(m.group(2))


def decode_remarks(tokens):
    out = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "AO1":
            out.append("AO1 = automated station without precipitation discriminator")
        elif t == "AO2":
            out.append("AO2 = automated station with precipitation discriminator")
        elif re.match(r"^SLP\d{3}$", t):
            v = int(t[3:]) / 10
            v += 1000 if v < 50 else 900
            out.append(f"{t} = sea-level pressure {v:.1f} hPa")
        elif re.match(r"^T[01]\d{3}[01]\d{3}$", t):
            a = int(t[2:5]) / 10 * (-1 if t[1] == "1" else 1)
            b = int(t[6:9]) / 10 * (-1 if t[5] == "1" else 1)
            out.append(f"{t} = temperature {a:.1f}°C, dew point {b:.1f}°C")
        elif t == "PK" and i + 3 < len(tokens) and tokens[i + 1] == "WND":
            m = re.match(r"^(\d{3})(\d{2,3})/(\d{2})(\d{2})$", tokens[i + 2])
            if m:
                out.append(f"PK WND {tokens[i+2]} = peak wind from {m.group(1)}° at {int(m.group(2))} kt "
                           f"at {m.group(3)}{m.group(4)} UTC")
                i += 2
        elif t == "$":
            out.append("$ = maintenance check indicator (station may need maintenance)")
        else:
            out.append(f"{t} = not decoded (unrecognized remark)")
        i += 1
    return out


def decode_metar(text):
    """Return dict of the 12 fields, or None if the text is not a plain METAR/SPECI."""
    toks = text.replace("=", "").split()
    if not toks:
        return None
    rtype = "METAR"
    if toks[0] in ("METAR", "SPECI"):
        rtype = toks.pop(0)
    if len(toks) < 3 or not re.match(r"^[A-Z]{4}$", toks[0]) or not re.match(r"^\d{6}Z$", toks[1]):
        return None
    f = {k: NP for k in FIELDS}
    station, ts = toks[0], toks[1]
    f["Airport"] = station
    f["Date"] = f"{int(ts[:2])}{'th' if 10 <= int(ts[:2]) % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get(int(ts[:2]) % 10,'th')}"
    f["Time"] = f"{ts[2:4]}{ts[4:6]} UTC"
    rest = toks[2:]
    rmk = []
    if "RMK" in rest:
        k = rest.index("RMK")
        rmk, rest = rest[k + 1:], rest[:k]
    wx, clouds, notes, rvr = [], [], [], []
    vis = None
    for t in rest:
        if t in ("AUTO", "COR"):
            notes.append("AUTO = fully automated report" if t == "AUTO" else "COR = corrected report")
        elif decode_wind(t) and f["Wind"] == NP:
            f["Wind"] = decode_wind(t)
        elif re.match(r"^\d{3}V\d{3}$", t):
            f["Wind"] += f"; direction varying between {t[:3]}° and {t[4:]}°" if f["Wind"] != NP else NP
        elif VIS_RE.match(t) and vis is None:
            v = t[:-2]
            if t == "P6SM":
                vis = "greater than 6 statute miles"
            elif v.startswith("M"):
                vis = f"less than {v[1:]} statute mile"
            else:
                vis = f"{v} statute mile" + ("" if v == "1" or "/" in v else "s")
        elif re.match(r"^\d$", t):  # first part of "1 1/2SM"
            vis = t
        elif vis is not None and re.match(r"^\d/\dSM$", t) and re.match(r"^\d$", vis):
            vis = f"{vis} {t[:-2]} statute miles"
        elif re.match(r"^R\d{2}[LCR]?/", t):
            m = re.match(r"^R(\d{2}[LCR]?)/([MP]?)(\d{4})(?:V([MP]?)(\d{4}))?FT$", t)
            if m:
                pre = {"M": "less than ", "P": "greater than ", "": ""}
                s = f"RVR runway {m.group(1)}: {pre[m.group(2)]}{_num(m.group(3))} ft"
                if m.group(5):
                    s = f"RVR runway {m.group(1)}: variable {_num(m.group(3))} to {_num(m.group(5))} ft"
                rvr.append(s)
            else:
                return None
        elif t == "NSW":
            wx.append("no significant weather")
        elif WX_RE.match(t) or t in ("TS", "VCTS"):
            wx.append(decode_weather(t))
        elif t in ("SKC", "CLR"):
            clouds.append(COVER[t])
        elif SKY_RE.match(t):
            c, h, ty = SKY_RE.match(t).groups()
            s = f"{COVER[c]} at {_num(int(h) * 100)} ft AGL"
            if ty:
                s = s.replace(COVER[c], f"{COVER[c]} {'cumulonimbus' if ty == 'CB' else 'towering cumulus'}", 1)
            clouds.append(s)
        elif re.match(r"^VV\d{3}$", t):
            clouds.append(f"vertical visibility {_num(int(t[2:]) * 100)} ft AGL (sky obscured)")
        elif decode_temp(t):
            tt, dd = decode_temp(t)
            f["Temperature"] = f"{tt}°C"
            f["Dew Point"] = NP if dd is None else f"{dd}°C"
        elif re.match(r"^A\d{4}$", t):
            f["Altimeter"] = f"{t[1:3]}.{t[3:]} inHg"
        else:
            return None  # unknown token: do not guess
    if vis is not None:
        if re.match(r"^\d$", vis):
            vis = f"{vis} statute miles" if vis != "1" else "1 statute mile"
        f["Visibility"] = vis
    if rvr:
        f["Visibility"] = (f["Visibility"] + "; " if f["Visibility"] != NP else "") + "; ".join(rvr)
    if wx:
        f["Weather"] = "; ".join(wx)
    if clouds:
        f["Clouds"] = "; ".join(clouds)
    r = [rtype] + notes
    if rmk:
        r += decode_remarks(rmk)
    f["Remarks"] = "; ".join(r)
    f["Station Type"] = NP
    return f


def fmt(f):
    return "\n".join(f"{k}: {f[k]}" for k in FIELDS)


if __name__ == "__main__":
    import sys
    print(fmt(decode_metar(" ".join(sys.argv[1:]))))
