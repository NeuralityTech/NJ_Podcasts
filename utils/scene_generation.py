import os
import json
from google.genai import types
from utils.models_config import get_gemini_client

def run_scene_generation(script_json_path, api_key, scene_count=8):
    if not os.path.exists(script_json_path):
        return None, "script.json not found."

    with open(script_json_path, 'r', encoding='utf-8') as f:
        script_data = json.load(f)
    
    script_text = script_data.get("script", "")
    
    try:
        client = get_gemini_client(api_key)
        if not client:
            return None, "Error: No Gemini client could be initialized (API Key missing and no Service Account found)."
        
        prompt = f"""TAB 8: DETERMINISTIC SCENE SEGMENTATION ENGINE

========================================================
MANDATORY CONSTRAINT: 
YOU MUST PRODUCE EXACTLY {scene_count} SCENES.
NO MORE. NO LESS. 
IF YOU DO NOT PRODUCE EXACTLY {scene_count} ELEMENTS, THE SYSTEM WILL CRASH.
========================================================

INPUT SCRIPT:
{script_text}

TARGET_SCENE_COUNT = {scene_count}

---

OBJECTIVE:
Split the script logically into exactly {scene_count} segments.

CORE SCENE RULES:
1. QUANTITY: Your JSON array MUST have exactly {scene_count} objects.
2. NARRATION: Use EXACT narration text (DO NOT paraphrase).
3. STRUCTURE: Every object MUST have "scene", "title", "text", "theme".
4. SEGMENTATION: 
   - If {scene_count} is small (e.g. 3-5), merge sentences into dense thematic scenes.
   - If {scene_count} is large (e.g. 15-20), split sentences into highly granular scenes.
5. INDEXING: Scene numbers MUST go from 1 to {scene_count}.

THEME BANK (SELECT ONE):
trust, financial performance, customer impact, business growth, digital transformation, innovation, risk and governance, sustainability, employee culture, future vision.

OUTPUT FORMAT (STRICT JSON ARRAY):
[
  {{
    "scene": 1,
    "title": "2–5 word short title",
    "text": "Exact narration text for this scene...",
    "theme": "one of the allowed themes or null"
  }}
]
"""
        from utils.models_config import ACTIVE_TEXT_MODEL
        response = client.models.generate_content(
            model=ACTIVE_TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        
        if response.text:
            text = response.text.strip()
            if text.startswith("```json"): text = text[7:-3].strip()
            elif text.startswith("```"): text = text[3:-3].strip()
            return json.loads(text), "Success"
        else:
            return None, "Empty response."
    except Exception as e:
        return None, f"Error: {str(e)}"

def process_scene_generation(latest_output_folder, api_key, scene_count=8):
    script_path = os.path.join(latest_output_folder, "script.json")
    scenes_json, msg = run_scene_generation(script_path, api_key, scene_count)
    if not scenes_json: return None, msg
    
    output_path = os.path.join(latest_output_folder, "scene.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(scenes_json, f, indent=2, ensure_ascii=False)
    return latest_output_folder, msg
