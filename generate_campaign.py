import os
import json
import random
from dotenv import load_dotenv
from google import genai
from google.genai import types
from content_carousel import finalize_image_prompt

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file!")

client = genai.Client(api_key=api_key)

def load_weekly_insights():
    path = os.path.join("data", "weekly_insights.json")
    if not os.path.exists(path):
        raise FileNotFoundError("weekly_insights.json not found. Run Stage 1 first.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_dynamic_campaign():
    data = load_weekly_insights()
    insights = data.get("consumer_search_intent", [])
    
    if not insights:
        raise ValueError("No consumer insights found in weekly_insights.json")
        
    selected_insight = random.choice(insights)
    
    # Αυστηρό Prompt με κανόνες στίξης, Copywriting & Single-Instance Overlays
    prompt = f"""
    You are the Global Content Engine for Sneakerness.
    Generate marketing copy and visual prompts based on this consumer insight:
    - Target Query: {selected_insight['query']}
    - Search Intent: {selected_insight['intent']}
    - Core Issue: {selected_insight['core_issue']}

    STRICT COPYWRITING RULES (ENGLISH ONLY):
    1. Language: Perfect, native American/British English.
    2. Tone: Soft-discovery, educational, and lifestyle-focused. DO NOT use hard-sell words like "buy", "shop now", "order today", or "limited stock".
    3. TITLE: Max 5 words. NO commas. Use a period at the end of thoughts (e.g., "REFINED WIDTH. ZERO BULK.").
    4. DESCRIPTION: Exactly 2 short, complete, grammatically perfect sentences focusing on posture support and foot fatigue relief. Max 25 words total.
    
    CRITICAL VISUAL PROMPT RULES (SUBMITTED_PROMPT):
    - Single continuous 9:16 vertical canvas composition; write it as a plain scene description.
    - Never put slide numbers, page counters, role labels (hook/body/CTA/overlay), section headings, UI words (buttons, arrows, dots, swipe, close icons) or any rating/review wording inside submitted_prompt.
    - On-image text listed ONCE, only in this form: Text on image (render each exactly once, nothing else): headline "..." ; subline "..." ; button text "..." — headline max 6 plain common words, subline max 8, button text max 6; then: All text spelled exactly as written, no ligatures or misspellings. Render each text line exactly once. Do not render any labels, placeholders, slide numbers, page counters, instructions or words from this prompt other than the quoted lines.
    - Badge optional: at most ONE, only a small top-right '100% AUTHENTIC' listed among the quoted lines; otherwise no badges.
    - Shoes grounded: one pair per shot, worn by the one person or resting naturally on the ground; the shoe's own design is the only branding (do not ask for a drawn logo or wordmark).
    - People (if any) wear the advertised sneakers or proper shoes — no bare feet. Props unbranded: no recognizable third-party brands/logos (no AirPods, iPhone, Apple Watch-like devices).
    - Clean bottom area featuring the product and subtle lifestyle props. By default no website text on the image. If a watermark field is set: REQUIRED — list it once among the quoted lines as watermark "<exact user domain>" bottom-right and render it EXACTLY ONCE (no second tiny/micro duplicate, shortened copy, or extra corner mark; do not also add "sneakerness" when the user typed a full domain) as clearly phone-readable bottom-right text (~7–9% of image height, clean sans-serif, strong contrast — must be easily readable at a glance on a phone screen; not microscopic; not faint grey on busy background; subtle dark/light shadow OK), ~2–3% margin from edges (no giant headline, not dominating the shoe). Other quoted lines must NOT contain any website/domain — the watermark is the only on-image site text.

    OUTPUT FORMAT:
    Return ONLY a valid JSON object matching this schema (no markdown formatting, no code blocks):
    {{
        "target_query": "{selected_insight['query']}",
        "tiktok_script": {{
            "hook": "...",
            "body": "...",
            "cta": "See details."
        }},
        "social_caption": "...",
        "pomelli_brief": {{
            "submitted_prompt": "Photorealistic vertical lifestyle ad photo, single continuous frame: one pair of the sneakers resting naturally on the ground in a calm everyday setting, high detail footwear, neutral tones. Text on image (render each exactly once, nothing else): headline \\"...\\" ; subline \\"...\\" ; button text \\"See details\\". All text spelled exactly as written, no ligatures or misspellings. Render each text line exactly once. Do not render any labels, placeholders, slide numbers, page counters, instructions or words from this prompt other than the quoted lines. No bare feet, unbranded props only, 9:16 aspect ratio.",
            "title": "...",
            "description": "...",
            "goal": "Educate and promote product discovery"
        }}
    }}
    """

    print("[*] Generating strict, validated English Campaign...")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    clean_text = response.text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    campaign_data = json.loads(clean_text)

    # Sanitize Title (Αφαίρεση κόμματος & Κεφαλαία)
    brief = campaign_data["pomelli_brief"]
    brief["title"] = brief["title"].replace(",", ".").upper()
    # Same cleanup as the app: strip slide counters / labels / rating words / logo cues,
    # append the standing rules + negatives, final-check line last.
    brief["submitted_prompt"] = finalize_image_prompt(brief.get("submitted_prompt", ""))

    # Save JSON for Pomelli / Ad Studio
    os.makedirs("output", exist_ok=True)
    json_path = os.path.join("output", "pomelli_brief.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=4)

    # Save Markdown Report
    md_content = f"""# 👟 Sneakerness Global Campaign Brief
**Target Consumer Query:** {campaign_data['target_query']}

---

## 🎨 POMELLI / NANO BANANA BRIEF
* **Prompt:** `{brief['submitted_prompt']}`
* **Title:** `{brief['title']}`
* **Description:** `{brief['description']}`
* **Goal:** `{brief['goal']}`

---

## 🎬 TIKTOK / REELS SCRIPT (15s)
* **Hook:** {campaign_data['tiktok_script']['hook']}
* **Body:** {campaign_data['tiktok_script']['body']}
* **CTA:** {campaign_data['tiktok_script']['cta']}

---

## 📝 ENGLISH SOCIAL CAPTION (SOFT DISCOVERY)
{campaign_data['social_caption']}
"""

    md_path = os.path.join("output", "campaign_latest.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"[SUCCESS] Clean & Validated Campaign Generated!")
    print(f" -> Pomelli Brief: {json_path}")
    print(f" -> Campaign Markdown: {md_path}")

if __name__ == "__main__":
    generate_dynamic_campaign()
