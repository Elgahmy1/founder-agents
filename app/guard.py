"""Policy guard: hard rules checked in code on every founder request, every
brief, and every generated artifact before it can enter the approval queue.

Deterministic patterns are the primary layer (they cannot be talked out of
their decision). The model is only used to word a refusal or a safe
alternative, never to decide whether a rule applies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Each rule: id, human reason, patterns matched against lower-cased text.
REQUEST_RULES: list[tuple[str, str, list[str]]] = [
    ("fake_social_proof", "We never write fake reviews, testimonials, ratings or sign-ups.",
     [r"\b(fake|invent|made[- ]up|fabricat\w*|generate|write|create)\b.{0,40}\b(reviews?|testimonials?|ratings?|sign[- ]?ups?|signups|endorsements?|case stud(y|ies)|followers|likes)\b",
      r"\b\d+\s*(five|5)[- ]star\b", r"\bfive[- ]star reviews?\b", r"\bpad\b.{0,20}\b(numbers|waitlist|metrics)\b",
      r"\b(inflate|boost|fake)\b.{0,20}\b(numbers|waitlist|metrics|traction|sign[- ]?ups?)\b"]),
    ("false_urgency", "We never add fake urgency such as countdown timers or invented scarcity.",
     [r"\bcountdown\b", r"\bonly \d+ (left|spots|seats)\b", r"\b(fake|false|artificial)\b.{0,15}\b(urgency|scarcity)\b",
      r"\boffer ends (tonight|today|in \d+)"]),
    ("income_promise", "We never promise income or guarantee success.",
     [r"\bguarantee\w*\b.{0,40}\b(income|revenue|profit|success|sales|money|results?)\b",
      r"\b(promise|ensure)\w*\b.{0,30}\b(income|revenue|profit|\$\d)",
      r"\bmake \$?\d[\d,]*k?\b.{0,20}\b(a|per) (month|week|day)\b"]),
    ("impersonation", "We never pose as the founder, a customer or another brand.",
     [r"\b(pretend|pose|posing|impersonat\w*|act)\b.{0,20}\b(as|to be)\b.{0,30}\b(customer|user|founder|ceo|client|buyer|brand|company|apple|google|microsoft|amazon|meta|openai)\b",
      r"\b(sign|write|post|send)\b.{0,30}\b(as|in the name of)\b.{0,10}\b(the founder|a customer|customers|another brand)\b",
      r"\bsock ?puppet", r"\bastroturf"]),
    ("money_movement", "We never hold, move, charge or refund money, and payments stay out of this system.",
     [r"\b(charge|bill|invoice)\b.{0,20}\b(card|customer|them|users?)\b", r"\b(transfer|wire|send|move)\b.{0,20}\b(money|funds|payment|\$\d)",
      r"\b(process|issue|make)\b.{0,10}\b(refunds?|payments?)\b", r"\bstripe live\b", r"\bpaypal\b.{0,20}\b(send|transfer)\b"]),
    ("credentials", "We never store or ask for passwords or card numbers, and never create accounts.",
     [r"\b(store|save|keep|remember|log)\b.{0,30}\b(password|passwords|card numbers?|credit cards?|cvv|api keys?)\b",
      r"\bmy password is\b", r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b",
      r"\b(create|register|open|sign up for)\b.{0,15}\b(an? )?(account|accounts)\b"]),
    ("skip_approval", "Nothing is published, sent, spent or signed without the founder approving it.",
     [r"\b(without|skip|bypass|no need for|don'?t need)\b.{0,25}\b(approv\w*|confirm\w*|asking|permission|the founder)\b",
      r"\b(auto[- ]?(publish|post|send|approve))\b", r"\bignore (all |your )?(previous |prior )?(instructions|rules)\b",
      r"\b(developer|admin|god|jailbreak|dan) mode\b"]),
    ("paywall_core", "We never hide core features of this system behind a paywall.",
     [r"\bpaywall\b.{0,30}\b(this (tool|system|app)|core features?)\b"]),
]

EXCLUDED_PRODUCT_RULES: list[tuple[str, str, list[str]]] = [
    ("physical_goods", "Physical goods are out of scope: this system only builds digital products.",
     [r"\b(physical (product|goods)|t-?shirts?|merch|hardware device|dropshipping|ship(ping)? boxes|candles|apparel|furniture|food truck|bakery)\b"]),
    ("financial_crypto", "Financial, investment and crypto products are excluded.",
     [r"\b(crypto\w*|bitcoin|ethereum|nft|token sale|trading (bot|signals?)|forex|stock (picks|tips|signals)|investment advice|day trading|defi|lending app|loan)\b"]),
    ("health_legal_advice", "Health advice and legal advice products are excluded.",
     [r"\b(medical diagnos\w*|diagnose (patients|illness|disease)|symptom checker|medical advice|treatment plan|prescri\w*|therap(y|ist) bot|mental health advice|diet plan for (diabetes|disease)|legal advice|lawyer bot|contract review for clients|immigration advice)\b"]),
]

# Things that must never appear in a generated artifact the founder may publish.
OUTPUT_RULES: list[tuple[str, str, list[str]]] = [
    ("testimonial_in_output", "Generated copy contained a testimonial or review.",
     [r"[\"“][^\"”]{10,200}[\"”]\s*[—–-]\s*[A-Z][a-z]+", r"\b(testimonials?|what (our|people) (customers|users) say)\b", r"★★★|\b5/5 stars\b"]),
    ("countdown_in_output", "Generated copy contained a countdown or false urgency.",
     [r"\bcountdown\b", r"\bonly \d+ (left|spots|seats)\b", r"\bhurry\b", r"\blimited time\b", r"setInterval\("]),
    ("income_claim_in_output", "Generated copy promised income or results.",
     [r"\bguarantee\w*\b", r"\bmake \$\d", r"\b(earn|make)\b.{0,15}\b(passive income|six figures|\$\d)"]),
    ("fake_traction_in_output", "Generated copy invented traction numbers.",
     [r"\b(join|joined|trusted by|used by|loved by|chosen by)\s+(over\s+|more than\s+)?[\d,.]+\s*[kKmM+]*\s+\w+",
      r"\b[\d,.]{2,}\s*[kKmM+]*\s*(happy |satisfied )?(users|customers|students|founders|members|subscribers|people|teams)\b"]),
    ("payment_in_output", "Generated copy tried to collect payment details.",
     [r"\b(card number|cvv|credit card|checkout|buy now|pay now)\b", r"type=[\"']?password"]),
]


@dataclass
class Verdict:
    allowed: bool
    rule: str | None = None
    reason: str | None = None


def _check(text: str, rules: list[tuple[str, str, list[str]]]) -> Verdict:
    for rule_id, reason, patterns in rules:
        for p in patterns:
            if re.search(p, text, flags=re.I | re.S):
                return Verdict(False, rule_id, reason)
    return Verdict(True)


def check_request(text: str) -> Verdict:
    """Founder free-text request or brief field."""
    v = _check(text, REQUEST_RULES)
    return v if not v.allowed else _check(text, EXCLUDED_PRODUCT_RULES)


def check_product(idea_text: str) -> Verdict:
    return _check(idea_text, EXCLUDED_PRODUCT_RULES)


def check_output(text: str) -> Verdict:
    """Generated artifact before it may be queued for publishing or sending."""
    return _check(text, OUTPUT_RULES)


def scrub_output(text: str) -> tuple[str, list[str]]:
    """Remove offending lines from generated copy; return text and removed rule ids."""
    removed: list[str] = []
    kept: list[str] = []
    for line in text.splitlines():
        v = check_output(line)
        if v.allowed:
            kept.append(line)
        else:
            removed.append(v.rule or "unknown")
    return "\n".join(kept), removed
