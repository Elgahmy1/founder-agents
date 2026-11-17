"""Deterministic Arabic normalization, so spelling variants common in Egyptian Arabic and in Whisper transcripts
(أ/إ/آ/ا, ة/ه, ى/ي, diacritics, tatweel) do not break quote matching or let a rule be dodged by spelling."""
from __future__ import annotations

import re

_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_MARKS = re.compile(r"[ً-ٰٟۖ-ۭـ]")  # tashkeel, superscript alef, Quranic marks, tatweel


def normalize_ar(text: str) -> str:
    return _MARKS.sub("", (text or "").translate(_MAP))


# Polite Egyptian / Arabic non-commitments and English equivalents: compliments or hope, not evidence of buying.
POLITE_NON_COMMITMENT = re.compile(
    r"ان شاء الله|انشاء الله|ان شالله|فكره (جامده|حلوه|تحفه|هايله)|ربنا يسهل|ربنا يوفقك|هجربه(ا)? (اكيد|اكيدا)?|"
    r"اكيد هستخدم|ممكن استخدمه|لو نزل هجرب|"
    r"\b(would|will) (totally|definitely|probably) (use|buy|try|pay)|sounds (great|cool|amazing)|great idea|love (it|this idea)|"
    r"insha(')?allah|fekra gamda|rabena yesahel", re.I)


def is_polite_non_commitment(quote: str) -> bool:
    return bool(POLITE_NON_COMMITMENT.search(normalize_ar(quote)))
