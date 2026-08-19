# research/run_stage1_research.py
import os
import json
from dotenv import load_dotenv
from ecom_monitor import get_ecom_insights
from search_intent import get_consumer_pain_points

load_dotenv()

def compile_weekly_insights():
    ecom_data = get_ecom_insights()
    intent_data = get_consumer_pain_points()
    
    weekly_output = {
        "status": "Success",
        "stage": "Stage 1 - Data-Driven Market Research",
        "ecom_monitoring": ecom_data,
        "consumer_search_intent": intent_data,
        "top_3_actionable_insights": [
            "1. Focus content on 8-10 hour standing comfort (High demand, size stockouts).",
            "2. Address wide-toe box fit needs without sacrificing streetwear aesthetic.",
            "3. Provide practical autumn suede maintenance/care guides."
        ]
    }
    
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "weekly_insights.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(weekly_output, f, ensure_ascii=False, indent=4)
        
    print(f"[SUCCESS] Research complete. Output saved to {output_path}")

if __name__ == "__main__":
    compile_weekly_insights()