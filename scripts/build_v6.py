"""Build data/decode_102026_v6.jsonl from v5.

1. Drop exact duplicate user prompts.
2. Repair records whose prompt contains a complete, decodable METAR/SPECI but whose answer
   marked supplied fields "Not provided." or copied raw tokens (e.g. "Wind: 22012G20KT").
3. Add generated METAR/SPECI records (deterministic decoder = ground truth).
4. Write a held-out METAR eval set (stations/values disjoint from training).
"""
import json, random, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from metar_decoder import decode_metar, fmt, FIELDS, NP

ROOT = pathlib.Path(__file__).resolve().parent.parent
random.seed(102026)

rows = [json.loads(l) for l in open(ROOT / "data/decode_102026_v5.jsonl")]
SYS_LONG = rows[0]["messages"][0]["content"]
SYS_SHORT = json.loads(open(ROOT / "eval/decode_102026_adversarial_v1.jsonl").readline())["messages"][0]["content"]

METAR_IN_PROMPT = re.compile(r"((?:METAR |SPECI )?[A-Z]{4} \d{6}Z [^`\n]+?)(?:`|$)")


def fld(a, n):
    m = re.search(rf"^{n}: (.*)$", a, re.M)
    return m.group(1) if m else ""


def extract_report(u):
    if re.search(r"\b(TAF|NOTAM|ACARS)\b", u):
        return None
    m = re.search(r"((?:METAR |SPECI )?[A-Z]{4} \d{6}Z\b[^`]*)$", u.strip().strip("`"))
    return m.group(1).strip() if m else None


# ---- 1 + 2: dedupe and repair ------------------------------------------------
seen, out, fixed = set(), [], 0
for r in rows:
    u = r["messages"][1]["content"]
    if u in seen:
        continue
    seen.add(u)
    rep = extract_report(u)
    dec = decode_metar(rep) if rep else None
    if dec:
        a = r["messages"][2]["content"]
        old_rem = fld(a, "Remarks")
        plain = bool(re.match(r"^(Decode|Please decode|Decode this|Decode the following)\b[^?]*$", u.split(rep)[0].strip() + " x"))
        # keep an explanatory Remarks (a real answer to a question), otherwise use decoder remarks
        keep_rem = (not plain) and old_rem.count(". ") >= 1 and old_rem != NP
        new = dict(dec)
        if keep_rem:
            new["Remarks"] = old_rem
        newtxt = fmt(new)
        if newtxt != a:
            fixed += 1
            r["messages"][2]["content"] = newtxt
    out.append(r)
print(f"deduped {len(rows) - len(out)}; repaired {fixed}")

# ---- 3: generated records ---------------------------------------------------
STATIONS = "KATL KBOS KBWI KCLE KCLT KCVG KDAL KDEN KDFW KDTW KEWR KFLL KIAD KIAH KJFK KLAS KLAX KMCI KMCO KMDW KMEM KMIA KMKE KMSP KMSY KORD KPDX KPHL KPHX KPIT KSAN KSEA KSFO KSLC KSTL KTPA KCMH KLUK KILN KDAY KLEX KSDF KBNA KRDU KOMA KABQ KANC PHNL".split()
_V5_ST = set(re.findall(r"\b([KP][A-Z]{3}) \d{6}Z", " ".join(r["messages"][1]["content"] for r in rows)))
HELDOUT = set(random.sample([s for s in STATIONS if s not in _V5_ST], 10))  # never appear in v5 prompts
TRAIN_ST = [s for s in STATIONS if s not in HELDOUT]

TEMPL = ["Decode this METAR: {r}", "Decode `{r}`", "Decode {r}", "What does this report say? {r}",
         "Please decode: {r}", "Translate this weather report: {r}", "Break down this observation: {r}"]


def gen_report(stations):
    rtype = random.choice(["METAR"] * 4 + ["SPECI"])
    st = random.choice(stations)
    day, hh, mm = random.randint(1, 28), random.randint(0, 23), random.choice([0, 15, 20, 35, 51, 53, 56] if rtype == "METAR" else range(0, 60))
    toks = [rtype, st, f"{day:02d}{hh:02d}{mm:02d}Z"]
    if random.random() < .2:
        toks.append("AUTO")
    k = random.random()
    if k < .08:
        toks.append("00000KT")
    elif k < .2:
        toks.append(f"VRB{random.randint(2, 6):02d}KT")
    else:
        d, s = random.randrange(10, 361, 10), random.randint(3, 30)
        w = f"{d % 360 or 360:03d}{s:02d}"
        if random.random() < .35:
            w += f"G{s + random.randint(6, 18):02d}"
        toks.append(w + "KT")
        if random.random() < .12 and s > 5:
            toks.append(f"{(d - 40) % 360 or 360:03d}V{(d + 30) % 360 or 360:03d}")
    low = random.random() < .3
    vis = random.choice(["1/4SM", "1/2SM", "3/4SM", "1SM", "1 1/2SM", "2SM", "3SM", "5SM"] if low else ["6SM", "7SM", "10SM", "P6SM"])
    if random.random() < .08 and low:
        toks += [vis, f"R{random.choice(['04', '10L', '27R', '18'])}/{random.choice(['0600', '1200', '2400', '4000'])}FT"]
    else:
        toks.append(vis)
    wxs = []
    if low or random.random() < .4:
        wxs = [random.choice(["-RA", "RA", "+RA", "-SN", "SN", "BR", "FG", "HZ", "-DZ", "TSRA", "+TSRA", "FZFG", "BLSN", "-FZRA", "VCSH", "FU", "-SHRA", "+SN BLSN", "RA BR", "SQ"])]
    toks += [x for w in wxs for x in w.split()]
    layers = []
    if low and random.random() < .5:
        layers = [f"VV{random.choice(['001', '002', '003', '005'])}"]
    else:
        n = random.choice([0, 1, 1, 2, 2, 3])
        base = random.randint(3, 30) if not low else random.randint(2, 15)
        order = ["FEW", "SCT", "BKN", "OVC"]
        for i in range(n):
            c = order[min(3, i + random.randint(0, 1))] if i == 0 else order[min(3, order.index(layers[-1][:3]) + random.randint(0, 1))]
            h = base + i * random.randint(5, 20)
            cb = "CB" if ("TS" in " ".join(wxs) and random.random() < .7 and i == 0 and c in ("BKN", "SCT", "OVC", "FEW")) else ""
            layers.append(f"{c}{h:03d}{cb}")
        if n == 0:
            layers = [random.choice(["CLR", "SKC"])]
    toks += layers
    t = random.randint(-18, 35)
    dp = t - random.randint(0, 8 if not low else 3)
    f = lambda x: f"M{abs(x):02d}" if x < 0 else f"{x:02d}"
    toks.append(f"{f(t)}/{f(dp)}")
    toks.append(f"A{random.randint(2940, 3040)}")
    if random.random() < .5:
        rm = ["RMK", random.choice(["AO2", "AO1", "AO2"])]
        if random.random() < .5:
            rm.append(f"SLP{random.randint(0, 999):03d}")
        toks += rm
    return " ".join(toks)


def record(sysmsg, u, a):
    return {"messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": u}, {"role": "assistant", "content": a}]}


def make(n, stations, sysmsgs):
    res, keys = [], set()
    while len(res) < n:
        rep = gen_report(stations)
        dec = decode_metar(rep)
        if not dec or rep in keys:
            continue
        keys.add(rep)
        u = random.choice(TEMPL).format(r=rep)
        res.append(record(random.choice(sysmsgs), u, fmt(dec)))
    return res


used_prompts = {r["messages"][1]["content"] for r in out}
gen = [r for r in make(260, TRAIN_ST, [SYS_LONG] * 3 + [SYS_SHORT]) if r["messages"][1]["content"] not in used_prompts]
random.shuffle(out := out + gen)

# partial-input records (decoder never invents missing groups)
PARTIAL = [("KDAY 051453Z 22012KT 10SM", "Altimeter/temp/sky missing"), ("KCVG 071451Z 18008KT 10SM FEW025", "Temp/altimeter missing"),
           ("KCMH 081253Z 31015G25KT 1 1/2SM +SN", "Sky/temp missing"), ("KDTW 121256Z 27018KT 10SM SCT050 A2998", "Temp missing")]
for rep, note in PARTIAL:
    d = decode_metar(rep)
    if d:
        d["Remarks"] = "Partial METAR: only the groups present were decoded. Missing groups were not inferred."
        out.append(record(SYS_LONG, f"Decode this partial METAR: {rep}", fmt(d)))

# ---- write train ------------------------------------------------------------
with open(ROOT / "data/decode_102026_v6.jsonl", "w") as fh:
    for r in out:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print("train records:", len(out))

# ---- 4: held-out eval ------------------------------------------------------------
ev = make(60, sorted(HELDOUT), [SYS_SHORT])
with open(ROOT / "eval/decode_102026_metar_heldout_v1.jsonl", "w") as fh:
    for r in ev:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print("heldout eval:", len(ev), "stations:", sorted(HELDOUT))
