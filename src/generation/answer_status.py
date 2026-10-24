"""The answer's status, reported by the generate call itself, plus a
zero-LLM check on it.

There is no separate verifier call: the generate prompt asks the model to end
its answer with one line, `STATUS: answered | partial | not_covered`, saying
how much of the question the source text covered. parse_status() strips that
line and reads it; a missing or garbled line counts as "partial".

A model's label on its own answer is not an independent check, so
check_identifiers() adds one where a wrong answer does the most damage: every
exact 3GPP identifier in the answer (timer T3510, cause #22, message name
ATTACH REQUEST) must appear in the source text the model was given. If one
doesn't, an "answered" label is downgraded to "partial".
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

STATUSES = ("answered", "partial", "not_covered")

_STATUS_LINE_RE = re.compile(r"^[\s*_`]*STATUS\s*:\s*(answered|partial|not[ _-]?covered)[\s*_`.]*$",
                             re.IGNORECASE | re.MULTILINE)

# Exact identifiers worth checking: timers, cause numbers, and upper-case
# message names ("REGISTRATION REQUEST", "DL NAS TRANSPORT").
TIMER_RE = re.compile(r"\bT\d{4}\b")
CAUSE_RE = re.compile(r"#\d+\b")
MESSAGE_NAME_RE = re.compile(r"\b[A-Z][A-Z0-9-]{2,}(?: [A-Z][A-Z0-9-]{1,})+\b")


def parse_status(text: str) -> Tuple[str, Optional[str]]:
    """(answer without its STATUS line, status or None if the line is missing).
    The last STATUS line wins; every STATUS line is removed from the text."""
    matches = list(_STATUS_LINE_RE.finditer(text))
    if not matches:
        return text.strip(), None
    status = re.sub(r"[ _-]", "_", matches[-1].group(1).lower())
    status = "not_covered" if status.startswith("not") else status
    return _STATUS_LINE_RE.sub("", text).strip(), status


def find_identifiers(text: str) -> List[str]:
    found: List[str] = []
    for pattern in (TIMER_RE, CAUSE_RE, MESSAGE_NAME_RE):
        for m in pattern.finditer(text):
            if m.group(0) not in found:
                found.append(m.group(0))
    return found


def check_identifiers(answer: str, source_text: str) -> List[str]:
    """Identifiers in the answer that never appear in the source text.
    Timers and causes match as whole tokens; message names case-insensitively,
    since specs write them both as "ATTACH REQUEST" and "attach request"."""
    source_lower = source_text.lower()
    missing: List[str] = []
    for ident in find_identifiers(answer):
        if MESSAGE_NAME_RE.fullmatch(ident):
            if re.sub(r"\s+", " ", ident.lower()) not in re.sub(r"\s+", " ", source_lower):
                missing.append(ident)
        elif not re.search(r"(?<![A-Za-z0-9])" + re.escape(ident) + r"(?![0-9])", source_text):
            missing.append(ident)
    return missing
