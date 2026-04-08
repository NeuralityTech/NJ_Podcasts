import os
import json
import re
from google.genai import types
from utils.models_config import ACTIVE_TEXT_MODEL, get_gemini_client

def run_script_generation(rag_output_path, api_key):
    if not os.path.exists(rag_output_path):
        return None, "rag_output.json not found."

    with open(rag_output_path, 'r', encoding='utf-8') as f:
        rag_data = json.load(f)

    rag_text = json.dumps(rag_data, indent=2, ensure_ascii=False)
    
    try:
        client = get_gemini_client(api_key)
        if not client:
            return None, "Error: No Gemini client could be initialized (API Key missing and no Service Account found)."
        
        prompt = f"""TAB 7: CORPORATE NARRATION SCRIPT GENERATION

You are an expert corporate narration scriptwriter and document synthesis engine.
Your task is to generate a professional 3-minute narration script (450–500 words) from the provided input data.

INPUT DATA (RAG OUTPUT):
{rag_text}

---

OBJECTIVE:
Convert the raw RAG output into a clean, continuous, voiceover-ready narration script.

PROCESS (VERY IMPORTANT):
1. CLEANING:
   - Remove ALL page references (e.g., “Page 12”, “p. 5”).
   - Remove ALL question formats.
   - Remove duplicate content and metadata artifacts.
2. MERGING LOGIC:
   - Combine related answers into unified ideas.
   - Maintain logical continuity start → growth → performance → customers → innovation → future.
3. NARRATIVE CONVERSION:
   - Transform all facts into storytelling flow instead of Q&A format.
   - Professional and clear tone, natural spoken language.

---

RULES:
- Use ONLY information present in input.
- STRICTLY 450–500 words.
- NO headings, section labels, or bullet points in script text.

OUTPUT FORMAT (STRICT JSON):
{{
  "script": "Full 450–500 word professional narration script..."
}}
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
            try:
                res = response.text.strip()
                if res.startswith("```json"): res = res[7:-3].strip()
                elif res.startswith("```"): res = res[3:-3].strip()
                data = json.loads(res)
                return data, "Success"
            except Exception as e:
                return None, f"JSON Error: {str(e)}"
        else: return None, "Empty response."

    except Exception as e:
        return {"script": "Mock: Trust, Performance, and a Vision for the Future..."}, f"Gemini Error: {str(e)}"

def process_script_generation(latest_output_folder, api_key):
    from utils import sequencing
    import shutil
    section_path = sequencing.init_new_section()
    rag_output_path = os.path.join(latest_output_folder, "rag_output.json")
    script_json, msg = run_script_generation(rag_output_path, api_key)
    if not script_json: return None, msg

    json_path = os.path.join(section_path, "script.json")
    txt_path = os.path.join(section_path, "script.txt")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(script_json, f, indent=2, ensure_ascii=False)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(script_json.get("script", "No script text found."))

    # CRITICAL: Copy rag_output.json into new section folder so downstream steps can find it
    dest_rag = os.path.join(section_path, "rag_output.json")
    if os.path.exists(rag_output_path) and not os.path.exists(dest_rag):
        shutil.copy2(rag_output_path, dest_rag)

    return section_path, msg
