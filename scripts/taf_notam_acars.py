"""Deterministic TAF / NOTAM / ACARS decoders + generators for Decode training data.

Conventions (consistent across the dataset):
- TAF: Date/Time = issuance timestamp. Wind/Visibility/Weather/Clouds = the BASE (initial) forecast group.
  Temperature/Dew Point/Altimeter = Not provided. (TX/TN go to Remarks). Validity + every change group go to Remarks.
- NOTAM: Date/Time = Not provided. unless an issue time is supplied. Item/status/effective period go to Remarks.
- ACARS: envelope text is preserved in Remarks without assigning unsupported meanings; embedded weather fills fields.
- Station Type is always Not provided. unless the input explicitly states it.
"""
import re, random
from metar_decoder import (decode_wind, decode_weather, decode_metar, WX_RE, SKY_RE, COVER, FIELDS, NP, fmt, _num)


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def hhmm(h, m="00"):
    return f"{int(h):02d}{int(m):02d}"


# ---------------------------------------------------------------- shared conditions
def parse_conditions(tokens):
    """Parse wind/vis/weather/sky tokens. Returns dict or None on any unknown token."""
    c = {"wind": None, "vis": None, "wx": [], "sky": []}
    pend = None
    for t in tokens:
        w = decode_wind(t)
        if w and c["wind"] is None:
            c["wind"] = w
        elif t == "P6SM":
            c["vis"] = "greater than 6 statute miles"
        elif re.match(r"^M?\d+/\d+SM$", t) or re.match(r"^\d+SM$", t):
            v = t[:-2]
            if pend:
                c["vis"] = f"{pend} {v} statute miles"; pend = None
            elif v.startswith("M"):
                c["vis"] = f"less than {v[1:]} statute mile"
            else:
                c["vis"] = f"{v} statute mile" + ("" if v == "1" or "/" in v else "s")
        elif re.match(r"^\d$", t):
            pend = t
        elif t == "NSW":
            c["wx"].append("no significant weather")
        elif WX_RE.match(t) or t in ("TS", "VCTS", "VCSH"):
            c["wx"].append(decode_weather(t))
        elif t in ("SKC",):
            c["sky"].append("sky clear")
        elif SKY_RE.match(t):
            cv, h, ty = SKY_RE.match(t).groups()
            s = f"{COVER[cv]}{' cumulonimbus' if ty == 'CB' else ' towering cumulus' if ty else ''} at {_num(int(h) * 100)} ft AGL"
            c["sky"].append(s)
        elif re.match(r"^VV\d{3}$", t):
            c["sky"].append(f"vertical visibility {_num(int(t[2:]) * 100)} ft AGL (sky obscured)")
        else:
            return None
    if pend:
        return None
    return c


def cond_text(c):
    parts = []
    if c["wind"]:
        parts.append("wind " + c["wind"])
    if c["vis"]:
        parts.append("visibility " + c["vis"])
    parts += c["wx"]
    parts += c["sky"]
    return "; ".join(parts) if parts else "no conditions stated"


# ---------------------------------------------------------------- TAF
def _dt(d, h):
    return f"{ordinal(d)} {int(h):02d}00 UTC" if int(h) != 24 else f"{ordinal(d)} 2400 UTC (end of day)"


def decode_taf(text):
    toks = text.replace("=", "").split()
    if toks and toks[0] == "TAF":
        toks.pop(0)
    amd = None
    if toks and toks[0] in ("AMD", "COR"):
        amd = toks.pop(0)
    if len(toks) < 4 or not re.match(r"^[A-Z]{4}$", toks[0]) or not re.match(r"^\d{6}Z$", toks[1]) or not re.match(r"^\d{4}/\d{4}$", toks[2]):
        return None
    st, issue, valid = toks[0], toks[1], toks[2]
    body = toks[3:]
    # split into groups
    groups, cur, hdr = [], None, "BASE"
    extras = []
    i = 0
    while i < len(body):
        t = body[i]
        if re.match(r"^FM\d{6}$", t) or t in ("TEMPO", "BECMG") or re.match(r"^PROB(30|40)$", t):
            if t.startswith("PROB") and i + 1 < len(body) and body[i + 1] == "TEMPO":
                hdr = t + " TEMPO"; i += 1
            else:
                hdr = t
            period = None
            if not t.startswith("FM"):
                if i + 1 < len(body) and re.match(r"^\d{4}/\d{4}$", body[i + 1]):
                    period = body[i + 1]; i += 1
                else:
                    return None
            cur = {"hdr": hdr, "period": period, "tok": []}
            groups.append(cur)
        elif re.match(r"^T[XN]M?\d{2}/\d{4}Z$", t):
            extras.append(t)
        else:
            if cur is None:
                cur = {"hdr": "BASE", "period": None, "tok": []}
                groups.append(cur)
            cur["tok"].append(t)
        i += 1
    if not groups or groups[0]["hdr"] != "BASE":
        return None
    parsed = []
    for g in groups:
        c = parse_conditions(g["tok"])
        if c is None:
            return None
        parsed.append(c)
    f = {k: NP for k in FIELDS}
    f["Airport"] = st
    f["Date"] = ordinal(issue[:2])
    f["Time"] = f"{issue[2:4]}{issue[4:6]} UTC"
    b = parsed[0]
    f["Wind"] = b["wind"] or NP
    f["Visibility"] = b["vis"] or NP
    f["Weather"] = "; ".join(b["wx"]) or NP
    f["Clouds"] = "; ".join(b["sky"]) or NP
    vd1, vh1, vd2, vh2 = valid[:2], valid[2:4], valid[5:7], valid[7:9]
    s = [f"TAF{' ' + amd if amd else ''} forecast (not an observation)."]
    s.append(f"Issued {ordinal(issue[:2])} at {issue[2:4]}{issue[4:6]} UTC.")
    s.append(f"Valid from {_dt(vd1, vh1)} to {_dt(vd2, vh2)}.")
    s.append(f"Base forecast: {cond_text(b)}.")
    names = {"BECMG": "Becoming", "TEMPO": "Temporarily", "PROB30": "30% probability", "PROB40": "40% probability",
             "PROB30 TEMPO": "30% probability of temporary", "PROB40 TEMPO": "40% probability of temporary"}
    for g, c in zip(groups[1:], parsed[1:]):
        if g["hdr"].startswith("FM"):
            d, h, m = g["hdr"][2:4], g["hdr"][4:6], g["hdr"][6:8]
            s.append(f"From {ordinal(d)} {h}{m} UTC: {cond_text(c)}.")
        else:
            p = g["period"]
            s.append(f"{names[g['hdr']]} between {_dt(p[:2], p[2:4])} and {_dt(p[5:7], p[7:9])}: {cond_text(c)}.")
    for x in extras:
        m = re.match(r"^T([XN])(M?)(\d{2})/(\d{2})(\d{2})Z$", x)
        kind = "maximum" if m.group(1) == "X" else "minimum"
        s.append(f"Forecast {kind} temperature {'-' if m.group(2) else ''}{int(m.group(3))}°C at {ordinal(m.group(4))} {m.group(5)}00 UTC.")
    f["Remarks"] = " ".join(s)
    return f


def gen_taf(stations, rng):
    st = rng.choice(stations)
    day = rng.randint(1, 25)
    ih = rng.choice([0, 5, 6, 11, 12, 17, 18, 23])
    im = rng.choice([0, 30, 40, 51])
    vstart = (ih + 1) if im >= 30 or ih in (5, 11, 17, 23) else ih
    vday, vh = day, vstart % 24
    if vstart >= 24:
        vday += 1
    span = rng.choice([24, 24, 30])
    # absolute hours
    a0 = vday * 24 + vh
    a1 = a0 + span

    def dh(a):
        d, h = divmod(a, 24)
        if h == 0 and a == a1:
            return f"{d-1:02d}24"
        return f"{d:02d}{h:02d}"
    toks = ["TAF"] if rng.random() < .85 else ["TAF", "AMD"]
    toks += [st, f"{day:02d}{ih:02d}{im:02d}Z", f"{dh(a0)}/{dh(a1)}"]

    def cond(base=False):
        t = []
        if rng.random() < .1:
            t.append("00000KT")
        else:
            d, s = rng.randrange(10, 361, 10), rng.randint(3, 25)
            w = f"{d % 360 or 360:03d}{s:02d}" + (f"G{s + rng.randint(6, 15):02d}" if rng.random() < .3 else "")
            t.append(w + "KT")
        low = rng.random() < .35
        t.append(rng.choice(["1SM", "2SM", "3SM", "1/2SM", "5SM"] if low else ["P6SM", "P6SM", "6SM"]))
        if low or rng.random() < .3:
            t.append(rng.choice(["-RA", "RA", "-SN", "SN", "BR", "FG", "TSRA", "-SHRA", "VCSH", "VCTS", "-DZ", "FZFG"]))
        if rng.random() < .85:
            n = rng.choice([1, 2, 2])
            base_h = rng.randint(3, 30) if not low else rng.randint(2, 12)
            order = ["FEW", "SCT", "BKN", "OVC"]
            ci = rng.randint(0, 2)
            for i in range(n):
                cb = "CB" if any("TS" in x for x in t) and i == 0 else ""
                t.append(f"{order[min(3, ci + i)]}{base_h + i * rng.randint(5, 15):03d}{cb}")
        else:
            t.append("SKC")
        return t
    toks += cond(True)
    ng = rng.choice([0, 1, 2, 2, 3])
    cuts = sorted(rng.sample(range(a0 + 3, a1 - 2), ng)) if ng else []
    for k in range(ng):
        kind = rng.choice(["FM", "FM", "TEMPO", "BECMG", "PROB30", "PROB40"])
        t0 = cuts[k]
        if kind == "FM":
            d, h = divmod(t0, 24)
            toks.append(f"FM{d:02d}{h:02d}{rng.choice([0, 0, 30]):02d}")
        else:
            t1 = min(a1, t0 + rng.randint(2, 5))
            pre = {"TEMPO": ["TEMPO"], "BECMG": ["BECMG"], "PROB30": ["PROB30"], "PROB40": ["PROB40", "TEMPO"] if rng.random() < .5 else ["PROB40"]}[kind]
            toks += pre + [f"{dh(t0)}/{dh(t1)}"]
        toks += cond()
    if rng.random() < .2:
        d1, h1 = divmod(a0 + rng.randint(4, 14), 24)
        toks.append(f"TX{rng.randint(5, 35):02d}/{d1:02d}{h1:02d}Z")
    return " ".join(toks)


# ---------------------------------------------------------------- NOTAM (short form)
ITEMS = [
    (r"^RWY (\d{2}[LCR]?(?:/\d{2}[LCR]?)?)$", lambda m: f"Runway {m.group(1)}"),
    (r"^TWY ([A-Z]{1,2}\d?)$", lambda m: f"Taxiway {m.group(1)}"),
    (r"^APRON$", lambda m: "Apron"),
    (r"^AD$", lambda m: "Aerodrome"),
    (r"^ILS RWY (\d{2}[LCR]?)$", lambda m: f"ILS for runway {m.group(1)}"),
    (r"^(VOR|DME|NDB|TACAN) ([A-Z]{3})$", lambda m: f"{m.group(1)} {m.group(2)}"),
    (r"^RWY (\d{2}[LCR]?) (?:LGT|LIGHTS?)$", lambda m: f"Runway {m.group(1)} lighting"),
    (r"^OBST (TOWER|CRANE) (\d{2,4})FT AGL$", lambda m: f"Obstacle ({m.group(1).lower()}) {_num(m.group(2))} ft AGL"),
]
STATUS = {"CLSD": "closed", "U/S": "unserviceable", "NOT AVBL": "not available", "INOP": "inoperative",
          "WIP": "work in progress", "CLSD WIP": "closed, work in progress", "LGTD": "lighted"}


def _period(p):
    m = re.match(r"^(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})(?: (EST))?$", p)
    if m:
        a = f"from the {ordinal(m.group(1))} at {m.group(2)}{m.group(3)}Z to the {ordinal(m.group(4))} at {m.group(5)}{m.group(6)}Z"
        return a + (" (end time estimated)" if m.group(7) else "")
    m = re.match(r"^(\d{4})-(\d{4}) DLY$", p)
    if m:
        return f"daily from {m.group(1)}Z to {m.group(2)}Z"
    m = re.match(r"^(\d{2})(\d{4})-(\d{4})$", p)  # DDHHMM-HHMM
    if m:
        return f"on the {ordinal(m.group(1))} from {m.group(2)}Z to {m.group(3)}Z"
    if p == "UFN":
        return "until further notice"
    if p == "PERM":
        return "permanent"
    return None


def decode_notam(text):
    t = text.strip()
    apt = None
    m = re.match(r"^([A-Z]{4}) (.*)$", t)
    if m and not re.match(r"^(RWY|TWY|APRON|OBST|ILS|VOR|DME|NDB)$", m.group(1)):
        apt, t = m.group(1), m.group(2)
    per = None
    for pat in (r" (\d{6}-\d{6}(?: EST)?)$", r" (\d{4}-\d{4} DLY)$", r" (\d{6}-\d{4})$", r" (UFN)$", r" (PERM)$"):
        mm = re.search(pat, t)
        if mm:
            per = _period(mm.group(1)); t = t[:mm.start()]; break
    stat = None
    for s in sorted(STATUS, key=len, reverse=True):
        if t.endswith(" " + s):
            stat = STATUS[s]; t = t[:-len(s) - 1]; break
    if stat is None:
        return None
    item = None
    for pat, fn in ITEMS:
        mm = re.match(pat, t)
        if mm:
            item = fn(mm); break
    if item is None:
        return None
    f = {k: NP for k in FIELDS}
    if apt:
        f["Airport"] = apt
    r = [f"NOTAM-style notice. Item: {item}. Status: {stat}."]
    r.append(f"Effective: {per}." if per else "Effective period: not provided.")
    if per and ("the " in per):
        r.append("Month and year are not supplied.")
    if not apt:
        r.append("Airport is not supplied.")
    f["Remarks"] = " ".join(r)
    return f


def gen_notam(stations, rng):
    item = rng.choice([
        f"RWY {rng.choice(['04', '09/27', '18/36', '10L/28R', '22', '13R/31L'])}",
        f"TWY {rng.choice(['A', 'B', 'C3', 'D', 'K'])}", "APRON", "AD",
        f"ILS RWY {rng.choice(['27', '09L', '18', '31R'])}",
        f"{rng.choice(['VOR', 'DME', 'NDB', 'TACAN'])} {rng.choice(['ABC', 'DAY', 'CVG', 'HVQ', 'LUK'])}",
        f"RWY {rng.choice(['09L', '27R', '18'])} LGT",
        f"OBST {rng.choice(['TOWER', 'CRANE'])} {rng.choice([150, 249, 385, 512])}FT AGL"])
    if item.startswith("OBST"):
        status = rng.choice(["LGTD", "U/S", "NOT AVBL"]) if False else "U/S"
    elif item.startswith(("VOR", "DME", "NDB", "TACAN", "ILS")):
        status = rng.choice(["U/S", "NOT AVBL", "INOP"])
    elif item.endswith("LGT"):
        status = rng.choice(["U/S", "INOP", "NOT AVBL"])
    else:
        status = rng.choice(["CLSD", "CLSD", "CLSD WIP", "WIP", "NOT AVBL"])
    d = rng.randint(1, 28)
    h1 = rng.randint(0, 20)
    per = rng.choice([f"{d:02d}{h1:02d}00-{d:02d}{h1 + rng.randint(1, 3):02d}00", f"{d:02d}{h1:02d}00-{(d % 28) + 1:02d}{rng.randint(0, 20):02d}00 EST",
                      f"{h1:02d}00-{h1 + rng.randint(1, 3):02d}00 DLY", "UFN", "PERM"])
    pre = rng.choice([f"{rng.choice(stations)} ", "", ""])
    return f"{pre}{item} {status} {per}"


# ---------------------------------------------------------------- ACARS
def decode_acars_pos(text):
    m = re.match(r"^ACARS (\d{6})Z ([A-Z0-9]{3,7}) ([A-Z]{4})-([A-Z]{4}) POS (\d{2}\.\d{2}[NS])/(\d{2,3}\.\d{2}[EW]) ALT (\d{4,5}) TAS (\d{3})KT GS (\d{3})KT OAT (M?\d{2})C WIND (\d{3})/(\d{2,3})$", text.strip())
    if not m:
        return None
    ts, flt, o, d, lat, lon, alt, tas, gs, oat, wd, ws = m.groups()
    f = {k: NP for k in FIELDS}
    f["Airport"] = f"{o}-{d}, flight {flt}"
    f["Date"] = ordinal(ts[:2]); f["Time"] = f"{ts[2:4]}{ts[4:6]} UTC"
    f["Wind"] = f"from {wd}° at {int(ws)} kt (at aircraft position/altitude)"
    f["Temperature"] = f"{'-' if oat.startswith('M') else ''}{int(oat.lstrip('M'))}°C (outside air temperature)"
    f["Remarks"] = (f"ACARS position report. Route {o} to {d}. Position {lat}/{lon}. Altitude {_num(alt)} ft. "
                    f"True airspeed {int(tas)} kt. Groundspeed {int(gs)} kt.")
    return f


def decode_acars_weather(text):
    """'ACARS payload' wrapping METAR/SPECI, optionally with envelope text before the product."""
    m = re.match(r"^(?:(.*?) )?((?:METAR|SPECI) [A-Z]{4} \d{6}Z .*)$", text.strip())
    if not m:
        return None
    env, pay = m.group(1), m.group(2)
    d = decode_metar(pay)
    if not d:
        return None
    rtype = pay.split()[0]
    note = f"ACARS message with an embedded {rtype}."
    if env:
        note += f" Envelope text as supplied: {env}. Aircraft and flight identifiers are shown as written; label meanings are not assumed."
    extra = d["Remarks"].replace(rtype, "", 1).lstrip("; ").strip()
    if extra:
        note += " Report remarks: " + extra + "."
    d["Remarks"] = note.strip()
    return d


def gen_acars(stations, rng, metar_gen, pool=None):
    if rng.random() < .4:
        st = rng.sample(pool or ["KORD", "KDEN", "KATL", "KDFW", "KLAX", "KJFK", "KSEA", "KMSP", "KDTW", "KIAH"], 2)
        flt = rng.choice(["UA", "DL", "AA", "WN", "AS"]) + str(rng.randint(100, 2999))
        lat = f"{rng.randint(28, 48)}.{rng.randint(0, 99):02d}N"; lon = f"{rng.randint(75, 122)}.{rng.randint(0, 99):02d}W"
        oat = rng.randint(40, 65)
        return (f"ACARS {rng.randint(1, 28):02d}{rng.randint(0, 23):02d}{rng.randint(0, 59):02d}Z {flt} {st[0]}-{st[1]} POS {lat}/{lon} "
                f"ALT {rng.choice(range(29000, 42000, 1000))} TAS {rng.randint(400, 490)}KT GS {rng.randint(380, 520)}KT OAT M{oat}C "
                f"WIND {rng.randrange(10, 361, 10) % 360 or 360:03d}/{rng.randint(5, 110):02d}")
    rep = metar_gen(stations)
    if rng.random() < .5:
        reg = f"N{rng.randint(100, 999)}{rng.choice(['UA', 'DL', 'AA', 'WN'])}"
        env = f"{reg} H1 {rng.randint(1, 9)} M0{rng.randint(1, 9)}A {rng.choice(['UA', 'DL', 'AA'])}{rng.randint(100, 2999)} #DFB"
        return f"{env} {rep}"
    return rep


if __name__ == "__main__":
    import sys
    rng = random.Random(1)
    print(fmt(decode_taf(" ".join(sys.argv[1:]) or gen_taf(["KDAY"], rng))))


def decode_acars_header(text):
    m = re.match(r"^\.\.?(N\d{1,3}[A-Z0-9]{1,2}) (H1|Q0|[A-Z0-9]{2}) (\d) (M\d{2}[A-Z]) ([A-Z0-9]{3,7})$", text.strip())
    if not m:
        return None
    reg, lab, blk, seq, flt = m.groups()
    f = {k: NP for k in FIELDS}
    r = (f"ACARS envelope/header only; no application payload is supplied. Aircraft: {reg}. Label: {lab}. Block ID: {blk}. "
         f"Message sequence: {seq}. Flight: {flt}.")
    r += " Q0 is the ACARS link-test label." if lab == "Q0" else f" The label {lab} alone does not establish a specific airline application."
    f["Remarks"] = r + " No weather or other payload content was decoded."
    return f


def gen_acars_header(rng):
    reg = f"N{rng.randint(100, 999)}{rng.choice(['UA', 'DL', 'AA', 'WN', 'AS'])}"
    return f"..{reg} {rng.choice(['H1', 'H1', 'Q0'])} {rng.randint(1, 9)} M{rng.randint(1, 20):02d}{rng.choice('ABC')} {rng.choice(['UA', 'DL', 'AA', 'WN', 'AS'])}{rng.randint(100, 2999)}"
