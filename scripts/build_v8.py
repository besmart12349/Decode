"""Build data/decode_102026_v8.jsonl from v7 and the multi-format held-out eval.

Repairs hand-written TAF/NOTAM/ACARS records with the verified decoders, fixes field misplacement,
rewrites glued Remarks, enforces Station Type, adds verified TAF/NOTAM/ACARS volume.
"""
import json, random, re, sys, pathlib, io, contextlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
with contextlib.redirect_stdout(io.StringIO()):
    import build_v7 as b7  # rebuilds v6/v7 deterministically
import build_v6 as b6
from metar_decoder import decode_metar, fmt, FIELDS, NP
from taf_notam_acars import *

ROOT = pathlib.Path(__file__).resolve().parent.parent
rng = random.Random(8)
SYS_S, SYS_L = b6.SYS_SHORT, b6.SYS_LONG
HELD = sorted(b6.HELDOUT)
rows = [json.loads(l) for l in open(ROOT / "data/decode_102026_v7.jsonl")]


def parse(a):
    return {l.split(": ", 1)[0]: (l.split(": ", 1)[1] if ": " in l else "") for l in a.split("\n")}


STRICT = {"Date": r"^\d+(st|nd|rd|th)$", "Time": r"^\d{4} UTC$", "Temperature": r"^-?\d+(\.\d)?°C( \([^)]*\))?$",
          "Dew Point": r"^-?\d+(\.\d)?°C( \([^)]*\))?$", "Altimeter": r"^\d\d\.\d\d inHg$"}

MANUAL = {  # prompt prefix -> (field overrides)
    "Parse this ACARS link-test message": {"Remarks": "ACARS envelope/header only. Aircraft: N123UA. Label: Q0. Block ID: 1. Remaining header text: 2032UA0045 (not interpreted). Q0 is the ACARS link-test label, used to check communication between the aircraft and ground system. No application payload is supplied."},
    "Parse this illustrative ACARS message": {"Remarks": "ACARS envelope/header only. Aircraft: N555AA. Label: H1. Block ID: 2. Message sequence: M14A. Flight: AA2055. No application payload is present, so nothing further is decoded. The label H1 alone does not establish a specific airline application."},
    "Decode this ACARS header: ..N842UA H1 6 M01A UA1412 #DFB": {"Remarks": "ACARS envelope with trailing payload-style text after #DFB. Aircraft: N842UA. Label: H1. Block ID: 6. Message sequence: M01A. Flight: UA1412. The trailing numeric text is airline/application-defined, so its format is not assumed and it is not decoded."},
    "Decode `BECMG 0716/0718": {"Remarks": "Partial TAF group. BECMG = becoming. Between the 7th 1600 UTC and the 7th 1800 UTC conditions change to: wind from 270° at 12 kt; visibility greater than 6 statute miles; scattered at 4,000 ft AGL. Station, issue time and the rest of the TAF are not supplied.", "Wind": "from 270° at 12 kt", "Visibility": "greater than 6 statute miles", "Clouds": "scattered at 4,000 ft AGL"},
    "Decode this simplified NOTAM: TWY A BTN": {"Remarks": "NOTAM-style notice. Item: Taxiway A between Taxiway B and Taxiway C. Status: closed. Effective: daily from 2000Z? no."},
    "Decode this simplified NOTAM: ILS RWY 24L LOC": {"Remarks": "NOTAM-style notice. Item: ILS for runway 24L, localizer (LOC) component. Status: unserviceable. Effective: from the 5th at 1200Z to the 5th at 1800Z. Month and year are not supplied. Airport is not supplied."},
    "Decode this simplified NOTAM: GPS UNREL": {"Remarks": "NOTAM-style notice. Item: GPS. Status: unreliable (UNREL). Effective: from the 5th at 1200Z to the 5th at 1800Z. Month and year are not supplied. Airport is not supplied."},
    "What do `PWINO`": {"Remarks": "These are METAR remark codes for sensors or data that are unavailable. PWINO: precipitation identifier information not available. FZRANO: freezing-rain sensor information not available. TSNO: thunderstorm information not available. RVRNO: RVR information not available. PNO: precipitation amount information not available. VISNO: visibility information at a secondary location not available."},
    "What is the difference between `BKN040` and": {"Remarks": "BKN040: broken cloud layer with a base at 4,000 ft AGL. BKN040CB: the same layer, identified as cumulonimbus. BKN is the coverage, 040 is the base in hundreds of feet, and CB marks cumulonimbus.", "Clouds": "broken at 4,000 ft AGL; broken cumulonimbus at 4,000 ft AGL (two codes compared)"},
    "Decode `R18/0600FT` and": {"Visibility": "RVR runway 18: 600 ft; RVR runway 18: less than 600 ft varying to 1,200 ft", "Remarks": "R18/0600FT: runway visual range for runway 18 is 600 ft. R18/M0600V1200FT: runway 18 RVR varies between below 600 ft (M = less than) and 1,200 ft."},
    "What does `RAB25E40` mean in METAR remarks": {"Weather": NP, "Remarks": "RAB25E40: rain began 25 minutes past the hour and ended 40 minutes past the hour."},
    "Decode SLP112": {"Altimeter": NP, "Remarks": "SLP112 is a METAR remark: sea-level pressure 1011.2 hPa. It is not the altimeter setting."},
    "What does NSC mean in a TAF": {"Altimeter": NP, "Remarks": "NSC means no significant cloud (no cloud below 5,000 ft AGL and no CB or TCU) in a TAF. The fragment alone does not establish the airport or valid period."},
}
MANUAL["Decode this simplified NOTAM: TWY A BTN"]["Remarks"] = ("NOTAM-style notice. Item: Taxiway A between Taxiway B and Taxiway C. Status: closed. "
                                                              "Effective: daily from 1200Z to 2000Z. Airport is not supplied.")

TAFRE = re.compile(r"((?:TAF )?(?:(?:AMD|COR) )?[A-Z]{4} \d{6}Z \d{4}/\d{4}[^`]*?)(?:`|\.?$)")
fixed = {"taf": 0, "notam": 0, "acars": 0, "manual": 0, "strict": 0, "station": 0}
for r in rows:
    u = r["messages"][1]["content"].strip()
    a = r["messages"][2]["content"]
    new = None
    mm = None
    for k, ov in MANUAL.items():
        if u.startswith(k):
            p = parse(a); p.update(ov); new = p; fixed["manual"] += 1; break
    if new is None and "ATIS KDAY INFORMATION D 1753Z" in u:
        p = parse(a); p.update({"Airport": "KDAY", "Time": "1753 UTC", "Wind": "from 220° at 12 kt", "Visibility": "10 statute miles",
                                "Remarks": "ACARS payload containing ATIS text (information D, 1753Z). Date is not supplied."}); new = p; fixed["manual"] += 1
    if new is None and re.match(r"^(Decode|Decode this|Decode the|What does this)\b", u) and not re.search(r"\b(means|if|when|should)\b", u):
        m = TAFRE.search(u.strip("`"))
        if m and not "ACARS" in u:
            d = decode_taf(m.group(1).strip());
            if d: new = d; fixed["taf"] += 1
        if new is None:
            body = re.sub(r"^(Decode this simplified NOTAM|Decode this NOTAM|Decode|What does this NOTAM mean\?)[: ]*", "", u).strip().strip("`").rstrip(".")
            d = decode_notam(body) if re.search(r"CLSD|U/S|NOT AVBL|INOP|WIP", body) and "ACARS" not in u else None
            if d: new = d; fixed["notam"] += 1
        if new is None:
            body = re.sub(r"^(Decode: |Decode )", "", u).strip("`")
            d = decode_acars_pos(body) or decode_acars_header(re.sub(r"^.*?(\.\.N)", r"..N", body) if "header" in u or "link-test" in u or "illustrative" in u else "x")
            if d: new = d; fixed["acars"] += 1
        if new is None and "ACARS" in u:
            m = re.search(r"((?:[^`]*? )?(?:METAR|SPECI) [A-Z]{4} \d{6}Z[^`]*?)(?:`|$)", u.split(":", 1)[-1].strip().strip("`"))
            if m:
                body = m.group(1).strip()
                d = decode_acars_weather(body)
                if d: new = d; fixed["acars"] += 1
    if new is None:
        new = parse(a)
        if "Station Type" in new and new["Station Type"] != NP:
            new["Station Type"] = NP; fixed["station"] += 1
    new = {k: new.get(k, NP) for k in FIELDS}
    new["Station Type"] = NP
    for k, pat in STRICT.items():
        v = new[k]
        if v != NP and not re.match(pat, v):
            moved = f"{k} text supplied: {v}"
            new["Remarks"] = new["Remarks"] if (new["Remarks"] != NP and v in new["Remarks"]) else (moved if new["Remarks"] == NP else new["Remarks"] + " " + moved)
            new[k] = NP; fixed["strict"] += 1
    r["messages"][2]["content"] = fmt(new)
print("repairs:", fixed)

# ---- generated records ------------------------------------------------------------
used = {r["messages"][1]["content"] for r in rows}
sysmix = [SYS_S, SYS_L]
TT = ["Decode this TAF: {x}", "Decode `{x}`", "Decode TAF: {x}", "What does this forecast say? {x}", "Explain this TAF: {x}"]
NT = ["Decode this NOTAM: {x}", "Decode `{x}`", "What does this NOTAM mean? {x}", "Decode this simplified NOTAM: {x}", "Decode: {x}"]
AT = ["Decode this ACARS message: {x}", "Decode: {x}", "Decode ACARS payload: {x}", "Parse this ACARS message: `{x}`"]
HT = ["Decode this ACARS header: {x}", "Parse this ACARS message: `{x}`"]
new = []


def add(tpl, x, dec, sysm):
    u = rng.choice(tpl).format(x=x)
    if dec and u not in used:
        used.add(u); new.append(b6.record(sysm, u, fmt(dec))); return True
    return False


def many(n, make, tpl, decode, sysm_pool=sysmix):
    c = 0
    while c < n:
        x = make()
        c += add(tpl, x, decode(x), rng.choice(sysm_pool))


tr = b6.TRAIN_ST
many(700, lambda: gen_taf(tr, rng), TT, decode_taf)
many(450, lambda: gen_notam(tr, rng), NT, decode_notam)
many(250, lambda: gen_acars(tr, rng, lambda st: b6.gen_report(st)), AT, lambda x: decode_acars_pos(x) or decode_acars_weather(x))
many(120, lambda: gen_acars_header(rng), HT, decode_acars_header)
rows += new
rng.shuffle(rows)
with open(ROOT / "data/decode_102026_v8.jsonl", "w") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print("v8 records:", len(rows), "(+%d generated)" % len(new))

# ---- multi-format held-out eval ---------------------------------------------------------
ev, used_ev = [], set()
erng = random.Random(99)
HELD_ROUTE = ["KABQ", "KBOS", "KBWI", "KDAL", "KPDX", "KPIT", "KRDU", "KSAN", "KSDF", "KSFO"]
for n, make, tpl, dec in [(40, lambda: gen_taf(HELD, erng), TT, decode_taf), (30, lambda: gen_notam(HELD, erng), NT, decode_notam),
                          (30, lambda: gen_acars(HELD, erng, lambda st: b6.gen_report(st), pool=HELD_ROUTE), AT, lambda x: decode_acars_pos(x) or decode_acars_weather(x))]:
    c = 0
    while c < n:
        x = make(); d = dec(x); u = erng.choice(tpl).format(x=x)
        if d and u not in used_ev:
            used_ev.add(u); ev.append(b6.record(SYS_S, u, fmt(d))); c += 1
with open(ROOT / "eval/decode_102026_multiformat_heldout_v1.jsonl", "w") as fh:
    for r in ev:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print("multiformat eval:", len(ev))
