# app.py - Multimodal Auto-Matching Sneakerness Engine (Dynamic Creative Edition)
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import streamlit as st
from google import genai
from google.genai import types

import product_history  # noqa: F401
from product_history import load_history, add_entry, delete_entry, get_entry
from pathlib import Path
from i18n import t

st.set_page_config(page_title="Sneakerness Studio Engine", page_icon="👟", layout="centered")

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

st.title(t("title", lang))
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

def safe_generate_ad_copy(brand_name, model_name, colorway_text, materials, watermark, lang="el"):
    # Ασπίδα αφαίρεσης ευαίσθητων λέξεων
    unsafe_keywords = ["kobe", "jordan", "lebron", "messi", "ronaldo", "curry"]
    clean_model_name = model_name
    for word in unsafe_keywords:
        if word in clean_model_name.lower():
            clean_model_name = clean_model_name.lower().replace(word, "signature pro")

    if lang == "el":
        lang_name = "Greek (Ελληνικά)"
        sys_instruction = (
            "You are an expert e-commerce copywriter specializing in soft-sell, educational, "
            "and discovery-focused footwear ad copy and engaging social media posts in Greek (Ελληνικά). "
            "NEVER use celebrity athlete names in your text overlays. "
            "Write ALL user-facing copy in natural, fluent Modern Greek."
        )
        script_prompt = f"""Write ALL ad assets and copy in GREEK (Ελληνικά) for {brand_name} {clean_model_name} in {colorway_text} ({materials}) for website {watermark}.

CRITICAL CONSTRAINTS:
1. ALL OUTPUT MUST BE IN GREEK (Ελληνικά). Do not use English for hooks, body, CTA, captions, or slide texts.
2. DO NOT use hard-sell verbs like "αγόρασε", "αγορά", "παράγγειλε", "buy", "shop", "order", "purchase".
3. Use soft discovery CTAs like "Ανακάλυψε περισσότερα στο {watermark}", "Εξερεύνησε τα χαρακτηριστικά στο {watermark}".
4. STRICTLY DO NOT include celebrity names or restricted player names in any text or overlay.

Return strict JSON with keys:
1. "hook": Image top text in Greek, max 10 words.
2. "body": Image mid text in Greek, max 10 words.
3. "cta": Image bottom soft CTA in Greek including '{watermark}', max 8 words.
4. "meta_caption": Greek Facebook/Instagram caption.
5. "tiktok_caption": Short Greek TikTok caption + 4 FYP hashtags.
6. "hashtags_meta": 8-10 trending hashtags (Greek or bilingual OK).
7. "slide1_text": Text overlay for Slide 1 in Greek.
8. "slide2_text": Text overlay for Slide 2 in Greek.
9. "slide3_text": Soft CTA text overlay for Slide 3 in Greek.
"""
        fallback = {
            "hook": f"Κουράστηκες από κούραση στα πόδια; Ανακάλυψε {brand_name} {clean_model_name}.",
            "body": "Σχεδιασμένο να απορροφά τους κραδασμούς και να στηρίζει τη στάση όλη μέρα.",
            "cta": f"Ανακάλυψε περισσότερα στο {watermark}.",
            "meta_caption": f"Οι πολλές ώρες όρθιος δεν χρειάζεται να επιβαρύνουν τα πόδια σου. Εξερεύνησε πώς το {brand_name} {clean_model_name} προσφέρει στήριξη στάσης. Μάθε περισσότερα στο {watermark}.",
            "tiktok_caption": f"Πώς αντιμετωπίζεις την κούραση στα πόδια; Δες την τεχνολογία πίσω από {brand_name} {clean_model_name} στο {watermark}! 👟 #Sneakerness #{brand_name}",
            "hashtags_meta": f"#Sneakerness #{brand_name} #DailyComfort #FootwearTech",
            "slide1_text": "Κουράστηκες από κούραση στα πόδια μετά από πολλές ώρες;",
            "slide2_text": f"Ανακάλυψε {brand_name} {clean_model_name}.",
            "slide3_text": f"Εξερεύνησε τα χαρακτηριστικά στο {watermark}",
        }
    else:
        lang_name = "English"
        sys_instruction = (
            "You are an expert e-commerce copywriter specializing in soft-sell, educational, "
            "and discovery-focused footwear ad copy and engaging social media posts in English. "
            "NEVER use celebrity athlete names in your text overlays."
        )
        script_prompt = f"""Write ALL ad assets and copy in ENGLISH for {brand_name} {clean_model_name} in {colorway_text} ({materials}) for website {watermark}.

CRITICAL CONSTRAINTS:
1. ALL OUTPUT MUST BE IN ENGLISH.
2. DO NOT use hard-sell verbs like "buy", "shop", "order", "purchase".
3. Use soft discovery CTAs like "Discover more at {watermark}", "Explore the full specs at {watermark}".
4. STRICTLY DO NOT include celebrity names or restricted player names in any text or overlay.

Return strict JSON with keys:
1. "hook": Image top text, max 10 words.
2. "body": Image mid text, max 10 words.
3. "cta": Image bottom soft CTA including '{watermark}', max 8 words.
4. "meta_caption": English Facebook/Instagram caption.
5. "tiktok_caption": Short English TikTok caption + 4 FYP hashtags.
6. "hashtags_meta": 8-10 trending English hashtags.
7. "slide1_text": Text overlay for Slide 1.
8. "slide2_text": Text overlay for Slide 2.
9. "slide3_text": Soft CTA text overlay for Slide 3.
"""
        fallback = {
            "hook": f"Tired of foot fatigue after long hours? Discover {brand_name} {clean_model_name}.",
            "body": "Engineered to absorb impact and support posture all day.",
            "cta": f"Discover more at {watermark}.",
            "meta_caption": f"Long shifts and daily standing don't have to take a toll on your feet. Explore how {brand_name} {clean_model_name} delivers posture support. Learn more at {watermark}.",
            "tiktok_caption": f"How do you deal with foot fatigue? Check out the tech behind {brand_name} {clean_model_name} at {watermark}! 👟 #Sneakerness #{brand_name}",
            "hashtags_meta": f"#Sneakerness #{brand_name} #DailyComfort #FootwearTech",
            "slide1_text": "Tired of Foot Fatigue After Long Hours?",
            "slide2_text": f"Discover {brand_name} {clean_model_name}.",
            "slide3_text": f"Explore the Full Specs at {watermark}",
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
):
    """Build 2–5 Nano Banana carousel prompts with a clear story arc."""
    hook_txt = ad_texts.get("slide1_text", ad_texts.get("hook", ""))
    product_txt = ad_texts.get("slide2_text", ad_texts.get("body", ""))
    cta_txt = ad_texts.get("slide3_text", ad_texts.get("cta", ""))
    body_txt = ad_texts.get("body", "")

    hook = (
        f"Create an image: Cinematic portrait of {selected_problem}. "
        f"Natural dramatic studio lighting. High emotion. Bold top text overlay: '{hook_txt}'. "
        f"{negative_constraint} Photorealistic 8k {ar_flag}"
    )
    product = (
        f"Create an image: Studio product photography of {brand} {safe_model_name} in {colorway} "
        f"colorway ({key_materials}) placed on a surface in {selected_env}. EDC props: {selected_props}. "
        f"Top-left tag '{selected_tag}', top-right badge '{selected_badge}'. Clean text overlay: '{product_txt}'. "
        f"{negative_constraint} Commercial studio lighting {ar_flag}"
    )
    product_cta = (
        f"Create an image: Studio product photography of {brand} {safe_model_name} in {colorway} "
        f"colorway ({key_materials}) placed on a surface in {selected_env}. EDC props: {selected_props}. "
        f"Top-left tag '{selected_tag}', top-right badge '{selected_badge}'. "
        f"Clean product showcase with soft CTA overlay: '{cta_txt}' and watermark '{custom_watermark}'. "
        f"{negative_constraint} Commercial studio lighting {ar_flag}"
    )
    lifestyle = (
        f"Create an image: Lifestyle environment scene in {selected_env} featuring EDC props: {selected_props}, "
        f"with {brand} {safe_model_name} in {colorway} colorway ({key_materials}) naturally placed in the scene. "
        f"Atmospheric natural light. Subtle text overlay: '{body_txt}'. "
        f"{negative_constraint} Photorealistic lifestyle photography 8k {ar_flag}"
    )
    specs = (
        f"Create an image: Sleek macro detail close-up photo of the sole and cushioning of "
        f"{brand} {safe_model_name} on {selected_env} background. Highlight materials: {key_materials}. "
        f"Clean overlay text: '{body_txt}'. "
        f"{negative_constraint} Commercial studio lighting {ar_flag}"
    )
    specs_cta = (
        f"Create an image: Sleek macro detail close-up photo of the sole and cushioning of "
        f"{brand} {safe_model_name} on {selected_env} background. Floating bold text '{custom_watermark}' "
        f"and soft CTA: '{cta_txt}'. "
        f"{negative_constraint} Commercial studio lighting {ar_flag}"
    )
    soft_cta = (
        f"Create an image: Clean minimal product still of {brand} {safe_model_name} in {colorway} "
        f"colorway ({key_materials}) on {selected_env} with soft negative space. "
        f"Floating bold watermark '{custom_watermark}' and soft CTA: '{cta_txt}'. "
        f"{negative_constraint} Commercial studio lighting {ar_flag}"
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


def clear_all_fields():
    st.session_state["brand_val"] = ""
    st.session_state["model_val"] = ""
    st.session_state["colorway_val"] = ""
    st.session_state["specs_val"] = ""
    st.session_state["env_desc_val"] = "minimalist concrete urban street with natural daylight"
    st.session_state["props_desc_val"] = "an open Kinfolk magazine, a ceramic cup of cappuccino, brass keys, succulent"
    st.session_state["problem_desc_val"] = "a tired worker sitting on stairs touching sore feet with work boots beside them"
    st.session_state["watermark_val"] = "SNEAKERNESS.EU"
    st.session_state["selected_tag_val"] = AUTHENTICITY_TAGS[0]
    st.session_state["selected_badge_val"] = CATEGORY_BADGES[0]
    st.session_state["ad_format_val"] = "Single Layout Ad (1 Εικόνα)"
    st.session_state["slide_count_val"] = 3
    st.session_state["aspect_ratio_val"] = "1:1 (Square)"
    st.session_state["history_image_path"] = None
    st.session_state["loaded_meta_caption"] = ""
    st.session_state["loaded_tiktok_caption"] = ""
    st.session_state["loaded_hashtags_meta"] = ""
    st.session_state["loaded_visual_prompt"] = ""
    st.session_state["loaded_slide1_prompt"] = ""
    st.session_state["loaded_slide2_prompt"] = ""
    st.session_state["loaded_slide3_prompt"] = ""
    st.session_state["loaded_slide4_prompt"] = ""
    st.session_state["loaded_slide5_prompt"] = ""
    st.session_state["show_loaded_pack"] = False
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
    st.session_state["watermark_val"] = entry.get("watermark", "SNEAKERNESS.EU") or "SNEAKERNESS.EU"
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
    st.session_state["loaded_visual_prompt"] = entry.get("visual_prompt", "") or ""
    st.session_state["loaded_slide1_prompt"] = entry.get("slide1_prompt", "") or ""
    st.session_state["loaded_slide2_prompt"] = entry.get("slide2_prompt", "") or ""
    st.session_state["loaded_slide3_prompt"] = entry.get("slide3_prompt", "") or ""
    st.session_state["loaded_slide4_prompt"] = entry.get("slide4_prompt", "") or ""
    st.session_state["loaded_slide5_prompt"] = entry.get("slide5_prompt", "") or ""
    st.session_state["show_loaded_pack"] = True
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1

if "brand_val" not in st.session_state: st.session_state["brand_val"] = ""
if "model_val" not in st.session_state: st.session_state["model_val"] = ""
if "colorway_val" not in st.session_state: st.session_state["colorway_val"] = ""
if "specs_val" not in st.session_state: st.session_state["specs_val"] = ""
if "env_desc_val" not in st.session_state: st.session_state["env_desc_val"] = "minimalist concrete urban street with natural daylight"
if "props_desc_val" not in st.session_state: st.session_state["props_desc_val"] = "an open Kinfolk magazine, a ceramic cup of cappuccino, brass keys, succulent"
if "problem_desc_val" not in st.session_state: st.session_state["problem_desc_val"] = "a tired worker sitting on stairs touching sore feet with work boots beside them"
if "uploader_key" not in st.session_state: st.session_state["uploader_key"] = 0
if "watermark_val" not in st.session_state: st.session_state["watermark_val"] = "SNEAKERNESS.EU"
if "selected_tag_val" not in st.session_state: st.session_state["selected_tag_val"] = AUTHENTICITY_TAGS[0]
if "selected_badge_val" not in st.session_state: st.session_state["selected_badge_val"] = CATEGORY_BADGES[0]
if "ad_format_val" not in st.session_state: st.session_state["ad_format_val"] = "Single Layout Ad (1 Εικόνα)"
if "slide_count_val" not in st.session_state: st.session_state["slide_count_val"] = 3
if "aspect_ratio_val" not in st.session_state: st.session_state["aspect_ratio_val"] = "1:1 (Square)"
if "history_image_path" not in st.session_state: st.session_state["history_image_path"] = None
if "loaded_meta_caption" not in st.session_state: st.session_state["loaded_meta_caption"] = ""
if "loaded_tiktok_caption" not in st.session_state: st.session_state["loaded_tiktok_caption"] = ""
if "loaded_hashtags_meta" not in st.session_state: st.session_state["loaded_hashtags_meta"] = ""
if "loaded_visual_prompt" not in st.session_state: st.session_state["loaded_visual_prompt"] = ""
if "loaded_slide1_prompt" not in st.session_state: st.session_state["loaded_slide1_prompt"] = ""
if "loaded_slide2_prompt" not in st.session_state: st.session_state["loaded_slide2_prompt"] = ""
if "loaded_slide3_prompt" not in st.session_state: st.session_state["loaded_slide3_prompt"] = ""
if "loaded_slide4_prompt" not in st.session_state: st.session_state["loaded_slide4_prompt"] = ""
if "loaded_slide5_prompt" not in st.session_state: st.session_state["loaded_slide5_prompt"] = ""
if "show_loaded_pack" not in st.session_state: st.session_state["show_loaded_pack"] = False


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
if st.button(t("generate_button", lang), type="primary"):
    if not brand or not model_name:
        st.error(t("generate_error", lang))
    else:
        with st.spinner(t("generate_spinner", lang, lang_name=t("lang_name", lang))):
            ad_texts = safe_generate_ad_copy(brand, model_name, colorway, key_materials, custom_watermark, lang=lang)

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

        negative_constraint = " STRICTLY NO text like 'Slide X of Y', NO carousel numbering, NO UI elements, NO page numbers. ONLY the requested overlay text."

        if ad_format == "Single Layout Ad (1 Εικόνα)":
            visual_prompt = f"""Create an image: Photorealistic vertical photograph of {brand} {safe_model_name} in {colorway} colorway ({key_materials}) placed on a smooth surface in the foreground, accompanied by {selected_props}. In the soft-focus upper background, {selected_problem}. Natural depth of field and continuous studio lighting. Render a top-left fabric tag reading '{selected_tag}' and a top-right badge reading '{selected_badge}'. Display headline text overlay '{ad_texts['hook']}', body text overlay '{ad_texts['body']}', and bottom watermark '{custom_watermark}' with soft CTA '{ad_texts['cta']}'. {negative_constraint} Photorealistic 8k, seamless single canvas {ar_flag}"""

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

        tab1, tab2 = st.tabs([
            t("tab_meta", lang, lang_name=t("lang_name", lang)),
            t("tab_tiktok", lang, lang_name=t("lang_name", lang)),
        ])
        
        with tab1:
            meta_post = f"{ad_texts.get('meta_caption', '')}\n\n{ad_texts.get('hashtags_meta', '')}"
            st.text_area(t("caption_meta_label", lang, lang_name=t("lang_name", lang)), value=meta_post, height=180)
            
        with tab2:
            tiktok_post = ad_texts.get('tiktok_caption', '')
            st.text_area(t("caption_tiktok_label", lang, lang_name=t("lang_name", lang)), value=tiktok_post, height=120)

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
            "ad_texts": ad_texts,
            "lang": lang,
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
        st.session_state["loaded_visual_prompt"] = hist_payload.get("visual_prompt", "")
        st.session_state["loaded_slide1_prompt"] = hist_payload.get("slide1_prompt", "")
        st.session_state["loaded_slide2_prompt"] = hist_payload.get("slide2_prompt", "")
        st.session_state["loaded_slide3_prompt"] = hist_payload.get("slide3_prompt", "")
        st.session_state["loaded_slide4_prompt"] = hist_payload.get("slide4_prompt", "")
        st.session_state["loaded_slide5_prompt"] = hist_payload.get("slide5_prompt", "")
        st.session_state["show_loaded_pack"] = False

        st.info(t("saved_info", lang, path=file_path))
        
        st.download_button(
            label=t("download_label", lang),
            data=txt_content,
            file_name=f"{brand}_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
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
    tab_h1, tab_h2 = st.tabs([
        t("tab_meta", lang, lang_name=t("lang_name", lang)),
        t("tab_tiktok", lang, lang_name=t("lang_name", lang)),
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

