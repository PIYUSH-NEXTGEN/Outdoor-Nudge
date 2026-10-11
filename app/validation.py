"""Validation, safety rules, and category selection for Outdoor Nudge."""
import random
import re

from .history import load_history
from .prompts import (TASK_CATEGORIES, LOW_ENERGY_CATS, HIGH_ENERGY_CATS,
                     MEDIUM_ENERGY_CATS)

STOPWORDS = {"a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "at", "with",
             "your", "you", "my", "20-minute", "20", "minute", "minutes", "outdoor", "outside"}


def first_verb(title: str) -> str:
    words = re.findall(r"[a-zA-Z']+", (title or "").lower())
    for w in words:
        if w not in STOPWORDS and len(w) > 2:
            return w
    return ""


def banned_verbs(exclude: list) -> set:
    verbs = set()
    for t in exclude or []:
        v = first_verb(t)
        if v:
            verbs.add(v)
    return verbs


HIGH_ENERGY_MARKERS = ("excit", "energy", "restless", "angry", "anger", "happy", "hyper",
                       "pumped", "furious", "procrastinat")


LOW_ENERGY_MARKERS = ("burned out", "burnout", "cranky", "numb", "anxious", "exam", "lonely",
                      "sleep", "tired", "exhaust", "sad", "low", "bored", "rainy", "calm")


def energy_pool(mood: str, easier: bool) -> tuple[str, list]:
    """Return (forced_energy_or_empty, category pool)."""
    mood_l = (mood or "").lower()
    if easier:
        return "low", LOW_ENERGY_CATS
    if any(k in mood_l for k in HIGH_ENERGY_MARKERS):
        # procrastinating -> medium (needs activation but not a sprint)
        if "procrastinat" in mood_l:
            return "medium", MEDIUM_ENERGY_CATS
        return "high", HIGH_ENERGY_CATS
    if any(k in mood_l for k in LOW_ENERGY_MARKERS):
        return "low", LOW_ENERGY_CATS
    return "", MEDIUM_ENERGY_CATS


CATEGORY_CAP = 2


def cap_categories(pool: list, hist: list | None = None) -> list:
    """Drop categories already used CATEGORY_CAP times in the last 10 requests
    (least-recently-used weighting then picks among what remains). If that would
    empty the pool, fall back to the least-used candidates so a pick is always possible."""
    if not pool:
        return pool
    if hist is None:
        hist = load_history()
    recent = [h.get("category", "") for h in hist[-10:]]
    counts: dict[str, int] = {}
    for c in recent:
        if c:
            counts[c] = counts.get(c, 0) + 1
    eligible = [c for c in pool if counts.get(c, 0) < CATEGORY_CAP]
    if not eligible:
        least = min(counts.get(c, 0) for c in pool)
        eligible = [c for c in pool if counts.get(c, 0) == least]
    return eligible


def pick_category(mood: str, easier: bool, exclude: list) -> tuple[str, str]:
    forced, pool = energy_pool(mood, easier)
    pool = list(pool) or list(MEDIUM_ENERGY_CATS)
    try:
        hist = load_history()
        pool = cap_categories(pool, hist)
        # least-recently-used weighting: categories unused for longer get higher weight
        last_used: dict[str, int] = {}
        for i, h in enumerate(hist):
            c = h.get("category", "")
            if c:
                last_used[c] = i
        now_idx = len(hist)
        weights = []
        for c in pool:
            age = now_idx - last_used.get(c, -len(pool))
            weights.append(1 + max(0, age))
        category = random.choices(pool, weights=weights, k=1)[0]
    except Exception:
        category = random.choice(pool)
    return category, forced


HIGH_ACTIVITY_WORDS = ("sprint", " brisk", " briskly", "run", "climb", "stairs", "chase",
                       "hop", "skip", "sweep", "race", "dash", "march", "power-walk", "power walk")


LOW_ACTIVITY_WORDS = ("sit", "sitting", "stand still", "lie ", "lying", "nap", "stare",
                      "watch ", "gaze", "listen quietly")


HIGH_ENERGY_SET = {"movement", "balance-play", "small-scavenger-hunt", "tidy-up-litter-pick"}


MEDIUM_OK_CATS = set(TASK_CATEGORIES.keys()) - {"observation", "sound-listening", "sketch-write-outdoors", "taste-smell"}


VENUE_BAN = (
    (r"\bmarkets?\b", "market"),
    (r"\bcoffee\s+carts?\b", "coffee cart"),
    (r"\bcaf[e\u00e9]s?\b", "cafe"),
    (r"\bcoffee\s+shops?\b", "coffee shop"),
    (r"\bbaker(?:y|ies)\b", "bakery"),
    (r"\brestaurants?\b", "restaurant"),
    (r"\bbars?\b", "bar"),
    (r"\bpubs?\b", "pub"),
    (r"\bstores?\b", "store"),
    (r"\bshops?\b", "shop"),
    (r"\bsupermarkets?\b", "supermarket"),
    (r"\bgrocer(?:y|ies)\b", "grocery"),
    (r"\bcourthouses?\b", "courthouse"),
    (r"\bcity\s+halls?\b", "city hall"),
    (r"\bpark(?!\s*(?:yourself|it\b|them\b|your\b))s?\b", "park"),
    (r"\bplaygrounds?\b", "playground"),
    (r"\bmalls?\b", "mall"),
    (r"\bshopping\s+cent(?:er|re)s?\b", "shopping centre"),
    (r"\blibrar(?:y|ies)\b", "library"),
    (r"\bmuseums?\b", "museum"),
    (r"\bgaller(?:y|ies)\b", "gallery"),
    (r"\bcinemas?\b", "cinema"),
    (r"\btheat(?:er|re)s?\b", "theater"),
    (r"\bstadiums?\b", "stadium"),
    (r"\barenas?\b", "arena"),
    (r"\bgyms?\b", "gym"),
    (r"\bzoos?\b", "zoo"),
    (r"\bcourts?\b", "court"),
    (r"\brivers?\b", "river"),
    (r"\briverside\b", "riverside"),
    (r"\blakes?\b", "lake"),
    (r"\blakeside\b", "lakeside"),
    (r"\bponds?\b", "pond"),
    (r"\bcreeks?\b", "creek"),
    (r"\bstreams?\b", "stream"),
    (r"\bbeach(?:es)?\b", "beach"),
    (r"\bseaside\b", "seaside"),
    (r"\bseas?\b", "sea"),
    (r"\boceans?\b", "ocean"),
    (r"\bcanals?\b", "canal"),
    (r"\bshores?\b", "shore"),
    (r"\bharbours?\b|\bharbors?\b", "harbor"),
    (r"\bpiers?\b", "pier"),
    (r"\bmarinas?\b", "marina"),
    (r"\bwaterfalls?\b", "waterfall"),
    (r"\bcafeterias?\b", "cafeteria"),
    (r"\bfood\s+courts?\b", "food court"),
)


LONELY_MOOD_RE = re.compile(
    r"\blonely\b|\bloneliness\b|\bisolated\b|\bisolation\b|\balone\b", re.IGNORECASE)


CONTACT_RE = re.compile(
    r"\bwav(?:e|es|ed|ing)\b|\bsmil(?:e|es|ed|ing)\b|\bgreet\w*|\bhello\b|\bhi\b|"
    r"good morning|neighbou?r\w*|\bstrangers?\b|someone|somebody|\bpeople\b|\bperson\b|"
    r"passers?-?by|\bpasserby\b|pedestrian\w*|\bnod(?:s|ded|ding)?\b|chat\w*|"
    r"eye contact|\bhumans?\b|\bothers\b|say (?:hi|hello|good morning)|"
    r"\bcouple\w*|\bfamil\w*|\bwhoever\b|\banyone\b|\bdog walk\w*|\bjoggers?\b|"
    r"\brunners?\b|\bkids?\b|\bchildren\b|\bchild\b|\bparents?\b|\blocals?\b",
    re.IGNORECASE,
)


NEG_WORDS = {"never", "not", "no", "don't", "dont", "doesn't", "doesnt", "avoid", "without",
             "skip", "refrain", "instead", "away", "kicked", "stop"}


def _negated(text: str, pos: int) -> bool:
    """True when the match at pos is preceded by a negation in the last few words
    ("never touch the flowers" is a warning, not an instruction)."""
    words = re.findall(r"[a-zA-Z']+", text[max(0, pos - 45):pos])
    return any(w.lower() in NEG_WORDS for w in words[-4:])


INGEST_BAN = (
    (r"\btast(?:e|es|ed|ing)\b", "safety-no-tasting"),
    (r"\beat(?:s|en|ing)?\b", "safety-no-eating"),
    (r"\blick(?:s|ed|ing)?\b", "safety-no-licking"),
    (r"\bbite(?:s|ing)?\b|\bbitten\b", "safety-no-biting"),
    (r"\bchew(?:s|ed|ing)?\b", "safety-no-chewing"),
    (r"\bswallows?\b|\bswallowing\b", "safety-no-swallowing"),
    (r"\bnibbles?\b|\bnibbling\b", "safety-no-nibbling"),
    (r"\bmunch(?:es|ed|ing)?\b", "safety-no-munching"),
    (r"\bforag(?:e|es|ed|ing)\b", "safety-no-foraging"),
    (r"\bedible\b", "safety-no-found-food"),
)


HAND_VERBS = (r"touch(?:es|ed|ing)?|picks?|picking|plucks?|plucking|grabs?|grabbing|"
              r"gathers?|gathered|collect(?:s|ed|ing)?|holds?|holding|rub(?:s|bed|bing)?|"
              r"feels?|feeling|handles?|handling|dig(?:s|ged|ging)?")


NATURE_OBJECTS = (r"plants?|flowers?|petals?|leaves?|leaf|berr(?:y|ies)|mushrooms?|grass|"
                  r"barks?|herbs?|twigs?|acorns?|moss")


LITTER_OBJECTS = (r"litter|trash|rubbish|debris|wrappers?|cigarette\w*|needles?|"
                  r"bottles?|cans?|nappies|diapers")


NATURE_HAND_RE = re.compile(rf"\b(?:{HAND_VERBS})\b[^.!?]{{0,45}}\b(?:{NATURE_OBJECTS})\b", re.I)


LITTER_HAND_RE = re.compile(rf"\b(?:{HAND_VERBS})\b[^.!?]{{0,45}}\b(?:{LITTER_OBJECTS})\b", re.I)


SHARP_LITTER_RE = re.compile(rf"\b(?:{HAND_VERBS})\b[^.!?]{{0,45}}\b(?:sharp|broken|needles?|wet)\b", re.I)


GLOVE_RE = re.compile(r"\bgloves?\b|\bbags?\s+as\s+a\s+glove\b|\bbag\s+over\s+your\s+hand|"
                      r"\bag[-\s]glove\b|\buse\s+(?:a|the|an|one)\s+bag\b", re.I)


SMELL_OBJ_RE = re.compile(r"\b(?:smell|sniffs?|sniffing|inhales?|inhaling|whiffs?|whiffing)\b"
                          r"[^.!?]{0,45}\b(?:flowers?|petals?|plants?|mushrooms?|litter|"
                          r"leaves?|berr(?:y|ies)|grass|trash)\b", re.I)


CLIMB_RE = re.compile(r"\bclimb(?:s|ed|ing)?\b|\bscal(?:e|es|ed|ing)\b|\bpull[- ]?ups?\b|"
                      r"\bmonkey bars?\b", re.I)


FURNITURE = (r"bench(?:es)?|chairs?|tables?|railing|railings|rails?|fences?|walls?|lamp\s?posts?|"
             r"bike\s?racks?|ledges?|curbs?|kerbs?|street\s?furniture|playgrounds?")


FURNITURE_RE = re.compile(
    rf"\b(?:balanc\w+|hop\w*|perch\w*|climb\w*)\b[^.!?]{{0,55}}\b(?:{FURNITURE})\b"
    rf"|\b(?:stand|stands|standing|sit|sits|sitting)\s+(?:on|upon)\s+(?:a\s+|the\s+|any\s+)?(?:{FURNITURE})\b",
    re.I)


ROAD_RE = re.compile(
    r"\b(?:highways?|motorways?|crosswalks?|jaywalk\w*|zebra crossings?)\b"
    r"|\b(?:walk\w*|stroll\w*|wander\w*|run\w*|march\w*|dash\w*|head|go(?:es|ing)?|cross\w*|"
    r"move\w*|step\w*|skips?|sprints?|cycling|cycle\w*|drive\w*|dodge|swerve|weave)\s+"
    r"(?:down|along|across|onto|into|over|to|near|toward|towards|past)\s+the\s+"
    r"(?:road|street|traffic|highway|motorway)\b"
    r"|\b(?:curb|curbs|curbside|kerb|kerbs|kerbside)\b",
    re.I)


WATER_RE = re.compile(
    r"\b(?:rivers?|lakes?|ponds?|creeks?|streams?|beach(?:es)?|seas?|oceans?|canals?|shores?|"
    r"harbou?rs?|piers?|marinas?|waterfalls?|puddles?|fountains?|swim\w*|wading|wade)\b"
    r"|\b(?:enter|step|jump|wade|dip|run|walk)\w*\s+(?:into|in|to)\s+(?:the\s+)?water\b"
    r"|\b(?:toes|feet)\s+in\s+(?:the\s+)?water\b",
    re.I)


OBJECT_BAN = (
    (r"\bbench(?:es)?\b", "bench"),
    (r"\bbins?\b", "bin"),
    (r"\bbike\s+racks?\b", "bike rack"),
    (r"\blamp\s?posts?\b|\blampposts?\b", "lamp post"),
    (r"\bbags?\b", "bag"),
    (r"\bpapers?\b", "paper"),
    (r"\bnotebooks?\b", "notebook"),
)


BAG_GLOVE_MASK = re.compile(r"\bbags?\s+as\s+a\s+glove\b|\bbag\s+over\s+your\s+hand\b|"
                            r"\buse\s+(?:a|the|an|one)\s+bag\b|\bag[-\s]glove\b|\bag\s+to\s+pick\b",
                            re.I)


NIGHT_ANCHOR_RE = re.compile(r"\b(?:doors?|doorstep|door step|stoop|threshold|porch|balcony|"
                             r"windows?|front steps?|entrance|gate|home)\b", re.I)


NIGHT_AWAY_MASK = re.compile(r"\b(?:to|toward|towards|back to|onto|at)\s+(?:the\s+|your\s+)?"
                             r"(?:front\s+)?(?:doors?|doorstep|stoop|threshold|porch|balcony|"
                             r"windows?|steps)\b", re.I)


NIGHT_AWAY_RE = re.compile(
    r"\b(?:walk|stroll\w*|wander\w*|run\w*|march\w*|head|go(?:es|ing)?|venture|roam\w*|drive|cycle)"
    r"\s+(?:out\s+)?(?:down|along|around|away|to|toward|towards|past|through|into|across|for a|far)\b"
    r"|\baway from (?:home|your door|the house)\b"
    r"|\baround the (?:block|neighbourhood|neighborhood)\b"
    r"|\b\d+\s*(?:m|meters?|metres?|minutes?|km)\s+(?:away|walk|from)\b"
    r"|\bto the (?:end|corner|store|shop|park)\b",
    re.I)


NIGHT_INTERACT_VERBS_RE = re.compile(
    r"\b(?:greet\w*|wave\w*|smile\w*|nod(?:s|ded|ding)?|chat\w*|talk\w*|"
    r"say\s+(?:hi|hello|hey|good (?:morning|evening))|ask\w*)\b", re.I)


NIGHT_HUMAN_RE = re.compile(r"\b(?:strangers?|passers?-?by|passersby|passerby|people|someone|"
                            r"somebody|person|pedestrian\w*|locals?|joggers?|walkers?|"
                            r"crowd|neighbou?r\w*)\b", re.I)


NEIGHBOUR_RE = re.compile(r"neighbou?r\w*", re.I)


# --- lonely-contact quality rules -----------------------------------------
# A "real person" a lonely task may connect with (nouns only, not verbs).
PERSON_TARGET_RE = re.compile(
    r"neighbou?r\w*|passers?-?by|passerby|friend\w*|famil\w*|someone|somebody|"
    r"people|persons?|pedestrian\w*|joggers?|runners?|dog[- ]?walk\w*|"
    r"locals?|kids?|children|child|parents?|strangers?|whoever|anyone|"
    r"partner|flatmates?|roommates?|colleagues?|coworkers?|mum|mom|dad|"
    r"sister|brother|cousin\w*|grandparent\w*|a face|new face|"
    r"another (?:person|human|soul|neighbou?r)|a real person", re.I)

# Gesture verbs whose target must be a real person (never an object).
CONTACT_VERB_RE = re.compile(
    r"\b(?:wave|waves|waved|waving|smile|smiles|smiled|smiling|"
    r"greet|greets|greeted|greeting|nod|nods|nodded|nodding)\b", re.I)

# Any act that actually reaches out to a person (gesture OR remote contact).
# A bare person-word (e.g. "your neighbor's garden") is NOT contact, so the
# day-lonely rule keys off this, not off PERSON_TARGET_RE alone.
CONTACT_ACT_RE = re.compile(
    r"\b(?:wave|waves|waved|waving|smile|smiles|smiled|smiling|"
    r"greet|greets|greeted|greeting|nod|nods|nodded|nodding|"
    r"chat|chats|chatted|chatting|talk|talks|talking|"
    r"say\s+(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|something|"
    r"good ?morning)|hello|\bhi\b|compliment|ask|asks|asking|"
    r"call|calls|calling|ring|rings|phone|phoning|dial|"
    r"text|texts|texting|message|messages|messaging|send|sends|sending|"
    r"voice ?note|leave a (?:message|note)|check in)\b", re.I)

# Things a contact gesture must NEVER be aimed at (not people).
NONPERSON_TARGET_RE = re.compile(
    r"shadows?|street ?lights?|streetlight|lamplights?|lamplight|lights?|"
    r"buildings?|clouds?|moon|stars?|trees?|plants?|flowers?|signs?|windows?|"
    r"doors?|walls?|sk(?:y|ies)|the air|ground|pavement|reflections?|statues?|"
    r"monuments?|cars?|birds?|squirrels?|traffic|your reflection", re.I)

# Night lonely: the ONLY safe contacts (message/voice note/call, or a quiet
# wave at a lit window / a neighbour at their door). No strangers required.
NIGHT_LONELY_CONTACT_RE = re.compile(
    r"\b(?:send|text|texts|texting|leave|drop|write)\b[^.!?]{0,35}"
    r"\b(?:message|text|voice ?note|voicemail|note)\b"
    r"|\b(?:voice ?note|voice message|voice memo|voicemail)\b"
    r"|\b(?:call|calls|calling|ring|rings|phone|phoning|dial|facetime|video[- ]?call)\b"
    r"[^.!?]{0,35}\b(?:a |your |one |some |a close )?"
    r"(?:friend|neighbou?r|someone|somebody|family|relative|parent|sibling|"
    r"sister|brother|partner|person|love ?one|loved ?one)\b"
    r"|\b(?:call|ring|phone|dial)\b[^.!?]{0,20}\b(?:them|him|her|up)\b"
    r"|\bwave\b[^.!?]{0,35}\b(?:lit|lighted|glowing|warm)\b[^.!?]{0,10}\bwindows?\b"
    r"|\bwave\b[^.!?]{0,35}\bneighbou?r\b", re.I)

# A solid night anchor that does NOT assume a balcony exists.
NIGHT_SOLID_ANCHOR_RE = re.compile(
    r"\b(?:doors?|doorstep|door step|stoop|threshold|porch|windows?|front steps?|"
    r"entrance|gate|home|your step|front door|doorway)\b", re.I)

# Loud / vigorous movement that must NOT appear in a night task.
NIGHT_LOUD_MOVE_RE = re.compile(
    r"jumping jacks?|star jumps?|burpees?|shadow[- ]?box\w*|sprint\w*|jog\w*|"
    r"\brunning?\b|\bmarch\w*|\bpower[- ]?walk\w*|\bskip(?:s|ping|ped)?\b|"
    r"\bhop(?:s|ping|ped)?\b|\bjumping\b|\bjumps?\b|\bbounc\w*|"
    r"jump\w* up and down|high knees|squat jumps?|tuck jumps?|plyometric\w*|\bkip\b|"
    r"\bbrisk(?:ly)?\b|\bdash\w*|\brace\w*|\bchase\w*|\bdodge\w*", re.I)

# Invented, non-universal scavenger items that must not appear in a hunt.
SCAVENGER_INVENTED_BAN = (
    (r"\bred doors?\b", "scavenger-red-door"),
    (r"\bcrooked signs?\b", "scavenger-crooked-sign"),
    (r"\bfeathers?\b", "scavenger-feather"),
    (r"\buneven(?:ness)?\b", "scavenger-unevenness"),
)

# Purely-mental activities that are not real outdoor doing (esp. sketch/write).
IN_HEAD_BAN = (
    (r"\bin your head\b", "sketch-in-your-head"),
    (r"\bin your mind\b", "sketch-in-your-head"),
    (r"\bin your imagination\b", "sketch-in-your-head"),
    (r"\bpurely in your\b", "sketch-in-your-head"),
    (r"\bonly in your head\b", "sketch-in-your-head"),
)

# A ~20-minute mission must not be shrunk to a few seconds as its total (e.g.
# "10 seconds apart", "for 5 seconds"). Per-item pacing like "30 seconds each"
# or "5 seconds to observe" is fine and NOT matched here.
SHORT_DURATION_RE = re.compile(
    r"\b\d{1,3}\s*seconds?\s+apart\b"
    r"|\b(?:for|in|within|over|lasts?|lasting|last|totaling|totalling|altogether)\s+"
    r"(?:just\s+|only\s+|about\s+)?\d{1,3}\s*seconds?\b", re.I)


def _contact_targets_person(m: re.Match, low: str) -> bool:
    """True when the contact gesture at match m is aimed at a real person.
    A gesture is bad when the words right after it name an object (shadow,
    light, building...) and no person."""
    target = low[m.end():m.end() + 45]
    if NONPERSON_TARGET_RE.search(target) and not PERSON_TARGET_RE.search(target):
        return False
    return True


WALK_ONLY_RE = re.compile(r"\b(?:go(?:ing)? for a (?:walk|stroll|wander)|take a (?:walk|stroll|wander)|"
                          r"head(?:ing)? out for a (?:walk|stroll)|go walking|walk around|stroll around|"
                          r"wander around|wander aimlessly|stretch your legs|get some fresh air|"
                          r"walk the block)\b", re.I)


WALK_GOAL_RE = re.compile(r"\b(?:find|finds|finding|spot|spots|spotting|count|counting|locate|locating|"
                          r"identify|trace|tracing|track|tracking|watch for|listen for|notice|observing|"
                          r"observe|search|hunt|sketch|draw|photograph|photo|map)\b", re.I)


ORDINARY_BAN = (
    (r"\bsip(?:s|ped|ping)?\b|\btake a (?:sip|swig|drink|gulp)\b|\bhave a (?:sip|drink)\b|"
     r"\bdrink\w*\s+(?:of\s+)?(?:some\s+|a\s+|the\s+|your\s+)*water\b|\bhydrat\w+\b|"
     r"\bwater break\b|\bdrink of water\b", "ordinary-sipping-drink"),
    (r"\b(?:go|walk|head|run|tip|pop)\s+(?:to|into)\s+(?:a|the|any|your)?\s*bin\b|"
     r"\bdeposit (?:it|them)?\s*in (?:a|the|any) bin\b|"
     r"\b(?:take|put|throw|empty|dump|carry)\w*\s+(?:out\s+)?(?:the\s+|your\s+)?"
     r"(?:trash|rubbish|bin|recycling|garbage)\b|\buse the bin\b", "ordinary-bin-chore"),
    (r"\b(?:brush|brushing) your (?:teeth|hair)\b|\bwash (?:your )?(?:face|hands|hair|dishes)\b|"
     r"\bmake your bed\b|\bget dressed\b|\bcheck your (?:notifications?|emails?|messages?|feed)\b|"
     r"\bscroll (?:through|down|social)\b|\bgo to (?:the )?(?:toilet|bathroom|loo|shower)\b|"
     r"\b(?:take|have) a shower\b|\bread your (?:emails?|messages?)\b", "ordinary-daily-activity"),
)


NIGHT_MOOD_RE = re.compile(r"\b(?:night|midnight|after dark)\b|\d{1,2}\s?pm\b|\d{1,2}\s?am\b|"
                           r"can['\u2019]?t\s+sleep|cannot\s+sleep|can\s+not\s+sleep|insomnia",
                           re.IGNORECASE)


def is_night_request(pod: str, hour: int, mood: str) -> bool:
    """Night safety rules apply when it is actually night, late evening (21:00+),
    or the mood text itself says it is night (e.g. "11pm can't sleep")."""
    return pod == "night" or hour >= 21 or bool(NIGHT_MOOD_RE.search(mood or ""))


def safety_violations(title_task: str, category: str = "", mood_l: str = "",
                      night: bool = False) -> list[str]:
    """Hard safety/realism checks on 'title + task'. Returns ALL failing reasons
    ([] means the text passes). Mood text exempts only assumed-object words."""
    out: list[str] = []
    low = (title_task or "").lower()
    mood_l = (mood_l or "").lower()

    def first_unnegated(pattern: re.Pattern, text: str = ""):
        target = text or low
        for m in pattern.finditer(target):
            if not _negated(target, m.start()):
                return m
        return None

    # 1. no eating / tasting / licking found things
    for pat, label in INGEST_BAN:
        if first_unnegated(re.compile(pat, re.I)):
            out.append(label)
    # smell-only: never smell flowers / picked things
    if first_unnegated(SMELL_OBJ_RE):
        out.append("safety-smell-not-taste-list")
    # bare-hand contact (gloves make contact OK; negated warnings are OK)
    glove_ok = bool(GLOVE_RE.search(low))
    if not glove_ok and first_unnegated(NATURE_HAND_RE):
        out.append("safety-no-bare-hands-on-plants")
    if not glove_ok and first_unnegated(LITTER_HAND_RE):
        out.append("safety-litter-needs-gloves")
    if category == "tidy-up-litter-pick" and not glove_ok:
        out.append("litter-needs-gloves")
    if (category == "tidy-up-litter-pick" or re.search(rf"\b(?:{LITTER_OBJECTS})\b", low)) \
            and first_unnegated(SHARP_LITTER_RE):
        out.append("safety-leave-sharp-wet-litter")
    # no climbing / furniture balance / roads / water
    if first_unnegated(CLIMB_RE):
        out.append("safety-no-climbing")
    furn_m = first_unnegated(FURNITURE_RE)
    if furn_m:
        seg = furn_m.group(0)
        if re.match(r"(?i)\s*(?:sit|sits|sitting|stand|stands|standing)\b", seg):
            # simply sitting/standing on furniture: OK only if the mood names that object
            obj_m = re.search(FURNITURE, seg, re.IGNORECASE)
            word = (obj_m.group(0) if obj_m else "").lower().rstrip("s")
            if not (word and word in mood_l):
                out.append("safety-no-furniture-balance")
        else:
            out.append("safety-no-furniture-balance")
    if first_unnegated(ROAD_RE):
        out.append("safety-no-roads")
    if first_unnegated(WATER_RE):
        out.append("safety-no-water")
    # assumed objects (mood may name them; "bag as a glove" phrases are exempt)
    scan = BAG_GLOVE_MASK.sub(" ", low)
    for pat, label in OBJECT_BAN:
        if re.search(pat, scan) and not re.search(pat, mood_l):
            out.append(f"object-ban:{label}")
    # night: anchor at own door/window (never assume a balcony), no walking away,
    # no stranger contact, and movement must be quiet
    if night:
        if not NIGHT_ANCHOR_RE.search(low):
            out.append("night-needs-door-anchor")
        elif not NIGHT_SOLID_ANCHOR_RE.search(low):
            # anchored only on something like a balcony -> assumes one exists
            out.append("night-assumes-balcony")
        away = NIGHT_AWAY_MASK.sub(" ", low)
        if first_unnegated(NIGHT_AWAY_RE, away):
            out.append("night-no-walking-away")
        if first_unnegated(NIGHT_LOUD_MOVE_RE):
            out.append("night-loud-movement")
        for m in NIGHT_INTERACT_VERBS_RE.finditer(low):
            if _negated(low, m.start()):
                continue
            tail = low[m.end():m.end() + 45]
            if NEIGHBOUR_RE.search(tail):
                continue
            verb = m.group(0).lower()
            intrinsic_human = verb.startswith(("greet", "chat", "talk", "ask", "say"))
            if NIGHT_HUMAN_RE.search(tail) or intrinsic_human:
                out.append("night-no-stranger-contact")
                break
        for m in re.finditer(r"\b(?:strangers?|passers?-?by|passersby)\b", low):
            if not _negated(low, m.start()):
                out.append("night-no-stranger-contact")
                break
    # lonely mood: contact must be with a REAL PERSON, never an object
    if LONELY_MOOD_RE.search(mood_l):
        if night:
            # night lonely: only message/voice note/call, or a quiet wave at a
            # lit window / a neighbour at their door - never a stranger errand
            if not NIGHT_LONELY_CONTACT_RE.search(low):
                out.append("lonely-night-needs-safe-contact")
        else:
            if not CONTACT_ACT_RE.search(low):
                out.append("lonely-needs-human-contact")
            # any wave/smile/greet must target a person, not an object
            for m in CONTACT_VERB_RE.finditer(low):
                if _negated(low, m.start()):
                    continue
                if not _contact_targets_person(m, low):
                    out.append("lonely-contact-not-a-person")
                    break
    # scavenger hunts: items must be universal, never invented specifics
    for pat, label in SCAVENGER_INVENTED_BAN:
        if first_unnegated(re.compile(pat, re.I)):
            out.append(label)
    # "sketch/write it in your head" is not a real outdoor activity
    for pat, label in IN_HEAD_BAN:
        if first_unnegated(re.compile(pat, re.I)):
            out.append(label)
    # a ~20-minute mission shrunk to a few seconds is trivial, not a real task
    if first_unnegated(SHORT_DURATION_RE):
        out.append("too-short-duration")
    # generic bare walk needs a specific odd goal
    if first_unnegated(WALK_ONLY_RE) and not WALK_GOAL_RE.search(low):
        out.append("generic-walk")
    # ordinary daily acts
    for pat, label in ORDINARY_BAN:
        if first_unnegated(re.compile(pat, re.I)):
            out.append(label)
    # de-duplicate, keep order
    return list(dict.fromkeys(out))


def validate_nudge(obj: dict, category: str = "", exclude: list | None = None,
                   forced_energy: str = "", mood: str = "", night: bool = False) -> tuple[dict | None, str]:
    def fail(reason: str):
        return None, reason
    if not isinstance(obj, dict):
        return fail("not-a-dict")
    for k in ("title", "task", "why_it_fits", "bring", "energy", "category"):
        if k not in obj:
            return fail(f"missing:{k}")
    # 'minutes' gets range-normalized below, so default it when the model omits the key
    # (some small models drop it on long replies; nothing useful is validated by failing)
    obj.setdefault("minutes", 20)
    if not isinstance(obj["title"], str) or not obj["title"].strip():
        return fail("bad:title")
    if not isinstance(obj["task"], str) or len(obj["task"].strip()) < 20:
        return fail("bad:task-short")
    if not isinstance(obj["why_it_fits"], str) or not obj["why_it_fits"].strip():
        return fail("bad:why")
    if not isinstance(obj["bring"], list):
        return fail("bad:bring-type")
    # tolerate junk entries: keep only non-empty strings (0-2), drop blanks/None/etc.
    cleaned = [b.strip() for b in obj["bring"] if isinstance(b, str) and b.strip()]
    if len(cleaned) > 2:
        cleaned = cleaned[:2]
    obj["bring"] = cleaned
    try:
        obj["minutes"] = int(obj["minutes"])
    except Exception:
        return fail("bad:minutes")
    if not (10 <= obj["minutes"] <= 40):
        obj["minutes"] = 20
    low = (obj["title"] + " " + obj["task"]).lower()
    if low.strip() in ("go for a walk in the park", "go for a walk in the park."):
        return fail("generic")
    # category + energy must match assignment
    if not isinstance(obj["category"], str) or obj["category"].strip() != (category or "").strip():
        return fail(f"category-mismatch:{obj.get('category')}")
    if obj["energy"] not in ("low", "medium", "high"):
        return fail("bad:energy")
    # forced energy must match
    if forced_energy and obj["energy"] != forced_energy:
        return fail(f"energy-mismatch:got-{obj['energy']}-want-{forced_energy}")
    # intensity cross-check by CATEGORY (not fragile word lists):
    # high energy may only use active categories; low energy may not use them
    if obj["energy"] == "high" and category not in HIGH_ENERGY_SET:
        return fail(f"high-needs-active-category:{category}")
    if obj["energy"] == "low" and category in HIGH_ENERGY_SET:
        return fail(f"low-cannot-use-active-category:{category}")
    if obj["energy"] == "medium" and category not in MEDIUM_OK_CATS and category not in HIGH_ENERGY_SET:
        return fail(f"medium-needs-moving-category:{category}")
    # count ban (unless observation)
    if category != "observation" and re.search(r"\bcount\w*\b", low):
        return fail("count-ban")
    # venue ban: title/task may only name a venue if the user's mood text names it
    mood_l = (mood or "").lower()
    for pat, label in VENUE_BAN:
        if re.search(pat, low) and not re.search(pat, mood_l):
            return fail(f"venue-ban:{label}")
    # hard safety & realism rules (no eating/tasting/bare hands, no climbing/roads/water,
    # no assumed objects, night door-anchor + quiet movement, no bare walks, no ordinary
    # chores, lonely = real-person contact, no "in your head", no invented scavenger items)
    viol = safety_violations(obj["title"] + " " + obj["task"], category, mood_l, night)
    if viol:
        return fail(viol[0])
    # verb ban: title's first verb must not repeat any exclude title's first verb
    bv = banned_verbs(exclude or [])
    tv = first_verb(obj["title"])
    if tv and tv in bv:
        return fail(f"verb-ban:{tv}")
    task_first = first_verb(obj["task"])
    if task_first and task_first in bv:
        return fail(f"verb-ban-task:{task_first}")
    return obj, "ok"
