# Decode dataset improvements

## v6 (this change)

Audit of `data/decode_102026_v5.jsonl` found:

- 21 METAR/SPECI records whose answers disagreed with the report (supplied Airport/Wind/Weather/Clouds/Altimeter marked "Not provided.", or raw tokens copied such as `Wind: 22012G20KT`, `Altimeter: A2992`).
- 3 exact duplicate prompts.
- Inconsistent Airport values (invented airport names in some records, bare identifier in others).
- Run-on, unpunctuated Remarks in TAF/NOTAM/ACARS records (27 over 150 chars) and duplicated phrases. **Not yet repaired**; needs a TAF/NOTAM/ACARS decoder or manual review.

Changes:

- `scripts/metar_decoder.py`: deterministic METAR/SPECI decoder (ground truth for generation and validation).
- `scripts/build_v6.py`: dedupes, repairs affected v5 records, adds 260 generated METAR/SPECI records (varied stations, RVR, VV, fractions, calm/VRB, AUTO, RMK) plus partial-input records, and writes the held-out eval.
- `data/decode_102026_v6.jsonl`: 663 -> 924 records, 0 validation errors (v5: 24).
- `eval/decode_102026_metar_heldout_v1.jsonl`: 60 METAR/SPECI cases at stations that never appear in any training prompt.
- `scripts/validate.py` (run before every release) and `scripts/score_eval.py` (per-field accuracy).

Conventions enforced: Airport = identifier as supplied (no invented names); Date = day of month only; Station Type = "Not provided." (AO1/AO2 explained in Remarks).

## Next

1. TAF/NOTAM/ACARS decoders for the same generate-and-validate loop; rewrite run-on Remarks.
2. Decide whether AO1/AO2 should populate Station Type (currently not, per v5 convention).
3. Expand adversarial eval beyond 10 cases (malformed groups, conflicting data, confusable codes).
