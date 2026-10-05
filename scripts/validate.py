"""Validate Decode JSONL files. Usage: python scripts/validate.py data/decode_102026_v8.jsonl [more.jsonl ...]

Hard errors (exit code 1): wrong roles, fields not exactly the 12 in order, <think>/code fences, empty values,
duplicate prompts, strict field-type violations (Date/Time/Temperature/Dew Point/Altimeter hold only their own
value), Station Type not "Not provided.", and decoder mismatches on plain METAR/SPECI/TAF/NOTAM/ACARS prompts.
Warnings: Remarks longer than 150 chars with no sentence/clause separator (run-on text).
Also prints the Not-provided rate so a collapse is visible.
"""
import json, re, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from metar_decoder import decode_metar, FIELDS, NP
from taf_notam_acars import decode_taf, decode_notam, decode_acars_pos, decode_acars_weather, decode_acars_header

STRICT = {"Date": r"^\d+(st|nd|rd|th)$", "Time": r"^\d{4} UTC$", "Temperature": r"^-?\d+(\.\d)?°C( \([^)]*\))?$",
          "Dew Point": r"^-?\d+(\.\d)?°C( \([^)]*\))?$", "Altimeter": r"^\d\d\.\d\d inHg$"}
PREFIX = (r"^(?:Decode this METAR: |Decode this TAF: |Decode TAF: |Decode this NOTAM: |Decode this simplified NOTAM: |Decode this ACARS message: |"
          r"Decode this ACARS header: |Decode ACARS payload: |Parse this ACARS message: `?|Decode `|Decode: |Decode |What does this report say\? |"
          r"What does this forecast say\? |What does this NOTAM mean\? |Explain this TAF: |Please decode: |Translate this weather report: |Break down this observation: )(.*?)`?$")


def parse(a):
    out = {}
    for l in a.split("\n"):
        k, _, v = l.partition(": ")
        out[k] = v
    return out, [l.split(":", 1)[0] for l in a.split("\n")]


def reference(body):
    for fn in (decode_taf, decode_acars_pos, decode_acars_header, decode_acars_weather, decode_notam, decode_metar):
        try:
            d = fn(body)
        except Exception:
            d = None
        if d:
            return d
    return None


def main(paths):
    errs, warns, npc, total = collections.Counter(), 0, 0, 0
    for p in paths:
        seen = set()
        for n, line in enumerate(open(p), 1):
            r = json.loads(line)
            m = r["messages"]
            u, a = m[1]["content"], m[2]["content"]
            f, labels = parse(a)
            total += 1
            if [x["role"] for x in m] != ["system", "user", "assistant"]:
                errs["roles"] += 1
            if labels != FIELDS:
                errs["fields/order"] += 1; print(f"{p}:{n} bad fields"); continue
            if "<think" in a or "```" in a:
                errs["think/fence"] += 1
            if any(not v.strip() for v in f.values()):
                errs["empty value"] += 1
            if u in seen:
                errs["duplicate prompt"] += 1; print(f"{p}:{n} duplicate prompt")
            seen.add(u)
            for k, pat in STRICT.items():
                if f[k] != NP and not re.match(pat, f[k]):
                    errs[f"strict:{k}"] += 1; print(f"{p}:{n} {k} = {f[k][:50]!r}")
            if f["Station Type"] != NP:
                errs["station type"] += 1; print(f"{p}:{n} Station Type = {f['Station Type']!r}")
            rm = f["Remarks"]
            if len(rm) > 150 and not re.search(r"[.;]\s", rm):
                warns += 1
            npc += sum(f[k] == NP for k in FIELDS[:10])
            mm = re.match(PREFIX, u)
            if mm and not re.search(r"\b(means|should|if|when|why|how)\b", u, re.I):
                d = reference(mm.group(1).strip().rstrip("."))
                if d:
                    bad = [k for k in FIELDS if k != "Remarks" and f.get(k) != d[k]]
                    if bad:
                        errs["decoder mismatch"] += 1; print(f"{p}:{n} mismatch in {bad}: {u[:70]}")
    print(f"records: {total}; Not-provided rate over the 10 data fields: {100 * npc // (10 * max(total, 1))}%; run-on remarks warnings: {warns}")
    print("errors:", dict(errs) or "none")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
