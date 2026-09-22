# app.py - Sneaker Image Studio (Dynamic Creative Edition)
import os
import json
import time
import random
import hashlib
import io
import zipfile
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import streamlit as st
from google import genai
from google.genai import types

import product_history  # noqa: F401
from product_history import load_history, add_entry, delete_entry, get_entry
from pathlib import Path
from i18n import t, pick_lang_text
import content_carousel
import usage
from content_carousel import (
    TOPIC_KEYS,
    APPEARANCE_KEYS,
    appearance_clause,
    append_appearance_clause,
    topic_label,
    weekly_suggestions,
    generate_content_carousel,
    build_content_txt,
    build_content_zip_bytes,
)
import video_prompts
from video_prompts import build_grok_video_beats, format_video_prompts_txt, ensure_video_beats

st.set_page_config(page_title="Sneaker Image Studio", page_icon="👟", layout="centered")

# Light UI polish (inject once after page_config)
_UI_CSS = """
<style>
/* Main canvas: slightly roomier, product-like feel */
.block-container {
  max-width: 820px;
  padding-top: 1.4rem;
  padding-bottom: 2.5rem;
}
/* Dark sidebar — readable with Streamlit dark theme light text */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
  border-right: 1px solid #1f2937;
}
section[data-testid="stSidebar"] > div {
  padding-top: 0.75rem;
}
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
  color: #e5e7eb !important;
}
/* Primary / default buttons */
div.stButton > button {
  border-radius: 10px;
  border: 1px solid #0f766e;
  background: linear-gradient(180deg, #14b8a6 0%, #0d9488 100%);
  color: #ffffff;
  font-weight: 600;
  transition: filter 0.15s ease, box-shadow 0.15s ease;
  box-shadow: 0 1px 2px rgba(15, 118, 110, 0.25);
}
div.stButton > button:hover {
  filter: brightness(1.05);
  box-shadow: 0 2px 8px rgba(13, 148, 136, 0.35);
  border-color: #0f766e;
  color: #ffffff;
}
div.stButton > button:focus {
  box-shadow: 0 0 0 2px rgba(45, 212, 191, 0.45);
}
/* Dark expanders — body text readable on dark theme */
div[data-testid="stExpander"] {
  border: 1px solid #334155;
  border-radius: 12px;
  background: #111827;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
  overflow: hidden;
  color: #e5e7eb;
}
div[data-testid="stExpander"] details {
  border: none !important;
}
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] p,
div[data-testid="stExpander"] span,
div[data-testid="stExpander"] .stMarkdown,
div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] {
  color: #e5e7eb !important;
}
/* Product badge under title */
.sis-product-badge {
  display: inline-block;
  margin: -0.35rem 0 0.85rem 0;
  padding: 0.2rem 0.7rem;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: #0f766e;
  background: #ecfdf5;
  border: 1px solid #99f6e4;
}
/* Optional: hide Streamlit chrome (common, low-risk) */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
</style>
"""
st.markdown(_UI_CSS, unsafe_allow_html=True)


if "lang" not in st.session_state:
    st.session_state["lang"] = "el"

# Language switcher (sidebar top) — before other UI so lang is ready
with st.sidebar:
    _lang_options = ["English", "Ελληνικά"]
    _lang_codes = {"English": "en", "Ελληνικά": "el"}
    _code_to_label = {"en": "English", "el": "Ελληνικά"}
    _cur = st.session_state.get("lang", "el")
    _cur_label = _code_to_label.get(_cur, "Ελληνικά")
    _picked = st.selectbox(
        t("language_label", st.session_state.get("lang", "el")),
        _lang_options,
        index=_lang_options.index(_cur_label) if _cur_label in _lang_options else 1,
        key="lang_select_label",
    )
    _new_lang = _lang_codes.get(_picked, "el")
    st.session_state["_lang_switch_pending"] = (
        st.session_state.get("lang", "el") != _new_lang
    )
    st.session_state["_lang_switch_from"] = st.session_state.get("lang", "el")
    st.session_state["lang"] = _new_lang

lang = st.session_state["lang"]

# Free / Pro plan badge + unlock (sidebar)
usage.sync_session(st.session_state)
with st.sidebar:
    st.markdown("---")
    if usage.is_pro(st.session_state):
        st.markdown(f"**{t('plan_pro', lang)}**")
    else:
        st.markdown(f"**{t('plan_free', lang)}**")
        _u_used, _u_lim = usage.usage_counts(st.session_state)
        st.caption(t("usage_line", lang, used=_u_used, limit=_u_lim))
        st.markdown(f"[{t('go_pro', lang)}]({usage.LEMON_CHECKOUT_URL})")
    _pro_code = st.text_input(
        t("unlock_placeholder", lang),
        value="",
        key="pro_code_input",
        type="password",
    )
    if st.button(t("unlock_pro", lang), key="unlock_pro_btn", use_container_width=True):
        if usage.try_unlock(st.session_state, _pro_code):
            st.success(t("unlock_ok", lang))
            st.rerun()
        else:
            st.error(t("unlock_bad", lang))


st.title(t("title", lang))
st.markdown(
    f'<span class="sis-product-badge">{t("product_badge", lang)}</span>',
    unsafe_allow_html=True,
)
st.subheader(t("subheader", lang))

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error(t("api_key_missing", lang))
    st.stop()

client = genai.Client(api_key=api_key)

# 1. DEFINITIONS
CATEGORY_BADGES = [
    "REVIEWED ★★★★★", 
    "DAILY APPROVED ★★★★★", 
    "CUSHIONING APPROVED", 
    "RUNNING TECH", 
    "HERITAGE DROP", 
    "STREET CLASSIC",
    "ULTRA COMFORT ★★★★★",
    "BESTSELLER SELECTION"
]

AUTHENTICITY_TAGS = [
    "100% AUTHENTIC GUARANTEED",
    "LIMITED EDITION DROP",
    "PREMIUM COMFORT EDITION",
    "OFFICIAL SNEAKERNESS SELECTION",
    "ORIGINAL HERITAGE DROP",
    "VERIFIED AUTHENTIC"
]

# 2. HELPER FUNCTIONS
def auto_analyze_shoe(brand_name, model_name, image_bytes=None, mime_type="image/jpeg", vibe="auto"):
    """Detect shoe + invent a scene. Fallbacks use pick_scene_pack (never the old Kinfolk/worker triple)."""
    vibe = vibe or st.session_state.get("scene_vibe_val", "auto") or "auto"
    if not image_bytes:
        pack = pick_scene_pack(brand_name, model_name, "", vibe=vibe, stable=True)
        return {
            "brand": brand_name if brand_name else "",
            "model": model_name if model_name else "",
            "specs": "",
            "colorway": "",
            "env_desc": pack["env_desc"],
            "props_desc": pack["props_desc"],
            "problem_desc": pack["problem_desc"],
        }

    prompt_search = """Examine the provided sneaker image with extreme precision.

CRITICAL IDENTIFICATION & DYNAMIC SCENE CREATION RULES:
1. "brand": Identify the EXACT footwear brand name visible on the shoe or tongue (e.g., HOKA, Puma, Nike, Adidas, New Balance, Brooks).
2. "model": Identify the EXACT shoe model name based on visible text. Check tongue, lateral side, or heel label carefully.
3. "colorway": Describe the exact observed colors in the image (e.g., "Cream / Red / Navy Blue").
4. "specs": Technical specifications specific to this exact model (e.g., Vibram Megagrip outsole, dual-density EVA midsole, breathable mesh upper).
5. "env_desc": Write a detailed, hyper-relevant 1-sentence English description of the IDEAL background environment tailored to this shoe's archetype.
6. "props_desc": Write a 1-sentence English list of 3-4 EDC props placed on the surface next to the shoe that match its lifestyle/vibe.
7. "problem_desc": Write a 1-sentence English description of a realistic human pain-point/problem scene matching this shoe's category. Prefer legs/feet/shoes framing; faces not required.

HARD BANS (do NOT default to these unless the shoe truly matches that exact vibe, and even then invent a NEW wording):
- tired worker sitting on stairs / sore feet with work boots
- Kinfolk magazine, ceramic cappuccino, brass keys, succulent plant
- generic "minimalist concrete urban street with natural daylight"

REQUIREMENTS:
- env_desc, props_desc, and problem_desc MUST match the shoe archetype (road running, trail, gym, street fashion, rainy commute, barista/retail shift, airport travel, post-run recovery, basketball court, etc.).
- Be DISTINCT from the banned defaults above.
- Invent a NEW scene in the spirit of these short EXAMPLE packs — do NOT copy examples verbatim:
  * Road running: outdoor track at dawn mist + GPS watch / race bib / flask — calves after tempo on the curb
  * Trail: muddy pine singletrack + poles / map / gaiters — mud-caked shoes paused on a rock
  * Gym: neon rubber-mat floor + chalk / straps / bands — feet planted under a squat rack
  * Rainy commute: wet metro tiles + umbrella / transit card / thermos — shoes beading rain on the platform
  * Boutique street: cobblestone shopfront light + crossbody / Polaroid / iced matcha — cropped stylish legs on a ledge
  * Airport travel: departure hall daylight + boarding pass / neck pillow / carry-on — legs stretched at the gate
  * Post-run recovery: curb outside a track at dusk + ice pack / recovery drink / massage ball — shoes half-off on the curb
  * Cafe barista shift: warm pendant-lit counter + milk pitcher / tickets / bar towel — standing-shift legs behind the bar
- Emphasize VARIETY across regenerations: same shoe analyzed again should be able to yield a different but still archetype-true scene.

Return ONLY a valid, raw JSON object matching this schema:
{
  "brand": "Detected Brand",
  "model": "Detected Model",
  "specs": "Technical features...",
  "colorway": "Detected colorway...",
  "env_desc": "Custom environmental background description...",
  "props_desc": "Custom EDC props list...",
  "problem_desc": "Custom human problem scene (legs/shoes OK, no face required)..."
}"""

    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        prompt_search
    ]

    models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]

    for model_item in models_to_try:
        try:
            res = client.models.generate_content(
                model=model_item,
                contents=contents
            )

            if res and res.text:
                clean_txt = res.text.strip()
                if clean_txt.startswith("```json"):
                    clean_txt = clean_txt[7:]
                if clean_txt.startswith("```"):
                    clean_txt = clean_txt[3:]
                if clean_txt.endswith("```"):
                    clean_txt = clean_txt[:-3]
                clean_txt = clean_txt.strip()

                data = json.loads(clean_txt)
                if not isinstance(data, dict):
                    raise ValueError("analyze JSON was not an object")
                brand_out = data.get("brand") or brand_name or ""
                model_out = data.get("model") or model_name or ""
                specs_out = data.get("specs") or ""
                env_out = data.get("env_desc") or ""
                props_out = data.get("props_desc") or ""
                problem_out = data.get("problem_desc") or ""
                if scene_matches_banned_defaults(env_out, props_out, problem_out):
                    pack = pick_scene_pack(brand_out, model_out, specs_out, vibe=vibe)
                    data["env_desc"] = pack["env_desc"]
                    data["props_desc"] = pack["props_desc"]
                    data["problem_desc"] = pack["problem_desc"]
                return data
        except Exception as e:
            st.warning(t("model_failed", st.session_state.get("lang", "el"), model=model_item, error=str(e)))
            time.sleep(1)

    pack = pick_scene_pack(brand_name, model_name, "", vibe=vibe, stable=True)
    return {
        "brand": "",
        "model": "",
        "specs": "",
        "colorway": "",
        "env_desc": pack["env_desc"],
        "props_desc": pack["props_desc"],
        "problem_desc": pack["problem_desc"],
    }


def safe_generate_ad_copy(brand_name, model_name, colorway_text, materials, watermark, lang="el", goal="auto", insight_context=""):
    # Ασπίδα αφαίρεσης ευαίσθητων λέξεων
    unsafe_keywords = ["kobe", "jordan", "lebron", "messi", "ronaldo", "curry"]
    clean_model_name = model_name
    for word in unsafe_keywords:
        if word in clean_model_name.lower():
            clean_model_name = clean_model_name.lower().replace(word, "signature pro")

    goal_angles = {
        "auto": "Let the shoe specs guide the angle; prefer soft comfort/discovery if unclear.",
        "comfort": "Angle: all-day comfort, cushioning, standing shifts, fatigue relief — soft discovery, no hard sell.",
        "wide_fit": "Angle: wide fit / toe box room without orthopedic look — soft discovery, no hard sell.",
        "style": "Angle: street style, silhouette, colorway aesthetic — soft discovery, no hard sell.",
        "rain_care": "Angle: rain protection, suede/mesh care, autumn maintenance — educational soft discovery, no hard sell.",
    }
    goal_key = (goal or "auto").strip().lower()
    if goal_key not in goal_angles:
        goal_key = "auto"
    goal_instruction = goal_angles[goal_key]
    insight_block = ""
    if insight_context and str(insight_context).strip():
        insight_block = (
            "\nEXTRA MARKET INSIGHT TO SOFTLY REFLECT (do not invent stats; keep soft-discovery):\n"
            + str(insight_context).strip()
            + "\n"
        )


    wm_clean = (watermark or "").strip()
    # Domain belongs primarily in captions; image overlays must not force site/CTA-with-URL.
    if wm_clean:
        caption_site_rule_el = (
            f"REQUIRED: Include site/domain '{wm_clean}' exactly once, naturally, in EACH of "
            f"meta_caption, tiktok_caption, pinterest_caption, and youtube_caption."
        )
        caption_site_rule_en = (
            f"REQUIRED: Include site/domain '{wm_clean}' exactly once, naturally, in EACH of "
            f"meta_caption, tiktok_caption, pinterest_caption, and youtube_caption."
        )
        image_overlay_rule_el = (
            "Image overlays (hook/body/cta/slide texts) must NOT include website URLs, domain strings, "
            "or 'Explore… at …' / 'Μάθε περισσότερα στο …' site CTAs. Soft CTA without a URL is OK."
        )
        image_overlay_rule_en = (
            "Image overlays (hook/body/cta/slide texts) must NOT include website URLs, domain strings, "
            "or 'Explore… at …' / 'Discover more at …' site CTAs. Soft CTA without a URL is OK."
        )
        site_for_prompt = wm_clean
    else:
        caption_site_rule_el = (
            "Do NOT invent a website/domain in captions; leave site out unless the user provided one."
        )
        caption_site_rule_en = (
            "Do NOT invent a website/domain in captions; leave site out unless the user provided one."
        )
        image_overlay_rule_el = (
            "Image overlays must NOT include any website, brand-store URL, or SNEAKERNESS.EU text."
        )
        image_overlay_rule_en = (
            "Image overlays must NOT include any website, brand-store URL, or SNEAKERNESS.EU text."
        )
        site_for_prompt = "(none — do not invent a site)"

    if lang == "el":
        lang_name = "Greek (Ελληνικά)"
        sys_instruction = (
            "You are an expert e-commerce copywriter specializing in soft-sell, educational, "
            "and discovery-focused footwear ad copy and engaging social media posts in Greek (Ελληνικά). "
            "NEVER use celebrity athlete names in your text overlays. "
            "Write ALL user-facing copy in natural, fluent Modern Greek."
        )
        script_prompt = f"""Write ALL ad assets and copy in GREEK (Ελληνικά) for {brand_name} {clean_model_name} in {colorway_text} ({materials}) for website {site_for_prompt}.

CRITICAL CONSTRAINTS:
1. ALL OUTPUT MUST BE IN GREEK (Ελληνικά). Do not use English for hooks, body, CTA, captions, or slide texts.
2. DO NOT use hard-sell verbs like "αγόρασε", "αγορά", "παράγγειλε", "buy", "shop", "order", "purchase".
3. Use soft discovery CTAs in overlays WITHOUT forcing a URL. Put the domain only in captions when provided.
4. STRICTLY DO NOT include celebrity names or restricted player names in any text or overlay.
5. {image_overlay_rule_el}
6. {caption_site_rule_el}

STORY GOAL / ANGLE: {goal_instruction}
{insight_block}
Return strict JSON with keys:
1. "hook": Image top text in Greek, max 10 words.
2. "body": Image mid text in Greek, max 10 words.
3. "cta": Image bottom soft CTA in Greek WITHOUT any website/URL/domain, max 8 words. Soft discovery only.
4. "meta_caption": Greek Facebook/Instagram caption.
5. "tiktok_caption": Short Greek TikTok caption + 4 FYP hashtags.
6. "hashtags_meta": 8-10 trending hashtags (Greek or bilingual OK).
7. "pinterest_caption": Greek Pinterest pin description — 2–4 short discovery/SEO-friendly sentences (light keyword phrases OK, not spammy); optional 3–5 hashtags at end.
8. "youtube_caption": Greek YouTube Shorts/community description — first line a strong hook; then 2–4 sentences on comfort/use; soft CTA; fewer hashtags than TikTok; MUST include the site/domain once naturally when the caption-site rule requires it.
9. "slide1_text": Text overlay for Slide 1 in Greek.
10. "slide2_text": Text overlay for Slide 2 in Greek.
11. "slide3_text": Soft CTA text overlay for Slide 3 in Greek WITHOUT website/URL/domain.
"""
        fallback = {
            "hook": f"Κουράστηκες από κούραση στα πόδια; Ανακάλυψε {brand_name} {clean_model_name}.",
            "body": "Σχεδιασμένο να απορροφά τους κραδασμούς και να στηρίζει τη στάση όλη μέρα.",
            "cta": "Μάθε περισσότερα.",
            "meta_caption": (f"Οι πολλές ώρες όρθιος δεν χρειάζεται να επιβαρύνουν τα πόδια σου. Εξερεύνησε πώς το {brand_name} {clean_model_name} προσφέρει στήριξη στάσης." + (f" Μάθε περισσότερα στο {wm_clean}." if wm_clean else "")),
            "tiktok_caption": (f"Πώς αντιμετωπίζεις την κούραση στα πόδια; Δες την τεχνολογία πίσω από {brand_name} {clean_model_name}" + (f" στο {wm_clean}" if wm_clean else "") + f"! 👟 #Sneakerness #{brand_name}"),
            "hashtags_meta": f"#Sneakerness #{brand_name} #DailyComfort #FootwearTech",
            "pinterest_caption": (f"Ψάχνεις άνετα sneakers για πολλές ώρες όρθιος; Το {brand_name} {clean_model_name} συνδυάζει στήριξη στάσης και καθημερινή άνεση. Ιδανικό για δουλειά, περπάτημα και ήπια χρήση όλη μέρα." + (f" Ανακάλυψε περισσότερα στο {wm_clean}." if wm_clean else "") + f" #Sneakerness #{brand_name} #ComfortShoes #DailyComfort"),
            "youtube_caption": (f"Κούραση στα πόδια μετά από πολλές ώρες;\nΤο {brand_name} {clean_model_name} έχει σχεδιαστεί για άνεση και στήριξη στην καθημερινότητα. Δες πώς βοηθά σε ορθοστασία και ήπια χρήση." + (f" Εξερεύνησε περισσότερα στο {wm_clean}." if wm_clean else "") + f" #Sneakerness #{brand_name}"),
            "slide1_text": "Κουράστηκες από κούραση στα πόδια μετά από πολλές ώρες;",
            "slide2_text": f"Ανακάλυψε {brand_name} {clean_model_name}.",
            "slide3_text": "Δες τα χαρακτηριστικά.",
        }
    else:
        lang_name = "English"
        sys_instruction = (
            "You are an expert e-commerce copywriter specializing in soft-sell, educational, "
            "and discovery-focused footwear ad copy and engaging social media posts in English. "
            "NEVER use celebrity athlete names in your text overlays."
        )
        script_prompt = f"""Write ALL ad assets and copy in ENGLISH for {brand_name} {clean_model_name} in {colorway_text} ({materials}) for website {site_for_prompt}.

CRITICAL CONSTRAINTS:
1. ALL OUTPUT MUST BE IN ENGLISH.
2. DO NOT use hard-sell verbs like "buy", "shop", "order", "purchase".
3. Use soft discovery CTAs in overlays WITHOUT forcing a URL (e.g. "Discover more", "See the full specs"). Put the domain only in captions when provided.
4. STRICTLY DO NOT include celebrity names or restricted player names in any text or overlay.
5. {image_overlay_rule_en}
6. {caption_site_rule_en}

STORY GOAL / ANGLE: {goal_instruction}
{insight_block}
Return strict JSON with keys:
1. "hook": Image top text, max 10 words.
2. "body": Image mid text, max 10 words.
3. "cta": Image bottom soft CTA WITHOUT any website/URL/domain, max 8 words. Soft discovery only.
4. "meta_caption": English Facebook/Instagram caption.
5. "tiktok_caption": Short English TikTok caption + 4 FYP hashtags.
6. "hashtags_meta": 8-10 trending English hashtags.
7. "pinterest_caption": English Pinterest pin description — 2–4 short discovery/SEO-friendly sentences (light keyword phrases OK, not spammy); optional 3–5 hashtags at end.
8. "youtube_caption": English YouTube Shorts/community description — first line a strong hook; then 2–4 sentences on comfort/use; soft CTA; fewer hashtags than TikTok; MUST include the site/domain once naturally when the caption-site rule requires it.
9. "slide1_text": Text overlay for Slide 1.
10. "slide2_text": Text overlay for Slide 2.
11. "slide3_text": Soft CTA text overlay for Slide 3 WITHOUT website/URL/domain.
"""
        fallback = {
            "hook": f"Tired of foot fatigue after long hours? Discover {brand_name} {clean_model_name}.",
            "body": "Engineered to absorb impact and support posture all day.",
            "cta": "Discover more.",
            "meta_caption": (f"Long shifts and daily standing don't have to take a toll on your feet. Explore how {brand_name} {clean_model_name} delivers posture support." + (f" Learn more at {wm_clean}." if wm_clean else "")),
            "tiktok_caption": (f"How do you deal with foot fatigue? Check out the tech behind {brand_name} {clean_model_name}" + (f" at {wm_clean}" if wm_clean else "") + f"! 👟 #Sneakerness #{brand_name}"),
            "hashtags_meta": f"#Sneakerness #{brand_name} #DailyComfort #FootwearTech",
            "pinterest_caption": (f"Looking for comfortable sneakers for long hours on your feet? The {brand_name} {clean_model_name} blends posture support with everyday comfort. Great for work, walking, and all-day wear." + (f" Discover more at {wm_clean}." if wm_clean else "") + f" #Sneakerness #{brand_name} #ComfortShoes #DailyComfort"),
            "youtube_caption": (f"Tired of foot fatigue after long hours?\nThe {brand_name} {clean_model_name} is built for daily comfort and posture support. See how it helps with standing and light everyday use." + (f" Explore more at {wm_clean}." if wm_clean else "") + f" #Sneakerness #{brand_name}"),
            "slide1_text": "Tired of Foot Fatigue After Long Hours?",
            "slide2_text": f"Discover {brand_name} {clean_model_name}.",
            "slide3_text": "Explore the full specs.",
        }

    models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]
    for model_item in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_item,
                contents=script_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=sys_instruction,
                    response_mime_type="application/json"
                )
            )
            if response and response.text:
                return json.loads(response.text.strip())
        except Exception:
            time.sleep(1)

    return fallback


# --- Bilingual social captions (EL/EN cache; image prompts & Grok beats stay EN) ---
_CAPTION_FIELD_KEYS = (
    "meta_caption",
    "tiktok_caption",
    "hashtags_meta",
    "pinterest_caption",
    "youtube_caption",
)
_CONTENT_CAPTION_KEYS = (
    "ig_caption",
    "tiktok_caption",
    "pinterest_caption",
    "youtube_caption",
)
_CONTENT_WIDGET_KEYS = ("c_ig_cap", "c_tt_cap", "c_pin_cap", "c_yt_cap")


def _extract_caption_dict(ad_texts: dict | None) -> dict:
    ad_texts = ad_texts or {}
    return {k: (ad_texts.get(k) or "") for k in _CAPTION_FIELD_KEYS}


def _other_lang(lang: str) -> str:
    return "en" if (lang or "el").strip().lower() == "el" else "el"


def apply_captions_for_lang(lang: str) -> bool:
    """Copy captions_{lang} cache into loaded_* keys and reset caption widgets."""
    lang = (lang or "el").strip().lower()
    if lang not in ("el", "en"):
        lang = "el"
    cache = st.session_state.get(f"captions_{lang}")
    if not isinstance(cache, dict):
        return False
    for k in _CAPTION_FIELD_KEYS:
        st.session_state[f"loaded_{k}"] = cache.get(k, "") or ""
    st.session_state["results_lang"] = lang
    for _wk in ("hist_meta_ta", "hist_tt_ta", "hist_pin_ta", "hist_yt_ta"):
        st.session_state.pop(_wk, None)
    return True


def store_product_caption_side(lang: str, ad_texts: dict | None) -> None:
    lang = (lang or "el").strip().lower()
    if lang not in ("el", "en"):
        lang = "el"
    st.session_state[f"captions_{lang}"] = _extract_caption_dict(ad_texts)


def ensure_product_captions_for_lang(lang: str, *, allow_regenerate: bool = True) -> bool:
    """Apply cached captions for lang; optionally regenerate the missing side once."""
    lang = (lang or "el").strip().lower()
    if lang not in ("el", "en"):
        lang = "el"
    if apply_captions_for_lang(lang):
        return True
    if not allow_regenerate:
        return False
    if not st.session_state.get("show_loaded_pack"):
        return False
    brand = (st.session_state.get("brand_val") or "").strip()
    model = (st.session_state.get("model_val") or "").strip()
    if not brand or not model:
        return False
    colorway = st.session_state.get("colorway_val", "") or ""
    specs = st.session_state.get("specs_val", "") or ""
    watermark = st.session_state.get("watermark_val", "") or ""
    goal = st.session_state.get("goal_val", "auto") or "auto"
    insight = st.session_state.get("active_insight", "") or ""
    with st.spinner(t("generate_spinner", lang, lang_name=t("lang_name", lang))):
        ad_texts = safe_generate_ad_copy(
            brand,
            model,
            colorway,
            specs,
            watermark,
            lang=lang,
            goal=goal,
            insight_context=insight,
        )
    store_product_caption_side(lang, ad_texts)
    return apply_captions_for_lang(lang)


def _extract_content_captions(result: dict | None) -> dict:
    result = result or {}
    return {k: (result.get(k) or "") for k in _CONTENT_CAPTION_KEYS}


def _extract_content_slides_copy(result: dict | None) -> list:
    """Slide title/body only (image_prompt stays on the active content_result)."""
    slides = (result or {}).get("slides") or []
    out = []
    for s in slides:
        if not isinstance(s, dict):
            continue
        out.append({
            "title": (s.get("title") or ""),
            "body": (s.get("body") or ""),
        })
    return out


def store_content_lang_cache(lang: str, result: dict | None) -> None:
    lang = (lang or "el").strip().lower()
    if lang not in ("el", "en"):
        lang = "el"
    st.session_state[f"content_captions_{lang}"] = _extract_content_captions(result)
    st.session_state[f"content_slides_{lang}"] = _extract_content_slides_copy(result)


def apply_content_for_lang(lang: str) -> bool:
    """Swap content_result captions + slide title/body from bilingual caches; keep image_prompt EN."""
    lang = (lang or "el").strip().lower()
    if lang not in ("el", "en"):
        lang = "el"
    caps = st.session_state.get(f"content_captions_{lang}")
    slides_copy = st.session_state.get(f"content_slides_{lang}")
    cr = st.session_state.get("content_result")
    if not isinstance(cr, dict):
        return False
    if not isinstance(caps, dict) and not isinstance(slides_copy, list):
        return False
    if isinstance(caps, dict):
        for k in _CONTENT_CAPTION_KEYS:
            cr[k] = caps.get(k, "") or ""
    if isinstance(slides_copy, list) and slides_copy:
        base_slides = list(cr.get("slides") or [])
        merged = []
        for i, sc in enumerate(slides_copy):
            base = dict(base_slides[i]) if i < len(base_slides) and isinstance(base_slides[i], dict) else {}
            if isinstance(sc, dict):
                base["title"] = sc.get("title", "") or base.get("title", "")
                base["body"] = sc.get("body", "") or base.get("body", "")
            merged.append(base)
        if len(base_slides) > len(merged):
            merged.extend(base_slides[len(merged):])
        cr["slides"] = merged
    cr["lang"] = lang
    st.session_state["content_result"] = cr
    st.session_state["content_results_lang"] = lang
    for _wk in _CONTENT_WIDGET_KEYS:
        st.session_state.pop(_wk, None)
    n = len(cr.get("slides") or [])
    for i in range(1, n + 1):
        st.session_state.pop(f"c_title_{i}", None)
        st.session_state.pop(f"c_body_{i}", None)
    try:
        st.session_state["content_txt"] = build_content_txt(cr)
        st.session_state["content_zip"] = build_content_zip_bytes(
            cr, aspect_ratio=st.session_state.get("aspect_ratio_val", "1:1 (Square)")
        )
    except Exception:
        pass
    return True


def ensure_content_for_lang(lang: str, *, allow_regenerate: bool = True) -> bool:
    """Apply content bilingual cache; optionally regenerate missing side once."""
    lang = (lang or "el").strip().lower()
    if lang not in ("el", "en"):
        lang = "el"
    if apply_content_for_lang(lang):
        return True
    if not allow_regenerate:
        return False
    cr = st.session_state.get("content_result")
    if not isinstance(cr, dict):
        return False
    topic_key = cr.get("topic_key") or st.session_state.get("content_topic_key", "tips")
    topic_override = st.session_state.get("content_topic_override", "") or cr.get("topic_en", "") or ""
    try:
        slide_count = int(
            cr.get("slide_count")
            or len(cr.get("slides") or [])
            or st.session_state.get("content_slide_count_val", 5)
        )
    except (TypeError, ValueError):
        slide_count = 5

    def _warn(msg):
        try:
            st.warning(t("model_failed", lang, model="gemini", error=msg))
        except Exception:
            pass

    with st.spinner(t("generate_content_spinner", lang)):
        other = generate_content_carousel(
            client,
            topic_key=topic_key,
            topic_override=topic_override,
            slide_count=slide_count,
            aspect_ratio=st.session_state.get("aspect_ratio_val", "1:1 (Square)"),
            insight_context=st.session_state.get("active_insight", "") or "",
            appearance=st.session_state.get("appearance_val", "eu"),
            lang=lang,
            models=["gemini-3.6-flash", "gemini-2.5-flash"],
            warn=_warn,
        )
    old_slides = cr.get("slides") or []
    new_slides = other.get("slides") or []
    if old_slides and new_slides and len(old_slides) == len(new_slides):
        for i, ns in enumerate(new_slides):
            if isinstance(ns, dict) and isinstance(old_slides[i], dict):
                ip = old_slides[i].get("image_prompt")
                if ip:
                    ns["image_prompt"] = ip
        other["slides"] = new_slides
    for k in ("topic_key", "topic_en", "video_beats", "slide_count"):
        if cr.get(k) and not other.get(k):
            other[k] = cr.get(k)
    store_content_lang_cache(lang, other)
    return apply_content_for_lang(lang)



# 3. RESET & INITIALIZE SESSION STATE


def watermark_image_clause(watermark: str) -> str:
    """Image-prompt watermark guidance.

    Default: no website / brand-store / SNEAKERNESS.EU text on the image.
    If user provides a domain string: REQUIRED phone-readable bottom-right watermark
    with the literal domain embedded in the prompt — never a vague "if provided" line.
    Overlay/CTA texts must NOT contain website/domain (watermark is the only on-image site text).
    Captions (meta/tiktok/pinterest/youtube) must include the domain when set.
    """
    w = (watermark or "").strip()
    if not w:
        return (
            " By default NO website, brand-store URL, or SNEAKERNESS.EU / sneakerness "
            "text on the image."
        )
    return (
        f" REQUIRED on-image watermark text (exactly once, bottom-right): {w} "
        f"Render that exact string EXACTLY ONCE as clearly phone-readable text "
        f"(~7–9% of image height, clean sans-serif, strong contrast — must be easily readable at a glance on a phone screen; not microscopic; not faint grey on busy background; subtle dark/light shadow OK), "
        f"leaving ~2–3% margin from the edges — must be readable on a phone without zoom; "
        f"do not also add a shortened/brand-name copy such as 'sneakerness' if the user "
        f"typed a full domain; ban any second tiny/micro duplicate or extra corner mark; "
        f"no other site URLs, no Explore CTA on image, not a giant headline, not dominating "
        f"the shoe. Overlay/CTA texts must NOT contain any website/domain — the watermark "
        f"is the only on-image site text."
    )


def build_carousel_prompts(
    slide_count,
    *,
    brand,
    safe_model_name,
    colorway,
    key_materials,
    selected_env,
    selected_props,
    selected_problem,
    selected_tag,
    selected_badge,
    custom_watermark,
    ad_texts,
    negative_constraint,
    ar_flag,
    appearance_extra="",
):
    """Build 2-5 Nano Banana carousel prompts with a clear story arc."""
    _appx = f" {appearance_extra}" if (appearance_extra or "").strip() else ""
    _no_face = "No identifiable face" in (appearance_extra or "") or "no portrait framing" in (
        appearance_extra or ""
    ).lower()
    brand_lock = (
        f" Hero footwear must match: {brand} {safe_model_name} {colorway}. "
        f"Clearly recognizable {brand} footwear, correct model silhouette and typical branding cues "
        f"— do not substitute Nike/Adidas/generic. Soft trademark-safe: correct brand family "
        f"silhouette/colors as provided; do not invent a different brand."
    )
    _distinct = (
        " CRITICAL: This slide's composition MUST be visually distinct from other slides — "
        "different camera distance and angle; do not repeat the same bench still-life layout."
    )
    hook_txt = ad_texts.get("slide1_text", ad_texts.get("hook", ""))
    product_txt = ad_texts.get("slide2_text", ad_texts.get("body", ""))
    cta_txt = ad_texts.get("slide3_text", ad_texts.get("cta", ""))
    body_txt = ad_texts.get("body", "")

    if _no_face:
        hook = (
            f"Create an image: WIDE environment lifestyle scene for {selected_problem}. "
            f"COMPOSITION LOCK — Slide 1 HOOK: wide establishing shot / environment mood; "
            f"shoe appears SMALLER in frame (not a product hero still-life); person-legs or "
            f"empty scene atmosphere OK; NO full-pair product still-life on a bench. "
            f"No face, no portrait framing — crop strictly below the chin; no partial face at frame edge; prioritize shoes, legs, hands, props. "
            f"Natural dramatic studio lighting. Atmospheric mood. Bold top text overlay: '{hook_txt}'. "
            f"{_distinct} "
            f"{negative_constraint}{brand_lock}{_appx} Photorealistic 8k {ar_flag}"
        )
    else:
        hook = (
            f"Create an image: WIDE cinematic lifestyle environment of {selected_problem}. "
            f"COMPOSITION LOCK — Slide 1 HOOK: wide establishing shot; shoe smaller in frame "
            f"or problem-focused mood; NOT a bench product still-life. "
            f"Natural dramatic studio lighting. High emotion. Bold top text overlay: '{hook_txt}'. "
            f"{_distinct} "
            f"{negative_constraint}{brand_lock}{_appx} Photorealistic 8k {ar_flag}"
        )
    product = (
        f"Create an image: Clean studio PRODUCT HERO of {brand} {safe_model_name} in {colorway} "
        f"colorway ({key_materials}) in {selected_env}. "
        f"COMPOSITION LOCK — Slide 2 PRODUCT: three-quarter (3/4) side angle, medium camera distance, "
        f"clean studio product hero; fewer or differently arranged props ({selected_props}) — "
        f"NOT wide environment, NOT macro sole, NOT the same bench still-life as other slides. "
        f"Top-left tag '{selected_tag}', top-right badge '{selected_badge}'. Clean text overlay: '{product_txt}'. "
        f"{_distinct} "
        f"{negative_constraint}{brand_lock}{_appx} Commercial studio lighting {ar_flag}"
    )
    _wm_img = watermark_image_clause(custom_watermark)
    product_cta = (
        f"Create an image: Clean studio PRODUCT HERO of {brand} {safe_model_name} in {colorway} "
        f"colorway ({key_materials}) in {selected_env}. "
        f"COMPOSITION LOCK — PRODUCT+CTA: three-quarter (3/4) side angle, medium camera distance, "
        f"clean product showcase; props sparingly ({selected_props}) — NOT macro sole, NOT wide "
        f"environment, NOT top-down flat lay. "
        f"Top-left tag '{selected_tag}', top-right badge '{selected_badge}'. "
        f"Clean product showcase with soft CTA overlay: '{cta_txt}'."
        f"{_wm_img} "
        f"{_distinct} "
        f"{negative_constraint}{brand_lock}{_appx} Commercial studio lighting {ar_flag}"
    )
    lifestyle = (
        f"Create an image: ON-FOOT crop / lifestyle action in {selected_env} featuring EDC props: {selected_props}, "
        f"with {brand} {safe_model_name} in {colorway} colorway ({key_materials}) naturally worn or mid-stride. "
        f"COMPOSITION LOCK — LIFESTYLE: on-foot crop or mid-distance lifestyle (legs/shoes in motion); "
        f"NOT studio bench still-life, NOT 3/4 product hero, NOT macro sole fill. "
        f"Atmospheric natural light. Subtle text overlay: '{body_txt}'. "
        f"{_distinct} "
        f"{negative_constraint}{brand_lock}{_appx} Photorealistic lifestyle photography 8k {ar_flag}"
    )
    specs = (
        f"Create an image: EXTREME MACRO close-up filling the entire frame with ONLY the sole and "
        f"cushioning of {brand} {safe_model_name}. Background hint of {selected_env} only. "
        f"Highlight materials: {key_materials}. "
        f"COMPOSITION LOCK — DETAIL/MACRO: sole/cushioning ONLY fills the frame; NO full pair on bench, "
        f"NO wide environment, NO 3/4 product hero — tight macro camera distance only. "
        f"Clean overlay text: '{body_txt}'. "
        f"{_distinct} "
        f"{negative_constraint}{brand_lock}{_appx} Commercial studio lighting {ar_flag}"
    )
    specs_cta = (
        f"Create an image: EXTREME MACRO close-up filling the entire frame with ONLY the sole and "
        f"cushioning of {brand} {safe_model_name}. Background hint of {selected_env} only. "
        f"COMPOSITION LOCK — DETAIL/MACRO+CTA: sole/cushioning ONLY fills the frame; NO full pair on bench, "
        f"NO wide environment, NO 3/4 product hero — tight macro camera distance only. "
        f"Soft CTA overlay: '{cta_txt}'."
        f"{_wm_img} "
        f"{_distinct} "
        f"{negative_constraint}{brand_lock}{_appx} Commercial studio lighting {ar_flag}"
    )
    soft_cta = (
        f"Create an image: TOP-DOWN flat lay of {brand} {safe_model_name} in {colorway} "
        f"colorway ({key_materials}) on {selected_env} with soft negative space. "
        f"COMPOSITION LOCK — CTA/FLAT LAY: bird's-eye top-down flat lay OR clean side-profile silhouette "
        f"with generous negative space — NEVER repeat prior slide's camera distance (not wide hook, "
        f"not 3/4 product hero, not macro sole fill). "
        f"Soft CTA overlay: '{cta_txt}'."
        f"{_wm_img} "
        f"{_distinct} "
        f"{negative_constraint}{brand_lock}{_appx} Commercial studio lighting {ar_flag}"
    )

    # roles: (role_i18n_key, prompt)
    if slide_count == 2:
        roles = [
            ("slide_role_hook", hook),
            ("slide_role_product_cta", product_cta),
        ]
    elif slide_count == 3:
        roles = [
            ("slide_role_hook", hook),
            ("slide_role_product", product),
            ("slide_role_specs_cta", specs_cta),
        ]
    elif slide_count == 4:
        roles = [
            ("slide_role_hook", hook),
            ("slide_role_product", product),
            ("slide_role_specs", specs),
            ("slide_role_cta", soft_cta),
        ]
    else:  # 5
        roles = [
            ("slide_role_hook", hook),
            ("slide_role_lifestyle", lifestyle),
            ("slide_role_product", product),
            ("slide_role_specs", specs),
            ("slide_role_cta", soft_cta),
        ]
    return roles



# --- Scene pack bank (English prompt text; diversify Scene elements) ---
BANNED_DEFAULT_ENV = "minimalist concrete urban street with natural daylight"
BANNED_DEFAULT_PROPS = "an open Kinfolk magazine, a ceramic cup of cappuccino, brass keys, succulent"
BANNED_DEFAULT_PROBLEM = "a tired worker sitting on stairs touching sore feet with work boots beside them"
BANNED_SCENE_MARKERS = (
    "kinfolk",
    "cappuccino",
    "brass keys",
    "succulent",
    "tired worker sitting on stairs",
    "minimalist concrete urban street",
    "work boots beside them",
)

SCENE_VIBE_KEYS = [
    "auto",
    "running",
    "trail",
    "gym",
    "street",
    "commute",
    "work",
    "travel",
    "recovery",
    "basketball",
]

SCENE_PACKS = {
    "running": [
        {
            "env_desc": "quiet outdoor track at soft dawn mist with lane lines still damp from overnight dew",
            "props_desc": "GPS watch, race bib folded once, lightweight hydration flask, chalked starting block marks",
            "problem_desc": "close-up of runner calves mid-stride after tempo intervals, shoes planted on the curb for a breath",
            "env_desc_el": "ήσυχος ανοιχτός στίβος σε απαλή ομίχλη αυγής με γραμμές διαδρόμων ακόμα υγρές από τη νυχτερινή δροσιά",
            "props_desc_el": "ρολόι GPS, νούμερο αγώνα διπλωμένο μια φορά, ελαφρύ φλασκί ενυδάτωσης, σημάδια εκκίνησης με κιμωλία",
            "problem_desc_el": "κοντινό πλάνο στις γάμπες δρομέα στη μέση του διασκελισμού μετά από tempo διαστήματα, παπούτσια ακουμπημένα στο πεζοδρόμιο για μια ανάσα",
        },
        {
            "env_desc": "city park loop path edged with autumn leaves and low morning sun through trees",
            "props_desc": "foam roller half-used, charcoal compression socks, energy gel wrappers, reflective vest",
            "problem_desc": "legs stretched on a park bench after a long easy run, one shoe loosened at the heel",
            "env_desc_el": "μονοπάτι πάρκου στην πόλη με φθινοπωρινά φύλλα στα πλαϊνά και χαμηλό πρωινό ήλιο μέσα από τα δέντρα",
            "props_desc_el": "foam roller μισοχρησιμοποιημένο, γκρι κάλτσες συμπίεσης, περιτυλίγματα ενεργειακών τζελ, ανακλαστικό γιλέκο",
            "problem_desc_el": "πόδια τεντωμένα σε παγκάκι πάρκου μετά από μεγάλο εύκολο τρέξιμο, το ένα παπούτσι χαλαρωμένο στη φτέρνα",
        },
        {
            "env_desc": "race-day expo plaza outside a start corral with banners blurred in daylight",
            "props_desc": "safety pins, timing chip bag, throwaway warm-up layer, electrolyte tablet tube",
            "problem_desc": "feet shifting nervously in the start corral, shoes tied tight for race pace",
            "env_desc_el": "πλατεία expo ημέρας αγώνα έξω από τον χώρο εκκίνησης με πανό θολά στο φως της ημέρας",
            "props_desc_el": "παραμάνες ασφαλείας, σακουλάκι chip χρονομέτρησης, φθηνό ζεστό ρούχο για ζέσταμα, σωληνάριο ηλεκτρολυτών",
            "problem_desc_el": "πόδια που κουνιούνται νευρικά στον χώρο εκκίνησης, παπούτσια δεμένα σφιχτά για ρυθμό αγώνα",
        },
    ],
    "trail": [
        {
            "env_desc": "muddy singletrack climbing through pine forest with soft filtered canopy light",
            "props_desc": "trekking poles clipped together, trail map in a zip pouch, muddy gaiters, bear-bell clip",
            "problem_desc": "mud-caked shoes and calves paused on a rock after a steep ascent, no face needed",
            "env_desc_el": "λασπωμένο μονοπάτι που ανεβαίνει μέσα από πευκόδασος με απαλό φιλτραρισμένο φως από την κόμη",
            "props_desc_el": "μπαστούνια trekking κλιπ μαζί, χάρτης trail σε τσαντάκι με φερμουάρ, λασπωμένα γκέτες, κουδουνάκι αρκούδας",
            "problem_desc_el": "παπούτσια και γάμπες γεμάτα λάσπη σταματημένα σε πέτρα μετά από απότομη ανάβαση, χωρίς πρόσωπο",
        },
        {
            "env_desc": "rocky alpine switchback with distant ridgeline and cool overcast sky",
            "props_desc": "hydration vest, protein bar, headlamp, compact first-aid tin",
            "problem_desc": "hikers legs braced on uneven stone, shoes gripping scree after a long descent",
            "env_desc_el": "βραχώδης αλπική στροφή με μακρινή κορυφογραμμή και δροσερό συννεφιασμένο ουρανό",
            "props_desc_el": "γιλέκο ενυδάτωσης, μπάρα πρωτεΐνης, φακός κεφαλής, μικρό κουτί πρώτων βοηθειών",
            "problem_desc_el": "πόδια πεζοπόρου στηριγμένα σε ανώμαλη πέτρα, παπούτσια που πιάνουν σε σάρα μετά από μεγάλη κατάβαση",
        },
    ],
    "gym": [
        {
            "env_desc": "neon-lit training floor with rubber mats, rack mirrors, and cool evening gym lighting",
            "props_desc": "chalk bowl, lifting straps, resistance bands, stainless water bottle",
            "problem_desc": "athlete feet planted under a squat rack between sets, shoes braced on the platform",
            "env_desc_el": "πάτωμα προπόνησης με νέον φωτισμό, λαστιχένια στρώματα, καθρέφτες ρακών και δροσερό βραδινό φως γυμναστηρίου",
            "props_desc_el": "μπολ με κιμωλία, ιμάντες άρσης, λάστιχα αντίστασης, ανοξείδωτο μπουκάλι νερού",
            "problem_desc_el": "πόδια αθλητή ακουμπημένα κάτω από squat rack ανάμεσα σε σετ, παπούτσια στηριγμένα στην πλατφόρμα",
        },
        {
            "env_desc": "bright functional-training studio with kettlebells lined along a white wall",
            "props_desc": "jump rope, foam yoga block, sweat towel, heart-rate armband",
            "problem_desc": "legs mid-lunge on turf after HIIT, shoes dusty with chalk residue",
            "env_desc_el": "φωτεινό στούντιο functional training με kettlebells στη σειρά κατά μήκος άσπρου τοίχου",
            "props_desc_el": "σκοινάκι, foam μπλοκ γιόγκα, πετσέτα ιδρώτα, περιβραχιόνιο καρδιακών παλμών",
            "problem_desc_el": "πόδια στη μέση ενός lunge σε χλοοτάπητα μετά από HIIT, παπούτσια σκονισμένα με υπόλειμμα κιμωλίας",
        },
    ],
    "street": [
        {
            "env_desc": "boutique cobblestone side street with shopfront glass and warm late-afternoon light",
            "props_desc": "crossbody bag, Polaroid camera, folded denim jacket, iced matcha cup",
            "problem_desc": "stylish cropped legs leaning on a storefront ledge, sneakers as the hero silhouette",
            "env_desc_el": "πλακόστρωτο πλαϊνό δρομάκι μπουτίκ με βιτρίνες και ζεστό απογευματινό φως",
            "props_desc_el": "τσάντα χιαστή, κάμερα Polaroid, διπλωμένο τζιν μπουφάν, παγωμένο ποτήρι matcha",
            "problem_desc_el": "κομψά κομμένα πόδια ακουμπημένα σε περβάζι βιτρίνας, τα sneakers ως ήρωας της σιλουέτας",
        },
        {
            "env_desc": "graffiti alley with soft bounce light from a neighboring cafe awning",
            "props_desc": "skateboard deck, wireless earbuds case, enamel pin card, chain wallet",
            "problem_desc": "street-style feet crossed on a curb, focusing on clean upper and sole stack",
            "env_desc_el": "σοκάκι με graffiti και απαλό ανακλώμενο φως από τέντα γειτονικού καφέ",
            "props_desc_el": "σανίδα skateboard, θήκη ασύρματων ακουστικών, κάρτα με καρφίτσα σμάλτου, πορτοφόλι με αλυσίδα",
            "problem_desc_el": "πόδια street-style σταυρωμένα στο πεζοδρόμιο, εστίαση στο καθαρό πάνω μέρος και τη στοίβα της σόλας",
        },
    ],
    "commute": [
        {
            "env_desc": "rainy metro platform with wet tiles reflecting overhead LEDs and distant train blur",
            "props_desc": "compact umbrella, transit card sleeve, dripping raincoat hem, reusable coffee thermos",
            "problem_desc": "commuter legs waiting on wet tiles, shoes beading rain after a soaked walk to the station",
            "env_desc_el": "βροχερή αποβάθρα μετρό με υγρά πλακάκια που αντανακλούν LED και μακρινό θόλωμα τρένου",
            "props_desc_el": "συμπαγής ομπρέλα, θήκη κάρτας μεταφοράς, στάζον στρίφωμα αδιάβροχου, επαναχρησιμοποιούμενο θερμός καφέ",
            "problem_desc_el": "πόδια επιβάτη που περιμένουν σε υγρά πλακάκια, παπούτσια με σταγόνες βροχής μετά από μουσκεμένο περπάτημα μέχρι τον σταθμό",
        },
        {
            "env_desc": "busy crosswalk at dusk with puddles and yellow taxi streaks in bokeh",
            "props_desc": "folded newspaper, bike helmet, wet scarf, phone with cracked case",
            "problem_desc": "feet stepping through a shallow puddle at a red light, shoes taking the splash",
            "env_desc_el": "πολυσύχναστη διάβαση στο σούρουπο με λακκούβες και κίτρινες γραμμές ταξί σε bokeh",
            "props_desc_el": "διπλωμένη εφημερίδα, κράνος ποδηλάτου, βρεγμένο κασκόλ, τηλέφωνο με ραγισμένη θήκη",
            "problem_desc_el": "πόδια που πατάνε μέσα από ρηχή λακκούβα σε κόκκινο φανάρι, παπούτσια που παίρνουν το πιτσίλισμα",
        },
    ],
    "work": [
        {
            "env_desc": "busy cafe counter area with warm pendant lights and steam from the espresso machine",
            "props_desc": "order ticket spike, milk pitcher, bar towel, tip jar coins",
            "problem_desc": "barista shift legs behind the counter after hours of standing, work sneakers loosened",
            "env_desc_el": "πολυσύχναστος χώρος πάγκου καφέ με ζεστά κρεμαστά φώτα και ατμό από τη μηχανή εσπρέσο",
            "props_desc_el": "καρφί για παραγγελίες, κανάτα γάλακτος, πετσέτα μπαρ, κέρματα σε βάζο φιλοδωρημάτων",
            "problem_desc_el": "πόδια βάρδιας barista πίσω από τον πάγκο μετά από ώρες όρθιος, τα work sneakers χαλαρωμένα",
        },
        {
            "env_desc": "retail shop floor aisle with soft overhead LEDs and clothing racks softly blurred",
            "props_desc": "price gun, folded stock boxes, name-badge lanyard, inventory tablet",
            "problem_desc": "retail associate legs pausing mid-aisle after a long standing shift, shoes still on",
            "env_desc_el": "διάδρομος καταστήματος retail με απαλά overhead LED και ράφια ρούχων απαλά θολά",
            "props_desc_el": "πιστόλι τιμών, διπλωμένα κουτιά στοκ, κορδόνι με κονκάρδα ονόματος, tablet αποθέματος",
            "problem_desc_el": "πόδια υπαλλήλου retail που σταματούν στη μέση του διαδρόμου μετά από μεγάλη βάρδια όρθιος, παπούτσια ακόμα φορεμένα",
        },
    ],
    "travel": [
        {
            "env_desc": "airport departure hall with polished floors, soft daylight from tall windows, and rolling suitcase blur",
            "props_desc": "boarding pass sleeve, compact neck pillow, passport holder, carry-on handle",
            "problem_desc": "traveler legs stretched beside a gate seat after a long walk through terminals",
            "env_desc_el": "αίθουσα αναχωρήσεων αεροδρομίου με γυαλισμένα πατώματα, απαλό φως ημέρας από ψηλά παράθυρα και θόλωμα βαλίτσας που κυλάει",
            "props_desc_el": "θήκη κάρτας επιβίβασης, συμπαγές μαξιλάρι αυχένα, θήκη διαβατηρίου, λαβή χειραποσκευής",
            "problem_desc_el": "πόδια ταξιδιώτη τεντωμένα δίπλα σε κάθισμα πύλης μετά από μεγάλο περπάτημα στους τερματικούς",
        },
        {
            "env_desc": "train platform with morning haze and distant countryside rolling stock",
            "props_desc": "weekender duffel, paperback novel, bottle of water, luggage tag",
            "problem_desc": "feet resting on a hard platform bench during a layover, shoes still laced for walking",
            "env_desc_el": "αποβάθρα τρένου με πρωινή ομίχλη και μακρινά βαγόνια στην ύπαιθρο",
            "props_desc_el": "σακ βουαγιάζ weekender, μυθιστόρημα τσέπης, μπουκάλι νερού, ετικέτα αποσκευής",
            "problem_desc_el": "πόδια ακουμπημένα σε σκληρό παγκάκι αποβάθρας σε ενδιάμεση στάση, παπούτσια ακόμα δεμένα για περπάτημα",
        },
    ],
    "recovery": [
        {
            "env_desc": "quiet curb outside a running track after sunset with streetlamps just flickering on",
            "props_desc": "ice pack wrap, recovery drink can, sweaty singlet draped aside, massage ball",
            "problem_desc": "post-run legs on the curb, shoes half-off, focusing on tired feet without showing a face",
            "env_desc_el": "ήσυχο πεζοδρόμιο έξω από στίβο μετά το ηλιοβασίλεμα με φανούς που μόλις ανάβουν",
            "props_desc_el": "παγοκύστη, κουτάκι recovery ποτού, ιδρωμένο φανελάκι στην άκρη, μπάλα μασάζ",
            "problem_desc_el": "πόδια μετά το τρέξιμο στο πεζοδρόμιο, παπούτσια μισοβγαλμένα, εστίαση σε κουρασμένα πέλματα χωρίς πρόσωπο",
        },
        {
            "env_desc": "sunny apartment balcony with a yoga mat rolled halfway and city rooftops beyond",
            "props_desc": "compression boots remote, protein shake, phone playing a stretch video, soft towel",
            "problem_desc": "recovery stretch on a mat, one shoe kicked aside, calves being rolled out",
            "env_desc_el": "ηλιόλουστο μπαλκόνι διαμερίσματος με στρώμα γιόγκα μισοτυλιγμένο και ταράτσες πόλης στο βάθος",
            "props_desc_el": "τηλεχειριστήριο μπότες συμπίεσης, πρωτεϊνικό shake, τηλέφωνο με βίντεο διατάσεων, απαλή πετσέτα",
            "problem_desc_el": "διάταση recovery σε στρώμα, το ένα παπούτσι πεταμένο στην άκρη, γάμπες που κυλιούνται",
        },
    ],
    "basketball": [
        {
            "env_desc": "indoor hardwood court with sharp overhead lights and painted free-throw arc",
            "props_desc": "basketball, towel on the baseline, ankle sleeve, sports drink bottle",
            "problem_desc": "player legs cutting hard near the key, shoes planted for a quick stop",
            "env_desc_el": "κλειστό γήπεδο παρκέ με έντονα overhead φώτα και βαμμένο τόξο ελεύθερης βολής",
            "props_desc_el": "μπάλα μπάσκετ, πετσέτα στη βασική γραμμή, μανίκι αστραγάλου, μπουκάλι αθλητικού ποτού",
            "problem_desc_el": "πόδια παίκτη που κόβουν απότομα κοντά στο καλάθι, παπούτσια ακουμπημένα για γρήγορο στοπ",
        },
        {
            "env_desc": "outdoor asphalt half-court at golden hour with chain net softly clinking",
            "props_desc": "worn basketball, portable speaker, chalked score tally, water jug",
            "problem_desc": "pickup-game feet at the top of the key between possessions, dusty court shoes",
            "env_desc_el": "εξωτερικό asfalt half-court στην χρυσή ώρα με αλυσίδα δίχτυ που κουδουνίζει απαλά",
            "props_desc_el": "φθαρμένη μπάλα μπάσκετ, φορητό ηχείο, σκορ με κιμωλία, μπιτόνι νερού",
            "problem_desc_el": "πόδια pickup αγώνα στην κορυφή της ρακέτας ανάμεσα σε κατοχές, σκονισμένα παπούτσια γηπέδου",
        },
    ],
    "lifestyle": [
        {
            "env_desc": "sunlit loft interior with raw wood floor and large window light pooling on the boards",
            "props_desc": "vinyl record sleeve, ceramic mug of black coffee, house keys, linen tote",
            "problem_desc": "relaxed weekend legs on a low stool, sneakers as the quiet hero of the frame",
            "env_desc_el": "ηλιόλουστο εσωτερικό loft με ακατέργαστο ξύλινο πάτωμα και μεγάλο φως παραθύρου που πέφτει στις σανίδες",
            "props_desc_el": "εξώφυλλο δίσκου βινυλίου, κεραμική κούπα μαύρου καφέ, κλειδιά σπιτιού, λινή τσάντα tote",
            "problem_desc_el": "χαλαρά πόδια Σαββατοκύριακου σε χαμηλό σκαμπό, τα sneakers ως ήσυχος ήρωας του κάδρου",
        },
        {
            "env_desc": "coastal boardwalk with soft sea breeze haze and pale wood planks",
            "props_desc": "sunglasses case, disposable camera, woven tote, cold sparkling water",
            "problem_desc": "leisurely walk pause on the boardwalk railing, focusing on shoes against weathered wood",
            "env_desc_el": "παραθαλάσσιο boardwalk με απαλή θαλασσινή αύρα-ομίχλη και χλωμές ξύλινες σανίδες",
            "props_desc_el": "θήκη γυαλιών ηλίου, κάμερα μιας χρήσης, πλεκτή τσάντα tote, κρύο ανθρακούχο νερό",
            "problem_desc_el": "παύση σε χαλαρό περπάτημα στο κάγκελο του boardwalk, εστίαση στα παπούτσια πάνω σε φθαρμένο ξύλο",
        },
    ],
}


def infer_scene_archetype(brand: str = "", model: str = "", specs: str = "", vibe: str = "auto") -> str:
    """Infer scene archetype from vibe override or shoe keywords."""
    vibe = (vibe or "auto").strip().lower()
    if vibe in SCENE_PACKS and vibe not in ("lifestyle",):
        return vibe
    if vibe in SCENE_VIBE_KEYS and vibe != "auto" and vibe in SCENE_PACKS:
        return vibe

    blob = f"{brand or ''} {model or ''} {specs or ''}".lower()
    if any(k in blob for k in ("trail", "gore-tex", "gore tex", "hike", "hiking", "mafate", "speedgoat", "ultrarunning", "off-road", "vibram")):
        return "trail"
    if any(k in blob for k in ("basketball", "hoops", "court", "kyrie", "lebron", "harden", "dame")):
        return "basketball"
    if any(k in blob for k in ("gym", "training", "crossfit", "metcon", "lifting", "nano", "trainer")):
        return "gym"
    if any(k in blob for k in (
        "brooks", "hoka", "pegasus", "ghost", "glycerin", "clifton", "bondi", "hyperion",
        "running", "runner", "marathon", "tempo", "road race", "racing flat", "vaporfly",
        "endorphin", "adrenaline", "saucony", "asics", "nimbus", "cumulus", "gel-kayano",
    )):
        return "running"
    if any(k in blob for k in ("commute", "rain", "waterproof", "city walk", "metro")):
        return "commute"
    if any(k in blob for k in ("travel", "airport", "walkable", "all day walk")):
        return "travel"
    if any(k in blob for k in ("recovery", "post-run", "after run", "cool down")):
        return "recovery"
    if any(k in blob for k in ("retail", "barista", "standing", "shift", "work boot", "nurse", "hospitality")):
        return "work"
    if any(k in blob for k in ("street", "lifestyle", "heritage", "og", "retro", "fashion", "dunk", "jordan", "samba", "gazelle")):
        return "street"
    return "lifestyle"


def pick_scene_pack(brand: str = "", model: str = "", specs: str = "", rng=None, vibe: str = "auto", stable: bool = False):
    """Pick a diverse {env_desc, props_desc, problem_desc} pack.

    rng: optional random.Random for tests.
    stable=True: hash brand+model for a deterministic fallback (still not the old Kinfolk/worker triple).
    vibe: SCENE_VIBE_KEYS value; 'auto' infers from keywords.
    """
    archetype = infer_scene_archetype(brand, model, specs, vibe=vibe)
    packs = SCENE_PACKS.get(archetype) or SCENE_PACKS["lifestyle"]
    if not packs:
        packs = SCENE_PACKS["lifestyle"]
    if stable:
        key = f"{(brand or '').strip().lower()}|{(model or '').strip().lower()}|{archetype}"
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % len(packs)
        pack = packs[idx]
    else:
        chooser = rng.choice if rng is not None else random.choice
        pack = chooser(packs)
    return {
        "env_desc": pack["env_desc"],
        "props_desc": pack["props_desc"],
        "problem_desc": pack["problem_desc"],
        "env_desc_el": pack.get("env_desc_el") or pack["env_desc"],
        "props_desc_el": pack.get("props_desc_el") or pack["props_desc"],
        "problem_desc_el": pack.get("problem_desc_el") or pack["problem_desc"],
    }


def scene_matches_banned_defaults(env_desc: str = "", props_desc: str = "", problem_desc: str = "") -> bool:
    """True if analyze/fallback still looks like the old hard-coded Kinfolk/worker triple."""
    blob = f"{env_desc or ''} {props_desc or ''} {problem_desc or ''}".lower()
    if not blob.strip():
        return True
    hits = sum(1 for m in BANNED_SCENE_MARKERS if m in blob)
    if hits >= 2:
        return True
    if BANNED_DEFAULT_ENV.lower() in (env_desc or "").lower():
        return True
    if BANNED_DEFAULT_PROPS.lower() in (props_desc or "").lower():
        return True
    if BANNED_DEFAULT_PROBLEM.lower() in (problem_desc or "").lower():
        return True
    return False


def apply_scene_pack_to_session(pack: dict, lang: str = None):
    """Write env/props/problem into session_state (visible UI lang + English shadows)."""
    lang = (lang or st.session_state.get("lang", "el") or "el").strip().lower()
    env_en = pack.get("env_desc", "") or ""
    props_en = pack.get("props_desc", "") or ""
    problem_en = pack.get("problem_desc", "") or ""
    env_el = pack.get("env_desc_el") or env_en
    props_el = pack.get("props_desc_el") or props_en
    problem_el = pack.get("problem_desc_el") or problem_en
    st.session_state["env_desc_en"] = env_en
    st.session_state["props_desc_en"] = props_en
    st.session_state["problem_desc_en"] = problem_en
    if lang == "el":
        st.session_state["env_desc_val"] = env_el
        st.session_state["props_desc_val"] = props_el
        st.session_state["problem_desc_val"] = problem_el
    else:
        st.session_state["env_desc_val"] = env_en
        st.session_state["props_desc_val"] = props_en
        st.session_state["problem_desc_val"] = problem_en


def scene_fields_for_prompts():
    """English scene strings for image prompt builders (never Greek)."""
    env = (st.session_state.get("env_desc_en") or st.session_state.get("env_desc_val") or "").strip()
    props = (st.session_state.get("props_desc_en") or st.session_state.get("props_desc_val") or "").strip()
    problem = (st.session_state.get("problem_desc_en") or st.session_state.get("problem_desc_val") or "").strip()
    return env, props, problem


def _iter_all_scene_packs():
    for packs in SCENE_PACKS.values():
        for pack in packs:
            yield pack


def find_scene_pack_by_text(env_text: str = "", props_text: str = "", problem_text: str = ""):
    """Match visible or EN pack text to a full bilingual pack, or None."""
    env_t = (env_text or "").strip()
    props_t = (props_text or "").strip()
    problem_t = (problem_text or "").strip()
    if not (env_t or props_t or problem_t):
        return None
    for pack in _iter_all_scene_packs():
        en_env = (pack.get("env_desc") or "").strip()
        en_props = (pack.get("props_desc") or "").strip()
        en_problem = (pack.get("problem_desc") or "").strip()
        el_env = (pack.get("env_desc_el") or "").strip()
        el_props = (pack.get("props_desc_el") or "").strip()
        el_problem = (pack.get("problem_desc_el") or "").strip()
        if env_t and env_t not in (en_env, el_env):
            continue
        if props_t and props_t not in (en_props, el_props):
            continue
        if problem_t and problem_t not in (en_problem, el_problem):
            continue
        # Prefer matching at least env when provided
        if env_t and env_t in (en_env, el_env):
            return pack
        if not env_t and (props_t or problem_t):
            return pack
    # Fallback: match env alone
    if env_t:
        for pack in _iter_all_scene_packs():
            if env_t in ((pack.get("env_desc") or "").strip(), (pack.get("env_desc_el") or "").strip()):
                return pack
    return None


def refresh_scene_fields_for_lang(new_lang: str, old_lang: str = None):
    """On el↔en switch, refresh visible scene fields from known packs or EN shadows."""
    new_lang = (new_lang or "el").strip().lower()
    old_lang = (old_lang or "").strip().lower()
    if old_lang and old_lang == new_lang:
        return False
    env_vis = st.session_state.get("env_desc_val", "") or ""
    props_vis = st.session_state.get("props_desc_val", "") or ""
    problem_vis = st.session_state.get("problem_desc_val", "") or ""
    pack = find_scene_pack_by_text(env_vis, props_vis, problem_vis)
    if pack:
        apply_scene_pack_to_session(pack, lang=new_lang)
        return True
    # If EN shadows exist and look like pack EN, flip visible from shadows
    env_en = st.session_state.get("env_desc_en", "") or ""
    props_en = st.session_state.get("props_desc_en", "") or ""
    problem_en = st.session_state.get("problem_desc_en", "") or ""
    if env_en or props_en or problem_en:
        pack2 = find_scene_pack_by_text(env_en, props_en, problem_en)
        if pack2:
            apply_scene_pack_to_session(pack2, lang=new_lang)
            return True
        # Custom text: keep EN shadows; show EN when lang=en, leave Greek custom as-is when el
        if new_lang == "en":
            st.session_state["env_desc_val"] = env_en or env_vis
            st.session_state["props_desc_val"] = props_en or props_vis
            st.session_state["problem_desc_val"] = problem_en or problem_vis
            return True
    return False


def translate_scene_lines_to_greek(env_en: str, props_en: str, problem_en: str):
    """Translate 3 English scene lines to natural Greek via Gemini. Returns dict or None."""
    env_en = (env_en or "").strip()
    props_en = (props_en or "").strip()
    problem_en = (problem_en or "").strip()
    if not (env_en or props_en or problem_en):
        return None
    # Prefer known pack mapping (no API)
    pack = find_scene_pack_by_text(env_en, props_en, problem_en)
    if pack and pack.get("env_desc_el"):
        return {
            "env_desc_el": pack.get("env_desc_el") or env_en,
            "props_desc_el": pack.get("props_desc_el") or props_en,
            "problem_desc_el": pack.get("problem_desc_el") or problem_en,
        }
    prompt = (
        "Translate these 3 sneaker scene description lines to natural Greek. "
        "Keep meaning and photographic detail. Return ONLY raw JSON with keys "
        "env_desc_el, props_desc_el, problem_desc_el.\n\n"
        f"env_desc: {env_en}\n"
        f"props_desc: {props_en}\n"
        f"problem_desc: {problem_en}\n"
    )
    models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]
    for model_item in models_to_try:
        try:
            res = client.models.generate_content(model=model_item, contents=prompt)
            if not res or not res.text:
                continue
            clean_txt = res.text.strip()
            if clean_txt.startswith("```json"):
                clean_txt = clean_txt[7:]
            if clean_txt.startswith("```"):
                clean_txt = clean_txt[3:]
            if clean_txt.endswith("```"):
                clean_txt = clean_txt[:-3]
            data = json.loads(clean_txt.strip())
            if not isinstance(data, dict):
                continue
            return {
                "env_desc_el": (data.get("env_desc_el") or env_en).strip(),
                "props_desc_el": (data.get("props_desc_el") or props_en).strip(),
                "problem_desc_el": (data.get("problem_desc_el") or problem_en).strip(),
            }
        except Exception:
            time.sleep(0.5)
    return None


def store_scene_from_analyze(env_en: str, props_en: str, problem_en: str, lang: str = None):
    """Store EN shadows always; set visible fields to EL when UI is Greek."""
    lang = (lang or st.session_state.get("lang", "el") or "el").strip().lower()
    env_en = env_en or ""
    props_en = props_en or ""
    problem_en = problem_en or ""
    st.session_state["env_desc_en"] = env_en
    st.session_state["props_desc_en"] = props_en
    st.session_state["problem_desc_en"] = problem_en
    if lang == "el":
        tr = translate_scene_lines_to_greek(env_en, props_en, problem_en)
        if tr:
            st.session_state["env_desc_val"] = tr["env_desc_el"]
            st.session_state["props_desc_val"] = tr["props_desc_el"]
            st.session_state["problem_desc_val"] = tr["problem_desc_el"]
        else:
            st.session_state["env_desc_val"] = env_en
            st.session_state["props_desc_val"] = props_en
            st.session_state["problem_desc_val"] = problem_en
    else:
        st.session_state["env_desc_val"] = env_en
        st.session_state["props_desc_val"] = props_en
        st.session_state["problem_desc_val"] = problem_en



GOAL_KEYS = ["auto", "comfort", "wide_fit", "style", "rain_care"]


def suggest_goal_from_specs(specs: str, model_name: str = "", brand: str = "") -> str:
    """Map shoe specs / model text to a suggested story goal (soft heuristic)."""
    blob = f"{specs or ''} {model_name or ''} {brand or ''}".lower()
    if any(k in blob for k in ("suede", "nubuck", "gore-tex", "waterproof", "rain", "water repellent", "gusset")):
        return "rain_care"
    if any(k in blob for k in ("wide", "2e", "4e", "toe box", "toebox", "wide fit", "roomy")):
        return "wide_fit"
    if any(k in blob for k in ("cushion", "comfort", "eva", "foam", "standing", "all-day", "all day", "fatigue", "plush", "maxx", "bondi", "clifton")):
        return "comfort"
    if any(k in blob for k in ("heritage", "og", "retro", "street", "classic", "silhouette", "leather")):
        return "style"
    return "comfort"


def load_weekly_insights(path: str | Path = "data/weekly_insights.json") -> dict:
    """Load static weekly insights JSON; return {} on missing/invalid."""
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _normalize_shoe_image_ext(ext: str | None = None, mime: str | None = None) -> str:
    """Return jpg/png/webp for ZIP shoe.* filename."""
    e = (ext or "").lstrip(".").lower()
    if e == "jpeg":
        e = "jpg"
    if e in ("jpg", "png", "webp"):
        return e
    m = (mime or "").lower()
    if "png" in m:
        return "png"
    if "webp" in m:
        return "webp"
    return "jpg"


def _mime_for_shoe_ext(ext: str) -> str:
    return {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")


def _read_history_shoe_bytes(path_str: str | None) -> tuple[bytes | None, str | None, str | None]:
    """Load shoe image bytes/ext/mime from a history image_path if present."""
    if not path_str:
        return None, None, None
    p = Path(path_str)
    if not p.is_file():
        return None, None, None
    try:
        data = p.read_bytes()
    except OSError:
        return None, None, None
    ext = _normalize_shoe_image_ext(p.suffix)
    return data, ext, _mime_for_shoe_ext(ext)


def build_pack_zip_bytes(
    *,
    brand: str,
    model_name: str,
    colorway: str,
    goal: str,
    lang: str,
    aspect_ratio: str,
    slide_count: int,
    specs: str,
    meta_caption: str,
    hashtags_meta: str,
    tiktok_caption: str,
    pinterest_caption: str = "",
    youtube_caption: str = "",
    visual_prompt: str = "",
    slide_prompts: list | None = None,
    image_bytes: bytes | None = None,
    image_ext: str | None = None,
    image_mime: str | None = None,
    video_prompts_txt: str = "",
    video_beats: dict | None = None,
) -> bytes:
    """Build an in-memory ZIP export pack (stdlib only). Includes shoe.* when image_bytes set."""
    slide_prompts = slide_prompts or []
    meta_body = f"{meta_caption or ''}\n\n{hashtags_meta or ''}".strip()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("captions_meta.txt", meta_body)
        zf.writestr("captions_tiktok.txt", tiktok_caption or "")
        zf.writestr("captions_pinterest.txt", pinterest_caption or "")
        zf.writestr("captions_youtube.txt", youtube_caption or "")
        _vtxt = (video_prompts_txt or "").strip()
        if not _vtxt and video_beats:
            _vtxt = format_video_prompts_txt(
                video_beats, brand=brand, model=model_name, colorway=colorway
            )
        if _vtxt:
            zf.writestr("video_prompts.txt", _vtxt)
        if visual_prompt:
            prompts_txt = visual_prompt
        else:
            parts = []
            for i, p in enumerate(slide_prompts, start=1):
                if p:
                    parts.append(f"=== slide{i} ===\n{p}")
            prompts_txt = "\n\n".join(parts) if parts else ""
        zf.writestr("prompts.txt", prompts_txt)
        meta = {
            "brand": brand,
            "model": model_name,
            "colorway": colorway,
            "goal": goal,
            "lang": lang,
            "aspect": aspect_ratio,
            "slide_count": slide_count,
            "specs": specs,
        }
        if video_beats:
            meta["video_beats"] = video_beats
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        if image_bytes:
            ext = _normalize_shoe_image_ext(image_ext, image_mime)
            zf.writestr(f"shoe.{ext}", image_bytes)
    return buf.getvalue()



def _video_role_label(role: str, lang: str) -> str:
    key = f"video_role_{role}"
    label = t(key, lang)
    return label if label != key else (role or "").replace("_", " ")


def render_video_beats_ui(video_pack: dict, *, lang: str, key_prefix: str = "vid") -> None:
    """Render Grok Video howto + beats + download inside a tab/section."""
    if not video_pack or not video_pack.get("beats"):
        return
    howto = video_pack.get("howto_el") if lang == "el" else video_pack.get("howto_en")
    st.caption(t("video_section_help", lang))
    st.info(t("video_howto", lang, howto=howto or ""))
    st.caption(t("video_duration_hint", lang, hint=video_pack.get("duration_hint") or ""))
    for b in video_pack.get("beats") or []:
        idx = b.get("index", 0)
        role = _video_role_label(b.get("role", ""), lang)
        st.markdown(f"**{t('video_beat_label', lang, n=idx, role=role)}**")
        summary = b.get("summary_el") or ""
        if summary:
            st.write(f"{t('video_summary_label', lang)} {summary}")
        st.caption(t("video_prompt_label", lang))
        st.code(b.get("prompt_en") or "", language="text")
    txt = format_video_prompts_txt(
        video_pack,
        brand=st.session_state.get("brand_val", ""),
        model=st.session_state.get("model_val", ""),
        colorway=st.session_state.get("colorway_val", ""),
        topic=(st.session_state.get("content_result") or {}).get("topic_en", ""),
    )
    st.download_button(
        label=t("video_download", lang),
        data=txt,
        file_name="video_prompts.txt",
        mime="text/plain",
        key=f"{key_prefix}_video_dl",
    )


def rebuild_video_beats_from_context(
    *,
    brand: str = "",
    model: str = "",
    colorway: str = "",
    specs: str = "",
    env: str = "",
    props: str = "",
    problem: str = "",
    watermark: str = "",
    appearance: str = "eu",
    goal: str = "auto",
    ad_format: str = "",
    slide_count: int = 3,
    lang: str = "el",
    existing=None,
    topic: str = "",
    slide_texts=None,
) -> dict:
    """Prefer stored video_beats; otherwise rebuild from product/content context."""
    if isinstance(existing, dict) and existing.get("beats"):
        return existing
    fmt = (ad_format or "").lower()
    try:
        sc = int(slide_count)
    except (TypeError, ValueError):
        sc = 3
    if "content" in fmt or (slide_texts and "product" not in fmt and "carousel" not in fmt and "single" not in fmt and goal == "content"):
        mode = "content"
    elif slide_texts and ("content" in fmt or goal == "content"):
        mode = "content"
    elif "carousel" in fmt:
        mode = "carousel"
    elif "single" in fmt or "1 εικόνα" in fmt or "1 εικονα" in fmt or sc <= 1:
        mode = "single"
    elif sc >= 2:
        mode = "carousel"
    else:
        mode = "single"
    return build_grok_video_beats(
        brand=brand,
        model=model,
        colorway=colorway,
        specs=specs,
        env=env,
        props=props,
        problem=problem,
        watermark=watermark,
        appearance=appearance,
        goal=goal,
        mode=mode,
        slide_count=slide_count,
        slide_texts=slide_texts,
        lang=lang,
        topic=topic,
    )



def clear_all_fields():
    st.session_state["brand_val"] = ""
    st.session_state["model_val"] = ""
    st.session_state["colorway_val"] = ""
    st.session_state["specs_val"] = ""
    _pack = pick_scene_pack("", "", "", vibe=st.session_state.get("scene_vibe_val", "auto") or "auto")
    apply_scene_pack_to_session(_pack, lang=st.session_state.get("lang", "el"))
    st.session_state["watermark_val"] = ""
    st.session_state["selected_tag_val"] = AUTHENTICITY_TAGS[0]
    st.session_state["selected_badge_val"] = CATEGORY_BADGES[0]
    st.session_state["ad_format_val"] = "Single Layout Ad (1 Εικόνα)"
    st.session_state["slide_count_val"] = 3
    st.session_state["aspect_ratio_val"] = "1:1 (Square)"
    st.session_state["history_image_path"] = None
    st.session_state["loaded_meta_caption"] = ""
    st.session_state["loaded_tiktok_caption"] = ""
    st.session_state["loaded_hashtags_meta"] = ""
    st.session_state["loaded_pinterest_caption"] = ""
    st.session_state["loaded_youtube_caption"] = ""
    st.session_state["captions_el"] = None
    st.session_state["captions_en"] = None
    st.session_state["results_lang"] = None
    st.session_state["content_captions_el"] = None
    st.session_state["content_captions_en"] = None
    st.session_state["content_slides_el"] = None
    st.session_state["content_slides_en"] = None
    st.session_state["content_results_lang"] = None
    st.session_state["loaded_visual_prompt"] = ""
    st.session_state["loaded_slide1_prompt"] = ""
    st.session_state["loaded_slide2_prompt"] = ""
    st.session_state["loaded_slide3_prompt"] = ""
    st.session_state["loaded_slide4_prompt"] = ""
    st.session_state["loaded_slide5_prompt"] = ""
    st.session_state["loaded_video_beats"] = None
    st.session_state["show_loaded_pack"] = False
    st.session_state["goal_val"] = "auto"
    st.session_state["appearance_val"] = "eu"
    st.session_state["active_insight"] = ""
    st.session_state["last_export_zip"] = None
    st.session_state["last_export_shoe"] = None
    st.session_state["last_export_shoe_ext"] = None
    st.session_state["last_export_shoe_mime"] = None
    st.session_state["last_export_shoe_name"] = None
    st.session_state["last_export_name"] = "content_pack.zip"
    st.session_state["last_export_txt"] = None
    st.session_state["last_export_txt_name"] = None
    st.session_state["last_export_path"] = None
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1


def apply_history_entry(entry: dict):
    """Populate session_state from a history entry; caller should st.rerun()."""
    st.session_state["brand_val"] = entry.get("brand", "") or ""
    st.session_state["model_val"] = entry.get("model", "") or ""
    st.session_state["colorway_val"] = entry.get("colorway", "") or ""
    st.session_state["specs_val"] = entry.get("specs", "") or ""
    _e = entry.get("env_desc", "") or ""
    _p = entry.get("props_desc", "") or ""
    _pr = entry.get("problem_desc", "") or ""
    st.session_state["env_desc_val"] = _e
    st.session_state["props_desc_val"] = _p
    st.session_state["problem_desc_val"] = _pr
    _e_en = entry.get("env_desc_en") or ""
    _p_en = entry.get("props_desc_en") or ""
    _pr_en = entry.get("problem_desc_en") or ""
    if not (_e_en or _p_en or _pr_en):
        _matched = find_scene_pack_by_text(_e, _p, _pr)
        if _matched:
            _e_en, _p_en, _pr_en = _matched["env_desc"], _matched["props_desc"], _matched["problem_desc"]
        else:
            # Legacy entries were English-only
            _e_en, _p_en, _pr_en = _e, _p, _pr
    st.session_state["env_desc_en"] = _e_en
    st.session_state["props_desc_en"] = _p_en
    st.session_state["problem_desc_en"] = _pr_en
    st.session_state["watermark_val"] = (entry.get("watermark") or "").strip()
    tag = entry.get("selected_tag") or AUTHENTICITY_TAGS[0]
    badge = entry.get("selected_badge") or CATEGORY_BADGES[0]
    st.session_state["selected_tag_val"] = tag if tag in AUTHENTICITY_TAGS else AUTHENTICITY_TAGS[0]
    st.session_state["selected_badge_val"] = badge if badge in CATEGORY_BADGES else CATEGORY_BADGES[0]
    formats = ["Single Layout Ad (1 Εικόνα)", "Carousel Pack (multi-slide)"]
    fmt = entry.get("ad_format") or formats[0]
    st.session_state["ad_format_val"] = fmt if fmt in formats else formats[0]
    try:
        sc = int(entry.get("slide_count") or 3)
    except (TypeError, ValueError):
        sc = 3
    st.session_state["slide_count_val"] = sc if sc in (2, 3, 4, 5) else 3
    ratios = ["9:16 (Story/TikTok)", "4:5 (Instagram Feed)", "1:1 (Square)", "2:3 (Portrait)", "16:9 (Landscape/YouTube)"]
    ar = entry.get("aspect_ratio") or "1:1 (Square)"
    st.session_state["aspect_ratio_val"] = ar if ar in ratios else "1:1 (Square)"
    img = entry.get("image_path")
    st.session_state["history_image_path"] = img if img else None
    st.session_state["loaded_meta_caption"] = entry.get("meta_caption", "") or ""
    st.session_state["loaded_tiktok_caption"] = entry.get("tiktok_caption", "") or ""
    st.session_state["loaded_hashtags_meta"] = entry.get("hashtags_meta", "") or ""
    st.session_state["loaded_pinterest_caption"] = entry.get("pinterest_caption", "") or ""
    st.session_state["loaded_youtube_caption"] = entry.get("youtube_caption", "") or ""
    # Bilingual caption caches (new history) or seed from single-lang entry
    _cap_el = entry.get("captions_el")
    _cap_en = entry.get("captions_en")
    if isinstance(_cap_el, dict):
        st.session_state["captions_el"] = _cap_el
    if isinstance(_cap_en, dict):
        st.session_state["captions_en"] = _cap_en
    _entry_lang = (entry.get("lang") or "el").strip().lower()
    if _entry_lang not in ("el", "en"):
        _entry_lang = "el"
    if not isinstance(st.session_state.get(f"captions_{_entry_lang}"), dict):
        store_product_caption_side(_entry_lang, {
            "meta_caption": entry.get("meta_caption", "") or "",
            "tiktok_caption": entry.get("tiktok_caption", "") or "",
            "hashtags_meta": entry.get("hashtags_meta", "") or "",
            "pinterest_caption": entry.get("pinterest_caption", "") or "",
            "youtube_caption": entry.get("youtube_caption", "") or "",
        })
    _ui_lang = st.session_state.get("lang", "el")
    if not apply_captions_for_lang(_ui_lang):
        st.session_state["results_lang"] = _entry_lang
    # Content-mode bilingual caches (when history entry is a content pack)
    _cc_el = entry.get("content_captions_el")
    _cc_en = entry.get("content_captions_en")
    _cs_el = entry.get("content_slides_el")
    _cs_en = entry.get("content_slides_en")
    if isinstance(_cc_el, dict):
        st.session_state["content_captions_el"] = _cc_el
    if isinstance(_cc_en, dict):
        st.session_state["content_captions_en"] = _cc_en
    if isinstance(_cs_el, list):
        st.session_state["content_slides_el"] = _cs_el
    if isinstance(_cs_en, list):
        st.session_state["content_slides_en"] = _cs_en
    if entry.get("content_slides") and not st.session_state.get("content_result"):
        st.session_state["content_result"] = {
            "slides": entry.get("content_slides") or [],
            "ig_caption": entry.get("meta_caption") or entry.get("ig_caption") or "",
            "tiktok_caption": entry.get("tiktok_caption") or "",
            "pinterest_caption": entry.get("pinterest_caption") or "",
            "youtube_caption": entry.get("youtube_caption") or "",
            "topic_key": entry.get("topic_key"),
            "topic_en": entry.get("topic_en"),
            "slide_count": entry.get("slide_count"),
            "lang": _entry_lang,
            "video_beats": entry.get("video_beats"),
        }
        if not isinstance(st.session_state.get(f"content_captions_{_entry_lang}"), dict):
            store_content_lang_cache(_entry_lang, st.session_state["content_result"])
        apply_content_for_lang(_ui_lang)
    elif isinstance(st.session_state.get("content_result"), dict) and (
        isinstance(_cc_el, dict) or isinstance(_cc_en, dict)
    ):
        apply_content_for_lang(_ui_lang)
    st.session_state["loaded_visual_prompt"] = entry.get("visual_prompt", "") or ""
    st.session_state["loaded_slide1_prompt"] = entry.get("slide1_prompt", "") or ""
    st.session_state["loaded_slide2_prompt"] = entry.get("slide2_prompt", "") or ""
    st.session_state["loaded_slide3_prompt"] = entry.get("slide3_prompt", "") or ""
    st.session_state["loaded_slide4_prompt"] = entry.get("slide4_prompt", "") or ""
    st.session_state["loaded_slide5_prompt"] = entry.get("slide5_prompt", "") or ""
    _vb = entry.get("video_beats")
    if not (isinstance(_vb, dict) and _vb.get("beats")):
        _vb = rebuild_video_beats_from_context(
            brand=entry.get("brand", "") or "",
            model=entry.get("model", "") or "",
            colorway=entry.get("colorway", "") or "",
            specs=entry.get("specs", "") or "",
            env=entry.get("env_desc_en") or entry.get("env_desc", "") or "",
            props=entry.get("props_desc_en") or entry.get("props_desc", "") or "",
            problem=entry.get("problem_desc_en") or entry.get("problem_desc", "") or "",
            watermark=(entry.get("watermark") or "").strip(),
            appearance=(entry.get("appearance") or "eu"),
            goal=(entry.get("goal") or "auto"),
            ad_format=entry.get("ad_format") or "",
            slide_count=entry.get("slide_count") or 3,
            lang=entry.get("lang") or st.session_state.get("lang", "el"),
            topic=entry.get("topic_en") or "",
            slide_texts=entry.get("content_slides"),
        )
    st.session_state["loaded_video_beats"] = _vb
    g = (entry.get("goal") or "auto").strip().lower()
    st.session_state["goal_val"] = g if g in GOAL_KEYS else "auto"
    ap = (entry.get("appearance") or "eu").strip().lower()
    st.session_state["appearance_val"] = ap if ap in APPEARANCE_KEYS else "eu"
    st.session_state["show_loaded_pack"] = True
    # Rebuild export ZIP from loaded history pack
    _slides = [
        entry.get("slide1_prompt", "") or "",
        entry.get("slide2_prompt", "") or "",
        entry.get("slide3_prompt", "") or "",
        entry.get("slide4_prompt", "") or "",
        entry.get("slide5_prompt", "") or "",
    ]
    try:
        _sc = int(entry.get("slide_count") or 3)
    except (TypeError, ValueError):
        _sc = 3
    _hist_img_b, _hist_img_ext, _hist_img_mime = _read_history_shoe_bytes(entry.get("image_path"))
    st.session_state["last_export_zip"] = build_pack_zip_bytes(
        brand=entry.get("brand", "") or "",
        model_name=entry.get("model", "") or "",
        colorway=entry.get("colorway", "") or "",
        goal=st.session_state["goal_val"],
        lang=entry.get("lang") or st.session_state.get("lang", "el"),
        aspect_ratio=entry.get("aspect_ratio") or "1:1 (Square)",
        slide_count=_sc,
        specs=entry.get("specs", "") or "",
        meta_caption=entry.get("meta_caption", "") or "",
        hashtags_meta=entry.get("hashtags_meta", "") or "",
        tiktok_caption=entry.get("tiktok_caption", "") or "",
        pinterest_caption=entry.get("pinterest_caption", "") or "",
        youtube_caption=entry.get("youtube_caption", "") or "",
        visual_prompt=entry.get("visual_prompt", "") or "",
        slide_prompts=[s for s in _slides if s],
        image_bytes=_hist_img_b,
        image_ext=_hist_img_ext,
        image_mime=_hist_img_mime,
        video_beats=st.session_state.get("loaded_video_beats"),
    )
    st.session_state["last_export_shoe"] = _hist_img_b
    st.session_state["last_export_shoe_ext"] = _hist_img_ext
    st.session_state["last_export_shoe_mime"] = _hist_img_mime
    _bn = (entry.get("brand") or "pack").replace(" ", "_")
    _mn = (entry.get("model") or "export").replace(" ", "_")
    st.session_state["last_export_name"] = f"{_bn}_{_mn}_pack.zip"
    if _hist_img_b and _hist_img_ext:
        st.session_state["last_export_shoe_name"] = f"{_bn}_{_mn}_shoe.{_hist_img_ext}"
    else:
        st.session_state["last_export_shoe_name"] = None
    # History ZIP is rebuilt above; clear generate-only TXT path so results UI stays accurate
    st.session_state["last_export_txt"] = None
    st.session_state["last_export_txt_name"] = None
    st.session_state["last_export_path"] = None
    for _wk in ("hist_meta_ta", "hist_tt_ta", "hist_pin_ta", "hist_yt_ta"):
        st.session_state.pop(_wk, None)
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1


def _parse_prompts_txt(text: str) -> dict:
    """Split prompts.txt into visual_prompt or slideN_prompt fields."""
    import re
    text = (text or "").strip()
    out = {
        "visual_prompt": "",
        "slide1_prompt": "",
        "slide2_prompt": "",
        "slide3_prompt": "",
        "slide4_prompt": "",
        "slide5_prompt": "",
    }
    if not text:
        return out
    parts = re.split(r"(?m)^===\s*slide(\d)\s*===\s*$", text)
    if len(parts) == 1:
        out["visual_prompt"] = text
        return out
    for i in range(1, len(parts), 2):
        try:
            n = int(parts[i])
        except (TypeError, ValueError):
            continue
        body = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        if 1 <= n <= 5:
            out[f"slide{n}_prompt"] = body
    return out


def _split_meta_caption_body(body: str) -> tuple[str, str]:
    """captions_meta.txt is caption + blank line + hashtags."""
    body = (body or "").strip()
    if not body:
        return "", ""
    if "\n\n" in body:
        cap, tags = body.split("\n\n", 1)
        return cap.strip(), tags.strip()
    return body, ""


def _normalize_import_entry(raw: dict, extras: dict | None = None) -> dict:
    """Map meta.json / history JSON (+ optional ZIP text extras) into apply_history_entry shape."""
    extras = extras or {}
    entry: dict = {}
    entry["brand"] = (raw.get("brand") or extras.get("brand") or "").strip()
    entry["model"] = (raw.get("model") or raw.get("model_name") or extras.get("model") or "").strip()
    entry["colorway"] = (raw.get("colorway") or extras.get("colorway") or "").strip()
    entry["specs"] = (raw.get("specs") or extras.get("specs") or "").strip()
    entry["goal"] = (raw.get("goal") or extras.get("goal") or "auto")
    entry["lang"] = raw.get("lang") or extras.get("lang") or "el"
    entry["appearance"] = raw.get("appearance") or extras.get("appearance") or "eu"

    aspect = raw.get("aspect_ratio") or raw.get("aspect") or extras.get("aspect_ratio") or "1:1 (Square)"
    entry["aspect_ratio"] = aspect

    try:
        sc = int(raw.get("slide_count") if raw.get("slide_count") is not None else extras.get("slide_count") or 3)
    except (TypeError, ValueError):
        sc = 3
    entry["slide_count"] = sc

    meta_cap = (raw.get("meta_caption") or extras.get("meta_caption") or "").strip()
    hashtags = (raw.get("hashtags_meta") or extras.get("hashtags_meta") or "").strip()
    if not meta_cap and extras.get("captions_meta_raw"):
        meta_cap, parsed_tags = _split_meta_caption_body(extras["captions_meta_raw"])
        if not hashtags:
            hashtags = parsed_tags
    entry["meta_caption"] = meta_cap
    entry["hashtags_meta"] = hashtags
    entry["tiktok_caption"] = (raw.get("tiktok_caption") or extras.get("tiktok_caption") or "").strip()
    entry["pinterest_caption"] = (raw.get("pinterest_caption") or extras.get("pinterest_caption") or "").strip()
    entry["youtube_caption"] = (raw.get("youtube_caption") or extras.get("youtube_caption") or "").strip()

    for k in ("visual_prompt", "slide1_prompt", "slide2_prompt", "slide3_prompt", "slide4_prompt", "slide5_prompt"):
        entry[k] = (raw.get(k) or extras.get(k) or "").strip()
    if not any(entry[k] for k in ("visual_prompt", "slide1_prompt", "slide2_prompt", "slide3_prompt", "slide4_prompt", "slide5_prompt")):
        if extras.get("prompts_txt"):
            entry.update(_parse_prompts_txt(extras["prompts_txt"]))
    _vb = raw.get("video_beats") or extras.get("video_beats")
    if isinstance(_vb, dict) and _vb.get("beats"):
        entry["video_beats"] = _vb
    elif extras.get("video_prompts_txt"):
        entry["video_prompts_txt"] = extras.get("video_prompts_txt")

    for k in ("env_desc", "props_desc", "problem_desc", "watermark", "selected_tag", "selected_badge", "ad_format", "image_path"):
        if raw.get(k) is not None:
            entry[k] = raw.get(k)

    if not entry.get("ad_format"):
        has_slides = any(entry.get(f"slide{i}_prompt") for i in range(1, 6))
        if has_slides or (entry.get("slide_count") or 0) >= 2:
            entry["ad_format"] = "Carousel Pack (multi-slide)"
        else:
            entry["ad_format"] = "Single Layout Ad (1 Εικόνα)"

    if raw.get("id"):
        entry["id"] = raw["id"]
    if raw.get("created_at"):
        entry["created_at"] = raw["created_at"]
    return entry



def _split_export_sections(text: str) -> dict[str, str]:
    """Split ===== HEADER ===== blocks into {HEADER_UPPER: body}."""
    import re
    text = text or ""
    parts = re.split(r"(?m)^={3,}\s*\n([^\n]+?)\s*\n={3,}\s*$", text)
    out: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        header = (parts[i] or "").strip().upper()
        body = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        if header:
            out[header] = body
    return out


def _parse_nano_banana_section(body: str) -> dict:
    """Parse NANO BANANA VISUAL PROMPT body: single prompt or Slide N: blocks."""
    import re
    body = (body or "").strip()
    out = {
        "visual_prompt": "",
        "slide1_prompt": "",
        "slide2_prompt": "",
        "slide3_prompt": "",
        "slide4_prompt": "",
        "slide5_prompt": "",
    }
    if not body:
        return out
    parts = re.split(r"(?mi)^Slide\s*(\d)\s*:\s*$", body)
    if len(parts) == 1:
        out["visual_prompt"] = body
        return out
    for i in range(1, len(parts), 2):
        try:
            n = int(parts[i])
        except (TypeError, ValueError):
            continue
        slide_body = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        if 1 <= n <= 5:
            out[f"slide{n}_prompt"] = slide_body
    return out


def _section_body(sections: dict[str, str], *needles: str) -> str:
    """Return first section body whose header contains all needles (casefold)."""
    needles_u = [n.upper() for n in needles]
    for header, body in sections.items():
        h = header.upper()
        if all(n in h for n in needles_u):
            return body
    return ""


def _parse_content_export_txt(text: str) -> dict | None:
    """Restore content_result from CONTENT CAROUSEL TXT export."""
    import re
    if "CONTENT CAROUSEL" not in (text or "").upper():
        return None
    sections = _split_export_sections(text)
    raw_json = _section_body(sections, "RAW JSON")
    if not raw_json:
        for header, body in sections.items():
            if "RAW" in header.upper() and "JSON" in header.upper():
                raw_json = body
                break
    if raw_json:
        try:
            data = json.loads(raw_json)
            if isinstance(data, dict) and (data.get("slides") or data.get("ig_caption") or data.get("tiktok_caption")):
                return data
        except Exception:
            pass

    slides = []
    for m in re.finditer(
        r"(?is)---\s*SLIDE\s*(\d+)\s*---\s*(.*?)(?=---\s*SLIDE\s*\d+\s*---|={3,}|$)",
        text,
    ):
        block = m.group(2) or ""
        title_m = re.search(r"(?im)^Title:\s*(.*)$", block)
        body_m = re.search(r"(?im)^Body:\s*(.*)$", block)
        prompt = ""
        pm = re.search(r"(?is)Image prompt:\s*(.*?)(?=\n\n|\Z)", block)
        if pm:
            prompt = (pm.group(1) or "").strip()
        slides.append(
            {
                "title": (title_m.group(1).strip() if title_m else ""),
                "body": (body_m.group(1).strip() if body_m else ""),
                "image_prompt": prompt,
            }
        )

    topic_key = ""
    topic_en = ""
    tk = re.search(r"(?im)^Topic key:\s*(.*)$", text)
    te = re.search(r"(?im)^Topic:\s*(.*)$", text)
    if tk:
        topic_key = tk.group(1).strip()
    if te:
        topic_en = te.group(1).strip()

    result = {
        "topic_key": topic_key,
        "topic_en": topic_en,
        "slides": slides,
        "slide_count": len(slides) if slides else 0,
        "ig_caption": _section_body(sections, "INSTAGRAM CAPTION"),
        "tiktok_caption": _section_body(sections, "TIKTOK CAPTION"),
        "pinterest_caption": _section_body(sections, "PINTEREST"),
        "youtube_caption": _section_body(sections, "YOUTUBE"),
    }
    if not slides and not any(result.get(k) for k in ("ig_caption", "tiktok_caption", "pinterest_caption", "youtube_caption")):
        return None
    return result


def _parse_product_export_txt(text: str) -> dict | None:
    """Parse product pack TXT (NANO BANANA / captions / RAW DATA JSON) into history entry."""
    sections = _split_export_sections(text)
    raw: dict = {}
    raw_body = ""
    for header, body in sections.items():
        if "RAW" in header.upper() and "JSON" in header.upper():
            raw_body = body
            break
    if raw_body:
        try:
            parsed = json.loads(raw_body)
            if isinstance(parsed, dict):
                raw = parsed
        except Exception:
            raw = {}

    extras: dict = {}
    nano = _section_body(sections, "NANO BANANA") or _section_body(sections, "VISUAL PROMPT")
    if nano:
        extras.update(_parse_nano_banana_section(nano))

    fb = ""
    for header, body in sections.items():
        h = header.upper()
        if "FACEBOOK" in h or ("INSTAGRAM" in h and "POST" in h):
            fb = body
            break
    if fb:
        extras["captions_meta_raw"] = fb
        cap, tags = _split_meta_caption_body(fb)
        extras["meta_caption"] = cap
        extras["hashtags_meta"] = tags

    for header, body in sections.items():
        h = header.upper()
        if "TIKTOK" in h:
            extras["tiktok_caption"] = body
        elif "PINTEREST" in h:
            extras["pinterest_caption"] = body
        elif "YOUTUBE" in h:
            extras["youtube_caption"] = body

    entry = _normalize_import_entry(raw, extras)
    useful = (
        entry.get("brand")
        or entry.get("model")
        or entry.get("meta_caption")
        or entry.get("visual_prompt")
        or any(entry.get(f"slide{i}_prompt") for i in range(1, 6))
        or entry.get("tiktok_caption")
        or entry.get("pinterest_caption")
        or entry.get("youtube_caption")
        or entry.get("specs")
    )
    if not useful:
        return None
    return entry


def _import_from_export_txt(text: str) -> tuple[dict | None, bytes | None, str | None, str]:
    """Parse downloaded product/content TXT export into import_pack_bytes result."""
    import re
    text = text or ""
    if "CONTENT CAROUSEL" in text.upper():
        content = _parse_content_export_txt(text)
        if content:
            return (
                {
                    "_kind": "content",
                    "content_result": content,
                    "content_txt": text,
                },
                None,
                None,
                "",
            )
        extras = {
            "visual_prompt": "",
            "slide1_prompt": "",
            "slide2_prompt": "",
            "slide3_prompt": "",
            "slide4_prompt": "",
            "slide5_prompt": "",
        }
        for m in re.finditer(
            r"(?is)---\s*SLIDE\s*(\d+)\s*---\s*(.*?)(?=---\s*SLIDE\s*\d+\s*---|={3,}|$)",
            text,
        ):
            try:
                n = int(m.group(1))
            except (TypeError, ValueError):
                continue
            block = m.group(2) or ""
            pm = re.search(r"(?is)Image prompt:\s*(.*?)(?=\n\n|\Z)", block)
            if pm and 1 <= n <= 5:
                extras[f"slide{n}_prompt"] = (pm.group(1) or "").strip()
        sections = _split_export_sections(text)
        extras["meta_caption"] = _section_body(sections, "INSTAGRAM CAPTION")
        extras["tiktok_caption"] = _section_body(sections, "TIKTOK CAPTION")
        extras["pinterest_caption"] = _section_body(sections, "PINTEREST")
        extras["youtube_caption"] = _section_body(sections, "YOUTUBE")
        entry = _normalize_import_entry({}, extras)
        if any(entry.get(f"slide{i}_prompt") for i in range(1, 6)) or entry.get("meta_caption"):
            return entry, None, None, ""
        return None, None, None, "bad"

    entry = _parse_product_export_txt(text)
    if entry:
        return entry, None, None, ""
    return None, None, None, "bad"


def import_pack_bytes(data: bytes, filename: str = "") -> tuple[dict | None, bytes | None, str | None, str]:
    """
    Parse uploaded ZIP, JSON, or TXT export into a history-shaped entry (or content pack).
    Returns (entry, image_bytes, mime_type, error_message).
    error_message empty on success.
    """
    name = (filename or "").lower()
    image_bytes = None
    mime = None
    try:
        if name.endswith(".zip") or (len(data) >= 2 and data[:2] == b"PK"):
            with zipfile.ZipFile(io.BytesIO(data), mode="r") as zf:
                names = zf.namelist()
                meta_name = None
                for cand in names:
                    base = cand.replace("\\", "/").split("/")[-1].lower()
                    if base == "meta.json":
                        meta_name = cand
                        break
                raw: dict = {}
                if meta_name:
                    parsed = json.loads(zf.read(meta_name).decode("utf-8"))
                    if not isinstance(parsed, dict):
                        return None, None, None, "bad"
                    raw = parsed

                def _read_txt(basename: str) -> str:
                    for cand in names:
                        if cand.replace("\\", "/").split("/")[-1].lower() == basename.lower():
                            try:
                                return zf.read(cand).decode("utf-8", errors="replace")
                            except Exception:
                                return ""
                    return ""

                extras = {
                    "captions_meta_raw": _read_txt("captions_meta.txt"),
                    "tiktok_caption": _read_txt("captions_tiktok.txt"),
                    "pinterest_caption": _read_txt("captions_pinterest.txt"),
                    "youtube_caption": _read_txt("captions_youtube.txt"),
                    "prompts_txt": _read_txt("prompts.txt"),
                    "video_prompts_txt": _read_txt("video_prompts.txt"),
                }
                if isinstance(raw, dict) and raw.get("video_beats"):
                    extras["video_beats"] = raw.get("video_beats")
                img_exts = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
                # Prefer shoe.jpg / shoe.png written by export; else first image in ZIP
                image_candidates = []
                for cand in names:
                    low = cand.replace("\\", "/").split("/")[-1].lower()
                    for ext, mt in img_exts.items():
                        if low.endswith(ext) and not low.startswith("."):
                            image_candidates.append((low.startswith("shoe."), cand, mt))
                            break
                image_candidates.sort(key=lambda x: (not x[0], x[1]))
                if image_candidates:
                    _, cand, mt = image_candidates[0]
                    image_bytes = zf.read(cand)
                    mime = mt

                if not raw and not extras["prompts_txt"] and not extras["captions_meta_raw"]:
                    return None, None, None, "bad"
                entry = _normalize_import_entry(raw, extras)
                useful = (
                    entry.get("brand")
                    or entry.get("model")
                    or entry.get("meta_caption")
                    or entry.get("visual_prompt")
                    or any(entry.get(f"slide{i}_prompt") for i in range(1, 6))
                    or entry.get("specs")
                )
                if not useful:
                    return None, None, None, "bad"
                return entry, image_bytes, mime, ""
        else:
            text = data.decode("utf-8", errors="replace")
            stripped = text.strip()
            is_txt_name = name.endswith(".txt")
            looks_export = (
                "NANO BANANA" in text.upper()
                or "CONTENT CAROUSEL" in text.upper()
                or "RAW DATA (JSON)" in text.upper()
                or "RAW JSON" in text.upper()
                or text.lstrip().startswith("=====")
            )
            if is_txt_name or (looks_export and not stripped.startswith("{") and not stripped.startswith("[")):
                return _import_from_export_txt(text)
            raw = json.loads(text)
            if not isinstance(raw, dict):
                return None, None, None, "bad"
            entry = _normalize_import_entry(raw, {})
            useful = (
                entry.get("brand")
                or entry.get("model")
                or entry.get("meta_caption")
                or entry.get("visual_prompt")
                or any(entry.get(f"slide{i}_prompt") for i in range(1, 6))
                or entry.get("specs")
            )
            if not useful:
                return None, None, None, "bad"
            return entry, None, None, ""
    except Exception:
        return None, None, None, "bad"


if "brand_val" not in st.session_state: st.session_state["brand_val"] = ""
if "model_val" not in st.session_state: st.session_state["model_val"] = ""
if "colorway_val" not in st.session_state: st.session_state["colorway_val"] = ""
if "specs_val" not in st.session_state: st.session_state["specs_val"] = ""
if "scene_vibe_val" not in st.session_state: st.session_state["scene_vibe_val"] = "auto"
if (
    "env_desc_val" not in st.session_state
    or "props_desc_val" not in st.session_state
    or "problem_desc_val" not in st.session_state
    or "env_desc_en" not in st.session_state
    or "props_desc_en" not in st.session_state
    or "problem_desc_en" not in st.session_state
):
    _init_pack = pick_scene_pack("", "", "", vibe=st.session_state.get("scene_vibe_val", "auto") or "auto")
    apply_scene_pack_to_session(_init_pack, lang=st.session_state.get("lang", "el"))

# Refresh visible scene text when UI language flips el↔en
if st.session_state.pop("_lang_switch_pending", False):
    refresh_scene_fields_for_lang(
        st.session_state.get("lang", "el"),
        st.session_state.get("_lang_switch_from", "el"),
    )
    _ui_lang = st.session_state.get("lang", "el")
    if st.session_state.get("show_loaded_pack"):
        ensure_product_captions_for_lang(_ui_lang)
    if isinstance(st.session_state.get("content_result"), dict):
        ensure_content_for_lang(_ui_lang)
if "uploader_key" not in st.session_state: st.session_state["uploader_key"] = 0
if "watermark_val" not in st.session_state: st.session_state["watermark_val"] = ""
if "selected_tag_val" not in st.session_state: st.session_state["selected_tag_val"] = AUTHENTICITY_TAGS[0]
if "selected_badge_val" not in st.session_state: st.session_state["selected_badge_val"] = CATEGORY_BADGES[0]
if "ad_format_val" not in st.session_state: st.session_state["ad_format_val"] = "Single Layout Ad (1 Εικόνα)"
if "slide_count_val" not in st.session_state: st.session_state["slide_count_val"] = 3
if "aspect_ratio_val" not in st.session_state: st.session_state["aspect_ratio_val"] = "1:1 (Square)"
if "history_image_path" not in st.session_state: st.session_state["history_image_path"] = None
if "loaded_meta_caption" not in st.session_state: st.session_state["loaded_meta_caption"] = ""
if "loaded_tiktok_caption" not in st.session_state: st.session_state["loaded_tiktok_caption"] = ""
if "loaded_hashtags_meta" not in st.session_state: st.session_state["loaded_hashtags_meta"] = ""
if "loaded_pinterest_caption" not in st.session_state: st.session_state["loaded_pinterest_caption"] = ""
if "loaded_youtube_caption" not in st.session_state: st.session_state["loaded_youtube_caption"] = ""
if "loaded_visual_prompt" not in st.session_state: st.session_state["loaded_visual_prompt"] = ""
if "loaded_slide1_prompt" not in st.session_state: st.session_state["loaded_slide1_prompt"] = ""
if "loaded_slide2_prompt" not in st.session_state: st.session_state["loaded_slide2_prompt"] = ""
if "loaded_slide3_prompt" not in st.session_state: st.session_state["loaded_slide3_prompt"] = ""
if "loaded_slide4_prompt" not in st.session_state: st.session_state["loaded_slide4_prompt"] = ""
if "loaded_slide5_prompt" not in st.session_state: st.session_state["loaded_slide5_prompt"] = ""
if "loaded_video_beats" not in st.session_state: st.session_state["loaded_video_beats"] = None
if "show_loaded_pack" not in st.session_state: st.session_state["show_loaded_pack"] = False
if "goal_val" not in st.session_state: st.session_state["goal_val"] = "auto"
if "appearance_val" not in st.session_state: st.session_state["appearance_val"] = "eu"
if "active_insight" not in st.session_state: st.session_state["active_insight"] = ""
if "last_export_zip" not in st.session_state: st.session_state["last_export_zip"] = None
if "last_export_shoe" not in st.session_state: st.session_state["last_export_shoe"] = None
if "last_export_shoe_ext" not in st.session_state: st.session_state["last_export_shoe_ext"] = None
if "last_export_shoe_mime" not in st.session_state: st.session_state["last_export_shoe_mime"] = None
if "last_export_shoe_name" not in st.session_state: st.session_state["last_export_shoe_name"] = None
if "last_export_name" not in st.session_state: st.session_state["last_export_name"] = "content_pack.zip"
if "last_export_txt" not in st.session_state: st.session_state["last_export_txt"] = None
if "last_export_txt_name" not in st.session_state: st.session_state["last_export_txt_name"] = None
if "last_export_path" not in st.session_state: st.session_state["last_export_path"] = None
if "app_mode_val" not in st.session_state: st.session_state["app_mode_val"] = "product"
if "content_topic_key" not in st.session_state: st.session_state["content_topic_key"] = "tips"
if "content_topic_override" not in st.session_state: st.session_state["content_topic_override"] = ""
if "content_slide_count_val" not in st.session_state: st.session_state["content_slide_count_val"] = 5
if "content_result" not in st.session_state: st.session_state["content_result"] = None
if "content_txt" not in st.session_state: st.session_state["content_txt"] = ""
if "content_zip" not in st.session_state: st.session_state["content_zip"] = None
if "content_zip_name" not in st.session_state: st.session_state["content_zip_name"] = "content_carousel.zip"


# 3b. HISTORY SIDEBAR (below language switcher)
with st.sidebar:
    st.markdown(t("history_title", lang))
    history_entries = load_history()
    history_entries_sorted = sorted(
        history_entries,
        key=lambda e: e.get("created_at", ""),
        reverse=True,
    )
    if not history_entries_sorted:
        st.caption(t("history_empty", lang))
    else:
        labels = []
        id_by_label = {}
        for e in history_entries_sorted:
            created = (e.get("created_at") or "")[:10]
            label = f"{e.get('brand', '')} {e.get('model', '')} — {created}".strip()
            base = label
            n = 2
            while label in id_by_label:
                label = f"{base} ({n})"
                n += 1
            labels.append(label)
            id_by_label[label] = e.get("id")

        selected_label = st.selectbox(t("history_select", lang), labels, key="history_select_label")
        col_load, col_del = st.columns(2)
        with col_load:
            if st.button(t("history_load", lang), use_container_width=True, key="history_load_btn"):
                entry = get_entry(id_by_label[selected_label])
                if entry:
                    apply_history_entry(entry)
                    st.rerun()
        with col_del:
            if st.button(t("history_delete", lang), use_container_width=True, key="history_delete_btn"):
                delete_entry(id_by_label[selected_label])
                st.rerun()

# 3b2. IMPORT PACK FROM PC
with st.sidebar:

    st.markdown("---")
    st.file_uploader(
        t("import_pack_label", lang),
        type=["zip", "json", "txt"],
        help=t("import_pack_help", lang),
        key="import_pack_uploader",
    )
    _imp = st.session_state.get("import_pack_uploader")
    if _imp is not None and st.session_state.get("_import_pack_done_name") != getattr(_imp, "name", None):
        _entry, _img_b, _mime, _err = import_pack_bytes(_imp.getvalue(), getattr(_imp, "name", "") or "")
        if _err or not _entry:
            st.error(t("import_bad", lang))
        else:
            if _entry.get("_kind") == "content":
                _cr = _entry.get("content_result") or {}
                st.session_state["content_result"] = _cr
                for _side, _key in (("el", "content_captions_el"), ("en", "content_captions_en")):
                    _caps = _entry.get(_key) or _cr.get(_key)
                    if isinstance(_caps, dict):
                        st.session_state[f"content_captions_{_side}"] = _caps
                for _side, _key in (("el", "content_slides_el"), ("en", "content_slides_en")):
                    _sl = _entry.get(_key) or _cr.get(_key)
                    if isinstance(_sl, list):
                        st.session_state[f"content_slides_{_side}"] = _sl
                _cr_lang = (_cr.get("lang") or _entry.get("lang") or lang or "el")
                if not isinstance(st.session_state.get(f"content_captions_{_cr_lang}"), dict):
                    store_content_lang_cache(_cr_lang, _cr)
                apply_content_for_lang(lang)
                st.session_state["content_txt"] = _entry.get("content_txt") or build_content_txt(
                    st.session_state.get("content_result") or _cr
                )
                st.session_state["app_mode_val"] = "content"
                if _cr.get("topic_key"):
                    st.session_state["content_topic_key"] = _cr.get("topic_key")
                if _cr.get("topic_en"):
                    st.session_state["content_topic_override"] = _cr.get("topic_en")
                try:
                    _sc = int(_cr.get("slide_count") or len(_cr.get("slides") or []) or 5)
                except (TypeError, ValueError):
                    _sc = 5
                if _sc in (4, 5, 6):
                    st.session_state["content_slide_count_val"] = _sc
            else:
                # Persist into history for this session/server lifetime; restore image if present
                try:
                    _saved = add_entry(_entry, image_bytes=_img_b, mime_type=_mime)
                    if _saved.get("image_path"):
                        _entry["image_path"] = _saved["image_path"]
                except Exception:
                    pass
                apply_history_entry(_entry)
            st.session_state["_import_pack_done_name"] = getattr(_imp, "name", None)
            st.success(t("import_ok", lang))
            st.rerun()



# 3c. WEEKLY INSIGHTS (sidebar)
with st.sidebar:
    st.markdown("---")
    st.markdown(t("insights_title", lang))
    _insights = load_weekly_insights()
    if not _insights:
        st.caption(t("insights_empty", lang))
    else:
        if st.session_state.get("active_insight"):
            st.info(t("insights_active", lang, text=st.session_state["active_insight"][:160]))
            if st.button(t("insights_clear", lang), key="clear_insight_btn"):
                st.session_state["active_insight"] = ""
                st.rerun()
        with st.expander(t("insights_actions", lang), expanded=True):
            for i, insight in enumerate(_insights.get("top_3_actionable_insights") or []):
                insight_txt = pick_lang_text(insight, lang)
                st.write(insight_txt)
                if st.button(t("insights_use", lang), key=f"use_action_insight_{i}"):
                    st.session_state["active_insight"] = insight_txt
                    st.rerun()
        with st.expander(t("insights_intent", lang), expanded=False):
            for i, row in enumerate(_insights.get("consumer_search_intent") or []):
                q = pick_lang_text(row.get("query", ""), lang)
                intent = pick_lang_text(row.get("intent", ""), lang)
                issue = pick_lang_text(row.get("core_issue", ""), lang)
                st.markdown(f"**{q}**")
                st.caption(f"{t('insights_intent_label', lang)}: {intent}")
                st.caption(f"{t('insights_issue', lang)}: {issue}")
                if st.button(t("insights_use", lang), key=f"use_intent_{i}"):
                    st.session_state["active_insight"] = f"{q} | {intent} | {issue}"
                    st.rerun()
        with st.expander(t("insights_ecom", lang), expanded=False):
            for i, row in enumerate(_insights.get("ecom_monitoring") or []):
                cat = pick_lang_text(row.get("category", ""), lang)
                demand = pick_lang_text(row.get("demand_trend", ""), lang)
                stock = pick_lang_text(row.get("stock_status", ""), lang)
                benefit = pick_lang_text(row.get("key_benefit", ""), lang)
                st.markdown(f"**{cat}**")
                st.caption(f"{t('insights_demand', lang)}: {demand}")
                st.caption(f"{t('insights_stock', lang)}: {stock}")
                st.caption(f"{t('insights_benefit', lang)}: {benefit}")
                if st.button(t("insights_use", lang), key=f"use_ecom_{i}"):
                    st.session_state["active_insight"] = f"{cat} | {demand} | {stock} | {benefit}"
                    st.rerun()


# 3d. QUICK-START ONBOARDING (before mode / upload)
with st.expander(t("onboarding_title", lang), expanded=True):
    st.markdown(t("onboarding_body", lang).replace("\n", "  \n"))

# 3e. APP MODE TOGGLE
_mode_options = ["product", "content"]
_mode_labels = {
    "product": t("mode_product", lang),
    "content": t("mode_content", lang),
}
_cur_mode = st.session_state.get("app_mode_val", "product")
if _cur_mode not in _mode_options:
    _cur_mode = "product"
_picked_mode_label = st.radio(
    t("mode_label", lang),
    [_mode_labels[k] for k in _mode_options],
    index=_mode_options.index(_cur_mode),
    horizontal=True,
    key="app_mode_radio",
)
_label_to_mode = {v: k for k, v in _mode_labels.items()}
st.session_state["app_mode_val"] = _label_to_mode.get(_picked_mode_label, "product")
app_mode = st.session_state["app_mode_val"]

# ========== CONTENT CAROUSEL MODE ==========
if app_mode == "content":
    st.markdown("---")
    st.markdown(f"### {t('weekly_suggestions_title', lang)}")
    _insights_for_topics = load_weekly_insights()
    _suggestions = weekly_suggestions(_insights_for_topics, lang=lang, count=4)
    for _si, _sug in enumerate(_suggestions):
        _c1, _c2 = st.columns([4, 1])
        with _c1:
            st.write(f"• {_sug}")
        with _c2:
            if st.button(t("weekly_suggestion_use", lang), key=f"use_weekly_sug_{_si}"):
                st.session_state["content_topic_override"] = _sug
                st.rerun()

    _topic_keys = TOPIC_KEYS
    _topic_display = [t(f"topic_{k}", lang) if t(f"topic_{k}", lang) != f"topic_{k}" else topic_label(k, lang) for k in _topic_keys]
    _cur_tk = st.session_state.get("content_topic_key", "tips")
    if _cur_tk not in _topic_keys:
        _cur_tk = "tips"
    _tk_idx = _topic_keys.index(_cur_tk)
    _picked_topic_label = st.selectbox(
        t("topic_picker_label", lang),
        _topic_display,
        index=_tk_idx,
        key="content_topic_select",
    )
    st.session_state["content_topic_key"] = _topic_keys[_topic_display.index(_picked_topic_label)]

    _override = st.text_input(
        t("topic_override_label", lang),
        value=st.session_state.get("content_topic_override", ""),
        placeholder=t("topic_override_placeholder", lang),
        key="content_override_input",
    )
    st.session_state["content_topic_override"] = _override

    _ar_options_c = ["9:16 (Story/TikTok)", "4:5 (Instagram Feed)", "1:1 (Square)", "2:3 (Portrait)", "16:9 (Landscape/YouTube)"]
    _ar_idx_c = _ar_options_c.index(st.session_state["aspect_ratio_val"]) if st.session_state.get("aspect_ratio_val") in _ar_options_c else _ar_options_c.index("1:1 (Square)")
    _aspect_c = st.selectbox(t("aspect_label", lang), _ar_options_c, index=_ar_idx_c, key="content_aspect_select")
    st.session_state["aspect_ratio_val"] = _aspect_c

    _appearance_labels_c = {
        "auto": t("appearance_auto", lang),
        "eu": t("appearance_eu", lang),
        "diverse": t("appearance_diverse", lang),
        "no_face": t("appearance_no_face", lang),
    }
    st.caption(t("appearance_help", lang))
    _cur_ap_c = st.session_state.get("appearance_val", "eu")
    if _cur_ap_c not in APPEARANCE_KEYS:
        _cur_ap_c = "eu"
    _picked_ap_c = st.selectbox(
        t("appearance_label", lang),
        [_appearance_labels_c[k] for k in APPEARANCE_KEYS],
        index=APPEARANCE_KEYS.index(_cur_ap_c),
        key="content_appearance_select",
    )
    _label_to_ap_c = {v: k for k, v in _appearance_labels_c.items()}
    st.session_state["appearance_val"] = _label_to_ap_c.get(_picked_ap_c, "eu")

    _sc_opts = [4, 5, 6]
    _cur_sc = st.session_state.get("content_slide_count_val", 5)
    if _cur_sc not in _sc_opts:
        _cur_sc = 5
    _slide_c = st.selectbox(
        t("content_slide_count_label", lang),
        _sc_opts,
        index=_sc_opts.index(_cur_sc),
        key="content_slide_count_select",
    )
    st.session_state["content_slide_count_val"] = _slide_c

    st.markdown("---")
    _can_gen_content = usage.can_generate(st.session_state)
    if not _can_gen_content:
        st.warning(t("limit_reached", lang))
        st.markdown(f"[{t('go_pro', lang)}]({usage.LEMON_CHECKOUT_URL})")
    if st.button(
        t("generate_content_button", lang),
        type="primary",
        key="gen_content_btn",
        disabled=not _can_gen_content,
    ):
        def _warn(msg):
            st.warning(t("model_failed", lang, model="gemini", error=msg))

        with st.spinner(t("generate_content_spinner", lang)):
            _result = generate_content_carousel(
                client,
                topic_key=st.session_state["content_topic_key"],
                topic_override=st.session_state.get("content_topic_override", "") or "",
                slide_count=int(st.session_state.get("content_slide_count_val", 5)),
                aspect_ratio=st.session_state.get("aspect_ratio_val", "1:1 (Square)"),
                insight_context=st.session_state.get("active_insight", "") or "",
                appearance=st.session_state.get("appearance_val", "eu"),
                lang=lang,
                models=["gemini-3.6-flash", "gemini-2.5-flash"],
                warn=_warn,
            )
        _cvb = build_grok_video_beats(
            brand="",
            model="",
            colorway="",
            specs="",
            watermark=st.session_state.get("watermark_val", ""),
            appearance=st.session_state.get("appearance_val", "eu"),
            goal="content",
            mode="content",
            slide_count=_result.get("slide_count") or len(_result.get("slides") or []) or 3,
            slide_texts=_result.get("slides") or [],
            lang=lang,
            topic=_result.get("topic_en") or "",
        )
        _result["video_beats"] = _cvb
        st.session_state["content_result"] = _result
        st.session_state["content_video_beats"] = _cvb
        # Bilingual content captions + slide title/body (image_prompt stays EN from primary)
        store_content_lang_cache(lang, _result)
        _c_other = _other_lang(lang)
        try:
            _result_other = generate_content_carousel(
                client,
                topic_key=st.session_state["content_topic_key"],
                topic_override=st.session_state.get("content_topic_override", "") or "",
                slide_count=int(st.session_state.get("content_slide_count_val", 5)),
                aspect_ratio=st.session_state.get("aspect_ratio_val", "1:1 (Square)"),
                insight_context=st.session_state.get("active_insight", "") or "",
                appearance=st.session_state.get("appearance_val", "eu"),
                lang=_c_other,
                models=["gemini-3.6-flash", "gemini-2.5-flash"],
                warn=_warn,
            )
            _old_slides = _result.get("slides") or []
            _new_slides = _result_other.get("slides") or []
            if _old_slides and _new_slides and len(_old_slides) == len(_new_slides):
                for _i, _ns in enumerate(_new_slides):
                    if isinstance(_ns, dict) and isinstance(_old_slides[_i], dict):
                        _ip = _old_slides[_i].get("image_prompt")
                        if _ip:
                            _ns["image_prompt"] = _ip
                _result_other["slides"] = _new_slides
            store_content_lang_cache(_c_other, _result_other)
        except Exception:
            pass
        apply_content_for_lang(lang)
        usage.record_generate(st.session_state)
        _result = st.session_state.get("content_result") or _result
        _txt = build_content_txt(_result)
        st.session_state["content_txt"] = _txt
        st.session_state["content_zip"] = build_content_zip_bytes(
            _result, aspect_ratio=st.session_state.get("aspect_ratio_val", "1:1 (Square)")
        )
        _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _tk = (_result.get("topic_key") or "content").replace(" ", "_")
        st.session_state["content_zip_name"] = f"content_{_tk}_{_ts}.zip"
        os.makedirs("output", exist_ok=True)
        _out = f"output/content_{_tk}_{_ts}.txt"
        with open(_out, "w", encoding="utf-8") as _f:
            _f.write(_txt)
        st.session_state["content_out_path"] = _out
        # Optional: light history entry with type=content
        try:
            add_entry({
                "type": "content",
                "brand": "Content",
                "model": _result.get("topic_en") or _tk,
                "colorway": "",
                "specs": "",
                "topic_key": _result.get("topic_key"),
                "topic_en": _result.get("topic_en"),
                "slide_count": _result.get("slide_count"),
                "aspect_ratio": st.session_state.get("aspect_ratio_val", "1:1 (Square)"),
                "appearance": st.session_state.get("appearance_val", "eu"),
                "meta_caption": _result.get("ig_caption", ""),
                "tiktok_caption": _result.get("tiktok_caption", ""),
                "hashtags_meta": "",
                "pinterest_caption": _result.get("pinterest_caption", ""),
                "youtube_caption": _result.get("youtube_caption", ""),
                "lang": lang,
                "content_captions_el": st.session_state.get("content_captions_el"),
                "content_captions_en": st.session_state.get("content_captions_en"),
                "content_slides_el": st.session_state.get("content_slides_el"),
                "content_slides_en": st.session_state.get("content_slides_en"),
                "content_slides": _result.get("slides"),
                "goal": "content",
                "ad_format": "Content Carousel",
                "slide1_prompt": (_result.get("slides") or [{}])[0].get("image_prompt", "") if (_result.get("slides") or []) else "",
                "slide2_prompt": (_result.get("slides") or [{}, {}])[1].get("image_prompt", "") if len(_result.get("slides") or []) > 1 else "",
                "slide3_prompt": (_result.get("slides") or [{}, {}, {}])[2].get("image_prompt", "") if len(_result.get("slides") or []) > 2 else "",
                "slide4_prompt": (_result.get("slides") or [{}, {}, {}, {}])[3].get("image_prompt", "") if len(_result.get("slides") or []) > 3 else "",
                "slide5_prompt": (_result.get("slides") or [{}, {}, {}, {}, {}])[4].get("image_prompt", "") if len(_result.get("slides") or []) > 4 else "",
                "content_slides": _result.get("slides"),
                "video_beats": _cvb,
            })
        except Exception:
            pass
        st.info(t("content_saved_info", lang, path=_out))

    _cr = st.session_state.get("content_result")
    if _cr:
        st.markdown(t("content_results_title", lang))
        for _i, _slide in enumerate(_cr.get("slides") or [], start=1):
            st.write(t("content_slide_heading", lang, n=_i))
            st.text_input(t("content_title_label", lang), value=_slide.get("title", ""), key=f"c_title_{_i}", disabled=False)
            st.text_area(t("content_body_label", lang), value=_slide.get("body", ""), height=80, key=f"c_body_{_i}")
            st.caption(t("content_prompt_label", lang))
            st.code(_slide.get("image_prompt", ""), language="text")
        st.markdown(t("content_captions_section", lang))
        _c_tabs = st.tabs([
            t("tab_meta", lang, lang_name=t("lang_name", lang)),
            t("tab_tiktok", lang, lang_name=t("lang_name", lang)),
            t("tab_pinterest", lang, lang_name=t("lang_name", lang)),
            t("tab_youtube", lang, lang_name=t("lang_name", lang)),
            t("tab_video", lang, lang_name=t("lang_name", lang)),
        ])
        with _c_tabs[0]:
            st.text_area(t("content_ig_label", lang), value=_cr.get("ig_caption", ""), height=140, key="c_ig_cap")
        with _c_tabs[1]:
            st.text_area(t("content_tiktok_label", lang), value=_cr.get("tiktok_caption", ""), height=100, key="c_tt_cap")
        with _c_tabs[2]:
            st.text_area(t("content_pinterest_label", lang), value=_cr.get("pinterest_caption", ""), height=140, key="c_pin_cap")
        with _c_tabs[3]:
            st.text_area(t("content_youtube_label", lang), value=_cr.get("youtube_caption", ""), height=120, key="c_yt_cap")
        with _c_tabs[4]:
            _cvb = _cr.get("video_beats") or st.session_state.get("content_video_beats")
            if not (isinstance(_cvb, dict) and _cvb.get("beats")):
                _cvb = build_grok_video_beats(
                    brand="",
                    model="",
                    colorway="",
                    specs="",
                    watermark=st.session_state.get("watermark_val", ""),
                    appearance=st.session_state.get("appearance_val", "eu"),
                    goal="content",
                    mode="content",
                    slide_count=_cr.get("slide_count") or len(_cr.get("slides") or []) or 3,
                    slide_texts=_cr.get("slides") or [],
                    lang=lang,
                    topic=_cr.get("topic_en") or "",
                )
                st.session_state["content_video_beats"] = _cvb
            render_video_beats_ui(_cvb, lang=lang, key_prefix="content")
        if st.session_state.get("content_txt"):
            st.download_button(
                label=t("content_download_txt", lang),
                data=st.session_state["content_txt"],
                file_name=st.session_state.get("content_zip_name", "content.txt").replace(".zip", ".txt"),
                mime="text/plain",
                key="dl_content_txt",
            )
        if st.session_state.get("content_zip"):
            st.download_button(
                label=t("content_download_zip", lang),
                data=st.session_state["content_zip"],
                file_name=st.session_state.get("content_zip_name", "content_carousel.zip"),
                mime="application/zip",
                help=t("export_zip_help", lang),
                key="dl_content_zip",
            )
    st.stop()  # Product pack UI below is skipped in content mode

# ========== PRODUCT PACK MODE (existing flow) ==========

# 4. UI & ACTIONS
col_header, col_reset = st.columns([3, 1])
with col_reset:
    st.write("")
    if st.button(t("clear_button", lang)):
        clear_all_fields()
        st.rerun()

col_up, col_preview = st.columns([2, 1])
with col_up:
    uploaded_file = st.file_uploader(
        t("upload_label", lang),
        type=["jpg", "jpeg", "png", "webp"],
        key=f"uploader_{st.session_state['uploader_key']}"
    )
with col_preview:
    if uploaded_file is not None:
        st.image(uploaded_file, caption=t("preview_caption", lang), use_container_width=True)
    elif st.session_state.get("history_image_path"):
        hist_img = Path(st.session_state["history_image_path"])
        if hist_img.is_file():
            st.image(str(hist_img), caption=t("from_history_caption", lang), use_container_width=True)

if st.button(t("analyze_button", lang)):
    if not uploaded_file:
        st.warning(t("analyze_warning", lang))
    else:
        with st.spinner(t("analyze_spinner", lang)):
            img_bytes = uploaded_file.getvalue()
            
            mime = "image/jpeg"
            if uploaded_file.name.lower().endswith(".webp"): mime = "image/webp"
            elif uploaded_file.name.lower().endswith(".png"): mime = "image/png"

            data = auto_analyze_shoe("", "", img_bytes, mime, vibe=st.session_state.get("scene_vibe_val", "auto") or "auto")
            
            st.session_state["brand_val"] = data.get("brand", "")
            st.session_state["model_val"] = data.get("model", "")
            st.session_state["colorway_val"] = data.get("colorway", "")
            st.session_state["specs_val"] = data.get("specs", "")
            store_scene_from_analyze(
                data.get("env_desc", "") or "",
                data.get("props_desc", "") or "",
                data.get("problem_desc", "") or "",
                lang=lang,
            )
            st.rerun()

# 5. INPUT FIELDS
col1, col2, col3 = st.columns(3)
with col1: 
    brand = st.text_input(t("brand_label", lang), value=st.session_state["brand_val"], placeholder=t("brand_placeholder", lang))
    st.session_state["brand_val"] = brand

with col2: 
    model_name = st.text_input(t("model_label", lang), value=st.session_state["model_val"], placeholder=t("model_placeholder", lang))
    st.session_state["model_val"] = model_name

with col3: 
    colorway = st.text_input(t("colorway_label", lang), value=st.session_state["colorway_val"], placeholder=t("colorway_placeholder", lang))
    st.session_state["colorway_val"] = colorway

custom_watermark = st.text_input(t("watermark_label", lang), value=st.session_state["watermark_val"])
st.session_state["watermark_val"] = custom_watermark

key_materials = st.text_area(t("specs_label", lang), value=st.session_state["specs_val"], placeholder=t("specs_placeholder", lang), height=80)
st.session_state["specs_val"] = key_materials

col_tag, col_badge = st.columns(2)
with col_tag:
    _tag_idx = AUTHENTICITY_TAGS.index(st.session_state["selected_tag_val"]) if st.session_state["selected_tag_val"] in AUTHENTICITY_TAGS else 0
    selected_tag = st.selectbox(t("tag_label", lang), AUTHENTICITY_TAGS, index=_tag_idx)
    st.session_state["selected_tag_val"] = selected_tag
with col_badge:
    _badge_idx = CATEGORY_BADGES.index(st.session_state["selected_badge_val"]) if st.session_state["selected_badge_val"] in CATEGORY_BADGES else 0
    selected_badge = st.selectbox(t("badge_label", lang), CATEGORY_BADGES, index=_badge_idx)
    st.session_state["selected_badge_val"] = selected_badge

st.markdown(t("scene_section", lang))
st.caption(t("scene_help", lang))
st.caption(t("scene_lang_note", lang))

_vibe_labels = {
    "auto": t("vibe_auto", lang),
    "running": t("vibe_running", lang),
    "trail": t("vibe_trail", lang),
    "gym": t("vibe_gym", lang),
    "street": t("vibe_street", lang),
    "commute": t("vibe_commute", lang),
    "work": t("vibe_work", lang),
    "travel": t("vibe_travel", lang),
    "recovery": t("vibe_recovery", lang),
    "basketball": t("vibe_basketball", lang),
}
_cur_vibe = st.session_state.get("scene_vibe_val", "auto")
if _cur_vibe not in SCENE_VIBE_KEYS:
    _cur_vibe = "auto"
_vibe_idx = SCENE_VIBE_KEYS.index(_cur_vibe)
_picked_vibe_label = st.selectbox(
    t("scene_vibe_label", lang),
    [_vibe_labels[k] for k in SCENE_VIBE_KEYS],
    index=_vibe_idx,
    key="scene_vibe_select_label",
)
_label_to_vibe = {v: k for k, v in _vibe_labels.items()}
st.session_state["scene_vibe_val"] = _label_to_vibe.get(_picked_vibe_label, "auto")

if st.button(t("shuffle_scene", lang), key="shuffle_scene_btn"):
    _shuffle_pack = pick_scene_pack(
        st.session_state.get("brand_val", ""),
        st.session_state.get("model_val", ""),
        st.session_state.get("specs_val", ""),
        vibe=st.session_state.get("scene_vibe_val", "auto") or "auto",
    )
    apply_scene_pack_to_session(_shuffle_pack, lang=lang)
    st.rerun()

selected_env = st.text_area(t("env_label", lang), value=st.session_state["env_desc_val"], height=70)
st.session_state["env_desc_val"] = selected_env

selected_props = st.text_area(t("props_label", lang), value=st.session_state["props_desc_val"], height=70)
st.session_state["props_desc_val"] = selected_props

selected_problem = st.text_area(t("problem_label", lang), value=st.session_state["problem_desc_val"], height=70)
st.session_state["problem_desc_val"] = selected_problem

# Keep EN shadows in sync when user edits a known pack or English text;
# image prompts always use English via scene_fields_for_prompts().
_pack_match = find_scene_pack_by_text(selected_env, selected_props, selected_problem)
if _pack_match:
    st.session_state["env_desc_en"] = _pack_match["env_desc"]
    st.session_state["props_desc_en"] = _pack_match["props_desc"]
    st.session_state["problem_desc_en"] = _pack_match["problem_desc"]
elif lang != "el":
    # Visible fields are English — treat edits as the prompt source.
    st.session_state["env_desc_en"] = selected_env
    st.session_state["props_desc_en"] = selected_props
    st.session_state["problem_desc_en"] = selected_problem

_prompt_env, _prompt_props, _prompt_problem = scene_fields_for_prompts()


# 5b. GOAL / STORY TEMPLATES (hybrid — does not replace scene fields)
st.markdown(t("goal_section", lang))
_suggested = suggest_goal_from_specs(
    st.session_state.get("specs_val", ""),
    st.session_state.get("model_val", ""),
    st.session_state.get("brand_val", ""),
)
_goal_labels = {
    "auto": t("goal_auto", lang),
    "comfort": t("goal_comfort", lang),
    "wide_fit": t("goal_wide_fit", lang),
    "style": t("goal_style", lang),
    "rain_care": t("goal_rain_care", lang),
}
st.caption(t("goal_suggested", lang, goal=_goal_labels.get(_suggested, _suggested)))
st.caption(t("goal_help", lang))
_cur_goal = st.session_state.get("goal_val", "auto")
if _cur_goal not in GOAL_KEYS:
    _cur_goal = "auto"
_goal_idx = GOAL_KEYS.index(_cur_goal)
_picked_goal_label = st.selectbox(
    t("goal_label", lang),
    [_goal_labels[k] for k in GOAL_KEYS],
    index=_goal_idx,
    key="goal_select_label",
)
_label_to_goal = {v: k for k, v in _goal_labels.items()}
_selected_goal = _label_to_goal.get(_picked_goal_label, "auto")
if _selected_goal == "auto":
    # Auto uses suggested angle for generation, but stores as auto
    st.session_state["goal_val"] = "auto"
    _effective_goal = _suggested
else:
    st.session_state["goal_val"] = _selected_goal
    _effective_goal = _selected_goal


# 5c. MODEL APPEARANCE (creative control for image prompts)
_appearance_labels = {
    "auto": t("appearance_auto", lang),
    "eu": t("appearance_eu", lang),
    "diverse": t("appearance_diverse", lang),
    "no_face": t("appearance_no_face", lang),
}
st.caption(t("appearance_help", lang))
_cur_appearance = st.session_state.get("appearance_val", "eu")
if _cur_appearance not in APPEARANCE_KEYS:
    _cur_appearance = "eu"
_appearance_idx = APPEARANCE_KEYS.index(_cur_appearance)
_picked_appearance_label = st.selectbox(
    t("appearance_label", lang),
    [_appearance_labels[k] for k in APPEARANCE_KEYS],
    index=_appearance_idx,
    key="appearance_select_label",
)
_label_to_appearance = {v: k for k, v in _appearance_labels.items()}
st.session_state["appearance_val"] = _label_to_appearance.get(_picked_appearance_label, "eu")
_effective_appearance = st.session_state["appearance_val"]
_appearance_extra = appearance_clause(_effective_appearance)

col_fmt, col_ar = st.columns(2)
with col_fmt:
    _fmt_options = ["Single Layout Ad (1 Εικόνα)", "Carousel Pack (multi-slide)"]
    # Migrate old label that hard-coded "3-Slide..."
    if "Carousel" in str(st.session_state.get("ad_format_val", "")) and st.session_state["ad_format_val"] not in _fmt_options:
        st.session_state["ad_format_val"] = "Carousel Pack (multi-slide)"
    _fmt_idx = _fmt_options.index(st.session_state["ad_format_val"]) if st.session_state["ad_format_val"] in _fmt_options else 0
    ad_format = st.selectbox(t("format_label", lang), _fmt_options, index=_fmt_idx)
    st.session_state["ad_format_val"] = ad_format
with col_ar:
    _ar_options = ["9:16 (Story/TikTok)", "4:5 (Instagram Feed)", "1:1 (Square)", "2:3 (Portrait)", "16:9 (Landscape/YouTube)"]
    _ar_idx = _ar_options.index(st.session_state["aspect_ratio_val"]) if st.session_state["aspect_ratio_val"] in _ar_options else _ar_options.index("1:1 (Square)")
    aspect_ratio = st.selectbox(t("aspect_label", lang), _ar_options, index=_ar_idx)
    st.session_state["aspect_ratio_val"] = aspect_ratio

if ad_format != "Single Layout Ad (1 Εικόνα)":
    if st.session_state.get("slide_count_val") not in (2, 3, 4, 5):
        st.session_state["slide_count_val"] = 3
    slide_count = st.selectbox(
        t("slide_count_label", lang),
        [2, 3, 4, 5],
        key="slide_count_val",
    )
else:
    slide_count = st.session_state.get("slide_count_val", 3)

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

st.markdown("---")

# 6. GENERATION
_can_gen_product = usage.can_generate(st.session_state)
if not _can_gen_product:
    st.warning(t("limit_reached", lang))
    st.markdown(f"[{t('go_pro', lang)}]({usage.LEMON_CHECKOUT_URL})")
if st.button(
    t("generate_button", lang),
    type="primary",
    disabled=not _can_gen_product,
):
    if not brand or not model_name:
        st.error(t("generate_error", lang))
    else:
        with st.spinner(t("generate_spinner", lang, lang_name=t("lang_name", lang))):
            ad_texts = safe_generate_ad_copy(
                brand, model_name, colorway, key_materials, custom_watermark,
                lang=lang,
                goal=_effective_goal,
                insight_context=st.session_state.get("active_insight", "") or "",
            )

        usage.record_generate(st.session_state)

        # 🛡️ Ασπίδα προστασίας από φίλτρα ασφαλείας
        unsafe_keywords = ["kobe", "jordan", "lebron", "messi", "ronaldo", "curry"]
        safe_model_name = model_name
        for word in unsafe_keywords:
            if word in safe_model_name.lower():
                safe_model_name = safe_model_name.lower().replace(word, "signature pro")

        # Καθαρισμός και στα κείμενα των ad_texts για ασφάλεια
        for key in ad_texts:
            if isinstance(ad_texts[key], str):
                for word in unsafe_keywords:
                    if word in ad_texts[key].lower():
                        ad_texts[key] = ad_texts[key].lower().replace(word, "signature pro")

        # Bilingual caption cache: active lang drives overlays; both cached for UI switch
        store_product_caption_side(lang, ad_texts)
        _cap_other_lang = _other_lang(lang)
        try:
            ad_texts_other = safe_generate_ad_copy(
                brand, model_name, colorway, key_materials, custom_watermark,
                lang=_cap_other_lang,
                goal=_effective_goal,
                insight_context=st.session_state.get("active_insight", "") or "",
            )
            for key in ad_texts_other:
                if isinstance(ad_texts_other[key], str):
                    for word in unsafe_keywords:
                        if word in ad_texts_other[key].lower():
                            ad_texts_other[key] = ad_texts_other[key].lower().replace(word, "signature pro")
            store_product_caption_side(_cap_other_lang, ad_texts_other)
        except Exception:
            pass
        apply_captions_for_lang(lang)

        _wm_clean = (custom_watermark or "").strip()
        if _wm_clean:
            _wm_neg = (
                f"REQUIRED on-image watermark text (exactly once, bottom-right): {_wm_clean} "
                "Render that exact string EXACTLY ONCE as clearly phone-readable text in the "
                "bottom-right corner (~7–9% of image height, clean sans-serif, strong contrast — must be easily readable at a glance on a phone screen; not microscopic; not faint grey on busy background; "
                "subtle dark/light shadow OK), leaving ~2–3% margin from the edges — readable on "
                "a phone without zoom; ban any second tiny/micro duplicate, shortened copy, or "
                "extra corner mark; no giant headline, not dominating the shoe, no Explore CTA on "
                "the image. Overlay/CTA texts must NOT contain any website/domain — the watermark "
                "is the only on-image site text. "
            )
        else:
            _wm_neg = (
                "By default NO website / brand-store / SNEAKERNESS.EU text on the image. "
                "Overlay/CTA texts must NOT contain any website/domain. "
            )
        negative_constraint = (
            " STRICTLY NO text like 'Slide X of Y', NO carousel numbering, NO carousel dots, "
            "NO LEARN MORE buttons, NO app UI chrome, NO page numbers. "
            "Do NOT invent badges/seals like OFFICIAL SELECTION / BESTSELLER / SNEAKERNESS "
            "unless that exact text is requested in this prompt. "
            + _wm_neg
            + "Overlay text must match the scene: ban work-shift / 'long shifts' overlay wording "
            "when the scene is running / track / curb-after-run; keep shift wording only for "
            "standing/work scenes. "
            "ONLY the requested overlay text."
        )
        _appearance_extra = appearance_clause(st.session_state.get("appearance_val", "eu"))
        _ui_env, _ui_props, _ui_problem = selected_env, selected_props, selected_problem
        selected_env, selected_props, selected_problem = scene_fields_for_prompts()
        _brand_lock = (
            f" Hero footwear must match: {brand} {safe_model_name} {colorway}. "
            f"Clearly recognizable {brand} footwear, correct model silhouette and typical "
            f"branding cues — do not substitute Nike/Adidas/generic. Soft trademark-safe: "
            f"correct brand family silhouette/colors as provided; do not invent a different brand."
        )

        if ad_format == "Single Layout Ad (1 Εικόνα)":
            _no_face = "No identifiable face" in (_appearance_extra or "")
            if _no_face:
                visual_prompt = f"""Create an image: Photorealistic lifestyle/product photograph prioritizing footwear of {brand} {safe_model_name} in {colorway} colorway ({key_materials}) on a smooth surface in the foreground with {selected_props}. Soft-focus upper background suggests {selected_problem} without showing an identifiable face (crop strictly below the chin; no partial face at frame edge; shoes, legs, hands, props only). Natural depth of field and continuous studio lighting. Render a top-left fabric tag reading '{selected_tag}' and a top-right badge reading '{selected_badge}'. Display headline text overlay '{ad_texts['hook']}', body text overlay '{ad_texts['body']}', and soft CTA overlay '{ad_texts['cta']}'.{watermark_image_clause(custom_watermark)} {negative_constraint}{_brand_lock}{(' ' + _appearance_extra) if _appearance_extra else ''} Photorealistic 8k, seamless single canvas {ar_flag}"""
            else:
                visual_prompt = f"""Create an image: Photorealistic vertical photograph of {brand} {safe_model_name} in {colorway} colorway ({key_materials}) placed on a smooth surface in the foreground, accompanied by {selected_props}. In the soft-focus upper background, {selected_problem}. Natural depth of field and continuous studio lighting. Render a top-left fabric tag reading '{selected_tag}' and a top-right badge reading '{selected_badge}'. Display headline text overlay '{ad_texts['hook']}', body text overlay '{ad_texts['body']}', and soft CTA overlay '{ad_texts['cta']}'.{watermark_image_clause(custom_watermark)} {negative_constraint}{_brand_lock}{(' ' + _appearance_extra) if _appearance_extra else ''} Photorealistic 8k, seamless single canvas {ar_flag}"""
            slide1_prompt = slide2_prompt = slide3_prompt = slide4_prompt = slide5_prompt = ""

        else:
            slide_count = int(st.session_state.get("slide_count_val", 3))
            if slide_count not in (2, 3, 4, 5):
                slide_count = 3
            carousel_roles = build_carousel_prompts(
                slide_count,
                brand=brand,
                safe_model_name=safe_model_name,
                colorway=colorway,
                key_materials=key_materials,
                selected_env=selected_env,
                selected_props=selected_props,
                selected_problem=selected_problem,
                selected_tag=selected_tag,
                selected_badge=selected_badge,
                custom_watermark=custom_watermark,
                ad_texts=ad_texts,
                negative_constraint=negative_constraint,
                ar_flag=ar_flag,
                appearance_extra=_appearance_extra,
            )
            slide_prompts = [p for _, p in carousel_roles]
            # Pad to 5 for history / session consistency
            while len(slide_prompts) < 5:
                slide_prompts.append("")
            slide1_prompt, slide2_prompt, slide3_prompt, slide4_prompt, slide5_prompt = slide_prompts[:5]

        # Build Grok Video beats with the same generate click (deterministic)
        _video_mode = "single" if ad_format == "Single Layout Ad (1 Εικόνα)" else "carousel"
        _video_sc = 3 if _video_mode == "single" else int(st.session_state.get("slide_count_val", 3) or 3)
        video_beats = build_grok_video_beats(
            brand=brand,
            model=safe_model_name,
            colorway=colorway,
            specs=key_materials,
            env=selected_env,
            props=selected_props,
            problem=selected_problem,
            watermark=custom_watermark,
            appearance=st.session_state.get("appearance_val", "eu"),
            goal=st.session_state.get("goal_val", "auto"),
            mode=_video_mode,
            slide_count=_video_sc,
            lang=lang,
        )
        st.session_state["loaded_video_beats"] = video_beats

        meta_post = f"{ad_texts.get('meta_caption', '')}\n\n{ad_texts.get('hashtags_meta', '')}"
        tiktok_post = ad_texts.get('tiktok_caption', '')
        pinterest_post = ad_texts.get('pinterest_caption', '')
        youtube_post = ad_texts.get('youtube_caption', '')

        lang_tag = "EL" if lang == "el" else "EN"
        os.makedirs("output", exist_ok=True)
        file_path = f"output/{brand}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        txt_content = f"""========================================
NANO BANANA VISUAL PROMPT
========================================
{visual_prompt if ad_format == 'Single Layout Ad (1 Εικόνα)' else chr(10).join((f'Slide {i}:' + chr(10) + p) for i, p in enumerate([slide1_prompt, slide2_prompt, slide3_prompt, slide4_prompt, slide5_prompt], start=1) if p)}

========================================
FACEBOOK & INSTAGRAM POST ({lang_tag})
========================================
{meta_post}

========================================
TIKTOK / CAROUSEL POST ({lang_tag})
========================================
{tiktok_post}

========================================
PINTEREST PIN DESCRIPTION ({lang_tag})
========================================
{pinterest_post}

========================================
YOUTUBE CAPTION ({lang_tag})
========================================
{youtube_post}

========================================
GROK VIDEO BEATS (EN prompts)
========================================
{format_video_prompts_txt(video_beats, brand=brand, model=model_name, colorway=colorway)}
========================================
RAW DATA (JSON)
========================================
{json.dumps(ad_texts, ensure_ascii=False, indent=2)}
"""

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(txt_content)
            

        # Persist to product history
        hist_payload = {
            "brand": brand,
            "model": model_name,
            "colorway": colorway,
            "specs": key_materials,
            "env_desc": _ui_env,
            "props_desc": _ui_props,
            "problem_desc": _ui_problem,
            "env_desc_en": selected_env,
            "props_desc_en": selected_props,
            "problem_desc_en": selected_problem,
            "watermark": custom_watermark,
            "ad_format": ad_format,
            "aspect_ratio": aspect_ratio,
            "selected_tag": selected_tag,
            "selected_badge": selected_badge,
            "meta_caption": ad_texts.get("meta_caption", ""),
            "tiktok_caption": ad_texts.get("tiktok_caption", ""),
            "hashtags_meta": ad_texts.get("hashtags_meta", ""),
            "pinterest_caption": ad_texts.get("pinterest_caption", ""),
            "youtube_caption": ad_texts.get("youtube_caption", ""),
            "ad_texts": ad_texts,
            "captions_el": st.session_state.get("captions_el"),
            "captions_en": st.session_state.get("captions_en"),
            "lang": lang,
            "goal": st.session_state.get("goal_val", "auto"),
            "appearance": st.session_state.get("appearance_val", "eu"),
            "video_beats": video_beats,
        }
        hist_payload["slide_count"] = int(st.session_state.get("slide_count_val", 3)) if ad_format != "Single Layout Ad (1 Εικόνα)" else 1
        if ad_format == "Single Layout Ad (1 Εικόνα)":
            hist_payload["visual_prompt"] = visual_prompt
            hist_payload["slide1_prompt"] = ""
            hist_payload["slide2_prompt"] = ""
            hist_payload["slide3_prompt"] = ""
            hist_payload["slide4_prompt"] = ""
            hist_payload["slide5_prompt"] = ""
        else:
            hist_payload["visual_prompt"] = ""
            hist_payload["slide1_prompt"] = slide1_prompt
            hist_payload["slide2_prompt"] = slide2_prompt
            hist_payload["slide3_prompt"] = slide3_prompt
            hist_payload["slide4_prompt"] = slide4_prompt
            hist_payload["slide5_prompt"] = slide5_prompt

        img_bytes = None
        mime = None
        src_path = None
        if uploaded_file is not None:
            img_bytes = uploaded_file.getvalue()
            mime = "image/jpeg"
            name_l = (uploaded_file.name or "").lower()
            if name_l.endswith(".webp"):
                mime = "image/webp"
            elif name_l.endswith(".png"):
                mime = "image/png"
        elif st.session_state.get("history_image_path"):
            src_path = st.session_state["history_image_path"]

        saved = add_entry(hist_payload, image_bytes=img_bytes, mime_type=mime, source_image_path=src_path)
        if saved.get("image_path"):
            st.session_state["history_image_path"] = saved["image_path"]

        st.session_state["loaded_meta_caption"] = ad_texts.get("meta_caption", "")
        st.session_state["loaded_tiktok_caption"] = ad_texts.get("tiktok_caption", "")
        st.session_state["loaded_hashtags_meta"] = ad_texts.get("hashtags_meta", "")
        st.session_state["loaded_pinterest_caption"] = ad_texts.get("pinterest_caption", "")
        st.session_state["loaded_youtube_caption"] = ad_texts.get("youtube_caption", "")
        st.session_state["loaded_visual_prompt"] = hist_payload.get("visual_prompt", "")
        st.session_state["loaded_slide1_prompt"] = hist_payload.get("slide1_prompt", "")
        st.session_state["loaded_slide2_prompt"] = hist_payload.get("slide2_prompt", "")
        st.session_state["loaded_slide3_prompt"] = hist_payload.get("slide3_prompt", "")
        st.session_state["loaded_slide4_prompt"] = hist_payload.get("slide4_prompt", "")
        st.session_state["loaded_slide5_prompt"] = hist_payload.get("slide5_prompt", "")

        # Feature C — ZIP export pack (in-memory); persist for download-safe results UI
        _zip_slides = []
        if ad_format == "Single Layout Ad (1 Εικόνα)":
            _zip_visual = visual_prompt
            _zip_sc = 1
        else:
            _zip_visual = ""
            _zip_slides = [p for p in [slide1_prompt, slide2_prompt, slide3_prompt, slide4_prompt, slide5_prompt] if p]
            _zip_sc = int(st.session_state.get("slide_count_val", 3))
        # Prefer freshly uploaded bytes; else history image file
        _zip_img_b = img_bytes
        _zip_img_mime = mime
        _zip_img_ext = None
        if _zip_img_b is None:
            _zip_img_b, _zip_img_ext, _zip_img_mime = _read_history_shoe_bytes(
                st.session_state.get("history_image_path")
            )
        else:
            if _zip_img_mime and "png" in _zip_img_mime:
                _zip_img_ext = "png"
            elif _zip_img_mime and "webp" in _zip_img_mime:
                _zip_img_ext = "webp"
            else:
                _zip_img_ext = "jpg"
        st.session_state["last_export_zip"] = build_pack_zip_bytes(
            brand=brand,
            model_name=model_name,
            colorway=colorway,
            goal=st.session_state.get("goal_val", "auto"),
            lang=lang,
            aspect_ratio=aspect_ratio,
            slide_count=_zip_sc,
            specs=key_materials,
            meta_caption=ad_texts.get("meta_caption", ""),
            hashtags_meta=ad_texts.get("hashtags_meta", ""),
            tiktok_caption=ad_texts.get("tiktok_caption", ""),
            pinterest_caption=ad_texts.get("pinterest_caption", ""),
            youtube_caption=ad_texts.get("youtube_caption", ""),
            visual_prompt=_zip_visual,
            slide_prompts=_zip_slides,
            image_bytes=_zip_img_b,
            image_ext=_zip_img_ext,
            image_mime=_zip_img_mime,
            video_beats=video_beats,
        )
        _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state["last_export_name"] = f"{brand}_{model_name}_{_ts}_pack.zip".replace(" ", "_")
        st.session_state["last_export_shoe"] = _zip_img_b
        st.session_state["last_export_shoe_ext"] = _zip_img_ext
        st.session_state["last_export_shoe_mime"] = _zip_img_mime
        if _zip_img_b and _zip_img_ext:
            st.session_state["last_export_shoe_name"] = f"{brand}_{model_name}_{_ts}_shoe.{_zip_img_ext}".replace(" ", "_")
        else:
            st.session_state["last_export_shoe_name"] = None
        st.session_state["last_export_txt"] = txt_content
        st.session_state["last_export_txt_name"] = f"{brand}_{model_name}_{_ts}.txt".replace(" ", "_")
        st.session_state["last_export_path"] = file_path
        # Reset persistent results widgets so new captions show after regenerate
        for _wk in ("hist_meta_ta", "hist_tt_ta", "hist_pin_ta", "hist_yt_ta"):
            st.session_state.pop(_wk, None)
        st.session_state["show_loaded_pack"] = True
        st.rerun()


# Persistent results (generate / history / import) — survives download-button reruns
if st.session_state.get("show_loaded_pack"):
    st.markdown("---")
    st.markdown(t("results_section", lang))
    if st.session_state.get("loaded_visual_prompt"):
        st.markdown(t("prompt_single", lang))
        st.code(st.session_state["loaded_visual_prompt"], language="text")
    elif st.session_state.get("loaded_slide1_prompt"):
        st.markdown(t("prompt_carousel", lang))
        _loaded_slides = [
            st.session_state.get("loaded_slide1_prompt", ""),
            st.session_state.get("loaded_slide2_prompt", ""),
            st.session_state.get("loaded_slide3_prompt", ""),
            st.session_state.get("loaded_slide4_prompt", ""),
            st.session_state.get("loaded_slide5_prompt", ""),
        ]
        try:
            _n_show = int(st.session_state.get("slide_count_val", 3) or 3)
        except (TypeError, ValueError):
            _n_show = 3
        if _n_show not in (2, 3, 4, 5):
            _n_show = 3
        _role_arcs = {
            2: ["slide_role_hook", "slide_role_product_cta"],
            3: ["slide_role_hook", "slide_role_product", "slide_role_specs_cta"],
            4: ["slide_role_hook", "slide_role_product", "slide_role_specs", "slide_role_cta"],
            5: ["slide_role_hook", "slide_role_lifestyle", "slide_role_product", "slide_role_specs", "slide_role_cta"],
        }
        _roles = _role_arcs[_n_show]
        for i, prompt in enumerate(_loaded_slides[:_n_show], start=1):
            if not prompt:
                continue
            role = t(_roles[i - 1], lang)
            st.write(t("slide_label", lang, n=i, role=role))
            st.code(prompt, language="text")
    st.markdown(t("captions_section", lang, lang_name=t("lang_name", lang)))
    tab_h1, tab_h2, tab_h3, tab_h4, tab_h5 = st.tabs([
        t("tab_meta", lang, lang_name=t("lang_name", lang)),
        t("tab_tiktok", lang, lang_name=t("lang_name", lang)),
        t("tab_pinterest", lang, lang_name=t("lang_name", lang)),
        t("tab_youtube", lang, lang_name=t("lang_name", lang)),
        t("tab_video", lang, lang_name=t("lang_name", lang)),
    ])
    with tab_h1:
        meta_loaded = (
            f"{st.session_state.get('loaded_meta_caption', '')}\n\n"
            f"{st.session_state.get('loaded_hashtags_meta', '')}"
        ).strip()
        st.text_area(
            t("caption_meta_label", lang, lang_name=t("lang_name", lang)),
            value=meta_loaded,
            height=180,
            key="hist_meta_ta",
        )
    with tab_h2:
        st.text_area(
            t("caption_tiktok_label", lang, lang_name=t("lang_name", lang)),
            value=st.session_state.get("loaded_tiktok_caption", ""),
            height=120,
            key="hist_tt_ta",
        )
    with tab_h3:
        st.text_area(
            t("caption_pinterest_label", lang, lang_name=t("lang_name", lang)),
            value=st.session_state.get("loaded_pinterest_caption", ""),
            height=180,
            key="hist_pin_ta",
        )
    with tab_h4:
        st.text_area(
            t("caption_youtube_label", lang, lang_name=t("lang_name", lang)),
            value=st.session_state.get("loaded_youtube_caption", ""),
            height=160,
            key="hist_yt_ta",
        )
    with tab_h5:
        _hv = st.session_state.get("loaded_video_beats")
        if not (isinstance(_hv, dict) and _hv.get("beats")):
            _hv = rebuild_video_beats_from_context(
                brand=st.session_state.get("brand_val", ""),
                model=st.session_state.get("model_val", ""),
                colorway=st.session_state.get("colorway_val", ""),
                specs=st.session_state.get("specs_val", ""),
                env=st.session_state.get("env_desc_en") or st.session_state.get("env_desc_val", ""),
                props=st.session_state.get("props_desc_en") or st.session_state.get("props_desc_val", ""),
                problem=st.session_state.get("problem_desc_en") or st.session_state.get("problem_desc_val", ""),
                watermark=st.session_state.get("watermark_val", ""),
                appearance=st.session_state.get("appearance_val", "eu"),
                goal=st.session_state.get("goal_val", "auto"),
                ad_format=st.session_state.get("ad_format_val", ""),
                slide_count=st.session_state.get("slide_count_val", 3),
                lang=lang,
            )
            st.session_state["loaded_video_beats"] = _hv
        render_video_beats_ui(_hv, lang=lang, key_prefix="results")

    if st.session_state.get("last_export_path"):
        st.info(t("saved_info", lang, path=st.session_state["last_export_path"]))
        st.caption(t("save_where_help", lang))
    st.caption(t("download_txt_help", lang))
    if st.session_state.get("last_export_zip"):
        st.download_button(
            label=t("export_zip_label", lang),
            data=st.session_state["last_export_zip"],
            file_name=st.session_state.get("last_export_name", "content_pack.zip"),
            mime="application/zip",
            help=t("export_zip_help", lang),
            key="export_zip_from_history",
        )
    if st.session_state.get("last_export_txt"):
        st.download_button(
            label=t("download_label", lang),
            data=st.session_state["last_export_txt"],
            file_name=st.session_state.get("last_export_txt_name") or "content_pack.txt",
            mime="text/plain",
            help=t("download_txt_help", lang),
            key="export_txt_from_results",
        )
    if st.session_state.get("last_export_shoe"):
        st.download_button(
            label=t("download_shoe_label", lang),
            data=st.session_state["last_export_shoe"],
            file_name=st.session_state.get("last_export_shoe_name") or f"shoe.{st.session_state.get('last_export_shoe_ext') or 'jpg'}",
            mime=st.session_state.get("last_export_shoe_mime") or "image/jpeg",
            help=t("download_shoe_help", lang),
            key="export_shoe_from_history",
        )

