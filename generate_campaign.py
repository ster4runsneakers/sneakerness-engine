import os
import json
import random
from dotenv import load_dotenv
from google import genai
from google.genai import types

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
    - Single continuous 9:16 vertical canvas composition.
    - Top-left badge: '100% AUTHENTIC GUARANTEED' (Render ONCE ONLY at absolute top-left).
    - Top-right badge: 'REVIEWED ★★★★★' (Render ONCE ONLY at absolute top-right).
    - STRICT NEGATIVE INSTRUCTION: ABSOLUTELY NO DUPLICATE BADGES. Do NOT repeat, mirror, or recreate badges, logos, or trust seals on the bottom panel or lower half.
    - Clean bottom area featuring the product, subtle lifestyle props, and clear brand watermark 'SNEAKERNESS.EU'.

    OUTPUT FORMAT:
    Return ONLY a valid JSON object matching this schema (no markdown formatting, no code blocks):
    {{
        "target_query": "{selected_insight['query']}",
        "tiktok_script": {{
            "hook": "...",
            "body": "...",
            "cta": "Explore more specs at SNEAKERNESS.EU"
        }},
        "social_caption": "...",
        "pomelli_brief": {{
            "submitted_prompt": "Photorealistic 3-part vertical storytelling ad layout, single continuous frame, top-left badge '100% AUTHENTIC GUARANTEED' (ONCE ONLY), top-right badge 'REVIEWED ★★★★★' (ONCE ONLY), no duplicate badges on bottom section, high detail footwear product shot, neutral tones, 9:16 aspect ratio",
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
