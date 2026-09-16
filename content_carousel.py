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
        "person appearance light-to-olive Mediterranean/European adult, natural look; "
        "do not default to unrelated ethnicity. If no person body is shown, ignore skin/ethnicity language."
    ),
    "diverse": (
        "If a person body is visible (legs/torso from the waist down or partial figure only): "
        "person appearance naturally diverse adults appropriate to everyday EU street/"
        "footwear content; vary across slides; avoid stereotypes. "
        "If no person body is shown, ignore skin/ethnicity language."
    ),
    "no_face": (
        "CRITICAL: No identifiable face, no portrait framing. Crop strictly below the chin; "
        "no partial face at the frame edge. Composition must prioritize footwear/legs/hands/props only. "
        "Do NOT describe facial features or head-and-shoulders portrait."
    ),
}


def appearance_clause(key: str) -> str:
    """Return English appearance clause for key, or empty for auto/unknown."""
    k = (key or "auto").strip().lower()
    return APPEARANCE_CLAUSES.get(k, "")


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
) -> dict[str, Any]:
    """Deterministic soft-discovery fallback if Gemini fails.

    Slides form one continuous mini-story; each body teaches from that slide's image
    and states why the visual/tip is useful.
    """
    # Continuous arc: hook problem/scene -> steps that continue -> soft CTA/takeaway
    templates = [
        (
            "Tired feet after long days?",
            "That end-of-day ache often starts with shoes that never get a quick check. Spotting the problem in this quiet scene is the first useful step.",
            f"Soft editorial photo of empty everyday sneakers by a window at dusk, calm tired-day mood, educational, no logos as hero text, no celebrities. Clean short typography overlay matching the title: Tired feet after long days? Soft-discovery, not an ad. Photorealistic 8k {ar_flag}",
        ),
        (
            "Start with a two-hour check",
            "After two hours on your feet, notice midsole compression, upper creases, and toe pinch. This close-up check shows what to fix next — before soreness becomes a habit.",
            f"Close-up lifestyle still of sneaker midsole and upper on a clean desk, natural light, Kinfolk aesthetic, educational. Clean short typography overlay matching: Start with a two-hour check. Soft-discovery, not hard sell. Photorealistic 8k {ar_flag}",
        ),
        (
            "Clean gently, dry slowly",
            "Once the pair is worth keeping, use a soft brush and mild soap where safe, then air-dry away from radiators. Gentle cleaning protects materials so cushioning lasts longer.",
            f"Hands gently brushing a sneaker with a soft brush, towels nearby, calm tutorial feel, no brand hard-sell. Clean short typography overlay matching: Clean gently, dry slowly. Photorealistic 8k {ar_flag}",
        ),
        (
            "Rotate and let foam rebound",
            "Alternating pairs between wear days lets midsole foam rebound and keeps odor down. Resting shoes on the shelf is a free comfort upgrade you can see.",
            f"Two pairs of everyday sneakers side by side on a shelf, soft daylight, organized storage, educational still life. Clean short typography overlay matching: Rotate and let foam rebound. Photorealistic 8k {ar_flag}",
        ),
        (
            "Match material to the day",
            "Mesh breathes on warm walks, suede needs rain care, foam cushions standing hours. Matching what you see in the shoe to how you use it breaks the same tired-feet loop.",
            f"Macro texture still of mesh and suede in one calm frame, soft studio light, educational product photography. Clean short typography overlay matching: Match material to the day. Photorealistic 8k {ar_flag}",
        ),
        (
            "Save this tip for later",
            "You now have a simple loop: check, care, rotate, match materials. Save this carousel and follow for the next calm footwear tip.",
            f"Minimal flat-lay of sneakers with notebook and coffee, negative space for soft CTA, calm discovery mood, no celebrity, no hard sell. Clean short typography overlay matching: Save this tip for later. Photorealistic 8k {ar_flag}",
        ),
    ]
    slides = []
    for i in range(slide_count):
        title, body, prompt = templates[i % len(templates)]
        if i == 0:
            title = "A calmer way to think about sneakers"
            body = (
                f"Today's focus: {topic_en}. This opening scene sets a common problem you can ease "
                "with small soft habits — no hard sell."
            )
            prompt = (
                f"Soft editorial photo of empty everyday sneakers by a window, calm morning light, "
                f"educational mood, no logos as hero text, no celebrities. Clean short typography overlay "
                f"matching: A calmer way to think about sneakers. Soft-discovery, not an ad. "
                f"Photorealistic 8k {ar_flag}"
            )
        elif i == slide_count - 1:
            title = "Follow for the next tip"
            body = (
                "Takeaway: small checks and gentle care compound. "
                "Explore more calm footwear advice anytime — soft discovery, not an ad."
            )
            prompt = (
                f"Minimal flat-lay of sneakers with notebook and coffee, negative space for soft CTA, "
                f"calm discovery mood, no celebrity, no hard sell. Clean short typography overlay matching: "
                f"Follow for the next tip. Photorealistic 8k {ar_flag}"
            )
        slides.append({
            "title": title,
            "body": body,
            "image_prompt": append_appearance_clause(prompt, appearance),
        })
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
    models: Optional[list[str]] = None,
    warn: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """
    Call Gemini to produce ENGLISH-ONLY educational carousel content.

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
            )
        else:
            appearance_block = (
                "\nPERSON / MODEL APPEARANCE (apply ONLY if a person body is visible from the legs/"
                "waist; soft creative control for brand consistency; do not force a face into frame):\n"
                f"{_appearance_clause}\n"
                "Include this guidance naturally in each image_prompt (English).\n"
            )

    models_to_try = models or ["gemini-3.6-flash", "gemini-2.5-flash"]

    insight_block = ""
    if insight_context and str(insight_context).strip():
        insight_block = (
            "\nEXTRA MARKET INSIGHT TO SOFTLY REFLECT (do not invent stats; keep soft-discovery):\n"
            + str(insight_context).strip()
            + "\n"
        )

    sys_instruction = (
        "You are an expert educational footwear content writer in the style of calm "
        "discovery accounts (like sneakers.loft vibe): soft tips, not ads. "
        "ALL output must be ENGLISH ONLY. NEVER use celebrity athlete names. "
        "NEVER use hard-sell verbs (buy, shop, order, purchase). "
        "Prefer soft CTAs: follow for next tip, save this, explore more. "
        "CRITICAL STORY RULE: titles and bodies across all slides MUST read as ONE continuous "
        "narrative when read in order — slide 1 hooks a problem/scene, middle slides continue "
        "with steps/tips that follow from the previous slide (not random disconnected tips), "
        "last slide is a soft CTA / takeaway. "
        "CRITICAL IMAGE-TEXT LOCK: for every slide, title + body must describe and teach from "
        "what that slide's image_prompt depicts; the body must state the practical usefulness "
        "of that visual (what the viewer learns and why the tip helps). "
        "When a person/model appearance guidance is provided in the user prompt, reflect it "
        "consistently in every image_prompt. "
        "HARD IMAGE RULES for every image_prompt: NEVER render Slide X of Y, LEARN MORE buttons, "
        "carousel dots, app UI chrome, or invented badges/seals (OFFICIAL SELECTION, BESTSELLER, "
        "SNEAKERNESS) unless the user prompt explicitly requests that exact text. "
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
        "is running/track/curb-after-run; keep shift wording only for standing/work scenes. "
        "If no_face: never write portrait/face/headshot language; prioritize shoes/legs/hands/props."
    )

    script_prompt = f"""Create an educational Instagram/TikTok CONTENT CAROUSEL (not a product ad) about:
TOPIC: {topic_en}

CRITICAL CONSTRAINTS:
1. ALL OUTPUT MUST BE IN ENGLISH ONLY (titles, bodies, captions, image prompts).
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
6. Each slide needs short on-screen title + short body (readable on phone).
7. Each slide needs an image generation prompt in Nano Banana / Midjourney style: soft-discovery aesthetic, photorealistic or clean editorial, calm lighting, no hard-sell product packaging UI, no celebrity faces.
8. Optional short on-image overlay: image_prompt MAY include the SAME short title (or a 2-5 word overlay matching the title) as clean typography on the image. Prefer soft-discovery aesthetic. Keep NO "Slide X of Y", NO carousel numbering, NO carousel dots, NO LEARN MORE buttons, NO app UI chrome, NO invented OFFICIAL/BESTSELLER/SNEAKERNESS seals, NO hard sell.
9. Append aspect flag exactly as: {ar_flag} at the end of every image_prompt.
10. By default NEVER put SNEAKERNESS.EU / sneakerness / any website on the image. If an explicit watermark/domain is provided in this prompt: REQUIRED — render watermark EXACTLY ONCE using that exact user string only (ban any second tiny/micro duplicate, shortened copy, or extra corner mark; do not also add "sneakerness" when the user typed a full domain) as clearly phone-readable bottom-right watermark (~7–9% of image height, clean sans-serif, strong contrast — must be easily readable at a glance on a phone screen; not microscopic; not faint grey on busy background; subtle dark/light shadow OK), ~2–3% margin from edges — readable on a phone without zoom; no giant headline, not dominating the shoe, no Explore CTA sentence on image. Overlay/CTA texts must NOT contain any website/domain — the watermark is the only on-image site text. MUST include the domain once naturally in ig/tiktok/pinterest/youtube captions when provided; do not force site into every image_prompt.
11. Overlay text must match the depicted scene (do not put work-shift / "long shifts" wording on a running / track / curb-after-run scene; keep work wording only for standing/work scenes).
12. If HARD APPEARANCE / no_face is active: crop strictly below the chin; no partial face at frame edge; write image_prompt as lifestyle/product framing with shoes/legs/hands/props - never portrait, face close-up, looking at camera, or headshot language.
{insight_block}{appearance_block}
Return strict JSON:
{{
  "slides": [
    {{
      "title": "short on-screen title EN",
      "body": "short body EN — continues the story AND states why the image/tip is useful",
      "image_prompt": "full EN image gen prompt (optional clean title overlay) ending with {ar_flag}"
    }}
  ],
  "ig_caption": "optional Instagram caption EN + light hashtags",
  "tiktok_caption": "optional TikTok caption EN + FYP hashtags",
  "pinterest_caption": "optional Pinterest pin description EN - 2-4 discovery/SEO sentences; optional 3-5 hashtags",
  "youtube_caption": "optional YouTube Shorts/community caption EN - strong hook first line; 2-4 sentences; soft CTA; fewer hashtags"
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
                    prompt = append_appearance_clause(prompt, _appearance_key)
                    normalized.append(
                        {
                            "title": str(s.get("title") or "").strip() or "Tip",
                            "body": str(s.get("body") or "").strip() or "",
                            "image_prompt": prompt,
                        }
                    )
                while len(normalized) < slide_count:
                    fb = _fallback_carousel(topic_en, slide_count, ar_flag, _appearance_key)
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
                }
        except Exception as e:
            if warn:
                try:
                    warn(f"{model_item}: {e}")
                except Exception:
                    pass
            time.sleep(1)

    fb = _fallback_carousel(topic_en, slide_count, ar_flag, _appearance_key)
    fb["topic_en"] = topic_en
    fb["appearance"] = _appearance_key
    fb["topic_key"] = topic_key
    fb["slide_count"] = slide_count
    fb["ar_flag"] = ar_flag
    return fb


def build_content_txt(result: dict[str, Any]) -> str:
    """Plain-text export for download."""
    lines = [
        "========================================",
        "CONTENT CAROUSEL (EN)",
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
        meta = {
            "type": "content",
            "topic_key": result.get("topic_key"),
            "topic_en": result.get("topic_en"),
            "slide_count": result.get("slide_count"),
            "aspect": aspect_ratio,
            "lang_output": "en",
        }
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return buf.getvalue()
