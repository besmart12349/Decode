"""Build data/decode_102026_v7.jsonl from v6, fixing the "Not provided." collapse.

v5/v6 problem: most records were 12-field shells with nearly every field "Not provided.",
so the cheapest way to lower loss was to always answer "Not provided.".
v7:
  * single-code / fragment prompts now fill the field(s) the code actually belongs to
  * +1,200 generated full METAR/SPECI decodes (decoder = ground truth)
  * +400 generated fragments (random group subsets of real-looking reports)
  * prints the Not-provided rate so regressions are visible
Held-out eval stations are never used in training.
"""
import json, random, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_v6 as b6  # reuses generator, rebuilds v6 as a side effect (deterministic)
from metar_decoder import decode_metar, fmt, FIELDS, NP

ROOT = pathlib.Path(__file__).resolve().parent.parent
random.seed(7)
SYS_S, SYS_L = b6.SYS_SHORT, b6.SYS_LONG
FRAG_NOTE = "Partial input: only the supplied group(s) were decoded. Station, time and all other groups were not supplied and were not inferred."


def decode_fragment(text):
    d = decode_metar("XXXX 010000Z " + text)
    if not d:
        return None
    for k in ("Airport", "Date", "Time"):
        d[k] = NP
    d["Remarks"] = FRAG_NOTE
    return d


rows = [json.loads(l) for l in open(ROOT / "data/decode_102026_v6.jsonl")]
PLAIN = re.compile(r"^(?:Decode|Decode fragment:?|What does) `?([^`?]+?)`?(?: mean\??)?$")
conv = 0
for r in rows:
    u = r["messages"][1]["content"].strip()
    m = PLAIN.match(u)
    if m and not re.search(r"\b[KP][A-Z]{3} \d{6}Z|TAF|NOTAM|ACARS|remark", u):
        d = decode_fragment(m.group(1).strip())
        if d and sum(v != NP for k, v in d.items() if k not in ("Remarks", "Station Type")) > 0:
            r["messages"][2]["content"] = fmt(d)
            conv += 1
print("fragment records converted to filled answers:", conv)

# generated full decodes
used = {r["messages"][1]["content"] for r in rows}
new = []
sysmix = [SYS_S, SYS_L]
for r in b6.make(1200, b6.TRAIN_ST, sysmix):
    if r["messages"][1]["content"] not in used:
        used.add(r["messages"][1]["content"]); new.append(r)

# generated fragments from real-looking reports
FRAG_T = ["Decode `{f}`", "Decode fragment: {f}", "What does `{f}` mean?", "Decode this partial report: {f}"]
nfrag = 0
while nfrag < 400:
    toks = b6.gen_report(b6.TRAIN_ST).split()[3:]
    toks = [t for t in toks if t not in ("AUTO",) and t != "RMK" and not t.startswith(("AO", "SLP"))]
    i = random.randrange(len(toks)); j = min(len(toks), i + random.choice([1, 1, 2, 3]))
    frag = " ".join(toks[i:j])
    d = decode_fragment(frag)
    if not d or all(v == NP for k, v in d.items() if k not in ("Remarks", "Station Type")):
        continue
    u = random.choice(FRAG_T).format(f=frag)
    if u in used:
        continue
    used.add(u); new.append(b6.record(random.choice(sysmix), u, fmt(d))); nfrag += 1

rows += new
random.shuffle(rows)
with open(ROOT / "data/decode_102026_v7.jsonl", "w") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

P = [{l.split(": ", 1)[0]: l.split(": ", 1)[1] if ": " in l else "" for l in r["messages"][2]["content"].split("\n")} for r in rows]
data_fields = FIELDS[:10]
filled = [sum(p[k] != NP for k in data_fields) for p in P]
print("v7 records:", len(rows))
print("records with >=1 data field filled: %d%%" % (100 * sum(f >= 1 for f in filled) // len(rows)))
print("records with >=6 of 10 data fields filled: %d%%" % (100 * sum(f >= 6 for f in filled) // len(rows)))
print("overall Not-provided rate across the 10 data fields: %d%%" % (100 * sum(10 - f for f in filled) // (10 * len(rows))))
