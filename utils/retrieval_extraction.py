import os
import json
import re
from google import genai # USING THE LATEST SDK (google-genai)
from google.genai import types
from utils.pdf_handler import get_pdf_page_index

from utils.models_config import ACTIVE_TEXT_MODEL, get_gemini_client

def clean_json_response(text):
    if not text: return ""
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```', '', text)
    text = text.strip()
    idx1 = text.find('[')
    idx2 = text.rfind(']')
    if idx1 != -1 and idx2 != -1:
        return text[idx1 : idx2 + 1]
    return text

def run_gemini_extraction(all_chunks, questions, api_key):
    try:
        client = get_gemini_client(api_key)
        if not client:
            return None, "Error: No Gemini client could be initialized (API Key missing and no Service Account found)."
        
        # ASSEMBLE CONTEXT
        context_parts = []
        for c in all_chunks:
            p = str(c.get('page', '?'))
            content = c.get('content', '')
            header = p if p.lower().startswith("page") else f"Page {p}"
            context_parts.append(f"[{header}]\n{content}\n")
        
        full_context = "\n".join(context_parts)
        
        # We'll batch to avoid token limits if many questions
        batch_size = 3
        all_final_data = []
        
        for i in range(0, len(questions), batch_size):
            batch = questions[i:i + batch_size]
            questions_block = "\n".join([f"- {q}" for q in batch])
            
            prompt = f"""TAB 6: CONTEXT-BASED QUESTION ANSWERING (AUDIT-GRADE RAG SYSTEM)

You are an expert DOCUMENT QUESTION ANSWERING SYSTEM designed for HIGH-ACCURACY, AUDITABLE RAG OUTPUT.
STRICTLY bound to the provided PDF context. ZERO hallucination with FULL traceability.

INPUTS:
DOCUMENT CONTEXT:
{full_context}

USER QUESTIONS:
{questions_block}

DOCUMENT NAME: custom_pages
PDF BASE URL: http://localhost:8000/static/pdfs

========================================================
STAGE 1: ANSWER GENERATION (DIRECT FROM CONTEXT)
========================================================
Using ONLY DOCUMENT CONTEXT:
- EXHAUSTIVE SEARCH RULE: You MUST search every single provided chunk. If a question mentions 'FY25' or 'Deposits', you MUST find the exact numeric data. DO NOT say 'not available' if any chunk contains related keywords.
- TRUTH SOURCE ONLY: Answer ONLY using the provided chunks.
- PIN-POINT ACCURACY: For every answer, provide the Page number and the specific Snippet used as a reference.
- IF NOT FOUND, return "Not available in document" (do not guess)

SEARCH DILIGENTLY. DO NOT SKIP ANY QUESTION. Answer every single question asked.

CRITICAL DATA TRACEABILITY RULE:
1. Value MUST match PDF EXACTLY.
2. SINGLE PAGE ONLY: Return exactly one page reference (e.g. Page 11).
3. NO RANGES: Never return "Page 11-12". Select only the most relevant page.
4. SNIPPET CONSISTENCY: Snippet and page number MUST match.

========================================================
STAGE 2: POST-CRITIC AGENT (STRICT VALIDATION)
========================================================
After generating the answer, you MUST perform STRICT VALIDATION:
1. PAGE VALIDATION: Referenced Page X MUST contain the answer.
2. SNIPPET VALIDATION: Snippet MUST be exact substring and contain the answer.
3. NUMERIC VALIDATION: NO rounding, NO conversion (1.2 -> 90% is FORBIDDEN).
4. PAGE CONSISTENCY: Answer and snippet MUST belong to SAME page.
5. LINK VALIDATION: Ensure URL followed correctly.

IF ANY VALIDATION FAILS, REJOIN AND REGENERATE.

FINAL OUTPUT FORMAT (STRICT JSON ONLY):
[
  {{
    "question": "string",
    "answer": "string",
    "references": [
      {{
        "page": "Page X",
        "snippet": "exact line from PDF"
      }}
    ]
  }}
]
"""
            
            response = client.models.generate_content(
                model=ACTIVE_TEXT_MODEL, 
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    top_k=1,
                    top_p=0.1
                )
            )
            
            if response.text:
                j_str = clean_json_response(response.text)
                try:
                    data = json.loads(j_str)
                    if isinstance(data, list):
                        all_final_data.extend(data)
                    else:
                         for q in batch: all_final_data.append({"question": q, "answer": "Format error: Response was not a list", "references": []})
                except Exception as ex:
                    print(f"RAG JSON Parsing Error on batch: {ex}")
                    print(f"Raw Output: {response.text}")
                    for q in batch: all_final_data.append({"question": q, "answer": f"Processing error: Unable to parse RAG json. Check terminal.", "references": []})
            else:
                for q in batch: all_final_data.append({"question": q, "answer": "Model failed to provide any output.", "references": []})

        return all_final_data, "Success"
    except Exception as e: return None, f"Global Error: {str(e)}"

def process_retrieval_extraction(latest_output_folder, questions, api_key):
    chunks_path = os.path.join(latest_output_folder, "chunks.json")
    if not os.path.exists(chunks_path): return None, "chunks.json missing."
    
    try:
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        # Diagnostic: Count unique pages in context
        pages_in_context = sorted(list(set([c.get('page', '?') for c in chunks])))
        msg_diag = f"SUCCESS: RAG Context Loaded ({len(chunks)} chunks across {len(pages_in_context)} pages: {', '.join(pages_in_context)})"
        
        result_json, ai_msg = run_gemini_extraction(chunks, questions, api_key)
        if not result_json: return None, ai_msg
        
        # Final result path mapping
        latest_output_folder = latest_output_folder # Keep reference
        msg = msg_diag
            
        output_path = os.path.join(latest_output_folder, "rag_output.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)
            
        # STAGE 3: HTML AUDIT FILE GENERATION (ALIGN WITH prompt4.txt TEMPLATE)
        html_cards = []
        
        # UPGRADE: Force absolute 'file:///' path for 100% reliable local browsing
        import pathlib
        # Always find the root output/ folder relative to CWD
        root_dir = os.getcwd()
        pdf_abs_path = os.path.abspath(os.path.join(root_dir, "output", "custom_pages.pdf"))
        # Standard file:/// format for local browsing
        pdf_base_url = pathlib.Path(pdf_abs_path).as_uri()

        for qa in result_json:
            q = qa.get("question", "")
            a = qa.get("answer", "")
            refs = qa.get("references", [])
            
            ref_html = ""
            for ref in refs:
                p_label_raw = ref.get("page", "1")
                # Clean "Page Page 5" duplication
                p_label = str(p_label_raw).strip()
                if p_label.lower().startswith("page "):
                     p_label = p_label[5:].strip()
                
                snip = ref.get("snippet", "")
                
                # RECALIBRATION: Map original page label to physical index in custom_pages.pdf
                physical_idx = get_pdf_page_index(p_label)
                
                snip_escaped = str(snip).replace('<', '&lt;').replace('>', '&gt;')
                # ENHANCED: Absolute URI with mandatory page anchor (added view=FitH for better browser compatibility)
                full_pdf_link = f"{pdf_base_url}#page={physical_idx}&view=FitH,0"
                ref_html += f'''
  <div class="reference" style="border-bottom: 2px solid #3498db; margin-bottom: 15px; padding-bottom: 5px;">
    <span style="font-weight: bold; font-size: 16px; color: #d35400;">→ GROUND TRUTH SOURCE: Page {p_label}</span> |
    <a class="link" href="{full_pdf_link}" target="_blank" style="font-weight: bold; background: #ffeb3b; padding: 2px 6px; border-radius: 4px; text-decoration: none; color: #000;">OPEN SOURCE PDF (Jump to Page {physical_idx})</a>
    <div class="snippet" style="margin-top: 10px; border: 1px dashed #7f8c8d; padding: 10px; background: white; white-space: pre-wrap;">{snip_escaped}</div>
  </div>'''

            q_esc = str(q).replace('<', '&lt;').replace('>', '&gt;')
            a_esc = str(a).replace('<', '&lt;').replace('>', '&gt;')
            
            html_cards.append(f'''
<div class="card">
  <div class="question">Q: {q_esc}</div>
  <div class="answer">A: {a_esc}</div>
  {ref_html}
</div>''')

        html_content = f'''<!DOCTYPE html>
<html>
<head>
  <title>RAG Audit Viewer</title>
  <style>
    body {{ font-family: Arial; padding: 20px; background: #f4f6f8; }}
    .card {{ background: #ffffff; padding: 16px; margin-bottom: 16px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .question {{ font-weight: bold; font-size: 18px; color: #2c3e50; }}
    .answer {{ margin-top: 8px; color: #34495e; font-size: 15px; }}
    .reference {{ margin-top: 10px; font-size: 14px; padding: 8px; background: #f9f9f9; border-left: 4px solid #3498db; }}
    .link {{ color: #2980b9; text-decoration: underline; cursor: pointer; }}
    .snippet {{ margin-top: 5px; font-style: italic; color: #7f8c8d; }}
  </style>
</head>
<body>
  <h2>Document QA Audit</h2>
  {''.join(html_cards)}
</body>
</html>'''

        audit_path = os.path.join(latest_output_folder, "rag_audit.html")
        with open(audit_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return latest_output_folder, msg
    except Exception as e: return None, f"Error: {str(e)}"
