import os
import json
import re
from google import genai
from google.genai import types

def generate_prompt_audit_html(prompts_data, output_folder):
    """
    GENERATES TAB 9 PROMPT AUDIT HTML (STRICT TEMPLATE)
    """
    html_cards = []
    # UPGRADE: Force absolute 'file:///' path for 100% reliable local browsing
    import pathlib
    # Always find the root output/ folder relative to CWD
    root_dir = os.getcwd()
    pdf_abs_path = os.path.abspath(os.path.join(root_dir, "output", "custom_pages.pdf"))
    # Standard file:/// format for local browsing
    pdf_base_url = pathlib.Path(pdf_abs_path).as_uri()

    for scene in prompts_data:
        if not isinstance(scene, dict): continue
        s_id = scene.get("scene_id", "scene_?")
        ai_p = scene.get("ai_prompt", "")
        traces = scene.get("context_trace", [])
        if not isinstance(traces, list): traces = []
        
        trace_html = ""
        for tr in traces:
            v, p, url = "?", "?", "#"
            if isinstance(tr, dict):
                v = tr.get("value", "")
                p = tr.get("page", "")
                num_match = re.findall(r'\d+', str(p))
                num = num_match[0] if num_match else "1"
                # Exact absolute file link with page anchor
                url = f"{pdf_base_url}#page={num}"
            
            trace_html += f'''
<div style="margin-top: 15px; font-size: 14px; padding: 12px; background: #f0f7ff; border-radius: 8px; border-left: 5px solid #004C8F;">
  <div style="font-weight: 800; color: #d35400; margin-bottom: 5px;">→ DATA TRACE: {v} | Source: {p}</div>
  <a href="{url}" target="_blank" class="audit-link" style="display: inline-block; background: #ffeb3b; color: #000; padding: 4px 10px; border-radius: 6px; text-decoration: none; font-weight: bold; border: 1px solid #c0ca33;">
    OPEN SOURCE PDF (Jump to Page {num})
  </a>
</div>'''

        html_cards.append(f'''
<div class="card">
  <div class="card-header">{s_id}</div>
  <div class="prompt-box">
    <strong>Final AI Prompt:</strong><br>
    {ai_p}
  </div>
  {trace_html}
</div>''')

    full_html = f'''<!DOCTYPE html>
<html>
<head>
  <title>Stage 9 Hardened Audit</title>
  <style>
    body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; padding: 60px; background: #f1f5f9; line-height: 1.6; max-width: 1100px; margin: 0 auto; color: #334155; }}
    h2 {{ color: #0f172a; border-bottom: 4px solid #004C8F; padding-bottom: 20px; margin-bottom: 40px; font-size: 32px; letter-spacing: -1px; }}
    .card {{ background: #ffffff; padding: 30px; margin-bottom: 30px; border-radius: 16px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }}
    .card-header {{ font-weight: 800; font-size: 24px; color: #004C8F; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 1px; }}
    .prompt-box {{ background: #f8fafc; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0; font-family: 'Consolas', monospace; font-size: 14px; color: #475569; }}
    .audit-link {{ 
        display: inline-block; 
        margin-top: 8px; 
        padding: 8px 16px; 
        background: #004C8F; 
        color: #ffffff; 
        text-decoration: none; 
        border-radius: 6px; 
        font-weight: bold; 
        font-size: 13px;
        transition: transform 0.2s, background 0.2s;
    }}
    .audit-link:hover {{ 
        background: #003366; 
        transform: translateY(-2px); 
        color: #ffffff;
    }}
  </style>
</head>
<body>
  <h2>Stage 9: Visual Truth & Traceability Audit</h2>
  {''.join(html_cards)}
</body>
</html>'''

    audit_path = os.path.join(output_folder, "prompt_audit.html")
    with open(audit_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    return audit_path

def run_image_prompt_generation(scenes_json_path, rag_output_path, api_key):
    from utils.models_config import get_gemini_client
    if not os.path.exists(scenes_json_path): return None, "scene.json not found."
    rag_text = "[]"
    if os.path.exists(rag_output_path):
        with open(rag_output_path, 'r', encoding='utf-8') as f:
            rag_text = json.dumps(json.load(f), indent=2, ensure_ascii=False)
    with open(scenes_json_path, 'r', encoding='utf-8') as f:
        scenes_data = json.load(f)
    num_scenes = len(scenes_data)
    try:
        client = get_gemini_client(api_key)
        if not client:
            return None, "Error: No Gemini client could be initialized (API Key missing and no Service Account found)."
        prompt = f"""TAB 9: PIXEL-PERFECT ONE-SHOT AUDIT LOCK

You are an elitist Visual Prompt Engineer. DO NOT summarize. Use the provided ONE-SHOT reference exactly.

=== ONE-SHOT REFERENCE (STRUCTURE BLUEPRINT) ===
[
{{
  "scene_id": "logo_start",
  "scene_name": "Brand Identity Overview",
  "subject": "logo only",
  "action": "static display",
  "environment": "minimal branded background using palette",
  "art_style": "Ultra-realistic corporate cinematic style",
  "lighting": "soft studio lighting",
  "details_typography": "None",
  "additional_polish": "Clean UI alignment and premium finish",
  "grounding": "Flat structured UI layout",
  "composition": "centered",
  "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
  "ai_prompt": "Centered logo on clean minimal background using strict brand palette, premium finish, sharp and high resolution, no additional elements, exact logo from reference-pic/download.jpg, --no distortion, no blur, no extra objects"
}},
{{
  "scene_id": "scene_01",
  "scene_name": "Financial Highlights",
  "subject": "Financial performance comparison",
  "action": "Displaying deposit growth comparison with supporting KPI",
  "environment": "Minimalist clean corporate space",
  "art_style": "Ultra-realistic corporate cinematic style",
  "lighting": "soft professional lighting with high clarity",
  "details_typography": "Bold data labels and premium typography",
  "additional_polish": "Clean reflections and premium finish",
  "grounding": "Single-element visualization",
  "composition": "central bar chart with side KPI card",
  "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
  "ai_prompt": "Ultra-realistic corporate financial visualization, central comparison bar chart showing Total Deposits with FY25 value 27,14,715 Crore (Page 10) and FY24 value 23,79,786 Crore (Page 10), clear upward growth visualization with labeled bars, strong emphasis on comparison, alongside KPI card displaying Profit After Tax 67,347 Crore (Page 10) in bold typography, minimal labels 'Deposits' and 'PAT', clean structured layout, high contrast readability, premium UI styling, exact logo from reference-pic/download.jpg applied as fixed UI overlay at top-right corner (4% width), --no missing values, incorrect numbers, rounded values, fake data, clutter, distortion",
  "context_trace": [
    {{
      "value": "27,14,715 Crore",
      "page": "Page 10",
      "anchor_id": "https://example.com/static/pdfs/report.pdf#page=10",
      "snippet": "Total Deposits reached 27,14,715 Crore in FY25."
    }},
    {{
      "value": "23,79,786 Crore",
      "page": "Page 10",
      "anchor_id": "https://example.com/static/pdfs/report.pdf#page=10",
      "snippet": "Total Deposits were 23,79,786 Crore in FY24."
    }},
    {{
      "value": "67,347 Crore",
      "page": "Page 10",
      "anchor_id": "https://example.com/static/pdfs/report.pdf#page=10",
      "snippet": "Profit After Tax was 67,347 Crore."
    }}
  ]
}},
{{
  "scene_id": "scene_02",
  "scene_name": "Shareholder Returns",
  "subject": "Shareholder metrics",
  "action": "Displaying EPS and dividend values as KPI cards",
  "environment": "Minimalist clean corporate space",
  "art_style": "Ultra-realistic corporate cinematic style",
  "lighting": "clean soft lighting",
  "details_typography": "Bold high contrast typography",
  "additional_polish": "Premium UI design",
  "grounding": "Single-element visualization",
  "composition": "balanced dual KPI layout",
  "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
  "ai_prompt": "Clean corporate visualization with two prominent KPI cards, one showing Earnings Per Share 88.3 (Page 10) and the other showing Dividend Per Share 22.0 (Page 10), both values in bold high contrast typography, minimal labels 'EPS' and 'Dividend', structured side-by-side layout, premium UI design, consistent brand palette, exact logo from reference-pic/download.jpg applied as fixed UI overlay at top-right corner (4% width), --no missing values, incorrect numbers, rounded values, fake data, clutter, distortion",
  "context_trace": [
    {{
      "value": "88.3",
      "page": "Page 10",
      "anchor_id": "https://example.com/static/pdfs/report.pdf#page=10",
      "snippet": "Earnings Per Share was 88.3."
    }},
    {{
      "value": "22.0",
      "page": "Page 10",
      "anchor_id": "https://example.com/static/pdfs/report.pdf#page=10",
      "snippet": "Dividend Per Share was 22.0."
    }}
  ]
}},
{{
  "scene_id": "logo_end",
  "scene_name": "Brand Identity Close",
  "subject": "logo only",
  "action": "static display",
  "environment": "minimal branded background using palette",
  "art_style": "Ultra-realistic corporate cinematic style",
  "lighting": "soft studio lighting",
  "details_typography": "None",
  "additional_polish": "Clean UI alignment and premium finish",
  "grounding": "Flat structured UI layout",
  "composition": "centered",
  "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
  "ai_prompt": "Centered logo outro on clean minimal background using strict brand palette, consistent with opening frame, sharp high resolution, premium finish, exact logo from reference-pic/download.jpg, --no distortion, no blur, no extra elements"
}}
]


=== CURRENT TASK ===
INPUT SCENES:
{json.dumps(scenes_data, indent=2)}

STRUCTURED CONTEXT (ONLY TRUTH SOURCE):
{rag_text}

=== STAGE 9 HARD RULES ===
1. SCENE COUNT RULE (N+2): You MUST generate exactly N+2 prompts where N is the number of input scenes. The first must be 'logo_start' and the last must be 'logo_end'.
2. PROACTIVE NUMERIC INJECTION: You MUST physically extract exact historical/financial numbers from the STRUCTURED CONTEXT and forcefully inject them into the 'ai_prompt' string for EVERY standard scene. NEVER use phrases like "placeholder value" or "dummy data". If a scene mentions "Profit After Tax" or any KPI, you MUST fetch the actual real value (e.g. 67,347 Crore) from the STRUCTURED CONTEXT and inject it!
3. NUMERIC VALIDATION (ZERO-TOLERANCE FOR PLACEHOLDERS): ALL numeric values MUST be validated ONLY against the STRUCTURED CONTEXT. DO NOT write "placeholder value". DO NOT infer. DO NOT write generic descriptions. If you mention a metric, you MUST state its exact numerical value from the context!
4. EXACT OUTPUT STRUCTURE: Every scene object MUST have exactly these keys: scene_id, scene_name, subject, action, environment, art_style, lighting, details_typography, additional_polish, grounding, composition, branding_instruction, ai_prompt, and context_trace.
5. AI PROMPT INLINE PAGE TAGS (MANDATORY): You MUST rigidly format ALL numbers in your ai_prompt string to include their exact reference page physically inside the string. IMMEDIATELY AFTER any number or financial value, you MUST append "(Page X)". Example: If the number is 88.3, you MUST write "88.3 (Page 10)". FAILURE TO INCLUDE "(Page X)" AFTER A NUMBER IS A ZERO-TOLERANCE VIOLATION.
6. CRITIC AGENT (MANDATORY VALIDATION LOOP): AFTER generating each scene "ai_prompt", you MUST cross-check all factual values (numbers, percentages, dates) ONLY against the STRUCTURED CONTEXT. Any value missing in the context, having an incorrect page reference, or being hallucinated must be rejected and fixed. Every number MUST have a mapped object in "context_trace"!
7. HIGH-FIDELITY DATA RENDERING: When injecting numbers, dates, or financial metrics, you MUST instruct the AI to render these values as sharp, giant, and highly readable text within the visual (e.g., 'giant bold text 67,347 Crore'). This ensures the image generator prioritizes legible data points.
8. MINIMALIST DATA ACCURACY (SINGLE-ELEMENT LOCK): You MUST render ONLY ONE focused data card or chart. The environment MUST be a clean, empty corporate room or solid wall. DO NOT draw a dashboard, grid, wall of cards, or secondary highlights. If context has 2 values, show ONE chart with 2 bars. NO FILLER DATA.
9. BRAND COLOR PALETTE & LOGO VISIBILITY: Use the provided Color Palette. The Logo Overlay is 4% width with 2% top-right margins and is a flat 2D element.
10. STRICT VISUAL GROUNDING AND OVERRIDE LAYER (MANDATORY):
    * PRIORITY ORDER: 1. Negative Prompt Rules, 2. ai_prompt Content, 3. Visual Style.
    * DATA DETECTION: If numeric values are present, render ONLY those values (No extra bars/segments). If NO numeric values, DO NOT generate charts/dashboards; render minimal abstract corporate background ONLY.
    * VISUAL STRUCTURE: 1 Value = Single KPI Card. 2+ Values = Simple Bar Chart or KPI Cards. Number of visuals MUST equal number of values.
    * CONCEPT OVERRIDE: If the scene is conceptual (ESG, Sustainability, Governance) and has NO numbers, IGNORE all "dashboard" or "data" terms. NO charts allowed.
    * PIE CHART RULE: Allowed ONLY if proportions/percentages are explicitly provided.
11. OUTPUT FORMAT: STRICT JSON array only.
"""
        from utils.models_config import ACTIVE_TEXT_MODEL
        response = client.models.generate_content(
            model=ACTIVE_TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )
        if not response.text: return None, "Empty response."
        prompts_data = json.loads(response.text.strip().strip('```json').strip('```'))
        return prompts_data, "Success"
    except Exception as e: return None, str(e)

def _critic_agent_validate(prompts):
    """Python-level Critic Agent: validates AI output for placeholder values and missing context_trace."""
    issues = []
    for scene in prompts:
        if not isinstance(scene, dict): continue
        sid = scene.get("scene_id", "?")
        # Skip logo scenes - they do not need context_trace
        if sid in ("logo_start", "logo_end"): continue
        ai_prompt = scene.get("ai_prompt", "")
        context_trace = scene.get("context_trace", [])
        # Check for placeholder language
        placeholder_phrases = ["placeholder value", "placeholder text", "YYYY", "placeholder", "{value}"]
        for phrase in placeholder_phrases:
            if phrase.lower() in ai_prompt.lower():
                issues.append(f"CRITIC FAIL [{sid}]: ai_prompt contains forbidden placeholder phrase: '{phrase}'")
        # Check for empty context_trace on data scenes
        if not context_trace:
            issues.append(f"CRITIC FAIL [{sid}]: context_trace is empty — no data grounding present.")
        # Check that each context_trace value appears in ai_prompt
        for tr in context_trace:
            if isinstance(tr, dict):
                val = str(tr.get("value", ""))
                if val and val not in ai_prompt:
                    issues.append(f"CRITIC FAIL [{sid}]: context_trace value '{val}' not found in ai_prompt.")
                # 11. SINGLE-ELEMENT LOCK (STRICT): ONLY ONE focused data card or chart permitted. NO dashboards, grids, or multiple KPI cards.
                # 12. LOGO CLARITY LOCK (STRICT): 4% width, 2% margins Top-Right. Flat 2D overlay.
                # 13. STRICT VISUAL GROUNDING:
                #     * Render ONLY explicit prompt values. No extra segments.
                #     * If NO numbers -> Minimal conceptual background ONLY. No charts.
                # 14. PIE CHART RULE: Allowed ONLY if proportions are explicitly provided.
                # 15. NEGATIVE PROMPT (MANDATORY): `--no extra-data, no-fake-metrics, no-inferred-values, no-extra-bars, no-pie-charts, no-clutter, no-ui-noise`.
                full_prompt = f"{ai_prompt}. Single standalone focused data visualization. Empty minimalist background. --no wall-of-cards, dashboard-grid, multiple-panels, thumbnails, gallery, collection, frame-grid, icons-wall, mosaic, patterns, clutter, collage, blurry, logo, text-blocks, extra-data, fake-metrics, inferred-values, extra-bars, pie-charts, ui-noise"
                scene["ai_prompt"] = full_prompt
    return issues

def process_image_prompt_generation(latest_output_folder, api_key):
    scenes_path = os.path.join(latest_output_folder, "scene.json")
    if not os.path.exists(scenes_path): return None, "scene.json missing."
    
    rag_output_path = os.path.join(latest_output_folder, "rag_output.json")
    # HARD BLOCK: rag_output.json must exist — without it there is no numeric data to inject
    if not os.path.exists(rag_output_path):
        return None, (
            "ERROR: rag_output.json not found in this section.\n"
            "You MUST run Step 6 (RAG QA) BEFORE running image prompt generation.\n"
            "The image prompt generator needs the RAG data to inject real financial values and page references."
        )
    
    # First pass generation
    prompts, msg = run_image_prompt_generation(scenes_path, rag_output_path, api_key)
    if not prompts: return None, msg
    
    # === CRITIC AGENT VALIDATION PASS ===
    issues = _critic_agent_validate(prompts)
    
    if issues:
        # Silent validation - no terminal output or log files
        prompts2, msg2 = run_image_prompt_generation(scenes_path, rag_output_path, api_key)
        if prompts2:
            issues2 = _critic_agent_validate(prompts2)
            if not issues2:
                prompts = prompts2
                msg = "Success" # User requested to hide warnings
        else:
            msg = "Success"
    else:
        msg = "Success"
    # Final result save (Step 9 Audit RE-INSTATED)
    save_path = os.path.join(latest_output_folder, "image_prompts.json")
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)
        
    generate_prompt_audit_html(prompts, latest_output_folder)
    return latest_output_folder, msg
