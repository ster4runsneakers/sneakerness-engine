# -*- coding: utf-8 -*-
"""Content carousel module for Sneakerness Studio (educational soft-discovery)."""
from __future__ import annotations

import json
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


def _fallback_carousel(topic_en: str, slide_count: int, ar_flag: str) -> dict[str, Any]:
    """Deterministic soft-discovery fallback if Gemini fails."""
    slides = []
    templates = [
        (
            "Tired feet after long days?",
            "Small habit changes and smarter cushioning choices can ease end-of-day soreness.",
            f"Soft editorial photo of empty sneakers by a window, calm morning light, educational mood, no logos as hero text, no celebrities. Overlay vibe for: Tired feet after long days? Soft-discovery, not an ad. Photorealistic 8k {ar_flag}",
        ),
        (
            "Start with a quick check",
            "Look at midsole compression, upper creases, and how your toes feel after two hours.",
            f"Close-up lifestyle still of sneaker midsole and upper on a clean desk, natural light, Kinfolk aesthetic, educational. Soft-discovery, not hard sell. Photorealistic 8k {ar_flag}",
        ),
        (
            "Clean gently, dry slowly",
            "Skip harsh heat. Soft brush, mild soap where safe, air dry away from radiators.",
            f"Hands gently brushing a sneaker with a soft brush, towels nearby, calm tutorial feel, no brand hard-sell. Photorealistic 8k {ar_flag}",
        ),
        (
            "Rotate and rest pairs",
            "Alternating pairs lets foam rebound and keeps odor down without heavy products.",
            f"Two pairs of everyday sneakers side by side on a shelf, soft daylight, organized storage, educational still life. Photorealistic 8k {ar_flag}",
        ),
        (
            "Save this tip for later",
            "Follow for the next soft tip — explore more calm footwear advice anytime.",
            f"Minimal flat-lay of sneakers with notebook and coffee, negative space for soft CTA, calm discovery mood, no celebrity, no hard sell. Photorealistic 8k {ar_flag}",
        ),
        (
            "Materials matter day to day",
            "Mesh breathes, suede needs care in rain, foam cushions standing hours — match the use.",
            f"Macro texture collage feel of mesh and suede (tasteful single frame), soft studio light, educational product photography. Photorealistic 8k {ar_flag}",
        ),
    ]
    for i in range(slide_count):
        title, body, prompt = templates[i % len(templates)]
        if i == 0:
            title = "A calmer way to think about sneakers"
            body = f"Today's focus: {topic_en}. Soft tips — no hard sell."
        if i == slide_count - 1:
            title = "Follow for the next tip"
            body = "Explore more calm footwear advice — soft discovery, not an ad."
        slides.append({"title": title, "body": body, "image_prompt": prompt})
    return {
        "slides": slides,
        "ig_caption": (
            f"Soft tip thread: {topic_en}. Save for later — educational, not a sales pitch. "
            "#Sneakerness #SneakerCare #SoftDiscovery"
        ),
        "tiktok_caption": (
            f"{topic_en} — quick educational carousel. Follow for the next tip 👟 "
            "#Sneakerness #SneakerTips #FootwearEducation #FYP"
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
    models: Optional[list[str]] = None,
    warn: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """
    Call Gemini to produce ENGLISH-ONLY educational carousel content.

    Returns dict with:
      slides: [{title, body, image_prompt}, ...]
      ig_caption, tiktok_caption
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
        "Prefer soft CTAs: follow for next tip, save this, explore more."
    )

    script_prompt = f"""Create an educational Instagram/TikTok CONTENT CAROUSEL (not a product ad) about:
TOPIC: {topic_en}

CRITICAL CONSTRAINTS:
1. ALL OUTPUT MUST BE IN ENGLISH ONLY (titles, bodies, captions, image prompts).
2. Soft-discovery / educational advice feel — NOT hard sell. No "buy", "shop", "order", "purchase".
3. STRICTLY NO celebrity names (no Jordan, Kobe, LeBron, Messi, Ronaldo, Curry, etc.).
4. Story arc across exactly {slide_count} slides: hook → tips/steps or list → soft CTA (follow for next tip / explore more).
5. Each slide needs short on-screen title + short body (readable on phone).
6. Each slide needs an image generation prompt in Nano Banana / Midjourney style: soft-discovery aesthetic, photorealistic or clean editorial, calm lighting, no hard-sell product packaging UI, no celebrity faces.
7. Append aspect flag exactly as: {ar_flag} at the end of every image_prompt.
8. Image prompts: STRICTLY NO text like 'Slide X of Y', NO carousel numbering, NO UI chrome — only optional short overlay text if helpful.
{insight_block}
Return strict JSON:
{{
  "slides": [
    {{
      "title": "short on-screen title EN",
      "body": "short body EN",
      "image_prompt": "full EN image gen prompt ending with {ar_flag}"
    }}
  ],
  "ig_caption": "optional Instagram caption EN + light hashtags",
  "tiktok_caption": "optional TikTok caption EN + FYP hashtags"
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
                    normalized.append(
                        {
                            "title": str(s.get("title") or "").strip() or "Tip",
                            "body": str(s.get("body") or "").strip() or "",
                            "image_prompt": prompt,
                        }
                    )
                while len(normalized) < slide_count:
                    fb = _fallback_carousel(topic_en, slide_count, ar_flag)
                    normalized.append(fb["slides"][len(normalized)])
                return {
                    "slides": normalized[:slide_count],
                    "ig_caption": str(data.get("ig_caption") or "").strip(),
                    "tiktok_caption": str(data.get("tiktok_caption") or "").strip(),
                    "topic_en": topic_en,
                    "topic_key": topic_key,
                    "slide_count": slide_count,
                    "ar_flag": ar_flag,
                }
        except Exception as e:
            if warn:
                try:
                    warn(f"{model_item}: {e}")
                except Exception:
                    pass
            time.sleep(1)

    fb = _fallback_carousel(topic_en, slide_count, ar_flag)
    fb["topic_en"] = topic_en
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
