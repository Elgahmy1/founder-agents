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
     [r"\b(fake|invent\w*|made[- ]up|fabricat\w*|generat\w*|writ\w*|creat\w*)\b.{0,40}\b(reviews?|testimonials?|ratings?|sign[- ]?ups?|signups|endorsements?|case stud(y|ies)|followers|likes)\b",
      r"\b(imaginary|fictional|fictitious|fake|made[- ]up|invented|non-?existent)\s+(customers|users|clients|reviewers|buyers|students)\b",
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
    # more phrasings found by testing judge-style trick prompts (see evals/red_team_prompts.json)
    ("fake_social_proof", "We never write fake reviews, testimonials, ratings or sign-ups.",
     [r"\bmak\w* up\b.{0,30}\b(reviews?|testimonials?|ratings?|quotes?|users?|customers?|sign[- ]?ups?)\b",
      r"\bcome up with\b.{0,30}\b(reviews?|testimonials?|ratings?)\b"]),
    ("fake_traction", "We never invent traction: user, customer and sign-up numbers come only from what the app actually counted.",
     [r"\b(say|says|saying|claim\w*|write|state|tell|show|put|mention|add)\b.{0,30}\b\d[\d,.]*\s*[kKmM+]*\s*(users|customers|students|sign[- ]?ups|signups|subscribers|members|downloads|people|buyers)\b",
      r"\b(already|over|more than)\s+[\d,.]+\s*[kKmM+]*\s+(users|customers|students|sign[- ]?ups|signups|subscribers|members|downloads)\b",
      r"\b(change|edit|set|update|bump|increase|raise|fix)\b.{0,25}\b(waitlist|sign[- ]?ups?|signups|visits?|count|counter)\b.{0,20}\b(to|by)\s+\d"]),
    ("skip_gate", "Gates cannot be skipped: you can override a recommendation at the gate yourself, and the log keeps both.",
     [r"\b(skip|bypass|ignore|disable|remove)\b.{0,15}\b(the |a |all )?(gates?|checks?|tests?|evidence threshold)\b",
      r"\b(launch|publish|ship|go)\b.{0,15}\b(anyway|regardless)\b"]),
    ("skip_approval", "Nothing is published, sent, spent or signed without the founder approving it.",
     [r"\bapprov\w*\b.{0,20}\b(everything|all of (it|them)|automatically|on my behalf)\b", r"\b(automatically|auto)\b.{0,10}\bapprov\w*"]),
    ("post_or_send", "The system never posts or sends anything itself: it drafts, you approve, and you post or send it personally.",
     [r"^\s*(please\s+|can you\s+|could you\s+)?(post|publish|tweet|share|upload)\b.{0,30}\b(on|to)\s+(twitter|x|facebook|linkedin|instagram|reddit|tiktok|discord|whatsapp|social media)\b",
      r"\b(post|publish|tweet|share|upload)\b.{0,40}\b(for me|on my behalf|automatically)\b",
      r"\b(send|email|dm|message)\b.{0,30}\b(to\s+)?\d+\s+(students|people|users|customers|leads|contacts)\b",
      r"\b(send|post|email)\b.{0,25}\b(it|this|them|the (outreach|emails?|messages?|posts?))\b.{0,15}\b(now|for me|on my behalf|automatically)\b"]),
    ("income_promise", "We never promise income or guarantee success.",
     [r"\b(promise|guarantee)\w*\b.{0,40}\b(will|pass|grades?|an? a\b|top marks|win|succeed|get (a|the) job|rank)\b",
      r"\b(earn|make|making|earning)\b.{0,20}\$\s?\d"]),
    ("impersonation", "We never pose as the founder, a customer or another brand.",
     [r"\bimpersonat\w*\b", r"\bas if (it'?s|it is|it were|they were|i were|we were) (from|by|written by|a)\b",
      r"\b(pretend|pose|posing|act)\b.{0,20}\b(as|to be)\b.{0,30}\b(professor|doctor|teacher|expert|student|celebrity|influencer|journalist|university|harvard|mit)\b"]),
    ("money_movement", "We never hold, move, charge or refund money, and payments stay out of this system.",
     [r"\b(refund|reimburse)\w*\b.{0,30}\b(customers?|users?|buyers?|them|automatically|orders?|their money)\b"]),
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
    ("fake_traction", "We never invent traction: user, customer and sign-up numbers come only from what the app actually counted.",
     [r"(عندنا|لدينا|قول إن|قول ان|اكتب إن|اكتب ان).{0,25}\d+.{0,15}(مستخدم|مشترك|عميل|زبون|طالب|طلاب|تحميل)",
      r"(آلاف|الاف|ألف|الف|مليون).{0,5}(مستخدم|مشترك|عميل|زبون)"]),
    ("income_promise", "We never promise income or guarantee success.",
     [r"(اضمن|ضمان|نضمن|مضمون|اوعد|أوعد|وعد).{0,30}(ينجح|هينجح|هينجحوا|نجاح|درج|علامة|يكسب|هيكسب|امتياز)"]),
    ("credentials", "We never store or ask for passwords or card numbers, and never create accounts.",
     [r"(خد|خذ|اطلب|اجمع|هات).{0,15}(رقم الكارت|رقم الفيزا|بيانات الكارت|الباسورد|كلمة السر)"]),
    ("post_or_send", "The system never posts or sends anything itself: it drafts, you approve, and you post or send it personally.",
     [r"(انشر|ابعت|ارسل|نزل).{0,30}(بدالي|بالنيابة|عني|من حسابي)",
      r"^\s*(انشر|ابعت|ارسل)\s.{0,25}(فيسبوك|فيس بوك|تويتر|انستجرام|انستا|لينكد|واتساب|تيك توك)"]),
    ("impersonation", "We never pose as the founder, a customer or another brand.",
     [r"(اعمل نفسك|عامل نفسك|خلي نفسك|انتحل|اتكلم كأنك|اكتب كأنك).{0,20}(دكتور|استاذ|أستاذ|طالب|خبير|عميل|شركة|مؤسس|بروفيسور)"]),
    # Egyptian colloquial (Masri)
    ("fake_social_proof", "We never write fake reviews, testimonials, ratings or sign-ups.",
     [r"(ريفيوهات|كومنتات|تعليقات|لايكات|فولورز|متابعين).{0,15}(فيك|فيكس|مضروب|مضروبه|مش حقيقي|مش حقيقيه)",
      r"(اعملي|اعملنا|اكتبلنا|ظبطلي|ظبطلنا).{0,15}(ريفيوهات|كومنتات|تقييمات|لايكات)",
      r"(اشتري|اشترى|هات).{0,10}(فولورز|متابعين|لايكات|ريفيوهات)"]),
    ("fake_traction", "We never invent traction: user, customer and sign-up numbers come only from what the app actually counted.",
     [r"(قول|قولهم|اكتب|حط).{0,15}(إن|ان|اننا|إننا).{0,10}(عندنا|معانا).{0,15}\d+"]),
    # Franco-Arabic / Arabizi (2=ء, 3=ع, 5=خ, 7=ح)
    ("fake_social_proof", "We never write fake reviews, testimonials, ratings or sign-ups.",
     [r"\b(e3mel|e3mly|e3mely|ekteb|ektebly|ektbly|zabatly)\b.{0,25}\b(reviews?|ta2yeem\w*|comments?|followers)\b",
      r"\b(reviews?|ta2yeem\w*|comments?|followers)\b.{0,15}\b(fake|wahmy\w*|mazyaf\w*|madroob\w*)\b",
      r"\b5 ?(negoom|nogoom|ngoom|nojoom)\b"]),
    ("fake_traction", "We never invent traction: user, customer and sign-up numbers come only from what the app actually counted.",
     [r"\b(2ol|oul|ekteb)\b.{0,15}\b(3andena|3ndna|ma3ana)\b.{0,10}\d+"]),
    ("income_promise", "We never promise income or guarantee success.",
     [r"\b(edman|madmoon|madmon|nedman)\b.{0,20}\b(rib7|ar?ba7|felos|floos|da5l|naga7)\b"]),
    ("false_urgency", "We never add fake urgency such as countdown timers or invented scarcity.",
     [r"\b3add? tanazoly\b", r"\bfadel \d+ (amaken|ama?kn)\b"]),
]

EXCLUDED_AR: list[tuple[str, str, list[str]]] = [
    ("financial_crypto", "Financial, investment and crypto products are excluded.",
     [r"(كريبتو|بيتكوين|عملات رقمية|عملات مشفرة|توصيات تداول|فوركس|اسهم|أسهم|استثمار)"]),
    ("health_legal_advice", "Health advice and legal advice products are excluded.",
     [r"(تشخيص|يشخص|يشخّص|تشخّص|استشارة طبية|استشارات طبية|نصايح طبية|علاج|روشتة|الأمراض|استشارة قانونية|استشارات قانونية|استشارات قانونيه|محامي|قضايا|طلاق)"]),
    ("physical_goods", "Physical goods are out of scope: this system only builds digital products.",
     [r"(تيشيرتات|ملابس|منتج ملموس|شحن منتجات|دروب شيبنج|جلد|جلود|هاند ?ميد|مشغولات|اكسسوارات|إكسسوارات|شنط)"]),
    ("financial_wallet", "Wallets, payment apps and fintech are excluded: a digital wallet is a financial product and a leather wallet is a physical good.",
     [r"(محفظ[ةه]|محافظ|دفع إلكتروني|دفع الكتروني|تحويل (فلوس|أموال|اموال)|قرض|قروض|بنك|تمويل|تأمين|فلوسك)"]),
]

EXCLUDED_PRODUCT_RULES: list[tuple[str, str, list[str]]] = [
    ("physical_goods", "Physical goods are out of scope: this system only builds digital products.",
     [r"\b(physical (product|goods)|t-?shirts?|merch|hardware device|dropshipping|ship(ping)? boxes|candles|apparel|furniture|food truck|bakery|leather\w*|handmade|handcrafted|jewel(le)?ry|cosmetics|skincare|clothing|sneakers|shoes)\b"]),
    ("financial_crypto", "Financial, investment and crypto products are excluded.",
     [r"\b(crypto\w*|bitcoin|ethereum|nft|token sale|trading (bot|signals?)|forex|stock (picks|tips|signals)|investment advice|day trading|defi|lending app|loans?|altcoins?|meme ?coins?)\b",
      r"\b(which|what) (stocks?|shares|coins?|tokens?) to buy\b|\b(stocks?|shares|coins?|tokens?) to buy\b",
      r"\b(stock|share|coin|token|crypto|options?) (picks|tips|signals|calls)\b|\binvest(ing|ment)? (tips|picks|signals)\b"]),
    ("financial_wallet", "Wallets, payment apps and fintech are excluded: a digital wallet is a financial product and a leather wallet is a physical good.",
     [r"\b(wallets?|e-?wallets?|payments? apps?|fintech|neo-?banks?|banking apps?|money transfers?|remittances?|budget(ing)? (app|tracker)s?|personal finance|expense tracker|portfolio trackers?|investing|investments?|insurance|credit scores?|bnpl|buy now,? pay later)\b"]),
    ("health_legal_advice", "Health advice and legal advice products are excluded.",
     [r"\b(medical diagnos\w*|diagnose (patients|illness|disease)|symptom checker|medical advice|treatment plan|prescri\w*|therap(y|ist) bot|mental health advice|diet plan for (diabetes|disease)|legal advice|lawyer bot|contract review for clients|immigration advice)\b",
      r"\b(divorce|custody|lawsuit|sue|visa) (papers|filings?|cases?|advice|lawyer)\b|\blegal (options|consultations?|counsel)\b|\bwrites? (your|their) (divorce|will|lawsuit|legal)\b",
      r"\b(cure|cures|curing|reverse|reverses|treat|treats|treating) (diabetes|cancer|depression|anxiety|disease|illness|adhd|obesity)\b",
      r"\b(diet|meal|nutrition) plans? (to|that) (cure|treat|reverse)\b|\btherapy (chatbot|bot|app)\b|\b(chatbot|bot|app|ai)\b[^.]{0,30}\b(therapy|counsel\w*)\b[^.]{0,20}\b(depression|anxiety|trauma|ptsd|addiction|eating disorders?)\b|\b(treat|cure|heal)\w* (depression|anxiety|ptsd|addiction)\b|\breplac\w* (a |your )?(therapist|doctor|psychiatrist|psychologist)\b|\bdiagnos\w*\b"]),
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
    joined = re.sub(r"(?<=[A-Za-z])[-._*~](?=[A-Za-z])", "", t)  # cryp-to, b.i.t.c.o.i.n
    if joined != t:
        variants.append(joined)
    despaced = re.sub(r"\b(\w) (?=\w\b)", r"\1", t)
    if despaced != t:
        variants.append(despaced)
    leet = re.sub(r"(?<=[a-z])[013457@](?=[a-z])|(?<=[a-z])[013457@]\b|\b[013457@](?=[a-z])",
                  lambda m: m.group(0).translate(_LEET), t.lower())
    if leet != t.lower():
        variants.append(leet)
    return variants


def _check(text: str, rules: list[tuple[str, str, list[str]]]) -> Verdict:
    from app.arabic import normalize_ar
    variants = normalize(text)
    variants += [normalize_ar(v) for v in variants if normalize_ar(v) != v]  # Arabic spelling variants
    for variant in variants:
        for rule_id, reason, patterns in rules:
            for p in patterns:
                if re.search(p, variant, flags=re.I | re.S) or re.search(_ar_pat(p), variant, flags=re.I | re.S):
                    return Verdict(False, rule_id, reason)
    return Verdict(True)


def _ar_pat(p: str) -> str:
    from app.arabic import normalize_ar
    return normalize_ar(p)


def check_request(text: str) -> Verdict:
    """Founder free-text request or brief field."""
    for rules in (REQUEST_RULES, ARABIC_RULES, EXCLUDED_PRODUCT_RULES, EXCLUDED_AR):
        v = _check(text, rules)
        if not v.allowed:
            return v
    return Verdict(True)


# A founder's value such as "no fake reviews" is a commitment, not a request. A value that only states what the
# founder refuses is not screened; anything else in it (a "but", an instruction verb) is screened as usual.
_REFUSAL_VALUE = re.compile(r"^\s*(no|never|not|zero|avoid\w*|without|refus\w*|لا|بدون|مفيش|عدم|ممنوع)\b", re.I)
_SNEAK = re.compile(r"\b(but|however|except|unless|write|make|generate|create|post|buy|add|give)\b|لكن|بس|اكتب|اعمل|ضيف", re.I)


def check_brief(brief) -> Verdict:
    """Idea, market and skills are screened in full; values that only state a refusal are skipped."""
    values = [v for v in brief.values if not (_REFUSAL_VALUE.search(v) and not _SNEAK.search(v))]
    return check_request(" ".join([brief.idea, brief.target_market, *brief.skills, *values]))


# A product whose purpose is fake reviews, fake urgency or promised income is excluded too, not only the request.
PRODUCT_PURPOSE_RULES = [r for r in REQUEST_RULES + ARABIC_RULES if r[0] == "income_promise"] + [
    ("fake_social_proof", "A product that fakes reviews, ratings, followers or sign-ups is excluded.",
     [r"\b(fake|fabricated|made[- ]up|bought|paid|invented)\s+(\w+[- ]?){0,2}(reviews?|ratings?|testimonials?|followers|sign-?ups|likes)\b",
      r"\bwrit\w*\s+(\d+\s+)?(five|5)[- ]star reviews?\b", r"\b(review|rating)s? farm\b",
      r"\b(buy|sell)\w*\s+(\w+\s+){0,2}(followers|likes|reviews|ratings)\b"])]


def check_product(idea_text: str) -> Verdict:
    for rules in (EXCLUDED_PRODUCT_RULES, EXCLUDED_AR, PRODUCT_PURPOSE_RULES):
        v = _check(idea_text, rules)
        if not v.allowed:
            return v
    return Verdict(True)


INJECTION_IN_SOURCE = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+)?(previous|prior|above|earlier)?\s*(instructions|rules|prompts?)"
    r"|you are (now )?(an? )?(ai|assistant|chatbot)|system prompt|<\s*/?\s*system\s*>|assistant:|###\s*instruction"
    r"|\b(mark|set|rate|score|label|classify)\s+(this|it|the (idea|gate|interview|problem|run))\s+(as\s+)?"
    r"(go|confirmed|strong|approved|5/5|10/10)\b"
    r"|\b(you must|always) (approve|confirm|recommend go|say go)\b"
    r"|تجاهل\s+(كل\s+)?(التعليمات|الأوامر|القواعد)|اعتبر\s+(الفكرة|المشكلة)\s+(مؤكدة|ناجحة)",
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


_SELF_INTRO = re.compile(r"\b(?:I'm|I’m|I am|my name is|this is)\s+([A-Z][a-z]+)\b|^[\s]*[—–-]+\s*([A-Z][a-z]+)\s*$", re.M)
_NOT_NAMES = {"Founder", "Not", "Building", "Researching", "Working", "Looking", "Trying", "A", "An", "The", "Just", "Currently",
              "Here", "So", "Also", "Still", "Really", "Very", "Excited", "Happy", "Glad", "New", "Curious", "Sharing"}


def invented_identity(text: str, signature: str) -> str | None:
    """Returns a name the text introduces or signs with that is not the founder's own."""
    own = {w for w in re.findall(r"[A-Za-z]+", signature)}
    for m in _SELF_INTRO.finditer(text):
        name = m.group(1) or m.group(2)
        if name and name not in own and name not in _NOT_NAMES:
            return name
    return None


def check_output(text: str) -> Verdict:
    """Generated artifact before it may be queued for publishing or sending.
    Disclaimers ("results are not guaranteed") are honest and allowed; promises are not."""
    return _check(NEGATED_GUARANTEE.sub(" ", text), OUTPUT_RULES)


PAYMENT_DETAILS_ASK = re.compile(
    r"\b(transaction|order|payment|receipt|invoice)\s*(id|number|no\.?|reference|details)\b"
    r"|\b(card|bank|iban|cvv|account)\s*(number|details|info)\b|\bcvv\b|\bpassword\b"
    r"|رقم\s*(المعامل[ةه]|العملي[ةه]|الكارت|البطاق[ةه]|الحساب)|كلم[ةه]\s*(السر|المرور)", re.I)
REFUND_PROMISE = re.compile(
    r"\b(i|we)\s*(?:'ll|will|am going to|are going to|can)\s+(?:\w+\s+){0,4}(refund|reimburse)"
    r"|\b(i|we)\s*(?:'ll|will)\s+(?:\w+\s+){0,3}(initiate|process|issue)\b[^.]{0,30}\brefund"
    r"|\byour refund (?:has been|is being|will be) (?:issued|processed|sent)", re.I)


def check_support_reply(text: str) -> Verdict:
    """A support reply the founder may send. On top of check_output: never ask for payment or account details,
    and never promise a refund (the system takes no money; refunds are the founder's own decision)."""
    v = check_output(text)
    if not v.allowed:
        return v
    if PAYMENT_DETAILS_ASK.search(text):
        return Verdict(False, "asks_payment_details", "asks the user for payment, account or password details")
    if REFUND_PROMISE.search(text):
        return Verdict(False, "refund_promise", "promises or claims a refund; refunds are the founder's decision")
    return Verdict(True, None, None)


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
