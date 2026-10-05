# Training notes: why the model answered "Not provided."

## Root cause (data)
v5: 92% of records had 9+ of the 10 data fields set to "Not provided." and only 24 of 663 records
had 6+ fields filled. Always answering "Not provided." was the lowest-loss strategy.
v7 (`data/decode_102026_v7.jsonl`): 2,524 records, 80% have at least one field filled, 59% have 6+ filled;
overall Not-provided rate across the 10 data fields is 39% (down from 95%), and the remainder is intentional
(genuinely missing groups in fragments).

## Unsloth settings to check (cannot see the notebook; verify these)
1. **Train on responses only** (`train_on_responses_only` with the Qwen chat-template markers). The system prompt
   is ~1.6k-3.3k chars versus a ~360 char answer, so without response-only loss most of the gradient is spent on
   memorizing the prompt.
2. **Chat template parity**: train and infer with the identical template. Qwen3.x templates can insert an empty
   think block; if training data omits it but inference adds it (or vice versa) outputs degrade.
3. **Same system prompt at inference** as in training. v7 mixes the short and long prompts.
4. Hold out `eval/decode_102026_metar_heldout_v1.jsonl` (unseen stations) and score with
   `scripts/score_eval.py`. Track per-field accuracy, not just loss. A model that outputs all "Not provided."
   scores ~0 on Wind/Clouds/Temperature immediately.
5. Run `python scripts/validate.py <file>` before every training run.

## About "reasoning"
The answer format forbids visible reasoning, and a 4B model does not need it for METAR grammar: it is a fixed
token grammar, and the fix is dense, correct, decoder-verified examples (the v7 generator). If accuracy on
TAF/ACARS stays low, the next step is the same generate-and-verify loop for those formats, not a thinking trace.
