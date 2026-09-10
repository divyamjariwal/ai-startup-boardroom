"""Deterministic, keyword-based reading of a raw startup idea (Step 4A).

``build_idea_profile`` turns free-text into a structured :class:`IdeaProfile`
using only ordered keyword maps and a handful of regexes. It performs no network
call, no LLM call, no filesystem access, and no randomness: the same input
always yields a byte-identical profile.

Deliberately coarse -- documented limitations:

* Matching is whole-token / hyphen-aware but has no stemming beyond the listed
  plural/hyphen variants, no synonym expansion, and no negation handling
  ("not for students" still matches "students").
* Cross-domain or genuinely novel ideas will frequently land ``industry`` and
  several other fields on their "unspecified" / ``UNKNOWN`` sentinel and list
  them in ``unresolved_fields``. That is the honest output; downstream code must
  treat sentinels neutrally.
* ``problem`` and ``customer_descriptor`` are regex extraction over conventional
  pitch phrasing; unconventional phrasing degrades to "unspecified".
* The keyword maps below are the single source of truth and the intended tuning
  surface. An LLM profiling pass is a possible future upgrade and is *not* part
  of Step 4.
"""

import re
from collections import Counter

from models.reference_class import (
    UNRESOLVED_FIELD_ORDER,
    BusinessModel,
    CustomerType,
    IdeaProfile,
    ProductForm,
    UnresolvedField,
)
from services.verifier import STOP_WORDS

# Hyphen/dot-aware token: keeps "e-learning", "u.s", "b2b", "gpt-4" as one token
# and always begins and ends on an alphanumeric. Distinct from verifier._tokens
# (which is [a-z0-9]+ only) because industry/geo surface forms are hyphenated.
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+\-]*[a-z0-9]|[a-z0-9]")


def tokenize(text: str) -> list[str]:
    """Lowercase, hyphen/dot-aware word tokenisation.

    The shared tokeniser for the reference-class feature: 4A keyword extraction
    and 4B problem-overlap scoring both use it so their notion of a "token"
    stays identical.
    """

    return _TOKEN_RE.findall(text.lower())

# Pitch boilerplate on top of the shared verifier stop-word list. Reused, not
# duplicated: services.verifier.STOP_WORDS is the base.
PITCH_STOP_WORDS: frozenset[str] = frozenset(STOP_WORDS) | {
    "we", "our", "us", "it", "its", "they", "their", "platform", "application",
    "app", "startup", "company", "business", "product", "solution", "solutions",
    "users", "customers", "people", "make", "makes", "help", "helps", "using",
    "use", "used", "based", "via", "also", "new", "provide", "provides",
    "providing", "offering", "offer", "offers", "enable", "enables", "allow",
    "allows", "lets", "let", "build", "building", "create", "creates", "creating",
    "powered", "driven", "first", "best", "world", "leading", "revenue", "model",
}

_KEYWORDS_MAX = 12
_UNIGRAMS_MAX = 10
_BIGRAMS_MAX = 4


def _tok(text: str) -> tuple[str, ...]:
    return tuple(tokenize(text))


def _terms(*raw: str) -> tuple[tuple[str, ...], ...]:
    """Pre-tokenize surface forms so matching is a token-subsequence check."""

    return tuple(_tok(item) for item in raw)


def _occurrences(tokens: list[str], term: tuple[str, ...]) -> list[int]:
    n = len(term)
    if n == 1:
        needle = term[0]
        return [i for i, t in enumerate(tokens) if t == needle]
    return [
        i
        for i in range(len(tokens) - n + 1)
        if tuple(tokens[i : i + n]) == term
    ]


def _present(tokens: list[str], term: tuple[str, ...]) -> bool:
    return bool(_occurrences(tokens, term))


# --------------------------------------------------------------------------- #
# Keyword maps (ordered; order is the tie-break priority).
# --------------------------------------------------------------------------- #
_INDUSTRY_KEYWORDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "edtech": _terms(
        "education", "tutor", "tutoring", "tutors", "learning", "learner",
        "learners", "student", "students", "course", "courses", "curriculum",
        "exam", "exams", "classroom", "teaching", "e-learning", "homework",
    ),
    "fintech": _terms(
        "payment", "payments", "banking", "lending", "loan", "loans", "credit",
        "invoice", "invoicing", "wallet", "remittance", "brokerage", "payroll",
        "accounting", "checkout",
    ),
    "insurtech": _terms(
        "insurance", "insurer", "insurers", "underwriting", "policyholder",
        "actuarial", "premiums",
    ),
    "healthtech": _terms(
        "health", "healthcare", "patient", "patients", "clinical", "clinic",
        "clinics", "medical", "telehealth", "telemedicine", "therapy",
        "wellness", "diagnosis", "ehr",
    ),
    "biotech": _terms(
        "biotech", "biotechnology", "genomic", "genomics", "molecule", "pharma",
        "pharmaceutical", "assay",
    ),
    "ecommerce": _terms(
        "ecommerce", "e-commerce", "retail", "storefront", "checkout", "dtc",
        "merchandise", "catalog",
    ),
    "logistics": _terms(
        "logistics", "shipping", "freight", "delivery", "deliveries", "courier",
        "warehouse", "warehousing", "supply chain", "fulfilment", "fulfillment",
        "last mile", "fleet",
    ),
    "proptech": _terms(
        "real estate", "property", "properties", "rental", "rentals",
        "landlord", "landlords", "tenant", "tenants", "mortgage", "housing",
        "apartment", "apartments",
    ),
    "hrtech": _terms(
        "recruiting", "recruitment", "hiring", "applicant", "applicants",
        "onboarding", "workforce", "hris",
    ),
    "martech": _terms(
        "marketing", "advertising", "campaign", "campaigns", "seo", "crm",
        "email marketing", "marketing automation", "attribution",
    ),
    "devtools": _terms(
        "developer", "developers", "sdk", "api", "devops", "deployment",
        "kubernetes", "observability", "debugging", "compiler",
    ),
    "cybersecurity": _terms(
        "security", "cybersecurity", "vulnerability", "vulnerabilities",
        "malware", "phishing", "encryption", "firewall", "siem",
        "authentication",
    ),
    "data_ai": _terms(
        "machine learning", "artificial intelligence", "dataset", "datasets",
        "llm", "large language model", "analytics", "inference", "embeddings",
    ),
    "agritech": _terms(
        "farm", "farming", "farmer", "farmers", "agriculture", "agricultural",
        "crop", "crops", "livestock", "soil", "irrigation", "agronomy",
    ),
    "climate": _terms(
        "carbon", "emissions", "renewable energy", "solar", "carbon offset",
        "sustainability", "decarbonization", "clean energy",
    ),
    "mobility": _terms(
        "rideshare", "ride hailing", "scooter", "scooters", "transit",
        "parking", "ev charging", "autonomous vehicle",
    ),
    "foodtech": _terms(
        "restaurant", "restaurants", "food delivery", "grocery", "groceries",
        "cloud kitchen", "recipe", "recipes", "meal kit", "dining",
    ),
    "gaming": _terms(
        "game", "games", "gaming", "esports", "gameplay", "multiplayer",
    ),
    "legaltech": _terms(
        "legal", "law firm", "contract review", "litigation", "compliance",
        "paralegal", "legal research",
    ),
    "traveltech": _terms(
        "travel", "trip planning", "hotel", "hotels", "flight booking",
        "itinerary", "tourism",
    ),
    "media": _terms(
        "content creation", "streaming", "video platform", "podcast",
        "podcasts", "publishing", "newsletter", "creator economy",
    ),
    "social": _terms(
        "social network", "online community", "messaging", "group chat",
        "followers", "social feed", "user generated content",
    ),
}

#: Closed vocabulary for IdeaProfile.industry (plus the "unspecified" sentinel).
INDUSTRY_TAGS: tuple[str, ...] = tuple(_INDUSTRY_KEYWORDS) + ("unspecified",)

# Checked in order; first rule with any surface form present wins. Structural
# forms are deliberately checked before the ubiquitous "app".
_PRODUCT_FORM_RULES: tuple[tuple[ProductForm, tuple[tuple[str, ...], ...]], ...] = (
    (
        ProductForm.HARDWARE,
        _terms(
            "device", "devices", "hardware", "wearable", "wearables", "sensor",
            "sensors", "chip", "chips", "robot", "robots", "drone", "drones",
            "physical product",
        ),
    ),
    (ProductForm.API, _terms("api", "sdk", "webhook", "webhooks", "rest api")),
    (
        ProductForm.MARKETPLACE,
        _terms(
            "marketplace", "two sided", "two-sided", "buyers and sellers",
            "matching platform", "gig",
        ),
    ),
    (
        ProductForm.PLATFORM,
        _terms("platform", "operating system", "infrastructure", "ecosystem"),
    ),
    (
        ProductForm.SAAS,
        _terms(
            "saas", "dashboard", "web app", "web-based", "web based",
            "admin panel", "workflow tool", "crm", "erp", "software",
        ),
    ),
    (ProductForm.APP, _terms("app", "mobile app", "mobile", "ios", "android")),
    (
        ProductForm.SERVICE,
        _terms(
            "managed service", "done for you", "done-for-you", "agency",
            "consultancy", "concierge", "we handle", "full service",
        ),
    ),
    (
        ProductForm.CONTENT,
        _terms(
            "content library", "courses", "videos", "streaming", "catalog of",
            "media",
        ),
    ),
)

# Ordered by priority per the spec. SUBSCRIPTION / FREEMIUM interaction has an
# explicit tie rule in _detect_business_model.
_BUSINESS_MODEL_RULES: tuple[tuple[BusinessModel, tuple[tuple[str, ...], ...]], ...] = (
    (
        BusinessModel.SUBSCRIPTION,
        _terms(
            "subscription", "subscriptions", "subscribe", "monthly fee",
            "per month", "annual plan", "recurring revenue", "per seat",
            "monthly subscription", "subscription model",
        ),
    ),
    (
        BusinessModel.FREEMIUM,
        _terms(
            "freemium", "free tier", "free plan", "upgrade to premium",
            "free and paid",
        ),
    ),
    (
        BusinessModel.MARKETPLACE,
        _terms(
            "take rate", "commission", "commissions", "transaction fee",
            "we take a cut", "percentage of each", "marketplace fee",
        ),
    ),
    (
        BusinessModel.TRANSACTIONAL,
        _terms(
            "pay per use", "per transaction", "usage based", "usage-based",
            "pay as you go", "per api call", "metered",
        ),
    ),
    (
        BusinessModel.ADVERTISING,
        _terms(
            "ad supported", "ad-supported", "advertising revenue", "ads",
            "sponsored", "sponsored content",
        ),
    ),
    (
        BusinessModel.LICENSING,
        _terms(
            "license", "licensing", "enterprise license", "white label",
            "white-label", "per deployment",
        ),
    ),
    (
        BusinessModel.HARDWARE,
        _terms(
            "sell the device", "unit price", "hardware sales",
            "one time purchase", "one-time purchase",
        ),
    ),
    (
        BusinessModel.SERVICES,
        _terms(
            "hourly rate", "project fee", "retainer", "professional services",
            "per engagement",
        ),
    ),
)

_FREEMIUM_UPGRADE_TERMS = _terms("premium", "pro", "upgrade")
_FREE_TERM = _tok("free")  # ("free",)

# DEVELOPER and PUBLIC_SECTOR take precedence over the BUSINESS / CONSUMER
# contest.
_CUSTOMER_TYPE_PRIORITY: tuple[tuple[CustomerType, tuple[tuple[str, ...], ...]], ...] = (
    (
        CustomerType.DEVELOPER,
        _terms(
            "developer", "developers", "engineer", "engineers",
            "engineering team", "engineering teams", "devops", "programmer",
            "programmers",
        ),
    ),
    (
        CustomerType.PUBLIC_SECTOR,
        _terms(
            "government", "public sector", "municipal", "municipality",
            "citizens", "ministry", "government agency",
        ),
    ),
)
_CUSTOMER_BUSINESS_TERMS = _terms(
    "business", "businesses", "b2b", "company", "companies", "enterprise",
    "enterprises", "team", "teams", "smb", "smbs", "organization",
    "organizations", "organisation", "organisations", "firm", "firms",
    "employer", "employers",
)
_CUSTOMER_CONSUMER_TERMS = _terms(
    "consumer", "consumers", "b2c", "individuals", "household", "households",
    "family", "families", "student", "students", "patient", "patients",
    "shopper", "shoppers", "traveler", "travelers", "traveller",
)

# Ordered; "Global" is last so a specific region always wins.
_GEO_REGIONS: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = (
    ("United States", _terms("us", "u.s", "usa", "united states", "american", "americans")),
    ("India", _terms("india", "indian", "bharat")),
    ("United Kingdom", _terms("uk", "u.k", "britain", "british", "england", "united kingdom")),
    ("European Union", _terms("eu", "europe", "european")),
    ("Canada", _terms("canada", "canadian")),
    ("Australia", _terms("australia", "australian")),
    ("Southeast Asia", _terms("southeast asia", "indonesia", "vietnam", "philippines", "thailand")),
    ("Africa", _terms("africa", "african", "nigeria", "kenya")),
    ("Latin America", _terms("latam", "latin america", "brazil", "mexico", "colombia")),
    ("Middle East", _terms("middle east", "uae", "saudi arabia", "gcc")),
    ("Global", _terms("global", "worldwide", "international", "any country", "anywhere")),
)

#: Canonical geography labels (the single source of truth for geography values).
#: Downstream normalisation -- e.g. 4C discovery -- must map to one of these so
#: services.similarity.score_similarity compares like with like.
GEO_REGION_LABELS: tuple[str, ...] = tuple(label for label, _ in _GEO_REGIONS)

#: Fallback audience nouns for customer_descriptor when no phrase pattern hits.
AUDIENCE_NOUNS: tuple[str, ...] = (
    "students", "developers", "engineers", "teams", "businesses", "freelancers",
    "founders", "startups", "patients", "doctors", "nurses", "teachers",
    "marketers", "designers", "recruiters", "landlords", "tenants", "shoppers",
    "drivers", "creators", "writers", "accountants", "lawyers", "clinicians",
    "researchers", "retailers", "farmers", "parents", "gamers",
)

_DESCRIPTOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bfor ([a-z][a-z \-]{2,60}?)(?:\.|,| who | to | that | in order| so )"),
    re.compile(r"\bhelps? ([a-z][a-z \-]{2,60}?) (?:to |do |with |manage |find |get )"),
    re.compile(r"\b(?:serving|aimed at|targeting|built for|designed for) ([a-z][a-z \-]{2,60})"),
    re.compile(r"\b([a-z][a-z \-]{2,40}?) who (?:want|need|struggle|have to|can'?t|cannot)\b"),
)
_DESCRIPTOR_TRAILING = {"who", "that", "to", "and", "for", "in", "with", "is", "are"}

_PROBLEM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"problem[:\-\s]+([^.]{10,240})"),
    re.compile(
        r"(?:pain point|biggest challenge|key challenge|struggle)[:\-\s]+([^.]{10,240})"
    ),
    re.compile(
        r"(?:it is|it'?s|its) "
        r"(?:hard|difficult|expensive|slow|tedious|painful|time[- ]consuming) "
        r"to ([^.]{5,180})"
    ),
    re.compile(
        r"(?:today|currently|right now),? ([^.]{10,200}?) "
        r"(?:is broken|is manual|is painful|takes too long|is expensive)"
    ),
    re.compile(r"(?:helps?|lets?|enables?|allows?) [a-z ]{2,40}? (?:to )?([^.]{8,180})"),
)
_PROBLEM_TRAILING = {
    "and", "or", "but", "because", "so", "to", "with", "the", "a", "an", "that",
}


# --------------------------------------------------------------------------- #
# Per-field detectors -- each returns a concrete value or None (=> unresolved).
# --------------------------------------------------------------------------- #
def _detect_industry(tokens: list[str]) -> str | None:
    best: str | None = None
    best_hits = 0
    for tag, terms in _INDUSTRY_KEYWORDS.items():
        hits = sum(1 for term in terms if _occurrences(tokens, term))
        if hits > best_hits:  # strict '>' => earlier tag wins ties
            best, best_hits = tag, hits
    return best if best_hits >= 2 else None


def _detect_product_form(tokens: list[str]) -> ProductForm | None:
    for form, terms in _PRODUCT_FORM_RULES:
        if any(_occurrences(tokens, term) for term in terms):
            return form
    return None


def _detect_business_model(tokens: list[str]) -> BusinessModel | None:
    matched = [
        model
        for model, terms in _BUSINESS_MODEL_RULES
        if any(_occurrences(tokens, term) for term in terms)
    ]
    if not matched:
        return None
    matched_set = set(matched)
    if {BusinessModel.SUBSCRIPTION, BusinessModel.FREEMIUM} <= matched_set:
        has_free = _present(tokens, _FREE_TERM)
        has_upgrade = any(_present(tokens, term) for term in _FREEMIUM_UPGRADE_TERMS)
        return (
            BusinessModel.FREEMIUM
            if (has_free and has_upgrade)
            else BusinessModel.SUBSCRIPTION
        )
    return matched[0]  # _BUSINESS_MODEL_RULES is already in priority order


def _detect_customer_type(tokens: list[str]) -> CustomerType | None:
    for ctype, terms in _CUSTOMER_TYPE_PRIORITY:
        if any(_occurrences(tokens, term) for term in terms):
            return ctype
    biz = [term for term in _CUSTOMER_BUSINESS_TERMS if _occurrences(tokens, term)]
    con = [term for term in _CUSTOMER_CONSUMER_TERMS if _occurrences(tokens, term)]
    if biz and con:
        if len(biz) != len(con):
            return CustomerType.BUSINESS if len(biz) > len(con) else CustomerType.CONSUMER
        biz_first = min(_occurrences(tokens, term)[0] for term in biz)
        con_first = min(_occurrences(tokens, term)[0] for term in con)
        return CustomerType.BUSINESS if biz_first <= con_first else CustomerType.CONSUMER
    if biz:
        return CustomerType.BUSINESS
    if con:
        return CustomerType.CONSUMER
    return None


def _detect_geography(tokens: list[str]) -> str | None:
    for label, terms in _GEO_REGIONS:
        if any(_occurrences(tokens, term) for term in terms):
            return label
    return None


def _clean_descriptor(raw_phrase: str) -> str | None:
    words = raw_phrase.split()
    while words and words[0] in PITCH_STOP_WORDS:
        words.pop(0)
    while words and words[-1] in _DESCRIPTOR_TRAILING:
        words.pop()
    if not words:
        return None
    if not any(w not in PITCH_STOP_WORDS and len(w) >= 3 for w in words):
        return None
    return " ".join(words)[:120]


def _detect_customer_descriptor(lower: str, tokens: list[str]) -> str | None:
    for pattern in _DESCRIPTOR_PATTERNS:
        match = pattern.search(lower)
        if match:
            cleaned = _clean_descriptor(match.group(1))
            if cleaned:
                return cleaned
    best: str | None = None
    best_key: tuple[int, int, int] | None = None
    for idx, noun in enumerate(AUDIENCE_NOUNS):
        occ = _occurrences(tokens, (noun,))
        if occ:
            key = (-len(occ), occ[0], idx)
            if best_key is None or key < best_key:
                best, best_key = noun, key
    return best


def _clean_problem(raw_phrase: str) -> str | None:
    words = " ".join(raw_phrase.split()).split()
    while words and words[-1].strip(",;:") in _PROBLEM_TRAILING:
        words.pop()
    if sum(1 for w in words if w not in PITCH_STOP_WORDS and len(w) >= 3) < 2:
        return None
    return " ".join(words)[:300]


def _detect_problem(lower: str) -> str | None:
    for pattern in _PROBLEM_PATTERNS:
        match = pattern.search(lower)
        if match:
            cleaned = _clean_problem(match.group(1))
            if cleaned:
                return cleaned
    return None


def _keywords(tokens: list[str]) -> list[str]:
    content = [
        (tok, i)
        for i, tok in enumerate(tokens)
        if tok not in PITCH_STOP_WORDS
        and 3 <= len(tok) <= 40  # upper bound keeps keywords within IdeaProfile's field cap
        and not tok.isdigit()
    ]
    if not content:
        return []

    unigram_count: Counter[str] = Counter(tok for tok, _ in content)
    unigram_first: dict[str, int] = {}
    for tok, i in content:
        unigram_first.setdefault(tok, i)
    unigrams = sorted(
        unigram_count, key=lambda t: (-unigram_count[t], unigram_first[t])
    )[:_UNIGRAMS_MAX]
    unigram_set = set(unigrams)

    # Bigrams: two content tokens ADJACENT IN THE ORIGINAL STREAM (pos+1), never
    # merely adjacent after stop-word removal.
    bigram_count: Counter[str] = Counter()
    bigram_first: dict[str, int] = {}
    for (tok_a, pos_a), (tok_b, pos_b) in zip(content, content[1:]):
        if pos_b == pos_a + 1:
            phrase = f"{tok_a} {tok_b}"
            if len(phrase) > 40:  # stay within IdeaProfile's keyword field cap
                continue
            bigram_count[phrase] += 1
            bigram_first.setdefault(phrase, pos_a)
    bigrams: list[str] = []
    for phrase in sorted(
        bigram_count, key=lambda p: (-bigram_count[p], bigram_first[p])
    ):
        first, second = phrase.split(" ")
        if first not in unigram_set or second not in unigram_set:
            bigrams.append(phrase)
        if len(bigrams) == _BIGRAMS_MAX:
            break

    merged = {u: unigram_first[u] for u in unigrams}
    merged.update({b: bigram_first[b] for b in bigrams})
    ordered = sorted(merged, key=lambda k: merged[k])
    return ordered[:_KEYWORDS_MAX]


def build_idea_profile(idea_text: str) -> IdeaProfile:
    """Derive a coarse structured :class:`IdeaProfile` from raw idea text.

    Deterministic and side-effect free. Raises ``ValueError`` on empty input.
    """

    if not idea_text or not idea_text.strip():
        raise ValueError("idea_text must be a non-empty string")

    lower = idea_text.lower()
    tokens = list(_TOKEN_RE.findall(lower))
    unresolved: set[UnresolvedField] = set()

    industry = _detect_industry(tokens)
    if industry is None:
        industry = "unspecified"
        unresolved.add(UnresolvedField.INDUSTRY)

    product_form = _detect_product_form(tokens)
    if product_form is None:
        product_form = ProductForm.UNKNOWN
        unresolved.add(UnresolvedField.PRODUCT_FORM)

    business_model = _detect_business_model(tokens)
    if business_model is None:
        business_model = BusinessModel.UNKNOWN
        unresolved.add(UnresolvedField.BUSINESS_MODEL)

    customer_type = _detect_customer_type(tokens)
    if customer_type is None:
        customer_type = CustomerType.UNKNOWN
        unresolved.add(UnresolvedField.CUSTOMER_TYPE)

    customer_descriptor = _detect_customer_descriptor(lower, tokens)
    if customer_descriptor is None:
        customer_descriptor = "unspecified"
        unresolved.add(UnresolvedField.CUSTOMER_DESCRIPTOR)

    problem = _detect_problem(lower)
    if problem is None:
        problem = "unspecified"
        unresolved.add(UnresolvedField.PROBLEM)

    geography = _detect_geography(tokens)
    if geography is None:
        geography = "unspecified"
        unresolved.add(UnresolvedField.GEOGRAPHY)

    return IdeaProfile(
        raw_text=idea_text[:10_000],
        customer_type=customer_type,
        customer_descriptor=customer_descriptor,
        problem=problem,
        product_form=product_form,
        business_model=business_model,
        industry=industry,
        geography=geography,
        keywords=_keywords(tokens),
        unresolved_fields=[f for f in UNRESOLVED_FIELD_ORDER if f in unresolved],
    )
