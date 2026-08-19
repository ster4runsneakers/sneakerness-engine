import os
import json
import random
from dotenv import load_dotenv
from google import genai

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
    
    # Αυστηρό Prompt με περιορισμούς χαρακτήρων, κανόνες στίξης & SINGLE-INSTANCE OVERLAY BADGES
    # Αυστηρό Prompt με περιορισμούς χαρακτήρων & κανόνες στίξης
    prompt = f"""
    You are the Global Content Engine for Sneakerness.
    Generate marketing copy based on this consumer insight:
    - Query: {selected_insight['query']}
    - Intent: {selected_insight['intent']}
    - Issue: {selected_insight['core_issue']}

    STRICT COPYWRITING RULES FOR POMELLI BRIEF:
    1. Language: Perfect, native American/British English.
    2. TITLE: Max 5 words. NO commas. Use a period at the end of thoughts (e.g., "REFINED WIDTH. ZERO BULK.").
    3. DESCRIPTION: Exactly 2 short, complete, grammatically perfect sentences. Max 25 words total.
    4. SUBMITTED PROMPT RULES (CRITICAL):
       - Generated prompt MUST describe a CLEAN vertical 9:16 layout without any duplicate graphics.
       - Include strict negative conditions in the prompt: "single frame composition, no split screen, no duplicate badges, no repeated trust seals on the bottom section, clean overall composition".

    OUTPUT FORMAT:
    Return ONLY a valid JSON object matching this schema (no markdown formatting, no code blocks):
    {{
        "target_query": "{selected_insight['query']}",
        "tiktok_script": {{
            "hook": "...",
            "body": "...",
            "cta": "..."
        }},
        "social_caption": "...",
        "pomelli_brief": {{
            "submitted_prompt": "Photorealistic lifestyle photography of a sneaker, single continuous frame, 9:16 aspect ratio, natural daylight, detailed texture, neutral tones, no split screen, no repeated overlays, clean lower composition",
            "title": "...",
            "description": "...",
            "goal": "Promote a new product"
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

    # Sanitize Title & Description
    brief = campaign_data["pomelli_brief"]
    brief["title"] = brief["title"].replace(",", ".").upper()

    # Save JSON for Pomelli
    os.makedirs("output", exist_ok=True)
    json_path = os.path.join("output", "pomelli_brief.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=4)

    # Save Markdown
    md_content = f"""# 👟 Sneakerness Global Campaign
**Target Insight:** {campaign_data['target_query']}

---

## 🎨 POMELLI CAMPAIGN BRIEF
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

## 📝 SOCIAL CAPTION
{campaign_data['social_caption']}
"""

    md_path = os.path.join("output", "campaign_latest.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"[SUCCESS] Clean & Validated Campaign Generated!")
    print(f" -> Pomelli Brief: {json_path}")

if __name__ == "__main__":
    generate_dynamic_campaign()
