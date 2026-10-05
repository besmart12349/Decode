"""Score model outputs against an eval JSONL.

Usage: python scripts/score_eval.py eval/decode_102026_metar_heldout_v1.jsonl predictions.jsonl
predictions.jsonl: one JSON object per line, same order as the eval file: {"output": "<model answer>"}
Reports exact format compliance and per-field accuracy (Remarks is not scored; it is free text).
"""
import json, sys, collections, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from metar_decoder import FIELDS


def parse(a):
    return {l.split(": ", 1)[0]: l.split(": ", 1)[1] if ": " in l else "" for l in a.split("\n")}, [l.split(":", 1)[0] for l in a.split("\n")]


def main(ev_path, pred_path):
    ev = [json.loads(l) for l in open(ev_path)]
    pr = [json.loads(l) for l in open(pred_path)]
    assert len(ev) == len(pr), "prediction count must match eval count"
    fmt_ok, hits = 0, collections.Counter()
    for e, p in zip(ev, pr):
        gold, _ = parse(e["messages"][2]["content"])
        out, labels = parse(p["output"].strip())
        fmt_ok += labels == FIELDS
        for k in FIELDS:
            if k != "Remarks" and out.get(k, "").strip().lower() == gold[k].strip().lower():
                hits[k] += 1
    n = len(ev)
    print(f"format compliance: {fmt_ok}/{n}")
    for k in FIELDS:
        if k != "Remarks":
            print(f"{k:13s} {hits[k]}/{n}")
    print(f"all-field exact: {sum(all(parse(p['output'].strip())[0].get(k,'').strip().lower()==parse(e['messages'][2]['content'])[0][k].strip().lower() for k in FIELDS if k!='Remarks') for e,p in zip(ev,pr))}/{n}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
