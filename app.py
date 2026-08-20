# app.py - Multimodal Auto-Matching Sneakerness Engine
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="Sneakerness Studio Engine", page_icon="👟", layout="centered")

st.title("👟 Sneakerness Ad, Carousel & Copy Studio")
st.subheader("Multimodal Auto-Matching Engine (English Content Edition)")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("❌ Δεν βρέθηκε το GEMINI_API_KEY στα Secrets / .env!")
    st.stop()

client = genai.Client(api_key=api_key)

# 1. DEFINITIONS
ENVIRONMENTS_MAP = {
    "🏢 Αστικός δρόμος μινιμαλιστικού μπετόν (Φυσικό φως)": "minimalist concrete urban street with natural daylight",
    "☕ Εσωτερικό ζεστής καφετέριας (Απαλός φωτισμός)": "warm coffee shop interior with soft ambient lighting",
    "🏭 Βιομηχανική αποθήκη από γυαλί & ατσάλι (Neon)": "industrial glass-and-steel warehouse with neon reflections",
    "🪵 Πολυτελές εκθεσιακό showroom (Δρυς & πέτρα)": "luxury editorial showroom with warm oak and stone",
    "🏛️ Ευρωπαϊκό πλακόστρωτο σοκάκι (Ηλιόλουστο)": "European city cobblestone pavement with warm sunlight",
    "🌿 Σύγχρονο αστικό πάρκο (Ξύλινος πάγκος & πράσινο)": "modern urban park with wooden bench and soft greenery background",
    "🏙️ Rooftop με θέα την πόλη (Απογευματινό ηλιοβασίλεμα)": "modern city rooftop lounge with warm sunset golden hour light",
    "🎨 Creative studio με λευκούς τοίχους & industrial floor": "bright creative design studio with polished concrete and white walls"
}

EDC_PROPS_MAP = {
    "📖 Περιοδικό Kinfolk, καπουτσίνο, μπρούτζινα κλειδιά, παχύφυτο": "an open Kinfolk magazine, a ceramic cup of cappuccino, brass keys, succulent",
    "📓 Μπλε δερμάτινο σημειωματάριο, γυαλιά ηλίου aviator, ρολόι, κρίκος": "a navy leather notebook, aviator sunglasses, a luxury watch, carabiner",
    "🖋️ Μπρούτζινο στυλό, δερμάτινο πορτοφόλι, ακουστικά, cold brew": "a minimalist brass pen, a folded leather wallet, wireless earbuds case, cold brew",
    "🧴 Παγούρι αλουμινίου, μηχανικό ρολόι, σκούρα γυαλιά ηλίου, κλειδιά": "a stainless steel water bottle, a mechanical watch, dark sunglasses, key ring",
    "🎧 Ασύρματα overhead ακουστικά, espresso, vintage φωτογραφική": "sleek wireless overhead headphones, double espresso cup, vintage film camera",
    "💻 Minimalist tablet, δερμάτινο λουράκι, μπλε γυαλιά, matcha latte": "a minimalist tablet with leather sleeve, tortoise sunglasses, matcha latte cup"
}

PROBLEM_SCENES_MAP = {
    "👷 Κουρασμένος εργάτης στις σκάλες (Μπότες δίπλα, πιάνει πέλματα)": "a tired worker sitting on stairs touching sore feet with work boots beside them",
    "💼 Υπάλληλος γραφείου στο γραφείο (Τρίβει φτέρνες από σφιχτά παπούτσια)": "an office worker at a desk rubbing sore heels after hours in uncomfortable formal shoes",
    "🏃 Κουρασμένος δρομέας στο πεζοδρόμιο (Πιάσιμο σε αστράγαλο/καμάρα)": "a tired runner sitting on a curb holding an aching foot arch and ankle after a long run",
    "🛍️ Εργαζόμενος λιανικής/εστίασης (Μασάζ στις γάμπες από 8ωρη ορθοστασία)": "a retail service worker leaning against a counter massaging fatigued calves from standing 8h",
    "🚛 Οδηγός/Μεταφορέας (Διατάσεις σε αρθρώσεις μετά από πολύωρο ταξίδι)": "a driver resting beside a vehicle stretching stiff joints and feet after a long haul",
    "🏥 Νοσηλευτής/Γιατρός σε διάδρομο (Ξεκούραση ποδιών μετά από βάρδια)": "a medical healthcare worker sitting on a bench in hallway unlacing shoes to relieve pressure",
    "🧳 Ταξιδιώτης σε αεροδρόμιο (Κουρασμένα πέλματα δίπλα σε βαλίτσα)": "a traveler sitting on airport lounge chair massaging tired feet next to a carry-on suitcase"
}

ENV_KEYS = list(ENVIRONMENTS_MAP.keys())
PROPS_KEYS = list(EDC_PROPS_MAP.keys())
PROBLEM_KEYS = list(PROBLEM_SCENES_MAP.keys())

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
            "env_index": 0,
            "props_index": 0,
            "problem_index": 0
        }

    prompt_search = f"""Examine the provided sneaker image with extreme precision.

CRITICAL IDENTIFICATION RULES:
1. "brand": Identify the EXACT footwear brand name visible on the shoe or tongue (e.g., HOKA, Puma, Nike, Adidas, New Balance, Brooks).
2. "model": Identify the EXACT shoe model name based on visible text (e.g., "Mafate Speed 2", "Clifton", "Bondi"). Check the tongue, lateral side, or heel label carefully.
3. "colorway": Describe the exact observed colors in the image (e.g., "Cream / Red / Navy Blue").
4. "specs": Technical specifications specific to this exact model (e.g., Vibram Megagrip outsole, dual-density EVA midsole, breathable mesh upper).
5. "env_index": Integer (0-{len(ENV_KEYS)-1}) matching ENVIRONMENTS.
6. "props_index": Integer (0-{len(PROPS_KEYS)-1}) matching EDC_PROPS.
7. "problem_index": Integer (0-{len(PROBLEM_KEYS)-1}) matching PROBLEM_SCENES.

Return ONLY a valid, raw JSON object matching this schema:
{{
  "brand": "Detected Brand",
  "model": "Detected Model",
  "specs": "Technical features...",
  "colorway": "Detected colorway...",
  "env_index": 0,
  "props_index": 0,
  "problem_index": 0
}}"""

    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        prompt_search
    ]

    models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro"]
    
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

                parsed = json.loads(clean_txt)
                parsed["env_index"] = min(max(int(parsed.get("env_index", 0)), 0), len(ENV_KEYS) - 1)
                parsed["props_index"] = min(max(int(parsed.get("props_index", 0)), 0), len(PROPS_KEYS) - 1)
                parsed["problem_index"] = min(max(int(parsed.get("problem_index", 0)), 0), len(PROBLEM_KEYS) - 1)
                return parsed
        except Exception as e:
            st.warning(f"⚠️ Μοντέλο {model_item} απέτυχε: {str(e)}")
            time.sleep(1)

    return {
        "brand": "",
        "model": "",
        "specs": "",
        "colorway": "",
        "env_index": 0,
        "props_index": 0,
        "problem_index": 0
    }

def safe_generate_ad_copy(brand_name, model_name, colorway_text, materials, watermark):
    sys_instruction = "You are an expert e-commerce copywriter specializing in soft-sell, educational, and discovery-focused footwear ad copy and engaging social media posts in English."
    
    script_prompt = f"""Write ALL ad assets and copy in ENGLISH for {brand_name} {model_name} in {colorway_text} ({materials}) for website {watermark}.

CRITICAL CONSTRAINTS:
1. ALL OUTPUT MUST BE IN ENGLISH.
2. DO NOT use hard-sell verbs like "buy", "shop", "order", "purchase".
3. Use soft discovery CTAs like "Discover more at {watermark}", "Explore the full specs at {watermark}".

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
    
    models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro"]
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
        "hook": f"Tired of foot fatigue after long hours? Discover {brand_name} {model_name}.",
        "body": "Engineered to absorb impact and support posture all day.",
        "cta": f"Discover more at {watermark}.",
        "meta_caption": f"Long shifts and daily standing don't have to take a toll on your feet. Explore how {brand_name} {model_name} delivers posture support. Learn more at {watermark}.",
        "tiktok_caption": f"How do you deal with foot fatigue? Check out the tech behind {brand_name} {model_name} at {watermark}! 👟 #Sneakerness #{brand_name}",
        "hashtags_meta": f"#Sneakerness #{brand_name} #DailyComfort #FootwearTech",
        "slide1_text": "Tired of Foot Fatigue After Long Hours?",
        "slide2_text": f"Discover {brand_name} {model_name}.",
        "slide3_text": f"Explore the Full Specs at {watermark}"
    }

# 3. RESET & INITIALIZE SESSION STATE
def clear_all_fields():
    st.session_state["brand_val"] = ""
    st.session_state["model_val"] = ""
    st.session_state["colorway_val"] = ""
    st.session_state["specs_val"] = ""
    st.session_state["env_idx"] = 0
    st.session_state["props_idx"] = 0
    st.session_state["prob_idx"] = 0
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1

if "brand_val" not in st.session_state: st.session_state["brand_val"] = ""
if "model_val" not in st.session_state: st.session_state["model_val"] = ""
if "colorway_val" not in st.session_state: st.session_state["colorway_val"] = ""
if "specs_val" not in st.session_state: st.session_state["specs_val"] = ""
if "env_idx" not in st.session_state: st.session_state["env_idx"] = 0
if "props_idx" not in st.session_state: st.session_state["props_idx"] = 0
if "prob_idx" not in st.session_state: st.session_state["prob_idx"] = 0
if "uploader_key" not in st.session_state: st.session_state["uploader_key"] = 0

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

if st.button("🔍 Αυτόματη Ανίχνευση (Specs, Χρώμα, Περιβάλλον & Σενάριο)"):
    if not uploaded_file:
        st.warning("⚠️ Παρακαλώ ανέβασε πρώτα μια φωτογραφία παπουτσιού!")
    else:
        with st.spinner("Ακριβής ανάλυση εικόνας και ταυτοποίηση μοντέλου..."):
            img_bytes = uploaded_file.getvalue()
            
            mime = "image/jpeg"
            if uploaded_file.name.lower().endswith(".webp"): mime = "image/webp"
            elif uploaded_file.name.lower().endswith(".png"): mime = "image/png"

            data = auto_analyze_shoe("", "", img_bytes, mime)
            
            st.session_state["brand_val"] = data.get("brand", "")
            st.session_state["model_val"] = data.get("model", "")
            st.session_state["colorway_val"] = data.get("colorway", "")
            st.session_state["specs_val"] = data.get("specs", "")
            st.session_state["env_idx"] = data.get("env_index", 0)
            st.session_state["props_idx"] = data.get("props_index", 0)
            st.session_state["prob_idx"] = data.get("problem_index", 0)
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

custom_watermark = st.text_input("Watermark / Domain", value="SNEAKERNESS.EU")

key_materials = st.text_area("Specs / Τεχνικά Χαρακτηριστικά", value=st.session_state["specs_val"], placeholder="Τεχνικά χαρακτηριστικά...", height=80)
st.session_state["specs_val"] = key_materials

col_tag, col_badge = st.columns(2)
with col_tag: selected_tag = st.selectbox("Tag (Πάνω Αριστερά)", AUTHENTICITY_TAGS)
with col_badge: selected_badge = st.selectbox("Badge (Πάνω Δεξιά)", CATEGORY_BADGES)

env_label = st.selectbox("Περιβάλλον Φόντου (Environment)", ENV_KEYS, index=st.session_state["env_idx"])
selected_env = ENVIRONMENTS_MAP[env_label]

props_label = st.selectbox("Αξεσουάρ Τραπεζιού (EDC Props)", PROPS_KEYS, index=st.session_state["props_idx"])
selected_props = EDC_PROPS_MAP[props_label]

prob_label = st.selectbox("Σενάριο Προβλήματος (Πάνω Εικόνα)", PROBLEM_KEYS, index=st.session_state["prob_idx"])
selected_problem = PROBLEM_SCENES_MAP[prob_label]

col_fmt, col_ar = st.columns(2)
with col_fmt:
    ad_format = st.selectbox("Τύπος Διαφήμισης (Format)", ["Single Layout Ad (1 Εικόνα)", "3-Slide Carousel Pack (3 Εικόνες)"])
with col_ar:
    aspect_ratio = st.radio("Αναλογία Εικόνας (Aspect Ratio)", ["9:16 (Story/TikTok)", "1:1 (Square)"], index=1)

ar_flag = "--ar 1:1" if "1:1" in aspect_ratio else "--ar 9:16"

st.markdown("---")

# 6. GENERATION
if st.button("🚀 Δημιουργία Content Pack", type="primary"):
    if not brand or not model_name:
        st.error("⚠️ Συμπλήρωσε ή ανίχνευσε πρώτα τη Μάρκα και το Μοντέλο!")
    else:
        with st.spinner("Δημιουργία Prompts, Social Captions & Copy (English)..."):
            ad_texts = safe_generate_ad_copy(brand, model_name, colorway, key_materials, custom_watermark)

        if ad_format == "Single Layout Ad (1 Εικόνα)":
            visual_prompt = f"""E-commerce 3-part vertical storytelling ad layout. SINGLE CANVAS COMPOSITION.

TOP OVERLAY BADGES (STRICTLY ONCE AT THE VERY TOP):
- Top-Left Badge: '{selected_tag}' (Render ONCE at absolute top-left corner).
- Top-Right Badge: '{selected_badge}' (Render ONCE at absolute top-right corner).
- NEGATIVE RULE: DO NOT repeat, mirror, or recreate badges or trust seals on the middle or lower panels.

TOP SECTION (PROBLEM SCENE): {selected_problem}. Overlay headline text: '{ad_texts['hook']}'.

MIDDLE SECTION (HERO PRODUCT): Studio product photo of {brand} {model_name} in {colorway} colorway ({key_materials}) placed on a surface in {selected_env}. EDC props: {selected_props}. Overlay body text: '{ad_texts['body']}'.

BOTTOM SECTION (FOOTER): Seamless continuation of the same surface background. Floating bold brand watermark '{custom_watermark}' and soft CTA text: '{ad_texts['cta']}'.

DESIGN REQUIREMENTS: Soft gradient feathered transition between all sections. Clean layout, photorealistic 8k, commercial studio lighting {ar_flag}"""

            st.markdown("#### 🍌 Nano Banana Prompt (Single Image)")
            st.code(visual_prompt, language="text")

        else:
            slide1_prompt = f"""Slide 1 of 3 Carousel: Cinematic portrait of {selected_problem}. Natural dramatic studio lighting. High emotion. Bold top text overlay: '{ad_texts.get('slide1_text', ad_texts['hook'])}'. Photorealistic 8k {ar_flag}"""
            
            slide2_prompt = f"""Slide 2 of 3 Carousel: Studio product photography of {brand} {model_name} in {colorway} colorway ({key_materials}) placed on a surface in {selected_env}. EDC props: {selected_props}. Top-left tag '{selected_tag}', top-right badge '{selected_badge}'. Clean text overlay: '{ad_texts.get('slide2_text', ad_texts['body'])}'. Commercial studio lighting {ar_flag}"""
            
            slide3_prompt = f"""Slide 3 of 3 Carousel: Sleek macro detail close-up photo of the sole and cushioning of {brand} {model_name} on {selected_env} background. Floating bold text '{custom_watermark}' and soft CTA: '{ad_texts.get('slide3_text', ad_texts['cta'])}'. Commercial studio lighting {ar_flag}"""

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
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"FB/IG POST (EN):\n{meta_post}\n\nTIKTOK POST (EN):\n{tiktok_post}\n\nDATA:\n{json.dumps(ad_texts, ensure_ascii=False, indent=2)}")
        st.info(f"💾 Αποθηκεύτηκε στο `{file_path}`")
