import os
import json
import re
from google import genai 
from google.genai import types
from utils.pdf_handler import get_pdf_page_index

def generate_prompt_audit_html(prompts_data, output_folder):
    """
    GENERATES TAB 9 PROMPT AUDIT HTML (STRICT TEMPLATE)
    """
    html_cards = []
    import pathlib
    root_dir = os.getcwd()
    pdf_abs_path = os.path.abspath(os.path.join(root_dir, "output", "custom_pages.pdf"))
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
                p_raw = tr.get("page", "")
                p = str(p_raw).strip()
                if p.lower().startswith("page "):
                    p = p[5:].strip()
                physical_idx = get_pdf_page_index(p)
                url = f"{pdf_base_url}#page={physical_idx}&view=FitH,0"
            
            trace_html += f'''
<div style="margin-top: 15px; font-size: 14px; padding: 12px; background: #f0f7ff; border-radius: 8px; border-left: 5px solid #004C8F;">
  <div style="font-weight: 800; color: #d35400; margin-bottom: 5px;">→ DATA TRACE: {v} | Source: {p}</div>
  <a href="{url}" target="_blank" class="audit-link" style="display: inline-block; background: #ffeb3b; color: #000; padding: 4px 10px; border-radius: 6px; text-decoration: none; font-weight: bold; border: 1px solid #c0ca33;">
    OPEN SOURCE PDF (Jump to Page {physical_idx})
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

def run_image_prompt_generation(scenes_json_path, rag_output_path, api_key, service_account_path=None):
    from utils.models_config import get_gemini_client
    if not os.path.exists(scenes_json_path): return None, "scene.json not found."
    
    rag_text = "[]"
    # DATA PIPELINE FIX: Check local section folder FIRST, then global output folder
    final_rag_path = rag_output_path
    if not os.path.exists(final_rag_path):
        global_rag = os.path.join(os.getcwd(), "output", "custom_pages", "auto", "rag_output.json")
        if os.path.exists(global_rag):
            print(f"DEBUG: Local rag_output.json not found. Falling back to global: {global_rag}")
            final_rag_path = global_rag
        else:
            return None, f"Source RAG data not found (tried {rag_output_path} and global output)."

    if os.path.exists(final_rag_path):
        try:
            with open(final_rag_path, 'r', encoding='utf-8') as f:
                rag_json = json.load(f)
                if not rag_json:
                    return None, "Error: RAG output file is empty []. Run Step 6 (RAG QA) again."
                rag_text = json.dumps(rag_json)
        except Exception as e:
            return None, f"Failed to read RAG data: {e}"
    
    # Also ensure scene.json is not empty
    with open(scenes_json_path, 'r', encoding='utf-8') as f:
        scenes_data = json.load(f)
        if not scenes_data:
            return None, "Error: scene.json is empty []. Run Step 8 (Scene Gen) again."
            
    palette_text = ""
    palette_path = os.path.join("reference-pic", "hdfc_bank_full_palette.md")
    if os.path.exists(palette_path):
        with open(palette_path, 'r', encoding='utf-8') as f:
            palette_text = f.read()

    print(f"DEBUG: Scenes found: {len(scenes_data)} | RAG data size: {len(rag_text)} chars")
        
    try:
        client = get_gemini_client(api_key, service_account_path)
        if not client:
            return None, "Error: No Gemini client could be initialized."
        
        prompt = f"""TAB 9: IMAGE PROMPT GENERATION (ABSOLUTE WHITE BACKGROUND LOCK)

You are an AI visual prompt engineer. Your output must ensure absolute brand consistency and zero background hallucinations.

COLOR PALETTE LOCK (SUPER STRICT)
Use ONLY:
1. HDFC Primary Blue: #004C8F
2. HDFC Primary Red: #ED232A
3. HDFC White: #FFFFFF
{palette_text}

MANDATORY BACKGROUND LOCK (WHITE ONLY)
The background MUST ONLY be:
- Solid Clean White background (#FFFFFF)
ZERO TOLERANCE for Blue backgrounds, bright colors, gray, or slate. 
Every single image MUST have a SOLID WHITE BACKGROUND.

HEADING & SUBJECT RULES (STRICT)
- HEADINGS MUST BE IN ALL CAPS.
- DO NOT include "Heading Text:" yourself.

LOGO FIDELITY LOCK (STRICT)
- exact logo from reference-pic/download.jpg at top-right corner (12% width, 2% margin).
- No doubling. No distortion.

PROMPT CLASSIFICATION SYSTEM (MANDATORY)
You MUST classify each scene BEFORE generating the prompt based on numeric density.
1. DATA-DRIVEN (1 value) → "single KPI highlight layout"
2. COMPARISON (>1 values) → "clean vertical comparison bar chart layout"
3. DISTRIBUTION (%) → "minimal donut chart layout"
4. TREND (Time) → "minimal line chart layout"
5. QUALITATIVE (Blank) → "single premium highlight card layout"
DATA ORDERING LOCK (STRICT ASCENDING - CRITICAL)
For all COMPARISON or DATA-DRIVEN layouts (bar charts, multi-value cards), you MUST arrange the data points in STRICT ASCENDING ORDER from left to right.
1. SCAN: Find all metrics for the scene in the RAG source.
2. NORMALIZE: Treat 'K27,14,715' as 2714715. Strip commas and currency symbols for comparison.
3. SORT: Arrange from SMALLEST numerical value (Left) to LARGEST numerical value (Right).
4. BUILD: Write the 'ai_prompt' and 'subject' based on this sorted sequence.
ZERO TOLERANCE for descending or random order.

STRICT RULES:
1. SCENE COUNT: Exactly N + 2 prompts.
2. NUMERIC TRACE: Every numeric value MUST include "(Page X)".
3. RE-CHECK: Read your generated JSON and ensure the numbers in 'ai_prompt' are numerically increasing.

OUTPUT STRUCTURE (STRICT JSON ONLY)
[
  {{
    "scene_id": "logo_start",
    "scene_name": "Brand Identity Overview",
    "subject": "LOGO ONLY",
    "action": "STATIC DISPLAY",
    "environment": "Solid Clean White background (#FFFFFF)",
    "composition": "CENTERED",
    "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
    "ai_prompt": "Centered HDFC Bank logo on SOLID Clean White background (#FFFFFF), sharp focus, no doubling, --no navy --no gray --no typo"
  }},
  {{
    "scene_id": "scene_01",
    "prompt_type": "DATA-DRIVEN",
    "composition": "single KPI highlight layout",
    "subject": "PROFIT AFTER TAX",
    "action": "highlighting financial metric",
    "environment": "Solid Clean White background (#FFFFFF)",
    "lighting": "soft professional lighting",
    "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
    "ai_prompt": "Corporate KPI card showing 67,347 Crore (Page 10), HDFC Primary Blue bold typography, on a SOLID White background (#FFFFFF), exact logo from reference-pic/download.jpg at top-right (12% width), large margins, --no doubling --no gray --no typo",
    "context_trace": [
      {{
        "value": "67,347 Crore",
        "page": "Page 10",
        "anchor_id": "https://example.com/static/pdfs/report.pdf#page=10",
        "snippet": "Profit After Tax was reported at 67,347 Crore."
      }}
    ]
  }},
  {{
    "scene_id": "scene_02",
    "prompt_type": "COMPARISON",
    "composition": "clean vertical comparison bar chart layout",
    "subject": "DEPOSIT GROWTH COMPARISON",
    "action": "comparing values in HDFC brand environment",
    "environment": "Solid Clean White background (#FFFFFF)",
    "lighting": "soft professional lighting",
    "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
    "ai_prompt": "Vertical bar chart comparing Deposits 23,79,786 Crore (Page 10) and 27,14,715 Crore (Page 10), proportional bars in HDFC Primary Blue and HDFC Red, on a SOLID White background (#FFFFFF), exact logo from reference-pic/download.jpg at top-right (12% width), no doubling, --no gradients --no gray --no navy background",
    "context_trace": [
      {{
        "value": "23,79,786 Crore",
        "page": "Page 10",
        "anchor_id": "https://example.com/static/pdfs/report.pdf#page=10",
        "snippet": "Deposits were 23,79,786 Crore."
      }},
      {{
        "value": "27,14,715 Crore",
        "page": "Page 10",
        "anchor_id": "https://example.com/static/pdfs/report.pdf#page=10",
        "snippet": "Deposits increased to 27,14,715 Crore."
      }}
    ]
  }},
  {{
    "scene_id": "scene_03",
    "prompt_type": "DISTRIBUTION",
    "composition": "minimal donut chart layout",
    "subject": "REVENUE SEGMENTATION",
    "action": "showing distribution on branded background",
    "environment": "Solid Clean White background (#FFFFFF)",
    "lighting": "soft studio lighting",
    "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
    "ai_prompt": "Minimal donut chart showing Revenue distribution: Retail 62% (Page 12) and Corporate 38% (Page 12), HDFC Primary Blue and HDFC Red segments on a SOLID White background (#FFFFFF), exact logo from reference-pic/download.jpg at top-right (12% width), --no doubling --no blur --no distortion",
    "context_trace": [
      {{
        "value": "62%",
        "page": "Page 12",
        "anchor_id": "https://example.com/static/pdfs/report.pdf#page=12",
        "snippet": "Retail segment contributed 62% of revenue."
      }},
      {{
        "value": "38%",
        "page": "Page 12",
        "anchor_id": "https://example.com/static/pdfs/report.pdf#page=12",
        "snippet": "Corporate segment contributed 38% of revenue."
      }}
    ]
  }},
  {{
    "scene_id": "scene_04",
    "prompt_type": "TREND",
    "composition": "minimal line chart layout",
    "subject": "PROFIT TREND OVER TIME",
    "action": "showing progression on branded background",
    "environment": "Solid Clean White background (#FFFFFF)",
    "lighting": "soft professional lighting",
    "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
    "ai_prompt": "Minimal line chart showing Profit trend FY21 12,450 Crore (Page 15) to FY23 18,300 Crore (Page 15), HDFC Primary Blue line on a SOLID White background (#FFFFFF), exact logo from reference-pic/download.jpg at top-right (12% width), --no doubling --no blur --no distortion",
    "context_trace": [
      {{
        "value": "12,450 Crore",
        "page": "Page 15",
        "anchor_id": "https://example.com/static/pdfs/report.pdf#page=15",
        "snippet": "Profit in FY21 was 12,450 Crore."
      }},
      {{
        "value": "18,300 Crore",
        "page": "Page 15",
        "anchor_id": "https://example.com/static/pdfs/report.pdf#page=15",
        "snippet": "Profit in FY23 reached 18,300 Crore."
      }}
    ]
  }},
  {{
    "scene_id": "scene_05",
    "prompt_type": "QUALITATIVE",
    "composition": "single premium highlight card layout",
    "subject": "TRUST AND STABILITY CONCEPT",
    "action": "representing brand strength",
    "environment": "Solid Clean White background (#FFFFFF)",
    "lighting": "bright professional lighting",
    "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
    "ai_prompt": "Premium corporate visual representing trust and stability, using SOLID Clean White background (#FFFFFF) and HDFC Primary Blue elements, crystal clear focus, exact logo from reference-pic/download.jpg at top-right (12% width), --no doubling --no blur --no distortion",
    "context_trace": []
  }},
  {{
    "scene_id": "scene_06",
    "prompt_type": "QUALITATIVE",
    "composition": "cinematic executive control room layout",
    "subject": "GOVERNANCE AND CUSTOMER TRUST",
    "action": "visualizing institutional strength and trust-building systems",
    "environment": "Solid Clean White background (#FFFFFF)",
    "lighting": "bright professional corporate lighting",
    "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
    "ai_prompt": "Cinematic financial control room representing governance, trust, and institutional strength, holographic security dashboards and compliance UI, on a SOLID Clean White background (#FFFFFF), exact logo from reference-pic/download.jpg at top-right (12% width), --no text clutter --no fake data --no distortion",
    "context_trace": []
  }},
  {{
    "scene_id": "logo_end",
    "scene_name": "Brand Identity Close",
    "subject": "LOGO ONLY",
    "action": "STATIC DISPLAY",
    "composition": "CENTERED",
    "environment": "Solid Clean White background (#FFFFFF)",
    "branding_instruction": "exact logo from reference-pic/download.jpg applied as fixed UI overlay",
    "ai_prompt": "Closing frame with centered corporate logo on SOLID White background (#FFFFFF), sharp focus, --no doubling"
  }}
]

=== CURRENT TASK ===
INPUT SCENES (N):
{json.dumps(scenes_data, indent=2)}

STRUCTURED CONTEXT (ONLY TRUTH SOURCE):
{rag_text}

    OUTPUT FORMAT: STRICT JSON array only.
"""
        from utils.models_config import ACTIVE_TEXT_MODEL
        response = client.models.generate_content(
            model=ACTIVE_TEXT_MODEL,
            contents=[
                prompt,
                f"INPUT SCENE DATA: {json.dumps(scenes_data)}",
                f"INPUT RAG TRUTH SOURCE: {rag_text}"
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )
        
        if response.text:
            text = response.text.strip()
            if text.startswith("```json"): text = text[7:-3].strip()
            elif text.startswith("```"): text = text[3:-3].strip()
            
            try:
                prompts_data = json.loads(text)
                if not isinstance(prompts_data, list) or len(prompts_data) == 0:
                    return None, "Error: AI generated an empty list []. This usually means the RAG data didn't provide enough specific metrics for the scenes."
                
                # Apply Critic Validation
                final_prompts = _critic_agent_validate(prompts_data)
                return final_prompts, "Success"
            except Exception as e:
                return None, f"JSON Parse Error: {str(e)}"
        else:
            return None, "Empty response from Gemini AI."
    except Exception as e:
        return None, str(e)

def _critic_agent_validate(prompts):
    """Python-level Critic Agent: validates keys and enforces ABSOLUTE WHITE BACKGROUND LOCK."""
    issues = []
    required_keys = ["scene_id", "scene_name", "subject", "action", "environment", "composition", "branding_instruction", "ai_prompt"]
    for scene in prompts:
        if not isinstance(scene, dict): continue
        sid = scene.get("scene_id", "scene_?")
        
        # AUTO-REPAIR MISSING KEYS
        if "scene_name" not in scene:
            scene["scene_name"] = sid.replace("_", " ").title()
        if "subject" not in scene:
            scene["subject"] = "Data Visualization"
        if "action" not in scene:
            scene["action"] = "Highlighting metrics"
        if "composition" not in scene:
            scene["composition"] = "clean standalone visualization"
        if "branding_instruction" not in scene:
            scene["branding_instruction"] = "exact logo from reference-pic/download.jpg applied as fixed UI overlay"
        
        # ABSOLUTE WHITE BACKGROUND LOCK FOR EVERY SCENE
        scene["environment"] = "Solid Clean White background (#FFFFFF)"
        
        ai_prompt = scene.get("ai_prompt", "").strip()
        subject = str(scene.get("subject", "")).strip().upper()
        context_trace = scene.get("context_trace", [])
        prompt_type = scene.get("prompt_type", "")
        
        # DUPLICATE HEADING PROTECTION
        ai_prompt = re.sub(r"(?i)^Heading Text: '.*?'\.\s*", "", ai_prompt)
        ai_prompt = re.sub(r"(?i)^HEADING: '.*?'\.\s*", "", ai_prompt)
        
        # REINFORCED STAGE 9 WHITE LOCK
        full_prompt = (
            f"HEADING: '{subject}'. {ai_prompt}. "
            f"MANDATORY BACKGROUND: Solid Clean White background (#FFFFFF) ONLY. Monochromatic solid fill. "
            f"TEXT PADDING: Ensure all text has large margins (15%), centering, no overflow. "
            f"exact logo from reference-pic/download.jpg at top-right (12% width, 2% margin). "
            f"--no blue --no navy --no gray --no slate --no texture --no doubling --no blur --no distortion --no typos --no text-overflow"
        )
        scene["ai_prompt"] = full_prompt
        
        if prompt_type != "QUALITATIVE" and sid not in ("logo_start", "logo_end"):
            if not re.search(r"\(Page \d+\)", ai_prompt):
                issues.append(f"CRITIC FAIL [{sid}]: Missing '(Page X)'")
    return prompts

def process_image_prompt_generation(latest_output_folder, api_key, service_account_path=None):
    scenes_path = os.path.join(latest_output_folder, "scene.json")
    if not os.path.exists(scenes_path): return None, "scene.json missing."
    rag_output_path = os.path.join(latest_output_folder, "rag_output.json")
    if not os.path.exists(rag_output_path):
        return None, "ERROR: rag_output.json not found."
    prompts, msg = run_image_prompt_generation(scenes_path, rag_output_path, api_key, service_account_path)
    if not prompts: return None, msg
    issues = _critic_agent_validate(prompts)
    save_path = os.path.join(latest_output_folder, "image_prompts.json")
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)
    generate_prompt_audit_html(prompts, latest_output_folder)
    return latest_output_folder, msg
