#!/usr/bin/env python3
"""Clip prospectus prose without cutting a word in half.

The pipeline cards showed "…enable autonomous recognition, decision-making
and motion pla" and "…improve operational efficienc" — fixed character cuts
landing mid-word. A clipped sentence is fine; a clipped WORD reads broken.
"""
import re

_END = re.compile(r"[.;:!?](?:\s|$)")
# PDF font artefacts that survive extraction ("/H1118/H1118250 278 272") —
# prose that carries them is unreadable, not merely long
_ARTEFACT = re.compile(r"/H\d{3,}|�|[Šš]{2,}")
# a TABLE read as prose: consecutive bare years or a run of bare numbers
# ("As of December 31, 2023 2024 2025 Self-operated offline stores 118 250")
_TABLE = re.compile(r"(?:\b(?:19|20)\d{2}\b[\s,]+){2,}|(?:\b\d[\d,.]*\b[ \t]+){3,}")


def clip_sentence(text, limit=600, hard=None):
    """Cut at the last SENTENCE end within `limit`; fall back to the last word
    boundary (with an ellipsis) when no sentence ends in range.

    hard = the absolute ceiling; text longer than `limit` but shorter than
    `hard` is returned whole rather than cut a few characters early.
    """
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if not s:
        return None
    # cut BEFORE the first extraction artefact rather than shipping glyph junk
    for rx in (_ARTEFACT, _TABLE):
        m = rx.search(s)
        if m:
            s = s[:m.start()].strip(" ,;:")
            # keep whole sentences out of what survived, never a half clause
            ends = [e.end() for e in _END.finditer(s)]
            if ends:
                s = s[:ends[-1]].strip()
            if len(s) < 15:
                return None
    # a trailing ":" is a table lead-in ("…as of the dates indicated:") —
    # step back to the sentence before it
    if s.endswith(":"):
        prev = [e.end() for e in _END.finditer(s[:-1])]
        if prev and prev[-1] > 40:
            s = s[:prev[-1]].strip()
        else:
            s = s[:-1].rstrip(" ,;") + "."
    # trim a dangling clause opener left behind by the cut
    s = re.sub(r"[\s,;:]*\b(?:As\s+of|As\s+at|For\s+the\s+(?:year|period)"
               r"(?:\s+ended)?|In\s+the\s+(?:year|period))\b[^.;]*$", "", s).strip()
    if not s:
        return None
    if len(s) <= (hard or limit):
        return s
    ends = [m.end() for m in _END.finditer(s) if m.end() <= limit]
    if ends and ends[-1] >= limit * 0.5:
        return s[:ends[-1]].strip()
    cut = s.rfind(" ", 0, limit)
    return (s[:cut] if cut > 0 else s[:limit]).rstrip(" ,;:") + "…"


def clip_phrase(text, limit=90):
    """Short clause for a bucket label — word boundary, no dangling ellipsis
    when the whole clause already fits."""
    s = re.sub(r"\s+", " ", str(text or "")).strip(" ,;:.")
    if len(s) <= limit:
        return s
    cut = s.rfind(" ", 0, limit)
    out = (s[:cut] if cut > 0 else s[:limit]).rstrip(" ,;:")
    # "…day-to-day operations and…" — drop a dangling connective
    out = re.sub(r"\s+(?:and|or|to|for|of|with|in|the|a|as)$", "", out, flags=re.I)
    return out + "…"
