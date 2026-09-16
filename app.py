# app.py - Sneaker Image Studio (Dynamic Creative Edition)
import os
import json
import time
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
    st.session_state["lang"] = _lang_codes.get(_picked, "el")

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
def auto_analyze_shoe(brand_name, model_name, image_bytes=None, mime_type="image/jpeg"):
    if not image_bytes:
        return {
            "brand": brand_name if brand_name else "",
            "model": model_name if model_name else "",
            "specs": "",
            "colorway": "",
            "env_desc": "minimalist concrete urban street with natural daylight",
            "props_desc": "an open Kinfolk magazine, a ceramic cup of cappuccino, brass keys, succulent",
            "problem_desc": "a tired worker sitting on stairs touching sore feet with work boots beside them"
        }

    prompt_search = """Examine the provided sneaker image with extreme precision.

CRITICAL IDENTIFICATION & DYNAMIC SCENE CREATION RULES:
1. "brand": Identify the EXACT footwear brand name visible on the shoe or tongue (e.g., HOKA, Puma, Nike, Adidas, New Balance, Brooks).
2. "model": Identify the EXACT shoe model name based on visible text. Check tongue, lateral side, or heel label carefully.
3. "colorway": Describe the exact observed colors in the image (e.g., "Cream / Red / Navy Blue").
4. "specs": Technical specifications specific to this exact model (e.g., Vibram Megagrip outsole, dual-density EVA midsole, breathable mesh upper).
5. "env_desc": Write a detailed, hyper-relevant 1-sentence English description of the IDEAL background environment tailored to this shoe's archetype (e.g. basketball court, urban street, trail, luxury lounge).
6. "props_desc": Write a 1-sentence English list of 3-4 EDC props placed on the surface next to the shoe that match its lifestyle/vibe.
7. "problem_desc": Write a 1-sentence English description of a realistic human pain-point/problem scene matching this shoe's category (e.g. tired athlete, fatigued retail worker, aching hiker, long shift worker).

Return ONLY a valid, raw JSON object matching this schema:
{
  "brand": "Detected Brand",
  "model": "Detected Model",
  "specs": "Technical features...",
  "colorway": "Detected colorway...",
  "env_desc": "Custom environmental background description...",
  "props_desc": "Custom EDC props list...",
  "problem_desc": "Custom human problem/fatigue scene..."
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

                return json.loads(clean_txt)
        except Exception as e:
            st.warning(t("model_failed", st.session_state.get("lang", "el"), model=model_item, error=str(e)))
            time.sleep(1)

    return {
        "brand": "",
        "model": "",
        "specs": "",
        "colorway": "",
        "env_desc": "minimalist concrete urban street with natural daylight",
        "props_desc": "an open Kinfolk magazine, a ceramic cup of cappuccino, brass keys, succulent",
        "problem_desc": "a tired worker sitting on stairs touching sore feet with work boots beside them"
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
        f"(~3–5% of image height, clean sans-serif, good contrast; subtle dark/light shadow OK), "
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
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        if image_bytes:
            ext = _normalize_shoe_image_ext(image_ext, image_mime)
            zf.writestr(f"shoe.{ext}", image_bytes)
    return buf.getvalue()


def clear_all_fields():
    st.session_state["brand_val"] = ""
    st.session_state["model_val"] = ""
    st.session_state["colorway_val"] = ""
    st.session_state["specs_val"] = ""
    st.session_state["env_desc_val"] = "minimalist concrete urban street with natural daylight"
    st.session_state["props_desc_val"] = "an open Kinfolk magazine, a ceramic cup of cappuccino, brass keys, succulent"
    st.session_state["problem_desc_val"] = "a tired worker sitting on stairs touching sore feet with work boots beside them"
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
    st.session_state["loaded_visual_prompt"] = ""
    st.session_state["loaded_slide1_prompt"] = ""
    st.session_state["loaded_slide2_prompt"] = ""
    st.session_state["loaded_slide3_prompt"] = ""
    st.session_state["loaded_slide4_prompt"] = ""
    st.session_state["loaded_slide5_prompt"] = ""
    st.session_state["show_loaded_pack"] = False
    st.session_state["goal_val"] = "auto"
    st.session_state["appearance_val"] = "eu"
    st.session_state["active_insight"] = ""
    st.session_state["last_export_zip"] = None
    st.session_state["last_export_shoe"] = None
    st.session_state["last_export_shoe_ext"] = None
    st.session_state["last_export_shoe_mime"] = None
    st.session_state["last_export_shoe_name"] = None
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1


def apply_history_entry(entry: dict):
    """Populate session_state from a history entry; caller should st.rerun()."""
    st.session_state["brand_val"] = entry.get("brand", "") or ""
    st.session_state["model_val"] = entry.get("model", "") or ""
    st.session_state["colorway_val"] = entry.get("colorway", "") or ""
    st.session_state["specs_val"] = entry.get("specs", "") or ""
    st.session_state["env_desc_val"] = entry.get("env_desc", "") or ""
    st.session_state["props_desc_val"] = entry.get("props_desc", "") or ""
    st.session_state["problem_desc_val"] = entry.get("problem_desc", "") or ""
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
    st.session_state["loaded_visual_prompt"] = entry.get("visual_prompt", "") or ""
    st.session_state["loaded_slide1_prompt"] = entry.get("slide1_prompt", "") or ""
    st.session_state["loaded_slide2_prompt"] = entry.get("slide2_prompt", "") or ""
    st.session_state["loaded_slide3_prompt"] = entry.get("slide3_prompt", "") or ""
    st.session_state["loaded_slide4_prompt"] = entry.get("slide4_prompt", "") or ""
    st.session_state["loaded_slide5_prompt"] = entry.get("slide5_prompt", "") or ""
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
                }
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
if "env_desc_val" not in st.session_state: st.session_state["env_desc_val"] = "minimalist concrete urban street with natural daylight"
if "props_desc_val" not in st.session_state: st.session_state["props_desc_val"] = "an open Kinfolk magazine, a ceramic cup of cappuccino, brass keys, succulent"
if "problem_desc_val" not in st.session_state: st.session_state["problem_desc_val"] = "a tired worker sitting on stairs touching sore feet with work boots beside them"
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
                st.session_state["content_txt"] = _entry.get("content_txt") or build_content_txt(_cr)
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
                models=["gemini-3.6-flash", "gemini-2.5-flash"],
                warn=_warn,
            )
        st.session_state["content_result"] = _result
        usage.record_generate(st.session_state)
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
                "lang": "en",
                "goal": "content",
                "ad_format": "Content Carousel",
                "slide1_prompt": (_result.get("slides") or [{}])[0].get("image_prompt", "") if (_result.get("slides") or []) else "",
                "slide2_prompt": (_result.get("slides") or [{}, {}])[1].get("image_prompt", "") if len(_result.get("slides") or []) > 1 else "",
                "slide3_prompt": (_result.get("slides") or [{}, {}, {}])[2].get("image_prompt", "") if len(_result.get("slides") or []) > 2 else "",
                "slide4_prompt": (_result.get("slides") or [{}, {}, {}, {}])[3].get("image_prompt", "") if len(_result.get("slides") or []) > 3 else "",
                "slide5_prompt": (_result.get("slides") or [{}, {}, {}, {}, {}])[4].get("image_prompt", "") if len(_result.get("slides") or []) > 4 else "",
                "content_slides": _result.get("slides"),
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
        st.text_area(t("content_ig_label", lang), value=_cr.get("ig_caption", ""), height=140, key="c_ig_cap")
        st.text_area(t("content_tiktok_label", lang), value=_cr.get("tiktok_caption", ""), height=100, key="c_tt_cap")
        st.text_area(t("content_pinterest_label", lang), value=_cr.get("pinterest_caption", ""), height=140, key="c_pin_cap")
        st.text_area(t("content_youtube_label", lang), value=_cr.get("youtube_caption", ""), height=120, key="c_yt_cap")
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

            data = auto_analyze_shoe("", "", img_bytes, mime)
            
            st.session_state["brand_val"] = data.get("brand", "")
            st.session_state["model_val"] = data.get("model", "")
            st.session_state["colorway_val"] = data.get("colorway", "")
            st.session_state["specs_val"] = data.get("specs", "")
            st.session_state["env_desc_val"] = data.get("env_desc", "")
            st.session_state["props_desc_val"] = data.get("props_desc", "")
            st.session_state["problem_desc_val"] = data.get("problem_desc", "")
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

selected_env = st.text_area(t("env_label", lang), value=st.session_state["env_desc_val"], height=70)
st.session_state["env_desc_val"] = selected_env

selected_props = st.text_area(t("props_label", lang), value=st.session_state["props_desc_val"], height=70)
st.session_state["props_desc_val"] = selected_props

selected_problem = st.text_area(t("problem_label", lang), value=st.session_state["problem_desc_val"], height=70)
st.session_state["problem_desc_val"] = selected_problem


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

        _wm_clean = (custom_watermark or "").strip()
        if _wm_clean:
            _wm_neg = (
                f"REQUIRED on-image watermark text (exactly once, bottom-right): {_wm_clean} "
                "Render that exact string EXACTLY ONCE as clearly phone-readable text in the "
                "bottom-right corner (~3–5% of image height, clean sans-serif, good contrast; "
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

            st.markdown(t("prompt_single", lang))
            st.code(visual_prompt, language="text")

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

            st.markdown(t("prompt_carousel", lang))
            for i, (role_key, prompt) in enumerate(carousel_roles, start=1):
                role = t(role_key, lang)
                st.write(t("slide_label", lang, n=i, role=role))
                st.code(prompt, language="text")

        st.markdown("---")
        st.markdown(t("captions_section", lang, lang_name=t("lang_name", lang)))

        tab1, tab2, tab3, tab4 = st.tabs([
            t("tab_meta", lang, lang_name=t("lang_name", lang)),
            t("tab_tiktok", lang, lang_name=t("lang_name", lang)),
            t("tab_pinterest", lang, lang_name=t("lang_name", lang)),
            t("tab_youtube", lang, lang_name=t("lang_name", lang)),
        ])
        
        with tab1:
            meta_post = f"{ad_texts.get('meta_caption', '')}\n\n{ad_texts.get('hashtags_meta', '')}"
            st.text_area(t("caption_meta_label", lang, lang_name=t("lang_name", lang)), value=meta_post, height=180)
            
        with tab2:
            tiktok_post = ad_texts.get('tiktok_caption', '')
            st.text_area(t("caption_tiktok_label", lang, lang_name=t("lang_name", lang)), value=tiktok_post, height=120)

        with tab3:
            pinterest_post = ad_texts.get('pinterest_caption', '')
            st.text_area(t("caption_pinterest_label", lang, lang_name=t("lang_name", lang)), value=pinterest_post, height=180)

        with tab4:
            youtube_post = ad_texts.get('youtube_caption', '')
            st.text_area(t("caption_youtube_label", lang, lang_name=t("lang_name", lang)), value=youtube_post, height=160)

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
            "env_desc": selected_env,
            "props_desc": selected_props,
            "problem_desc": selected_problem,
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
            "lang": lang,
            "goal": st.session_state.get("goal_val", "auto"),
            "appearance": st.session_state.get("appearance_val", "eu"),
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
        st.session_state["show_loaded_pack"] = False

        st.info(t("saved_info", lang, path=file_path))
        st.caption(t("save_where_help", lang))
        

        # Feature C — ZIP export pack (in-memory)
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

        # Recommended: ZIP (text + shoe). TXT kept for text-only.
        if st.session_state.get("last_export_zip"):
            st.download_button(
                label=t("export_zip_label", lang),
                data=st.session_state["last_export_zip"],
                file_name=st.session_state.get("last_export_name", "content_pack.zip"),
                mime="application/zip",
                help=t("export_zip_help", lang),
                key="export_zip_after_gen",
            )
        st.download_button(
            label=t("download_label", lang),
            data=txt_content,
            file_name=f"{brand}_{model_name}_{_ts}.txt".replace(" ", "_"),
            mime="text/plain",
            help=t("download_txt_help", lang),
            key="export_txt_after_gen",
        )
        if st.session_state.get("last_export_shoe"):
            st.download_button(
                label=t("download_shoe_label", lang),
                data=st.session_state["last_export_shoe"],
                file_name=st.session_state.get("last_export_shoe_name") or f"shoe.{st.session_state.get('last_export_shoe_ext') or 'jpg'}",
                mime=st.session_state.get("last_export_shoe_mime") or "image/jpeg",
                help=t("download_shoe_help", lang),
                key="export_shoe_after_gen",
            )


# Show pack loaded from history (without regenerating)
if st.session_state.get("show_loaded_pack"):
    st.markdown("---")
    st.markdown(t("loaded_from_history", lang))
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
    tab_h1, tab_h2, tab_h3, tab_h4 = st.tabs([
        t("tab_meta", lang, lang_name=t("lang_name", lang)),
        t("tab_tiktok", lang, lang_name=t("lang_name", lang)),
        t("tab_pinterest", lang, lang_name=t("lang_name", lang)),
        t("tab_youtube", lang, lang_name=t("lang_name", lang)),
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
    if st.session_state.get("last_export_shoe"):
        st.download_button(
            label=t("download_shoe_label", lang),
            data=st.session_state["last_export_shoe"],
            file_name=st.session_state.get("last_export_shoe_name") or f"shoe.{st.session_state.get('last_export_shoe_ext') or 'jpg'}",
            mime=st.session_state.get("last_export_shoe_mime") or "image/jpeg",
            help=t("download_shoe_help", lang),
            key="export_shoe_from_history",
        )

