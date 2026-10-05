"""Validate a Decode JSONL file. Usage: python scripts/validate.py data/decode_102026_v6.jsonl [more.jsonl ...]

Checks: roles, exact 12 fields in order, no <think>/code fences, no empty values, no duplicate prompts,
and (for plain METAR/SPECI prompts) that every field matches the deterministic decoder.
Exit code 1 if any hard error is found.
"""
import json, re, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from metar_decoder import decode_metar, FIELDS, NP


def parse(a):
    out = {}
    for l in a.split("\n"):
        k, _, v = l.partition(": ")
        out[k] = v
    return out, [l.split(":", 1)[0] for l in a.split("\n")]


def main(paths):
    errs = collections.Counter()
    for p in paths:
        seen = set()
        for n, line in enumerate(open(p), 1):
            r = json.loads(line)
            m = r["messages"]
            u, a = m[1]["content"], m[2]["content"]
            if [x["role"] for x in m] != ["system", "user", "assistant"]:
                errs["roles"] += 1
            f, labels = parse(a)
            if labels != FIELDS:
                errs["fields/order"] += 1; print(f"{p}:{n} bad fields")
            if "<think" in a or "```" in a:
                errs["think/fence"] += 1
            if any(not v.strip() for v in f.values()):
                errs["empty value"] += 1; print(f"{p}:{n} empty value")
            if u in seen:
                errs["duplicate prompt"] += 1; print(f"{p}:{n} duplicate prompt")
            seen.add(u)
            mm = re.match(r"^(?:Decode this METAR: |Decode `|Decode |What does this report say\? |Please decode: |Translate this weather report: |Break down this observation: )(.*?)`?$", u)
            if mm and not re.search(r"TAF|NOTAM|ACARS", u):
                d = decode_metar(mm.group(1))
                if d:
                    bad = [k for k in FIELDS if k != "Remarks" and f.get(k) != d[k]]
                    if bad:
                        errs["decoder mismatch"] += 1; print(f"{p}:{n} mismatch in {bad}")
    print("errors:", dict(errs) or "none")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
