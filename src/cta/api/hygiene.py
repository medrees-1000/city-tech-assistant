"""Input hygiene (tester round 2, T13; docs/decisions.md): the question is cleaned at API entry,
before any screen, redaction, log write or model call. Postgres cannot store a NUL character in a
text column, so one such character used to make the log row fail after the question was answered.
"""

import re

# C0 and C1 controls except newline and tab, bidi overrides/isolates, zero-width characters, the
# soft hyphen
REMOVE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f‪-‮⁦-⁩​-‍⁠﻿­]")
SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """The question without hidden characters and with every whitespace run as one space.
    Idempotent: normalizing twice gives the same text."""
    return SPACES.sub(" ", REMOVE.sub("", text)).strip()
