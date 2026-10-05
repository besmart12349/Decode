# Decode dataset improvements

## v8 (current: use `data/decode_102026_v8.jsonl`)

4,044 records. Everything decodable is generated or repaired by deterministic decoders
(`scripts/metar_decoder.py`, `scripts/taf_notam_acars.py`) and checked by `scripts/validate.py` (0 errors).

- METAR/SPECI full decodes: 1,512 records, 4% Not-provided rate (v5 was 95% across the dataset).
- TAF: 769 records. Fields = base forecast + issue time; validity and every FM/TEMPO/BECMG/PROB group in Remarks.
- NOTAM: 492 records (runway/taxiway/navaid/obstacle items, status, effective period).
- ACARS: 433 records (position reports, embedded METAR/SPECI with envelope preserved, envelope-only headers).
- Hand-written records repaired: glued Remarks rewritten, misplaced values moved out of Altimeter/Time fields,
  ICAO codes removed from Station Type (always "Not provided." now).
- Evals (stations never seen in training): `eval/decode_102026_metar_heldout_v1.jsonl` (60),
  `eval/decode_102026_multiformat_heldout_v1.jsonl` (100: 40 TAF, 30 NOTAM, 30 ACARS),
  plus the original 10-case adversarial file.

Known limits: ~20% of records are policy/Q&A prompts with mostly-Not-provided answers (intentional, but do not
increase this share); NOTAM/ACARS grammars cover a defined subset, not full ICAO/airline formats; no real-world
METAR/TAF samples are included, all generated data is synthetic.

## v6/v7 history


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
