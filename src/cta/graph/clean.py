"""Clean a question for the search and the classifier (tester round 1, item B; docs/decisions.md).

Markup, emoji and redaction placeholders add noise to the embedding of a short question and can push
its best match just under the cutoff (a tester's "<script>alert(1)</script> whats the tuition
deadline" scored 0.574 against 0.59, while the plain question answers). This returns the text the
retrieval query and the classifier should see. It is used ONLY there: the injection screen and the
personal-data redaction run first on the raw text, and the answer prompt and the logs keep the text
as it came. A question with nothing to clean is returned unchanged, byte for byte.
"""

import re
import unicodedata

BLOCKS = re.compile(r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)
TAGS = re.compile(r"</?[A-Za-z][^<>]*>?")  # an opening or closing tag, even a cut-off one
PLACEHOLDERS = re.compile(r"\[(?:EMAIL|PHONE|ID|NAME|SSN)\]")
INVISIBLE = re.compile("[​-‏⁠︀-️\U000e0100-\U000e01ef\U0001f3fb-\U0001f3ff]")
EMOJI_EXTRA = "‼⁉™ℹ"  # !! and !? as emoji, TM, info
FULLWIDTH_PUNCTUATION = re.compile("[！-／：-＠［-｀｛-･]")


def is_pictograph(ch: str) -> bool:
    return unicodedata.category(ch) == "So" or ch in EMOJI_EXTRA


def clean_for_search(text: str) -> str:
    """The question without HTML tags (and script or style contents), emoji and pictographs, zero
    width characters, full-width punctuation and redaction placeholders, spaces collapsed. Unchanged
    when there is nothing to remove."""
    out = BLOCKS.sub(" ", text)
    out = TAGS.sub(" ", out)
    out = PLACEHOLDERS.sub(" ", out)
    out = INVISIBLE.sub("", out)
    out = FULLWIDTH_PUNCTUATION.sub(" ", out)
    out = "".join(" " if is_pictograph(ch) else ch for ch in out)
    if out == text:
        return text
    out = re.sub(r"\s+([,.;:!?])", r"\1", " ".join(out.split()))
    return out
