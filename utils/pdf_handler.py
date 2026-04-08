import os
import re
import time
import json
import fitz  # PyMuPDF

def parse_page_range(range_str, total_pages):
    return [p.strip() for p in range_str.split(',') if p.strip()]

def extract_pages(input_pdf, output_pdf, requested_labels):
    """
    EXTRACTS PAGES USING PHYSICAL INDEXING (1-BASED).
    Example: '1-2' extracts actual physical page 1 and 2.
    """
    if not os.path.exists(input_pdf):
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")
    
    shadow_pdf = output_pdf + ".tmp"
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()
    
    indices_to_extract = set()
    label_map = {} # { physical_idx: label_string }
    
    # 2. RESOLVE MAPPING (PHYSICAL ONLY)
    for req in requested_labels:
        req = req.strip()
        if '-' in req:
            try:
                start_l, end_l = [s.strip() for s in req.split('-')]
                s_i, e_i = int(start_l) - 1, int(end_l) - 1
                for i in range(max(0, min(s_i, e_i)), min(len(doc), max(s_i, e_i) + 1)):
                    indices_to_extract.add(i)
                    label_map[i] = str(i + 1)
            except: continue
        else:
            try:
                idx = int(req) - 1
                if 0 <= idx < len(doc): 
                    indices_to_extract.add(idx)
                    label_map[idx] = str(idx + 1)
            except: continue

    sorted_indices = sorted(list(indices_to_extract))
    
    # 3. SAVE THE PDF
    try:
        for idx in sorted_indices:
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)
        new_doc.save(shadow_pdf)
        new_doc.close()
        doc.close()
        
        # Overwrite logic
        if os.path.exists(output_pdf): os.remove(output_pdf)
        os.rename(shadow_pdf, output_pdf)
        
        # 4. SAVE THE PERMANENT SIDECAR LABELS
        final_labels = [label_map.get(idx, str(idx+1)) for idx in sorted_indices]
            
        sidecar_path = output_pdf.replace(".pdf", "_labels.json")
        with open(sidecar_path, 'w', encoding='utf-8') as f:
            json.dump(final_labels, f)

    except Exception as e:
        if os.path.exists(shadow_pdf): os.remove(shadow_pdf)
        raise e
        
    return output_pdf
