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

st.set_page_config(page_title="Sneakerness Studio Engine", page_icon="👟", layout="centered")

st.title("👟 Sneakerness Ad, Carousel & Copy Studio")
st.subheader("Multimodal Auto-Matching Engine (Dynamic Content Edition)")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("❌ Δεν βρέθηκε το GEMINI_API_KEY στα Secrets / .env!")
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
            st.warning(f"⚠️ Μοντέλο {model_item} απέτυχε: {str(e)}")
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

def safe_generate_ad_copy(brand_name, model_name, colorway_text, materials, watermark):
    # 🛡️ Ασπίδα αφαίρεσης ευαίσθητων λέξεων
    unsafe_keywords = ["kobe", "jordan", "lebron", "messi", "ronaldo", "curry"]
    clean_model_name = model_name
    for word in unsafe_keywords:
        if word in clean_model_name.lower():
            clean_model_name = clean_model_name.lower().replace(word, "signature pro")

    sys_instruction = "You are an expert e-commerce copywriter specializing in soft-sell, educational, and discovery-focused footwear ad copy and engaging social media posts in English. NEVER use celebrity athlete names in your text overlays."
    
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
            
    return {
        "hook": f"Tired of foot fatigue after long hours? Discover {brand_name} {clean_model_name}.",
        "body": "Engineered to absorb impact and support posture all day.",
        "cta": f"Discover more at {watermark}.",
        "meta_caption": f"Long shifts and daily standing don't have to take a toll on your feet. Explore how {brand_name} {clean_model_name} delivers posture support. Learn more at {watermark}.",
        "tiktok_caption": f"How do you deal with foot fatigue? Check out the tech behind {brand_name} {clean_model_name} at {watermark}! 👟 #Sneakerness #{brand_name}",
        "hashtags_meta": f"#Sneakerness #{brand_name} #DailyComfort #FootwearTech",
        "slide1_text": "Tired of Foot Fatigue After Long Hours?",
        "slide2_text": f"Discover {brand_name} {clean_model_name}.",
        "slide3_text": f"Explore the Full Specs at {watermark}"
    }

# 3. RESET & INITIALIZE SESSION STATE
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
    st.session_state["aspect_ratio_val"] = "1:1 (Square)"
    st.session_state["history_image_path"] = None
    st.session_state["loaded_meta_caption"] = ""
    st.session_state["loaded_tiktok_caption"] = ""
    st.session_state["loaded_hashtags_meta"] = ""
    st.session_state["loaded_visual_prompt"] = ""
    st.session_state["loaded_slide1_prompt"] = ""
    st.session_state["loaded_slide2_prompt"] = ""
    st.session_state["loaded_slide3_prompt"] = ""
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
    formats = ["Single Layout Ad (1 Εικόνα)", "3-Slide Carousel Pack (3 Εικόνες)"]
    fmt = entry.get("ad_format") or formats[0]
    st.session_state["ad_format_val"] = fmt if fmt in formats else formats[0]
    ratios = ["9:16 (Story/TikTok)", "1:1 (Square)"]
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
if "aspect_ratio_val" not in st.session_state: st.session_state["aspect_ratio_val"] = "1:1 (Square)"
if "history_image_path" not in st.session_state: st.session_state["history_image_path"] = None
if "loaded_meta_caption" not in st.session_state: st.session_state["loaded_meta_caption"] = ""
if "loaded_tiktok_caption" not in st.session_state: st.session_state["loaded_tiktok_caption"] = ""
if "loaded_hashtags_meta" not in st.session_state: st.session_state["loaded_hashtags_meta"] = ""
if "loaded_visual_prompt" not in st.session_state: st.session_state["loaded_visual_prompt"] = ""
if "loaded_slide1_prompt" not in st.session_state: st.session_state["loaded_slide1_prompt"] = ""
if "loaded_slide2_prompt" not in st.session_state: st.session_state["loaded_slide2_prompt"] = ""
if "loaded_slide3_prompt" not in st.session_state: st.session_state["loaded_slide3_prompt"] = ""
if "show_loaded_pack" not in st.session_state: st.session_state["show_loaded_pack"] = False


# 3b. HISTORY SIDEBAR
with st.sidebar:
    st.markdown("### Ιστορικό / History")
    history_entries = load_history()
    history_entries_sorted = sorted(
        history_entries,
        key=lambda e: e.get("created_at", ""),
        reverse=True,
    )
    if not history_entries_sorted:
        st.caption("Δεν υπάρχουν αποθηκευμένα προϊόντα ακόμα.")
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

        selected_label = st.selectbox("Επιλογή προϊόντος", labels, key="history_select_label")
        col_load, col_del = st.columns(2)
        with col_load:
            if st.button("Load", use_container_width=True, key="history_load_btn"):
                entry = get_entry(id_by_label[selected_label])
                if entry:
                    apply_history_entry(entry)
                    st.rerun()
        with col_del:
            if st.button("Delete", use_container_width=True, key="history_delete_btn"):
                delete_entry(id_by_label[selected_label])
                st.rerun()

# 4. UI & ACTIONS
col_header, col_reset = st.columns([3, 1])
with col_reset:
    st.write("")
    if st.button("🧹 Νέο Παπούτσι / Clear"):
        clear_all_fields()
        st.rerun()

col_up, col_preview = st.columns([2, 1])
with col_up:
    uploaded_file = st.file_uploader(
        "📷 Ανέβασε φωτογραφία παπουτσιού", 
        type=["jpg", "jpeg", "png", "webp"],
        key=f"uploader_{st.session_state['uploader_key']}"
    )
with col_preview:
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Προεπισκόπηση", use_container_width=True)
    elif st.session_state.get("history_image_path"):
        hist_img = Path(st.session_state["history_image_path"])
        if hist_img.is_file():
            st.image(str(hist_img), caption="Από ιστορικό", use_container_width=True)

if st.button("🔍 Δυναμική Ανίχνευση & Δημιουργία Σκηνής (Custom Specs & Scene)"):
    if not uploaded_file:
        st.warning("⚠️ Παρακαλώ ανέβασε πρώτα μια φωτογραφία παπουτσιού!")
    else:
        with st.spinner("Πλήρης ανάλυση εικόνας, ταυτοποίηση & παραγωγή custom σκηνής..."):
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
    brand = st.text_input("Brand / Μάρκα", value=st.session_state["brand_val"], placeholder="π.χ. HOKA")
    st.session_state["brand_val"] = brand

with col2: 
    model_name = st.text_input("Model Name / Μοντέλο", value=st.session_state["model_val"], placeholder="π.χ. Mafate Speed 2")
    st.session_state["model_val"] = model_name

with col3: 
    colorway = st.text_input("Colorway / Χρώμα", value=st.session_state["colorway_val"], placeholder="π.χ. Cream / Red")
    st.session_state["colorway_val"] = colorway

custom_watermark = st.text_input("Watermark / Domain", value=st.session_state["watermark_val"])
st.session_state["watermark_val"] = custom_watermark

key_materials = st.text_area("Specs / Τεχνικά Χαρακτηριστικά", value=st.session_state["specs_val"], placeholder="Τεχνικά χαρακτηριστικά...", height=80)
st.session_state["specs_val"] = key_materials

col_tag, col_badge = st.columns(2)
with col_tag:
    _tag_idx = AUTHENTICITY_TAGS.index(st.session_state["selected_tag_val"]) if st.session_state["selected_tag_val"] in AUTHENTICITY_TAGS else 0
    selected_tag = st.selectbox("Tag (Πάνω Αριστερά)", AUTHENTICITY_TAGS, index=_tag_idx)
    st.session_state["selected_tag_val"] = selected_tag
with col_badge:
    _badge_idx = CATEGORY_BADGES.index(st.session_state["selected_badge_val"]) if st.session_state["selected_badge_val"] in CATEGORY_BADGES else 0
    selected_badge = st.selectbox("Badge (Πάνω Δεξιά)", CATEGORY_BADGES, index=_badge_idx)
    st.session_state["selected_badge_val"] = selected_badge

st.markdown("#### 🎨 Δυναμικά Στοιχεία Σκηνής (Custom Scene Prompts)")

selected_env = st.text_area("Περιβάλλον Φόντου (Custom Environment)", value=st.session_state["env_desc_val"], height=70)
st.session_state["env_desc_val"] = selected_env

selected_props = st.text_area("Αξεσουάρ / EDC Props (Custom Props)", value=st.session_state["props_desc_val"], height=70)
st.session_state["props_desc_val"] = selected_props

selected_problem = st.text_area("Σενάριο Προβλήματος (Custom Problem Scene)", value=st.session_state["problem_desc_val"], height=70)
st.session_state["problem_desc_val"] = selected_problem

col_fmt, col_ar = st.columns(2)
with col_fmt:
    _fmt_options = ["Single Layout Ad (1 Εικόνα)", "3-Slide Carousel Pack (3 Εικόνες)"]
    _fmt_idx = _fmt_options.index(st.session_state["ad_format_val"]) if st.session_state["ad_format_val"] in _fmt_options else 0
    ad_format = st.selectbox("Τύπος Διαφήμισης (Format)", _fmt_options, index=_fmt_idx)
    st.session_state["ad_format_val"] = ad_format
with col_ar:
    _ar_options = ["9:16 (Story/TikTok)", "1:1 (Square)"]
    _ar_idx = _ar_options.index(st.session_state["aspect_ratio_val"]) if st.session_state["aspect_ratio_val"] in _ar_options else 1
    aspect_ratio = st.radio("Αναλογία Εικόνας (Aspect Ratio)", _ar_options, index=_ar_idx)
    st.session_state["aspect_ratio_val"] = aspect_ratio

ar_flag = "--ar 1:1" if "1:1" in aspect_ratio else "--ar 9:16"

st.markdown("---")

# 6. GENERATION
if st.button("🚀 Δημιουργία Content Pack", type="primary"):
    if not brand or not model_name:
        st.error("⚠️ Συμπλήρωσε ή ανίχνευσε πρώτα τη Μάρκα και το Μοντέλο!")
    else:
        with st.spinner("Δημιουργία Prompts, Social Captions & Copy (English)..."):
            ad_texts = safe_generate_ad_copy(brand, model_name, colorway, key_materials, custom_watermark)

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

            st.markdown("#### 🍌 Nano Banana Prompt (Single Image)")
            st.code(visual_prompt, language="text")

        else:
            slide1_prompt = f"""Create an image: Cinematic portrait of {selected_problem}. Natural dramatic studio lighting. High emotion. Bold top text overlay: '{ad_texts.get('slide1_text', ad_texts['hook'])}'. {negative_constraint} Photorealistic 8k {ar_flag}"""
            
            slide2_prompt = f"""Create an image: Studio product photography of {brand} {safe_model_name} in {colorway} colorway ({key_materials}) placed on a surface in {selected_env}. EDC props: {selected_props}. Top-left tag '{selected_tag}', top-right badge '{selected_badge}'. Clean text overlay: '{ad_texts.get('slide2_text', ad_texts['body'])}'. {negative_constraint} Commercial studio lighting {ar_flag}"""
            
            slide3_prompt = f"""Create an image: Sleek macro detail close-up photo of the sole and cushioning of {brand} {safe_model_name} on {selected_env} background. Floating bold text '{custom_watermark}' and soft CTA: '{ad_texts.get('slide3_text', ad_texts['cta'])}'. {negative_constraint} Commercial studio lighting {ar_flag}"""

            st.markdown("#### 🍌 Nano Banana Prompts (3-Slide Carousel Pack)")
            st.write("**Slide 1 (The Hook / Problem):**")
            st.code(slide1_prompt, language="text")
            st.write("**Slide 2 (The Solution / Product):**")
            st.code(slide2_prompt, language="text")
            st.write("**Slide 3 (Soft Discovery CTA):**")
            st.code(slide3_prompt, language="text")

        st.markdown("---")
        st.markdown("### 📲 English Social Media Captions (Soft Discovery)")

        tab1, tab2 = st.tabs(["📘 Facebook & Instagram (English)", "🎵 TikTok / Carousel (English)"])
        
        with tab1:
            meta_post = f"{ad_texts.get('meta_caption', '')}\n\n{ad_texts.get('hashtags_meta', '')}"
            st.text_area("FB / IG Caption (English):", value=meta_post, height=180)
            
        with tab2:
            tiktok_post = ad_texts.get('tiktok_caption', '')
            st.text_area("TikTok Caption (English):", value=tiktok_post, height=120)

        os.makedirs("output", exist_ok=True)
        file_path = f"output/{brand}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        txt_content = f"""========================================
NANO BANANA VISUAL PROMPT
========================================
{visual_prompt if ad_format == 'Single Layout Ad (1 Εικόνα)' else f'Slide 1:\n{slide1_prompt}\n\nSlide 2:\n{slide2_prompt}\n\nSlide 3:\n{slide3_prompt}'}

========================================
FACEBOOK & INSTAGRAM POST (EN)
========================================
{meta_post}

========================================
TIKTOK / CAROUSEL POST (EN)
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
        }
        if ad_format == "Single Layout Ad (1 Εικόνα)":
            hist_payload["visual_prompt"] = visual_prompt
            hist_payload["slide1_prompt"] = ""
            hist_payload["slide2_prompt"] = ""
            hist_payload["slide3_prompt"] = ""
        else:
            hist_payload["visual_prompt"] = ""
            hist_payload["slide1_prompt"] = slide1_prompt
            hist_payload["slide2_prompt"] = slide2_prompt
            hist_payload["slide3_prompt"] = slide3_prompt

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
        st.session_state["show_loaded_pack"] = False

        st.info(f"💾 Αποθηκεύτηκε στο `{file_path}`")
        
        st.download_button(
            label="📥 Download Content Pack (.txt)",
            data=txt_content,
            file_name=f"{brand}_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )


# Show pack loaded from history (without regenerating)
if st.session_state.get("show_loaded_pack"):
    st.markdown("---")
    st.markdown("### Φορτωμένο από Ιστορικό / Loaded from History")
    if st.session_state.get("loaded_visual_prompt"):
        st.markdown("#### Nano Banana Prompt (Single Image)")
        st.code(st.session_state["loaded_visual_prompt"], language="text")
    elif st.session_state.get("loaded_slide1_prompt"):
        st.markdown("#### Nano Banana Prompts (3-Slide Carousel Pack)")
        st.write("**Slide 1 (The Hook / Problem):**")
        st.code(st.session_state["loaded_slide1_prompt"], language="text")
        st.write("**Slide 2 (The Solution / Product):**")
        st.code(st.session_state["loaded_slide2_prompt"], language="text")
        st.write("**Slide 3 (Soft Discovery CTA):**")
        st.code(st.session_state["loaded_slide3_prompt"], language="text")
    st.markdown("### English Social Media Captions (Soft Discovery)")
    tab_h1, tab_h2 = st.tabs(["Facebook & Instagram (English)", "TikTok / Carousel (English)"])
    with tab_h1:
        meta_loaded = (
            f"{st.session_state.get('loaded_meta_caption', '')}\n\n"
            f"{st.session_state.get('loaded_hashtags_meta', '')}"
        ).strip()
        st.text_area("FB / IG Caption (English):", value=meta_loaded, height=180, key="hist_meta_ta")
    with tab_h2:
        st.text_area(
            "TikTok Caption (English):",
            value=st.session_state.get("loaded_tiktok_caption", ""),
            height=120,
            key="hist_tt_ta",
        )

