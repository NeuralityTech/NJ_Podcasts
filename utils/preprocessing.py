import os
import json
import re

def clean_text(text):
    if not text: return ""
    text = re.sub(r'\\+([%$&_#{}])', r'\1', text)
    text = re.sub(r'\\\s+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def table_to_text(table_data):
    """
    CONVERTS TABLE TO NATURAL LANGUAGE (STRICT TAB 4 RULES)
    """
    rows = table_data.get("table_body", [])
    if not rows: return ""
    
    # COUNT TOTAL CELLS
    total_cells = sum(len(row) for row in rows)
    if total_cells >= 100:
        return "" # LARGE TABLES (cells >= 100): COMPLETELY IGNORE
        
    headers = [str(cell.get("text", cell.get("content", ""))).strip() for cell in rows[0]]
    if not any(headers): headers = [f"Column {i+1}" for i in range(len(rows[0]))]
    
    row_sentences = []
    # Identify a potential subject column (e.g., Year, Name, Product)
    subject_idx = -1
    for i, h in enumerate(headers):
        if any(keyword in h.lower() for keyword in ["year", "name", "product", "item", "category", "date"]):
            subject_idx = i
            break

    for row in rows[1:]:
        pairs = []
        subject_val = ""
        if subject_idx != -1 and subject_idx < len(row):
            subject_val = str(row[subject_idx].get("text", row[subject_idx].get("content", ""))).strip()

        for i, cell in enumerate(row):
            if i == subject_idx: continue # Skip subject column as we use it as the anchor
            h = headers[i] if i < len(headers) else f"Column {i+1}"
            v = str(cell.get("text", cell.get("content", ""))).strip()
            if v:
                pairs.append(f"{h} is {v}")
        
        if pairs:
            if subject_val:
                sentence = f"For {headers[subject_idx]} {subject_val}, " + ", ".join(pairs[:-1]) + (f" and {pairs[-1]}." if len(pairs) > 1 else f"{pairs[-1]}.")
            else:
                sentence = ", ".join(pairs[:-1]) + (f" and {pairs[-1]}." if len(pairs) > 1 else f"{pairs[-1]}.")
            row_sentences.append(sentence)
            
    return " ".join(row_sentences)

def process_preprocessing(latest_output_folder, ui_selected_labels=None):
    """
    Normalizes MinerU output (TAB 4 STRICT).
    Input: *_middle.json
    """
    middle_json_path = None
    for f in os.listdir(latest_output_folder):
        if f.endswith("_middle.json"):
            middle_json_path = os.path.join(latest_output_folder, f)
            break
            
    if not middle_json_path: return None, "Error: _middle.json not found."

    try:
        with open(middle_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e: return None, f"JSON Error: {str(e)}"

    # PINNED LABEL DETECTION
    pinned_labels = []
    output_dir = os.path.dirname(latest_output_folder)
    sidecar_candidate = os.path.join(output_dir, "custom_pages_labels.json")
    
    if os.path.exists(sidecar_candidate):
        try:
             with open(sidecar_candidate, 'r') as f:
                 pinned_labels = json.load(f)
        except: pass
        
    master_labels = pinned_labels if pinned_labels else (ui_selected_labels if ui_selected_labels else [])

    pages_list = data.get("pdf_info", [])
    cleaned_pages_data = []

    for idx, page_data in enumerate(pages_list):
        if master_labels and idx < len(master_labels):
            p_val = str(master_labels[idx])
        else:
            p_val = str(page_data.get("page_no", idx + 1))
            
        page_text_parts = []
        blocks = page_data.get("preproc_blocks", [])
        
        for block in blocks:
            b_t = block.get("type", "").lower()
            # DROP IMAGES / FORMULAS (MANDATORY)
            if any(x in b_t for x in ["image", "figure", "formula"]): continue
            
            if "table" in b_t: 
                tbl_text = table_to_text(block)
                if tbl_text: page_text_parts.append(tbl_text)
                continue
            
            lines = block.get("lines", [])
            block_content = " ".join([" ".join([str(s.get("content", s.get("text", ""))) for s in l.get("spans", [])]) for l in lines]) if lines else block.get("text", "")
            if block_content and str(block_content).strip():
                page_text_parts.append(str(block_content))

        full_text = clean_text(" ".join(page_text_parts))
        if full_text:
            cleaned_pages_data.append({
                "page": p_val,
                "text": full_text,
                "tokens": int(len(full_text.split()) * 1.3) # TOKEN COUNT (UI ONLY)
            })

    return cleaned_pages_data, f"Normalized {len(cleaned_pages_data)} pages."
