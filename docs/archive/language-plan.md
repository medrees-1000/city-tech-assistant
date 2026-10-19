# Language plan (tester round 1b, Part 2)

**Status (2026-10-15, updated after the probes):** plan written before the code. The owner chose **option 1** (understand any language, reply in English, with one short line in the student's language saying the answer is in English) with **option 3** (an English-only notice) as the fallback if the pre-registered rule R4 failed. **R4 failed** on the first probe run (hard failures in Spanish, Haitian Creole and Chinese), so **option 3 is the default** (`guardrails.non_english: english_only`). The option 1 code is still there, behind `guardrails.non_english: translate` (env `CTA_NON_ENGLISH`), so the owner can switch without new code. Results: `docs/decisions.md`, "Tester round 1b, Part 2". Everything marked "my call" is a design detail the owner can disagree with. The rule and the probe definitions are in `docs/decisions.md` ("Tester round 1b, Part 2").

**Why.** An outside tester found that questions in Spanish, Arabic, Haitian Creole and Russian abstain ("couldn't find anything") where the English equivalents answer, and that a Chinese drop-deadline question gave a narrower answer than English. Likely cause: retrieval compares meaning in English and falls under the 0.59 cutoff for other languages. The cutoff and retrieval are not touched.

## Where it sits (API layer only; nothing in the pipeline or eval path imports it)
```
question -> Stage 1 guards (kill switch, rate limit, spend cap)
         -> Stage 2 screens on the original text (distress, bereavement, personal data, injection, stress), scrub
         -> language prefilter (plain code)  -- English-looking: skip, nothing changes
         -> language step (ONE small model call) on the redacted text -> {language, english, note}
              language "en": downstream uses the original text, byte for byte
              otherwise: ALL screens run again on the English translation (injection, distress tiers,
                         bereavement, personal data, stress), then the router gets the English text
                         (classifier, CLARIFY and NO ADVICE detectors, calendar, chain, retrieval)
         -> answer = note line in the student's language + blank line + the normal English answer
```
- **Prefilter (plain code, no model).** Skip the language step when the text is pure ASCII **and** holds at least two distinct words from a small English function-word list chosen to be rare in Spanish, French, Portuguese and Italian (the list is in the decisions entry). Everything else goes to the language step. The step is never run on English-looking text, so English questions cost nothing extra.
- **Language step (my call).** One call to the same model as the classifier (`chat_model`), temperature 0, reasoning off, JSON output, the API's per-call timeout (15 s), its tokens and cost added to the request's cost (so the daily spend cap counts it). Input: the already-**redacted** text. Output: `language` (BCP-47 or "en"), `english` (an English translation; the original if English), `note` (one short sentence in the student's language: this answer is in English and the sources are in English; no facts, no numbers, no contacts).
- **Fail-safe.** A failed call, a timeout, invalid JSON or an unusable field falls back to today's behaviour with the original text (and no note). A note that fails the checks (more than 160 characters, a digit, an `@`, a link, a line break) is replaced by the English line "This answer is in English; the sources are in English."
- **Guardrails after translation.** The existing screens are English-only, so a non-English distress or injection message must still be caught: every screen runs again on the English translation before retrieval. A blocked message gets its fixed English reply (the 988 reply, the injection reply, ...), **with the language note first**.
- **What the model sees.** The classifier, the calendar selector, the chain code, the retrieval and the answer model get the **English text only** (never the original), so the answer prompt is unchanged.
- **Logging.** `how_found` gains `language` (`{"code", "english"}`, the English text is the redacted translation); the existing `trace` JSON of the log row holds it (no migration). The extra call's tokens, time and cost are in the existing token, stage and cost fields. The raw original text is never stored beyond today's redacted question.
- **Page.** Each answer paragraph renders with `dir="auto"` so an Arabic note line is displayed right to left.

## Option 3 (fallback, only if the rule fails)
Same detection step. For a non-English question: a fixed English reply (with the note line in the student's language first) saying the assistant currently answers in English only and asking the student to ask again in English; no retrieval; route `guardrail`; its own blocked reason in `/health`; distress and injection still get their own replies.

## What I cannot check
The translations of the probes are model-made and the owner cannot read most of these languages, so the probes check **retrieval, route and dates only, not translation quality**. The note line comes from the model and is checked only for shape (no digits, no links, short).
