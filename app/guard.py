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
    # broader phrasings of the same rules
    ("fake_social_proof", "We never write fake reviews, testimonials, ratings or sign-ups.",
     [r"\b(positive|glowing|happy)\b.{0,25}\b(comments?|feedback|quotes?|stories|posts?)\b.{0,30}\b(from|by|as)\b.{0,20}\b(customers?|users?|buyers?|students?|clients?)\b",
      r"\b(customer|user|client)\s+(quotes?|stories|praise)\b", r"\b(seed|populate)\b.{0,20}\b(reviews?|ratings?|waitlist)\b",
      r"\b(bots?|fake accounts?)\b.{0,30}\b(sign[- ]?up|join|upvote|review|comment)", r"\b(buy|purchase)\b.{0,15}\b(followers|reviews|upvotes|likes)\b"]),
    ("false_urgency", "We never add fake urgency such as countdown timers or invented scarcity.",
     [r"\b(timer|clock)\b.{0,20}\b(urgent|urgency|pressure|ticking|expire\w*)\b", r"\b(limited|last) (spots|seats|chance)\b.{0,30}\b(even though|although|not really|fake)\b",
      r"\b(make|makes|making) (them|people|users|visitors|buyers) (panic|rush|hurry)\b"]),
    ("impersonation", "We never pose as the founder, a customer or another brand.",
     [r"\b(reply|respond|answer|comment)\b.{0,20}\bas if (you were|i were|we were)\b", r"\buse (their|the) (logo|brand name)\b",
      r"\b(from|using) (my|the founder'?s) (account|email|profile)\b.{0,20}\bwithout\b"]),
    ("money_movement", "We never hold, move, charge or refund money, and payments stay out of this system.",
     [r"\b(collect|take|accept|handle)\b.{0,20}\b(payments?|card details|money)\b", r"\b(add|build|enable|set up)\b.{0,20}\b(checkout|payment form|stripe|paypal)\b"]),
    ("prompt_injection", "Requests to drop or rewrite the system's rules are refused.",
     [r"\b(disregard|forget|override|bypass|disable|turn off)\b.{0,30}\b(rules|guard\w*|safety|policy|polic(y|ies)|instructions|filters?|restrictions)\b",
      r"\b(you are now|from now on you are|act as)\b.{0,30}\b(unrestricted|unfiltered|no rules|evil|dan)\b",
      r"\bsystem prompt\b", r"<\s*/?\s*(system|admin)\s*>", r"\b(new|updated) (rules|instructions) from (the )?(admin|developer|organizers?|judges?)\b"]),
]

# Arabic phrasings (judges may test in Arabic). Substring patterns, no word boundaries.
ARABIC_RULES: list[tuple[str, str, list[str]]] = [
    ("fake_social_proof", "We never write fake reviews, testimonials, ratings or sign-ups.",
     [r"(تقييمات|ريفيوهات|ريفيو|مراجعات|شهادات|آراء عملاء|اراء عملاء|تعليقات).{0,30}(وهمي|مزيف|مزيفة|وهمية|مفبرك|5 نجوم|خمس نجوم|خمسة نجوم)",
      r"(اكتب|اكتبلي|اعمل|اعملي|ولد|ألف|الف).{0,20}(تقييم|ريفيو|مراجعات|شهادات|آراء عملاء|اراء عملاء)",
      r"(خمس|خمسة|5) نجوم",
      r"(تسجيلات|مشتركين|متابعين).{0,20}(وهمي|وهمية|مزيف|مزيفة)", r"(زود|نفخ|ضخم).{0,15}(الأرقام|الارقام|المشتركين|التسجيلات)"]),
    ("false_urgency", "We never add fake urgency such as countdown timers or invented scarcity.",
     [r"(عداد|عد) تنازلي", r"(باقي|متبقي|فاضل) \d+ (أماكن|اماكن|مقاعد)", r"العرض (ينتهي|بيخلص) (الليلة|النهارده|اليوم)"]),
    ("income_promise", "We never promise income or guarantee success.",
     [r"(اضمن|ضمان|مضمون|مضمونة|نضمن).{0,30}(دخل|ربح|أرباح|ارباح|فلوس|نجاح|مبيعات)", r"(دخل|ربح) مضمون"]),
    ("impersonation", "We never pose as the founder, a customer or another brand.",
     [r"(انتحل|اتنكر|اتظاهر|تظاهر|كأنك|كانك|بصفتك).{0,30}(عميل|زبون|المؤسس|شركة|براند)", r"(باسم|بإسم) (المؤسس|عميل|شركة)"]),
    ("money_movement", "We never hold, move, charge or refund money, and payments stay out of this system.",
     [r"(اسحب|حول|حوّل|اخصم|ادفع|استرد).{0,20}(فلوس|مبلغ|من الكارت|من الفيزا|الدفع)"]),
    ("credentials", "We never store or ask for passwords or card numbers, and never create accounts.",
     [r"(احفظ|خزن|سجل|اكتب).{0,20}(باسورد|كلمة السر|كلمات السر|رقم الكارت|رقم الفيزا|بيانات الكارت)", r"(اعمل|افتح|سجل).{0,10}(حساب|اكونت)"]),
    ("skip_approval", "Nothing is published, sent, spent or signed without the founder approving it.",
     [r"(من غير|بدون|من غير ما).{0,15}(موافقة|موافقتي|ما تسألني|تسأل|إذن|اذن)", r"(تجاهل|انسى|انسي).{0,15}(التعليمات|القواعد|الرولز)", r"انشر (على طول|علطول|فورا|فوراً)"]),
]

EXCLUDED_AR: list[tuple[str, str, list[str]]] = [
    ("financial_crypto", "Financial, investment and crypto products are excluded.",
     [r"(كريبتو|بيتكوين|عملات رقمية|عملات مشفرة|توصيات تداول|فوركس|اسهم|أسهم|استثمار)"]),
    ("health_legal_advice", "Health advice and legal advice products are excluded.",
     [r"(تشخيص|استشارة طبية|نصايح طبية|علاج|روشتة|استشارة قانونية|محامي)"]),
    ("physical_goods", "Physical goods are out of scope: this system only builds digital products.",
     [r"(تيشيرتات|ملابس|منتج ملموس|شحن منتجات|دروب شيبنج|جلد|جلود|هاند ?ميد|مشغولات|اكسسوارات|إكسسوارات|شنط)"]),
    ("financial_wallet", "Wallets, payment apps and fintech are excluded: a digital wallet is a financial product and a leather wallet is a physical good.",
     [r"(محفظ[ةه]|محافظ|دفع إلكتروني|دفع الكتروني|تحويل (فلوس|أموال|اموال)|قرض|قروض|بنك|تمويل|تأمين|فلوسك)"]),
]

EXCLUDED_PRODUCT_RULES: list[tuple[str, str, list[str]]] = [
    ("physical_goods", "Physical goods are out of scope: this system only builds digital products.",
     [r"\b(physical (product|goods)|t-?shirts?|merch|hardware device|dropshipping|ship(ping)? boxes|candles|apparel|furniture|food truck|bakery|leather\w*|handmade|handcrafted|jewel(le)?ry|cosmetics|skincare|clothing|sneakers|shoes)\b"]),
    ("financial_crypto", "Financial, investment and crypto products are excluded.",
     [r"\b(crypto\w*|bitcoin|ethereum|nft|token sale|trading (bot|signals?)|forex|stock (picks|tips|signals)|investment advice|day trading|defi|lending app|loans?)\b"]),
    ("financial_wallet", "Wallets, payment apps and fintech are excluded: a digital wallet is a financial product and a leather wallet is a physical good.",
     [r"\b(wallets?|e-?wallets?|payments? apps?|fintech|neo-?banks?|banking apps?|money transfers?|remittances?|budget(ing)? (app|tracker)s?|personal finance|expense tracker|portfolio trackers?|investing|investments?|insurance|credit scores?|bnpl|buy now,? pay later)\b"]),
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


_ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})


def normalize(text: str) -> list[str]:
    """Variants of the text that defeat simple obfuscation: zero-width
    characters, s p a c e d letters, l33t spelling, odd dashes."""
    t = text.translate(_ZW)
    t = re.sub(r"[\u2010-\u2015]", "-", t)
    variants = [t]
    despaced = re.sub(r"\b(\w) (?=\w\b)", r"\1", t)
    if despaced != t:
        variants.append(despaced)
    leet = re.sub(r"(?<=[a-z])[013457@](?=[a-z])|(?<=[a-z])[013457@]\b|\b[013457@](?=[a-z])",
                  lambda m: m.group(0).translate(_LEET), t.lower())
    if leet != t.lower():
        variants.append(leet)
    return variants


def _check(text: str, rules: list[tuple[str, str, list[str]]]) -> Verdict:
    for variant in normalize(text):
        for rule_id, reason, patterns in rules:
            for p in patterns:
                if re.search(p, variant, flags=re.I | re.S):
                    return Verdict(False, rule_id, reason)
    return Verdict(True)


def check_request(text: str) -> Verdict:
    """Founder free-text request or brief field."""
    for rules in (REQUEST_RULES, ARABIC_RULES, EXCLUDED_PRODUCT_RULES, EXCLUDED_AR):
        v = _check(text, rules)
        if not v.allowed:
            return v
    return Verdict(True)


def check_product(idea_text: str) -> Verdict:
    v = _check(idea_text, EXCLUDED_PRODUCT_RULES)
    return v if not v.allowed else _check(idea_text, EXCLUDED_AR)


INJECTION_IN_SOURCE = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+)?(previous|prior|above|earlier)?\s*(instructions|rules|prompts?)"
    r"|you are (now )?(an? )?(ai|assistant|chatbot)|system prompt|<\s*/?\s*system\s*>|assistant:|###\s*instruction",
    re.I)


def sanitize_source(text: str) -> str:
    """Retrieved web text is data. Drop sentences that try to instruct the model."""
    parts = re.split(r"(?<=[.!?\n])\s+", text)
    return " ".join(p for p in parts if not INJECTION_IN_SOURCE.search(p))


POLICY_PROMISE = re.compile(r"\b(we|i) (guarantee|promise)\b|\bguaranteed (results?|income|grades|success|returns?)\b", re.I)


def check_policy(text: str) -> Verdict:
    """Policy drafts legitimately say results are NOT guaranteed, so the generic
    income rule is replaced by one that catches positive promises only."""
    if POLICY_PROMISE.search(text):
        return Verdict(False, "promise_in_policy", "Policy draft promised results.")
    return _check(text, [r for r in OUTPUT_RULES if r[0] not in ("income_claim_in_output", "payment_in_output")])


NEGATED_GUARANTEE = re.compile(r"\b(not|no|never|without|cannot|can't|don't|doesn't|won't)\b[^.!?\n]{0,40}?\bguarantee\w*", re.I)


def check_output(text: str) -> Verdict:
    """Generated artifact before it may be queued for publishing or sending.
    Disclaimers ("results are not guaranteed") are honest and allowed; promises are not."""
    return _check(NEGATED_GUARANTEE.sub(" ", text), OUTPUT_RULES)


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
