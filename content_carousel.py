# -*- coding: utf-8 -*-
"""Content carousel module for Sneakerness Studio (educational soft-discovery)."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

# Topic catalog: key -> Greek UI title + English brief for the model
TOPIC_CATALOG: dict[str, dict[str, str]] = {
    "cleaning": {
        "el": "Καθαρισμός sneakers",
        "en": "How to clean sneakers safely at home (mesh, leather, suede basics)",
    },
    "storage": {
        "el": "Σωστή αποθήκευση",
        "en": "How to store sneakers to keep shape, color, and materials longer",
    },
    "maintenance": {
        "el": "Φροντίδα & συντήρηση",
        "en": "Weekly maintenance habits for everyday sneakers",
    },
    "top5": {
        "el": "Top 5 συμβουλές",
        "en": "Top 5 practical sneaker care tips beginners overlook",
    },
    "tips": {
        "el": "Γρήγορες συμβουλές",
        "en": "Quick everyday sneaker tips for comfort and longevity",
    },
    "sizing": {
        "el": "Μέγεθος & εφαρμογή",
        "en": "How to choose sneaker size and fit (toe room, width, break-in)",
    },
    "myth_bust": {
        "el": "Μύθοι vs πραγματικότητα",
        "en": "Common sneaker myths busted (cleaning, waterproofing, comfort)",
    },
    "office_vs_run": {
        "el": "Γραφείο vs τρέξιμο",
        "en": "Office walking shoes vs running shoes — what actually differs",
    },
    "joint_pain": {
        "el": "Πόνος στις αρθρώσεις",
        "en": "Soft education on cushioning and joint comfort for long standing days",
    },
    "rain_winter": {
        "el": "Βροχή & χειμώνας",
        "en": "Rain and winter sneaker care (suede, mesh, drying, protection)",
    },
    "mistakes": {
        "el": "Συχνά λάθη",
        "en": "Common mistakes that ruin sneakers faster than expected",
    },
    "materials": {
        "el": "Υλικά sneakers",
        "en": "Sneaker materials explained simply (mesh, suede, leather, foam)",
    },
}

TOPIC_KEYS = list(TOPIC_CATALOG.keys())

# Fixed educational weekly ideas (Greek display text)
_FIXED_WEEKLY_EL = [
    "Πώς καθαρίζεις σουέτ χωρίς να σκουραίνει",
    "5 συνήθειες που κρατούν τα sneakers πιο άνετα στη δουλειά",
    "Φαρδύ πάτημα χωρίς «ορθοπεδική» εμφάνιση — τι να κοιτάς",
    "Βροχή και mesh: τι κάνεις μετά τη βόλτα",
    "Μύθος: όσο πιο σκληρή η σόλα, τόσο καλύτερη στήριξη",
    "Αποθήκευση: γιατί δεν τα στοιβάζεις το ένα πάνω στο άλλο",
    "Γραφείο vs τρέξιμο: πότε αλλάζεις παπούτσι",
]



APPEARANCE_KEYS = ["auto", "eu", "diverse", "no_face"]

# English clauses injected into image prompts (Gemini/Grok).
APPEARANCE_CLAUSES = {
    "auto": "",
    "eu": (
        "If a person body is visible (legs/torso from the waist down or partial figure only): "
        "prefer one adult only; person appearance light-to-olive Mediterranean/European adult, natural look; "
        "do not default to unrelated ethnicity. If no person body is shown, ignore skin/ethnicity language."
    ),
    "diverse": (
        "If a person body is visible (legs/torso from the waist down or partial figure only): "
        "prefer one adult only; person appearance naturally diverse adults appropriate to everyday EU street/"
        "footwear content; vary across slides; avoid stereotypes. "
        "If no person body is shown, ignore skin/ethnicity language."
    ),
    "no_face": (
        "CRITICAL: No identifiable face, no portrait framing. Crop strictly below the chin; "
        "no partial face at the frame edge. Composition must prioritize footwear/legs/hands/props only — "
        "legs/shoes of at most one person OR product-only. "
        "Do NOT describe facial features or head-and-shoulders portrait."
    ),
}


def appearance_clause(key: str) -> str:
    """Return English appearance clause for key, or empty for auto/unknown."""
    k = (key or "auto").strip().lower()
    return APPEARANCE_CLAUSES.get(k, "")



def overlay_english_image_clause() -> str:
    """Hard lock: typography rendered on generated images must stay Latin/English."""
    return (
        " All on-image text must be English using Latin letters only; "
        "never Greek or Cyrillic letters on the image."
    )


FINAL_CHECK_LINE = (
    "Final check: correct sneaker model/colorway with the shoe's own real design details, "
    "each quoted text line legible, spelled correctly and shown once, "
    "no extra fingers/limbs, no bare feet, no third-party brands."
)
# Older final-check wording (kept only so finalize_image_prompt can strip it from old prompts).
_LEGACY_FINAL_CHECK_LINES = (
    "Final check: correct sneaker model/colorway, accurate logo, legible correct text, "
    "no extra fingers/limbs, no bare feet, no third-party brands.",
)
# Plain-sentence marker of the standing rules (no ALL-CAPS heading the model could render).
_IMAGE_RULES_MARKER = "Keep on-image text minimal"
_LEGACY_IMAGE_RULES_MARKER = "ON-IMAGE TEXT & PROPS RULES"

TEXT_ONCE_LINE = (
    "Render each text line exactly once. Do not render any labels, placeholders, slide numbers, "
    "page counters, instructions or words from this prompt other than the quoted lines."
)
SPELLED_EXACTLY_LINE = "All text spelled exactly as written, no ligatures or misspellings."
GROUNDED_SHOES_LINE = (
    "Shoes are grounded: worn by the person or resting naturally on the ground or floor; "
    "one pair per shot."
)
BRAND_DESIGN_LINE = (
    "The brand shows only through the real shoe design itself (its own stripes, panels and colors); "
    "do not draw any separate logo, emblem or wordmark anywhere on the image."
)
IMAGE_NEGATIVES_LINE = (
    "Negatives: no slide numbers, no page counter, no placeholder text, no duplicated text, "
    "no UI icons, no arrows, no close buttons, no swipe indicators, no app interface, "
    "no star ratings, no drawn brand logos or wordmarks, no extra logos, no levitating or "
    "floating shoes, no pedestals or cylinders, no stacked shoes, no bare feet, no barefoot people, "
    "no garbled or misspelled text, no third-party logos."
)


def _quote_line(text) -> str:
    """One on-image line, trimmed, double quotes swapped so the quoting stays unambiguous."""
    t = re.sub(r"\s+", " ", str(text or "")).strip().strip('"').strip()
    t = t.replace('"', "'")
    t = re.sub(r"[★☆]+", "", t).strip()
    return t


def on_image_text_block(
    headline: str = "",
    subline: str = "",
    button: str = "",
    *,
    watermark: str = "",
    badge: bool = False,
) -> str:
    """The ONLY on-image text, listed once, in one clear sentence.

    No role labels like 'Hook:' / 'CTA overlay:' and no slide counters — just the quoted lines.
    """
    parts = []
    h, b, c, w = _quote_line(headline), _quote_line(subline), _quote_line(button), _quote_line(watermark)
    if h:
        parts.append(f'headline "{h}"')
    if b:
        parts.append(f'subline "{b}"')
    if c:
        parts.append(f'button text "{c}"')
    if badge:
        parts.append('small badge "100% AUTHENTIC" top-right')
    if w:
        parts.append(f'watermark "{w}" bottom-right')
    if not parts:
        return " No text, letters or words anywhere on the image."
    return (
        " Text on image (render each exactly once, nothing else): "
        + " ; ".join(parts)
        + ". " + SPELLED_EXACTLY_LINE + " " + TEXT_ONCE_LINE
    )


# Third-party brand / product names that must never appear as props on the image.
_THIRD_PARTY_PROP_SWAPS = (
    (r"\bair\s*pods?\b", "unbranded wireless earbuds"),
    (r"\bi\s*phones?\b", "unbranded smartphone"),
    (r"\bi\s*pads?\b", "unbranded tablet"),
    (r"\bmac\s*books?\b", "unbranded laptop"),
    (r"\bapple\s+watch(es)?\b", "unbranded smartwatch"),
    (r"\bgalaxy\s+(buds|watch)\b", "unbranded \\1"),
    (r"\bgarmin\b", "unbranded"),
    (r"\bpolaroid\b", "unbranded instant"),
    (r"\bgo\s*pro\b", "unbranded action camera"),
    (r"\bkindle\b", "unbranded e-reader"),
    (r"\bstarbucks\b", "unbranded"),
    (r"\bcoca[- ]?cola\b|\bcoke\b", "unlabeled soda"),
    (r"\bred\s*bull\b", "unlabeled energy drink"),
    (r"\bray[- ]?ban\b", "unbranded"),
    (r"\bbeats\s+(headphones|earbuds)\b", "unbranded \\1"),
)


def unbrand_props(text: str) -> str:
    """Swap recognizable third-party product names in prop text for unbranded wording."""
    out = str(text or "")
    for pat, rep in _THIRD_PARTY_PROP_SWAPS:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return re.sub(r"\bunbranded\s+unbranded\b", "unbranded", out, flags=re.IGNORECASE)


def image_text_rules_clause(include_text_once: bool = True) -> str:
    """Standing rules for EVERY image prompt (text, badges, feet, props, grounding, negatives)."""
    return (
        f" {_IMAGE_RULES_MARKER}: only the quoted lines of this prompt appear on the image; "
        "headline max 6 plain common words, subline max 8, button text max 6; "
        "all text spelled exactly as written, no ligatures or misspellings, no invented words. "
        "At most one badge on the whole image, and only the single authenticity badge when the "
        "quoted lines include it. "
        "Any person shown wears the advertised sneakers or proper shoes (no socks-only feet). "
        "Props are unbranded: no recognizable third-party devices, cups, cans or sportswear. "
        + GROUNDED_SHOES_LINE + " "
        + BRAND_DESIGN_LINE + " "
        + (TEXT_ONCE_LINE + " " if include_text_once else "")
        + IMAGE_NEGATIVES_LINE + " "
    )


# --- Legacy meta-label cleanup -------------------------------------------------------------
# Old prompts (history, imported txt, LLM output) contained labels the image model rendered
# literally: "Slide X of Y", "Soft CTA overlay:", "COMPOSITION LOCK — Slide 1 HOOK:", star/review
# words, "accurate logo", "typical branding cues" (-> drawn logos). Rewrite / drop them.
_LEGACY_META_SUBS = (
    # Old standing-rules clause (b0b5332) — replaced by the new clause.
    (r"\s*ON-IMAGE TEXT & PROPS RULES:.*?third-party logos\.\s*", " "),
    # Old negative block about slide counters / UI chrome / review badges.
    (r"STRICTLY NO text like '?Slide X of Y'?[^.]*\.", " "),
    (r"NO review/rating badges,[^.]*?\([^)]*\)[^.]*\.", " "),
    (r"NO review/rating badges[^.]*\.", " "),
    (r"\(no OFFICIAL[^)]*\)", " "),
    (r"NEVER render Slide X of Y[^.]*\.", " "),
    (r"No UI chrome:[^;.]*;", " "),
    (r"no badges, seals, stamps, star ratings or review marks on screen\.", " "),
    (r"NO badges, tags, seals, stamps, stickers or star ratings anywhere on the image\.", "No badges on the image."),
    (r"\(no stars, no other tags, seals or stickers\)", ""),
    (r",?\s*no stars,?\s*no review seals,?", ","),
    (r"'?\b[Ss]lide\s+[XN]\s+of\s+[YM]\b'?", " "),
    (r"\b[Ss]lide\s+\d+\s+of\s+\d+\b", " "),
    (r"\b(?:REVIEWED|ULTRA COMFORT|BESTSELLER(?: SELECTION)?|OFFICIAL(?: SNEAKERNESS)? SELECTION)\b\s*", ""),
    (r"[★☆]+", ""),
    # Old English-only lock wording (listed role words + Greek alphabet the model could copy).
    (r"ALL on-image overlay / headline / body / CTA text MUST be English using Latin letters only\.\s*"
     r"NEVER use Greek letters \([^)]*\), NEVER Cyrillic, on the image\.",
     "All on-image text must be English using Latin letters only; never Greek or Cyrillic letters on the image."),
    (r"This slide's composition MUST be visually distinct from other slides",
     "This image's composition is visually distinct from the other images in the set"),
    (r"By default NO website.{0,80}?text on the image\.", "No website or URL text on the image."),
    (r"\bONLY the requested overlay text\.", "Only the quoted text lines."),
    # Section headings that read like labels.
    (r"COMPOSITION LOCK\s*[—–-]\s*(?:Slide\s*\d+\s*)?[A-Z/+ ]*:\s*", "Composition: "),
    (r"ANATOMY & COMPOSITION SAFETY \(CRITICAL\):\s*", ""),
    (r"\bCRITICAL:\s*", ""),
    # Overlay role labels -> neutral quoted lines.
    (r"Display headline text overlay\s*'", "headline '"),
    (r"(?:Bold top |Clean |Subtle )?text overlay:\s*'", "on-image text '"),
    (r"Clean overlay text:\s*'", "on-image text '"),
    (r"body text overlay\s*'", "subline '"),
    (r"(?:Clean product showcase with )?[Ss]oft CTA overlay:?\s*'", "button text '"),
    (r"Clean short typography overlay matching(?: the title)?:\s*", "Small clean headline text: "),
    (r"calm negative space", "calm negative space"),
    (r"\s*Place the soft CTA just above the bottom-right watermark[^—]*—[^.]*\.\s*\)?\.?", " "),
    # Logo-drawing triggers.
    (r"typical branding cues", "the shoe's own real design details"),
    (r"accurate logo", "the shoe's own real design details"),
    (r"no drawn logos", "no drawn logos"),
)


def sanitize_image_prompt_meta(prompt: str) -> str:
    """Strip/neutralize meta labels, slide counters, star/review words and logo-drawing cues."""
    out = str(prompt or "")
    for pat, rep in _LEGACY_META_SUBS:
        out = re.sub(pat, rep, out, flags=re.DOTALL)
    for line in _LEGACY_FINAL_CHECK_LINES:
        out = out.replace(line, " ")
    out = re.sub(r"\s+([.,])", r"\1", out)
    out = re.sub(r"\.\s*\.", ".", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def prompt_has_legacy_meta(prompt: str) -> bool:
    """True if a stored prompt still carries old meta labels / counters / star words."""
    p = str(prompt or "")
    return bool(re.search(
        r"Slide\s+[XN\d]+\s+of|COMPOSITION LOCK|CTA overlay|text overlay|[★☆]|REVIEWED|BESTSELLER|"
        + re.escape(_LEGACY_IMAGE_RULES_MARKER) + r"|accurate logo|typical branding cues",
        p, flags=re.IGNORECASE,
    ))


def finalize_image_prompt(prompt: str, ar_flag: str = "") -> str:
    """Clean meta labels, inject standing image rules (once) and end with the final checklist line.

    Idempotent. If the prompt ends with an aspect flag (e.g. '--ar 1:1'), the checklist goes
    right before it so the flag stays last.
    """
    p = str(prompt or "").strip()
    if not p:
        return p
    p = p.replace(FINAL_CHECK_LINE, "").strip()
    p = sanitize_image_prompt_meta(p)
    flag = (ar_flag or "").strip()
    found = re.findall(r"--ar\s+\d+:\d+", p)
    if not flag and found:
        flag = found[-1]
    tail = ""
    if flag:
        # Aspect flag always goes last (some callers appended clauses after it).
        p = re.sub(r"\s*--ar\s+\d+:\d+\s*", " ", p).strip()
        tail = " " + flag
    if _IMAGE_RULES_MARKER not in p:
        if p and p[-1] not in ".!?":
            p = p + "."
        p = p + image_text_rules_clause(include_text_once=TEXT_ONCE_LINE not in p)
    return (p.rstrip() + " " + FINAL_CHECK_LINE + tail).strip()


def anatomy_safety_clause() -> str:
    return (
        " Anatomy and composition: maximum ONE person in frame (prefer zero people / product-only when possible). "
        "If a person is shown: coherent realistic anatomy only — exactly two arms, two legs, two feet; "
        "every visible limb clearly attached to that one body; the person is properly supported "
        "(sitting on a real bench/chair/curb or standing on the ground). "
        "Shoes are either (a) worn correctly on that person's feet, or (b) one pair resting naturally "
        "on the ground or floor with NO people interacting with them. "
        "Avoid: two people interacting with feet/legs, holding/removing socks or shoes from another person, "
        "extra limbs, detached legs, merged bodies, impossible joints, disembodied feet, "
        "duplicate pairs of shoes that do not match the feet, bare feet / barefoot people "
        "(anyone shown wears sneakers or proper shoes). "
        "Prefer simple readable commercial composition: one pair on the ground OR a single waist-down "
        "person with BOTH shoes on their own feet. "
    )


def _sanitize_no_face_prompt(prompt: str) -> str:
    """Rewrite common portrait/face framing so models do not ignore a trailing no_face clause."""
    if not prompt:
        return prompt or ""
    out = prompt
    replacements = [
        (r"\bCinematic portrait of\b", "Lifestyle footwear/legs scene of"),
        (r"\bcinematic portrait of\b", "lifestyle footwear/legs scene of"),
        (r"\bportrait of a\b", "lifestyle scene of a"),
        (r"\bPortrait of a\b", "Lifestyle scene of a"),
        (r"\bhead-and-shoulders\b", "waist-down crop"),
        (r"\bheadshot\b", "product/lifestyle frame"),
        (r"\bface close-up\b", "footwear close-up"),
        (r"\blooking at (the )?camera\b", "out of frame"),
        (r"\bclose-up (of )?(a )?face\b", "close-up of footwear"),
    ]
    for pat, repl in replacements:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


def append_appearance_clause(prompt: str, appearance: str = "auto") -> str:
    """Append appearance clause to an image prompt; insert before trailing --ar flag."""
    key = (appearance or "auto").strip().lower()
    clause = appearance_clause(key)
    if not (prompt or "").strip():
        return prompt or ""
    out = prompt
    if key == "no_face":
        out = _sanitize_no_face_prompt(out)
    if not clause:
        return out
    if clause in out:
        return out
    m = re.search(r"(\s*--ar\s+\S+)\s*$", out)
    if m:
        return (out[: m.start()].rstrip() + " " + clause + m.group(1)).strip()
    return (out.rstrip() + " " + clause).strip()



def topic_label(key: str, lang: str = "el") -> str:
    """UI label for a topic key."""
    entry = TOPIC_CATALOG.get(key) or {}
    if lang == "en":
        # Short EN labels for picker (derived from key + brief head)
        en_labels = {
            "cleaning": "Sneaker cleaning",
            "storage": "Proper storage",
            "maintenance": "Care & maintenance",
            "top5": "Top 5 tips",
            "tips": "Quick tips",
            "sizing": "Size & fit",
            "myth_bust": "Myths vs reality",
            "office_vs_run": "Office vs running",
            "joint_pain": "Joint comfort",
            "rain_winter": "Rain & winter",
            "mistakes": "Common mistakes",
            "materials": "Sneaker materials",
        }
        return en_labels.get(key, entry.get("en", key))
    return entry.get("el", key)


def topic_brief_en(key: str, override: str = "") -> str:
    """English brief passed to Gemini (override wins if provided)."""
    if override and override.strip():
        return override.strip()
    entry = TOPIC_CATALOG.get(key) or {}
    return entry.get("en") or key.replace("_", " ")


def weekly_suggestions(
    insights: Optional[dict] = None,
    *,
    lang: str = "el",
    count: int = 4,
) -> list[str]:
    """
    3–5 ready topic ideas in Greek (or EN if lang=en).
    Mixes weekly_insights actionable items with fixed educational topics.
    Rotates lightly by ISO week so the panel feels fresh.
    """
    ideas: list[str] = []
    insights = insights or {}

    # From weekly insights (prefer EL display for Greek UI)
    for row in insights.get("top_3_actionable_insights") or []:
        if isinstance(row, dict):
            txt = (row.get("el") if lang == "el" else row.get("en")) or row.get("el") or row.get("en") or ""
        else:
            txt = str(row)
        txt = str(txt).strip()
        # Strip leading "1. " numbering if present
        if len(txt) > 3 and txt[0].isdigit() and txt[1] in ".)":
            txt = txt[2:].strip()
        elif len(txt) > 4 and txt[0].isdigit() and txt[1] == ".":
            txt = txt[2:].strip()
        if txt:
            ideas.append(txt)

    for row in insights.get("consumer_search_intent") or []:
        if not isinstance(row, dict):
            continue
        q = row.get("query") or {}
        if isinstance(q, dict):
            txt = (q.get("el") if lang == "el" else q.get("en")) or q.get("el") or q.get("en") or ""
        else:
            txt = str(q)
        txt = str(txt).strip()
        if txt and txt not in ideas:
            ideas.append(txt)

    fixed = list(_FIXED_WEEKLY_EL)
    if lang == "en":
        fixed = [
            "How to clean suede without darkening it",
            "5 habits that keep sneakers comfortable at work",
            "Wide fit without an orthopedic look — what to check",
            "Rain and mesh: what to do after a walk",
            "Myth: harder sole always means better support",
            "Storage: why you should not stack sneakers",
            "Office vs running: when to switch shoes",
        ]

    week = datetime.utcnow().isocalendar()[1]
    # Rotate fixed list by week
    rot = week % max(len(fixed), 1)
    fixed = fixed[rot:] + fixed[:rot]
    for f in fixed:
        if f not in ideas:
            ideas.append(f)

    count = max(3, min(5, int(count or 4)))
    return ideas[:count]


def _parse_json_response(text: str) -> dict:
    clean = (text or "").strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return json.loads(clean.strip())


def _fallback_carousel(
    topic_en: str,
    slide_count: int,
    ar_flag: str,
    appearance: str = "auto",
    lang: str = "en",
) -> dict[str, Any]:
    """Deterministic soft-discovery fallback if Gemini fails.

    Slides form one continuous mini-story; each body teaches from that slide's image
    and states why the visual/tip is useful. UI copy follows lang; image_prompt stays EN.
    """
    lang = (lang or "en").strip().lower()
    # Continuous arc: hook problem/scene -> steps that continue -> soft CTA/takeaway
    # Each tuple: (title_en, body_en, title_el, body_el, image_prompt_en)
    templates = [
        (
            "Tired feet after long days?",
            "That end-of-day ache often starts with shoes that never get a quick check. Spotting the problem in this quiet scene is the first useful step.",
            "Κουρασμένα πόδια μετά από μεγάλες μέρες;",
            "Ο πόνος στο τέλος της ημέρας συχνά ξεκινά από παπούτσια που δεν ελέγχονται ποτέ γρήγορα. Το να δεις το πρόβλημα σε αυτή την ήσυχη σκηνή είναι το πρώτο χρήσιμο βήμα.",
            f"Soft editorial photo of empty everyday sneakers by a window at dusk, calm tired-day mood, educational, no drawn logos, no celebrities. {on_image_text_block('Tired feet after long days?')} Photorealistic 8k {ar_flag}",
        ),
        (
            "Start with a two-hour check",
            "After two hours on your feet, notice midsole compression, upper creases, and toe pinch. This close-up check shows what to fix next — before soreness becomes a habit.",
            "Ξεκίνα με έλεγχο στις δύο ώρες",
            "Μετά από δύο ώρες όρθιος, πρόσεξε συμπίεση midsole, τσακίσεις upper και πίεση στα δάχτυλα. Αυτός ο κοντινός έλεγχος δείχνει τι να διορθώσεις μετά — πριν ο πόνος γίνει συνήθεια.",
            f"Close-up lifestyle still of sneaker midsole and upper on a clean desk, natural light, Kinfolk aesthetic, educational. {on_image_text_block('Start with a two-hour check')} Photorealistic 8k {ar_flag}",
        ),
        (
            "Clean gently, dry slowly",
            "Once the pair is worth keeping, use a soft brush and mild soap where safe, then air-dry away from radiators. Gentle cleaning protects materials so cushioning lasts longer.",
            "Καθάρισε απαλά, στέγνωσε αργά",
            "Όταν το ζευγάρι αξίζει να το κρατήσεις, χρησιμοποίησε μαλακή βούρτσα και ήπιο σαπούνι όπου είναι ασφαλές, μετά άφησέ τα να στεγνώσουν μακριά από καλοριφέρ. Ο απαλός καθαρισμός προστατεύει τα υλικά ώστε η απορρόφηση να διαρκεί περισσότερο.",
            f"Hands gently brushing a sneaker with a soft brush, towels nearby, calm tutorial feel, no brand hard-sell. {on_image_text_block('Clean gently, dry slowly')} Photorealistic 8k {ar_flag}",
        ),
        (
            "Rotate and let foam rebound",
            "Alternating pairs between wear days lets midsole foam rebound and keeps odor down. Resting shoes on the shelf is a free comfort upgrade you can see.",
            "Εναλλαγή και άσε τον αφρό να επανέλθει",
            "Η εναλλαγή ζευγαριών ανάμεσα στις μέρες χρήσης αφήνει τον αφρό midsole να επανέλθει και μειώνει τις οσμές. Η ξεκούραση στο ράφι είναι δωρεάν αναβάθμιση άνεσης που φαίνεται.",
            f"One pair of everyday sneakers resting on a low wooden shelf, soft daylight, organized storage, educational still life. {on_image_text_block('Rotate and let foam rebound')} Photorealistic 8k {ar_flag}",
        ),
        (
            "Match material to the day",
            "Mesh breathes on warm walks, suede needs rain care, foam cushions standing hours. Matching what you see in the shoe to how you use it breaks the same tired-feet loop.",
            "Ταίριαξε υλικό με την ημέρα",
            "Το mesh αναπνέει σε ζεστές βόλτες, το σουέτ χρειάζεται φροντίδα στη βροχή, ο αφρός απορροφά ώρες όρθιας στάσης. Το να ταιριάζεις αυτό που βλέπεις στο παπούτσι με το πώς το χρησιμοποιείς σπάει τον ίδιο κύκλο κουρασμένων ποδιών.",
            f"Macro texture still of mesh and suede in one calm frame, soft studio light, educational product photography. {on_image_text_block('Match material to the day')} Photorealistic 8k {ar_flag}",
        ),
        (
            "Save this tip for later",
            "You now have a simple loop: check, care, rotate, match materials. Save this carousel and follow for the next calm footwear tip.",
            "Αποθήκευσε αυτή τη συμβουλή για αργότερα",
            "Τώρα έχεις έναν απλό κύκλο: έλεγχος, φροντίδα, εναλλαγή, ταίριασμα υλικών. Αποθήκευσε αυτό το carousel και ακολούθησε για την επόμενη ήρεμη συμβουλή υποδημάτων.",
            f"Minimal flat-lay of one pair of sneakers lying on the floor with an unbranded notebook and plain coffee cup, calm negative space, calm discovery mood, no celebrity, no hard sell. {on_image_text_block('Save this tip for later')} Photorealistic 8k {ar_flag}",
        ),
    ]
    slides = []
    for i in range(slide_count):
        title_en, body_en, title_el, body_el, prompt = templates[i % len(templates)]
        if i == 0:
            title_en = "A calmer way to think about sneakers"
            body_en = (
                f"Today's focus: {topic_en}. This opening scene sets a common problem you can ease "
                "with small soft habits — no hard sell."
            )
            title_el = "Ένας πιο ήρεμος τρόπος να σκέφτεσαι τα sneakers"
            body_el = (
                f"Το σημερινό θέμα: {topic_en}. Αυτή η εναρκτήρια σκηνή δείχνει ένα συνηθισμένο πρόβλημα "
                "που μπορείς να απαλύνεις με μικρές ήπιες συνήθειες — χωρίς hard sell."
            )
            prompt = (
                f"Soft editorial photo of empty everyday sneakers by a window, calm morning light, "
                f"educational mood, no drawn logos, no celebrities, soft-discovery mood. "
                f"{on_image_text_block('A calmer way to think about sneakers')} "
                f"Photorealistic 8k {ar_flag}"
            )
        elif i == slide_count - 1:
            title_en = "Follow for the next tip"
            body_en = (
                "Takeaway: small checks and gentle care compound. "
                "Explore more calm footwear advice anytime — soft discovery, not an ad."
            )
            title_el = "Ακολούθησε για την επόμενη συμβουλή"
            body_el = (
                "Συμπέρασμα: οι μικροί έλεγχοι και η απαλή φροντίδα αθροίζονται. "
                "Εξερεύνησε περισσότερες ήρεμες συμβουλές υποδημάτων όποτε θες — soft discovery, όχι διαφήμιση."
            )
            prompt = (
                f"Minimal flat-lay of one pair of sneakers lying on the floor with an unbranded notebook and plain coffee cup, calm negative space, "
                f"calm discovery mood, no celebrity, no hard sell. "
                f"{on_image_text_block('Follow for the next tip')} Photorealistic 8k {ar_flag}"
            )
        title = title_el if lang == "el" else title_en
        body = body_el if lang == "el" else body_en
        if "Latin letters only" not in prompt:
            prompt = (prompt + " " + overlay_english_image_clause()).strip()
        slides.append({
            "title": title,
            "body": body,
            "image_prompt": finalize_image_prompt(append_appearance_clause(prompt, appearance), ar_flag),
        })
    if lang == "el":
        return {
            "slides": slides,
            "ig_caption": (
                f"Ήπια σειρά συμβουλών: {topic_en}. Αποθήκευσέ το για αργότερα — εκπαιδευτικό, όχι πωλητικό. "
                "#Sneakerness #SneakerCare #SoftDiscovery"
            ),
            "tiktok_caption": (
                f"{topic_en} — γρήγορο εκπαιδευτικό carousel. Ακολούθησε για την επόμενη συμβουλή. "
                "#Sneakerness #SneakerTips #FootwearEducation #FYP"
            ),
            "pinterest_caption": (
                f"Εκπαιδευτικές συμβουλές sneakers: {topic_en}. Soft-discovery για καθημερινή άνεση και φροντίδα "
                "υποδημάτων — αποθήκευσε αυτό το pin. #Sneakerness #SneakerCare #FootwearTips #SoftDiscovery"
            ),
            "youtube_caption": (
                f"{topic_en} — ήρεμες συμβουλές υποδημάτων\n"
                f"Ένα σύντομο εκπαιδευτικό carousel για {topic_en}. Soft discovery, όχι διαφήμιση. "
                "Ακολούθησε για την επόμενη συμβουλή. #Sneakerness #SneakerTips"
            ),
        }
    return {
        "slides": slides,
        "ig_caption": (
            f"Soft tip thread: {topic_en}. Save for later - educational, not a sales pitch. "
            "#Sneakerness #SneakerCare #SoftDiscovery"
        ),
        "tiktok_caption": (
            f"{topic_en} - quick educational carousel. Follow for the next tip. "
            "#Sneakerness #SneakerTips #FootwearEducation #FYP"
        ),
        "pinterest_caption": (
            f"Educational sneaker tips: {topic_en}. Soft-discovery advice for everyday footwear comfort "
            "and care - save this pin for later. #Sneakerness #SneakerCare #FootwearTips #SoftDiscovery"
        ),
        "youtube_caption": (
            f"{topic_en} - calm footwear tips\n"
            f"A short educational carousel on {topic_en}. Soft discovery, not a sales pitch. "
            "Follow for the next tip. #Sneakerness #SneakerTips"
        ),
    }


def generate_content_carousel(
    client: Any,
    *,
    topic_key: str = "tips",
    topic_override: str = "",
    slide_count: int = 5,
    aspect_ratio: str = "1:1 (Square)",
    insight_context: str = "",
    appearance: str = "eu",
    lang: str = "en",
    models: Optional[list[str]] = None,
    warn: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """
    Call Gemini to produce educational carousel content.

    When lang=el: slide titles/bodies and all four captions are Greek;
    image_prompt fields stay ENGLISH for Gemini/Grok/Nano Banana
    (any on-image overlay text inside image_prompt stays English/Latin).
    When lang=en: everything English as before.

    Returns dict with:
      slides: [{title, body, image_prompt}, ...]
      ig_caption, tiktok_caption, pinterest_caption, youtube_caption
    """
    slide_count = int(slide_count or 5)
    if slide_count < 4:
        slide_count = 4
    if slide_count > 6:
        slide_count = 6

    if aspect_ratio.startswith("4:5"):
        ar_flag = "--ar 4:5"
    elif aspect_ratio.startswith("2:3"):
        ar_flag = "--ar 2:3"
    elif aspect_ratio.startswith("16:9"):
        ar_flag = "--ar 16:9"
    elif aspect_ratio.startswith("9:16"):
        ar_flag = "--ar 9:16"
    else:
        ar_flag = "--ar 1:1"

    topic_en = topic_brief_en(topic_key, topic_override)
    _appearance_key = (appearance or "auto").strip().lower()
    if _appearance_key not in APPEARANCE_KEYS:
        _appearance_key = "auto"
    _appearance_clause = appearance_clause(_appearance_key)
    _lang = (lang or "en").strip().lower()
    if _lang not in ("en", "el"):
        _lang = "en"
    _ui_is_el = _lang == "el"
    appearance_block = ""
    if _appearance_clause:
        if _appearance_key == "no_face":
            appearance_block = (
                "\nHARD APPEARANCE CONSTRAINT (apply to EVERY slide image_prompt):\n"
                f"{_appearance_clause}\n"
                "WRITE each image_prompt WITHOUT words like: portrait, face close-up, looking at camera, "
                "headshot, head-and-shoulders, facial features, smiling face. "
                "Crop strictly below the chin; no partial face at the frame edge. "
                "Use lifestyle/product framing instead: footwear, legs, hands, props, environments.\n"
                + anatomy_safety_clause() + "\n"
            )
        else:
            appearance_block = (
                "\nPERSON / MODEL APPEARANCE (apply ONLY if a person body is visible from the legs/"
                "waist; soft creative control for brand consistency; do not force a face into frame):\n"
                f"{_appearance_clause}\n"
                "Include this guidance naturally in each image_prompt (English). Prefer one adult only.\n"
                + anatomy_safety_clause() + "\n"
            )

    models_to_try = models or ["gemini-3.6-flash", "gemini-2.5-flash"]

    insight_block = ""
    if insight_context and str(insight_context).strip():
        insight_block = (
            "\nEXTRA MARKET INSIGHT TO SOFTLY REFLECT (do not invent stats; keep soft-discovery):\n"
            + str(insight_context).strip()
            + "\n"
        )

    _lang_rule = (
        "DUAL-LANGUAGE OUTPUT: slide title and body MUST be natural Greek (Ελληνικά); "
        "ig_caption, tiktok_caption, pinterest_caption, youtube_caption MUST be natural Greek; "
        "EVERY image_prompt MUST stay ENGLISH ONLY (for image models). "
        "Any on-image overlay / typography quoted inside image_prompt MUST be English Latin letters only "
        "(never Greek letters on the image, even when the slide title is Greek). "
        if _ui_is_el else
        "ALL output must be ENGLISH ONLY (titles, bodies, captions, and image prompts). "
    )
    sys_instruction = (
        "You are an expert educational footwear content writer in the style of calm "
        "discovery accounts (like sneakers.loft vibe): soft tips, not ads. "
        + _lang_rule +
        "NEVER use celebrity athlete names. "
        "NEVER use hard-sell verbs (buy, shop, order, purchase). "
        "Prefer soft CTAs: follow for next tip, save this, explore more. "
        "CRITICAL STORY RULE: titles and bodies across all slides MUST read as ONE continuous "
        "narrative when read in order — slide 1 hooks a problem/scene, middle slides continue "
        "with steps/tips that follow from the previous slide (not random disconnected tips), "
        "last slide is a soft CTA / takeaway. "
        "CRITICAL IMAGE-TEXT LOCK: for every slide, title + body must describe and teach from "
        "what that slide's image_prompt depicts; the body must state the practical usefulness "
        "of that visual (what the viewer learns and why the tip helps). "
        "CRITICAL SHARED-CAPTION LOCK: ig_caption, tiktok_caption, pinterest_caption, and "
        "youtube_caption must summarize the SAME story/scenes the slides' image_prompts depict — "
        "do not invent a different setting than slides 1..N show. "
        "When a person/model appearance guidance is provided in the user prompt, reflect it "
        "consistently in every image_prompt. "
        "IMAGE PROMPT RULES (write image_prompt as a plain scene description): never put slide "
        "numbers, page counters, role labels (hook/body/CTA), section headings, UI words (buttons, "
        "arrows, dots, swipe, close icons) or any badge/rating/review wording inside image_prompt. "
        "On-image text: at most one short headline (max 6 plain common English words), written ONLY as: "
        "Text on image (render each exactly once, nothing else): headline \"...\". "
        "Shoes grounded: worn by the one person or one pair resting naturally on the ground or floor; "
        "never on pedestals, cylinders or stacked; never floating. Do not ask for a drawn brand logo or "
        "wordmark — the shoe's own design is the only branding. "
        "No bare feet — anyone shown wears sneakers or proper shoes. Props unbranded only: no "
        "recognizable third-party brands/logos (no AirPods, iPhone, Apple Watch-like devices). "
        "End every image_prompt with: '" + FINAL_CHECK_LINE + "' then the aspect flag. "
        "NEVER auto-brand SNEAKERNESS.EU / sneakerness on the image by default. "
        "If an explicit watermark/domain string is provided: REQUIRED — render watermark "
        "EXACTLY ONCE using that exact user string only (ban any second tiny/micro duplicate, "
        "shortened copy, or extra corner mark; do not also add \"sneakerness\" when the user "
        "typed a full domain) as clearly phone-readable bottom-right watermark (~7–9% of image "
        "height, clean sans-serif, strong contrast — must be easily readable at a glance on a phone screen; not microscopic; not faint grey on busy background; subtle dark/light shadow OK), ~2–3% margin "
        "from edges — readable on a phone without zoom; no giant headline, not dominating the "
        "shoe, no Explore CTA on image. Overlay/CTA texts must NOT contain any website/domain — "
        "the watermark is the only on-image site text. "
        "When watermark/domain is provided, MUST include it once naturally in ig/tiktok/pinterest/youtube captions; "
        "do not force site into every image_prompt. "
        "Overlay text must match the scene: ban work-shift / long-shifts wording when the scene "
        "is running/track/curb-after-run/park leisure; keep shift wording only for standing/work scenes; "
        "problem/hook wording must match the visible setting (no shift wording on park/dusk leisure unless workplace). "
        "If no_face: never write portrait/face/headshot language; prioritize shoes/legs/hands/props. "
        + anatomy_safety_clause()
    )

    _copy_lang_rule = (
        "Slide title + body + all four captions MUST be natural Greek (Ελληνικά). "
        "image_prompt MUST remain ENGLISH ONLY for image generation models; "
        "on-image overlay text inside image_prompt MUST be English (Latin) — never Greek letters on the image."
        if _ui_is_el
        else "ALL OUTPUT MUST BE IN ENGLISH ONLY (titles, bodies, captions, image prompts)."
    )
    _json_title = "short on-screen title EL (Greek)" if _ui_is_el else "short on-screen title EN"
    _json_body = (
        "short body EL (Greek) — continues the story AND states why the image/tip is useful"
        if _ui_is_el
        else "short body EN — continues the story AND states why the image/tip is useful"
    )
    _json_ig = "optional Instagram caption EL (Greek) + light hashtags" if _ui_is_el else "optional Instagram caption EN + light hashtags"
    _json_tt = "optional TikTok caption EL (Greek) + FYP hashtags" if _ui_is_el else "optional TikTok caption EN + FYP hashtags"
    _json_pin = "optional Pinterest pin description EL (Greek) - 2-4 discovery/SEO sentences; optional 3-5 hashtags" if _ui_is_el else "optional Pinterest pin description EN - 2-4 discovery/SEO sentences; optional 3-5 hashtags"
    _json_yt = "optional YouTube Shorts/community caption EL (Greek) - strong hook first line; 2-4 sentences; soft CTA; fewer hashtags" if _ui_is_el else "optional YouTube Shorts/community caption EN - strong hook first line; 2-4 sentences; soft CTA; fewer hashtags"

    script_prompt = f"""Create an educational Instagram/TikTok CONTENT CAROUSEL (not a product ad) about:
TOPIC: {topic_en}

CRITICAL CONSTRAINTS:
1. LANGUAGE: {_copy_lang_rule}
2. Soft-discovery / educational advice feel - NOT hard sell. No "buy", "shop", "order", "purchase".
3. STRICTLY NO celebrity names (no Jordan, Kobe, LeBron, Messi, Ronaldo, Curry, etc.).
4. CONTINUOUS STORY ARC across exactly {slide_count} slides:
   - Slide 1 = hook (problem or scene that opens the story).
   - Middle slides = steps/tips that CONTINUE from the previous slide (not a random tip dump).
   - Last slide = soft CTA / takeaway.
   Titles and bodies MUST read as one continuous narrative when read in order.
5. IMAGE-TEXT LOCK: for each slide, title + body MUST describe and teach from what that slide's image_prompt depicts.
   The body MUST state the practical usefulness of that visual (what the viewer learns / why this tip helps).
   Encode usefulness IN the body (do not invent extra JSON fields).
5b. CRITICAL SHARED-CAPTION LOCK: ig_caption, tiktok_caption, pinterest_caption, and youtube_caption MUST summarize the SAME story/scenes as slides 1..N image_prompts — do NOT invent a different setting than the slides depict.
6. Each slide needs short on-screen title + short body (readable on phone).
7. Each slide needs an image generation prompt in Nano Banana / Midjourney style: soft-discovery aesthetic, photorealistic or clean editorial, calm lighting, no hard-sell product packaging UI, no celebrity faces.
8. Optional on-image text: image_prompt MAY include ONE short 2-6 plain common word ENGLISH (Latin letters only) headline, written ONLY in this exact form: Text on image (render each exactly once, nothing else): headline "..." — then "All text spelled exactly as written, no ligatures or misspellings." Do NOT put Greek letters on the image even if the slide title is Greek; prefer a short English paraphrase of the title. Never write slide numbers, page counters, role labels (hook/body/CTA/overlay), section headings, UI words (buttons, arrows, dots, swipe, close icons) or any badge/rating/review words inside image_prompt. No hard sell. ALL on-image text MUST be English using Latin letters only, never Greek or Cyrillic letters.
9. Append aspect flag exactly as: {ar_flag} at the end of every image_prompt.
10. By default NEVER put SNEAKERNESS.EU / sneakerness / any website on the image. If an explicit watermark/domain is provided in this prompt: REQUIRED — render watermark EXACTLY ONCE using that exact user string only (ban any second tiny/micro duplicate, shortened copy, or extra corner mark; do not also add "sneakerness" when the user typed a full domain) as clearly phone-readable bottom-right watermark (~7–9% of image height, clean sans-serif, strong contrast — must be easily readable at a glance on a phone screen; not microscopic; not faint grey on busy background; subtle dark/light shadow OK), ~2–3% margin from edges — readable on a phone without zoom; no giant headline, not dominating the shoe, no Explore CTA sentence on image. Overlay/CTA texts must NOT contain any website/domain — the watermark is the only on-image site text. MUST include the domain once naturally in ig/tiktok/pinterest/youtube captions when provided; do not force site into every image_prompt.
11. Overlay text must match the depicted scene (do not put work-shift / "long shifts" wording on a running / track / curb-after-run / park leisure scene; keep work wording only for standing/work scenes; problem/hook wording must match the visible setting).
12. If HARD APPEARANCE / no_face is active: crop strictly below the chin; no partial face at frame edge; write image_prompt as lifestyle/product framing with shoes/legs/hands/props - never portrait, face close-up, looking at camera, or headshot language. Prefer legs/shoes of at most one person OR product-only.
13. Anatomy and composition (apply to EVERY image_prompt): Maximum ONE person (prefer product-only). Coherent anatomy only — exactly two arms, two legs, two feet; limbs attached; person supported on bench/chair/curb/ground. Shoes worn on that person OR one pair resting naturally on the ground/floor with no people — one pair per shot, never on a pedestal/cylinder, never stacked, never levitating. Avoid: two people handling feet/legs, holding/removing socks/shoes from another, extra/detached limbs, merged bodies, disembodied feet, mismatched duplicate shoes, bare feet (anyone shown wears sneakers or proper shoes — add "no bare feet" to negatives). Do not ask for a drawn brand logo or wordmark; the real shoe design is the only branding.
14. PROPS: unbranded only — no recognizable third-party brands or logos (no AirPods, iPhone, Apple Watch-like devices, branded cups/cans); write "unbranded" for tech props.
15. FINAL LINE: end every image_prompt with "{FINAL_CHECK_LINE}" right before {ar_flag}.
{insight_block}{appearance_block}
Return strict JSON:
{{
  "slides": [
    {{
      "title": "{_json_title}",
      "body": "{_json_body}",
      "image_prompt": "full EN image gen prompt (optional clean ENGLISH Latin overlay only — never Greek letters on image) ending with {ar_flag}"
    }}
  ],
  "ig_caption": "{_json_ig}",
  "tiktok_caption": "{_json_tt}",
  "pinterest_caption": "{_json_pin}",
  "youtube_caption": "{_json_yt}"
}}
Exactly {slide_count} objects inside "slides".
"""

    try:
        from google.genai import types
    except ImportError:
        types = None  # type: ignore

    for model_item in models_to_try:
        try:
            kwargs: dict[str, Any] = {
                "model": model_item,
                "contents": script_prompt,
            }
            if types is not None:
                kwargs["config"] = types.GenerateContentConfig(
                    system_instruction=sys_instruction,
                    response_mime_type="application/json",
                )
            response = client.models.generate_content(**kwargs)
            if response and response.text:
                data = _parse_json_response(response.text)
                slides = data.get("slides") or []
                if not isinstance(slides, list) or len(slides) < 1:
                    raise ValueError("empty slides")
                # Normalize slide count
                normalized = []
                for s in slides[:slide_count]:
                    if not isinstance(s, dict):
                        continue
                    prompt = str(s.get("image_prompt") or "")
                    if ar_flag not in prompt:
                        prompt = (prompt + " " + ar_flag).strip()
                    if "Latin letters only" not in prompt:
                        prompt = (prompt + " " + overlay_english_image_clause()).strip()
                    prompt = append_appearance_clause(prompt, _appearance_key)
                    prompt = finalize_image_prompt(prompt, ar_flag)
                    normalized.append(
                        {
                            "title": str(s.get("title") or "").strip() or "Tip",
                            "body": str(s.get("body") or "").strip() or "",
                            "image_prompt": prompt,
                        }
                    )
                while len(normalized) < slide_count:
                    fb = _fallback_carousel(topic_en, slide_count, ar_flag, _appearance_key, lang=_lang)
                    normalized.append(fb["slides"][len(normalized)])
                return {
                    "slides": normalized[:slide_count],
                    "ig_caption": str(data.get("ig_caption") or "").strip(),
                    "tiktok_caption": str(data.get("tiktok_caption") or "").strip(),
                    "pinterest_caption": str(data.get("pinterest_caption") or "").strip(),
                    "youtube_caption": str(data.get("youtube_caption") or "").strip(),
                    "topic_en": topic_en,
                    "topic_key": topic_key,
                    "slide_count": slide_count,
                    "ar_flag": ar_flag,
                    "appearance": _appearance_key,
                    "lang": _lang,
                }
        except Exception as e:
            if warn:
                try:
                    warn(f"{model_item}: {e}")
                except Exception:
                    pass
            time.sleep(1)

    fb = _fallback_carousel(topic_en, slide_count, ar_flag, _appearance_key, lang=_lang)
    fb["topic_en"] = topic_en
    fb["appearance"] = _appearance_key
    fb["topic_key"] = topic_key
    fb["slide_count"] = slide_count
    fb["ar_flag"] = ar_flag
    fb["lang"] = _lang
    return fb


def build_content_txt(result: dict[str, Any]) -> str:
    """Plain-text export for download."""
    lines = [
        "========================================",
        f"CONTENT CAROUSEL ({(result.get('lang') or 'en').upper()})",
        f"Topic key: {result.get('topic_key', '')}",
        f"Topic: {result.get('topic_en', '')}",
        f"Slides: {result.get('slide_count', len(result.get('slides') or []))}",
        "========================================",
        "",
    ]
    for i, s in enumerate(result.get("slides") or [], start=1):
        lines.append(f"--- SLIDE {i} ---")
        lines.append(f"Title: {s.get('title', '')}")
        lines.append(f"Body: {s.get('body', '')}")
        lines.append("Image prompt:")
        lines.append(s.get("image_prompt", ""))
        lines.append("")
    lines.append("========================================")
    lines.append("INSTAGRAM CAPTION")
    lines.append("========================================")
    lines.append(result.get("ig_caption") or "")
    lines.append("")
    lines.append("========================================")
    lines.append("TIKTOK CAPTION")
    lines.append("========================================")
    lines.append(result.get("tiktok_caption") or "")
    lines.append("")
    lines.append("========================================")
    lines.append("PINTEREST DESCRIPTION")
    lines.append("========================================")
    lines.append(result.get("pinterest_caption") or "")
    lines.append("")
    lines.append("========================================")
    lines.append("YOUTUBE CAPTION")
    lines.append("========================================")
    lines.append(result.get("youtube_caption") or "")
    lines.append("")
    vb = result.get("video_beats")
    if isinstance(vb, dict) and vb.get("beats"):
        lines.append("========================================")
        lines.append("GROK VIDEO BEATS (EN prompts)")
        lines.append("========================================")
        try:
            from video_prompts import format_video_prompts_txt
            lines.append(format_video_prompts_txt(vb, topic=result.get("topic_en") or ""))
        except Exception:
            for b in vb.get("beats") or []:
                lines.append(f"--- BEAT {b.get('index')} ---")
                lines.append(b.get("prompt_en") or "")
                lines.append("")
    vu = result.get("video_unified")
    if isinstance(vu, dict) and vu.get("prompt_en"):
        lines.append("========================================")
        lines.append("GROK VIDEO UNIFIED (EN)")
        lines.append("========================================")
        try:
            from video_prompts import format_unified_video_txt
            lines.append(format_unified_video_txt(vu, topic=result.get("topic_en") or ""))
        except Exception:
            lines.append(vu.get("prompt_en") or "")
            lines.append("")
    lines.append("========================================")
    lines.append("RAW JSON")
    lines.append("========================================")
    lines.append(json.dumps(result, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def build_content_zip_bytes(result: dict[str, Any], *, aspect_ratio: str = "") -> bytes:
    """ZIP with captions, prompts, meta — reuse pattern from app build_pack_zip_bytes."""
    import io
    import zipfile

    slides = result.get("slides") or []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("captions_meta.txt", result.get("ig_caption") or "")
        zf.writestr("captions_tiktok.txt", result.get("tiktok_caption") or "")
        zf.writestr("captions_pinterest.txt", result.get("pinterest_caption") or "")
        zf.writestr("captions_youtube.txt", result.get("youtube_caption") or "")
        parts = []
        for i, s in enumerate(slides, start=1):
            parts.append(
                f"=== slide{i} ===\n"
                f"Title: {s.get('title', '')}\n"
                f"Body: {s.get('body', '')}\n"
                f"Prompt:\n{s.get('image_prompt', '')}"
            )
        zf.writestr("prompts.txt", "\n\n".join(parts))
        vb = result.get("video_beats")
        if isinstance(vb, dict) and vb.get("beats"):
            try:
                from video_prompts import format_video_prompts_txt
                zf.writestr(
                    "video_prompts.txt",
                    format_video_prompts_txt(vb, topic=result.get("topic_en") or ""),
                )
            except Exception:
                pass
            meta_vb = vb
        else:
            meta_vb = None
        vu = result.get("video_unified")
        meta_vu = None
        if isinstance(vu, dict) and vu.get("prompt_en"):
            try:
                from video_prompts import format_unified_video_txt
                zf.writestr(
                    "video_unified.txt",
                    format_unified_video_txt(vu, topic=result.get("topic_en") or ""),
                )
            except Exception:
                pass
            meta_vu = vu
        meta = {
            "type": "content",
            "topic_key": result.get("topic_key"),
            "topic_en": result.get("topic_en"),
            "slide_count": result.get("slide_count"),
            "aspect": aspect_ratio,
            "lang_output": result.get("lang") or "en",
        }
        if meta_vb:
            meta["video_beats"] = meta_vb
        if meta_vu:
            meta["video_unified"] = meta_vu
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return buf.getvalue()
