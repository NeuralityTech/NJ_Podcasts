import os
import json
import re

def split_sentences(text):
    # Basic sentence splitter using regex
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def process_chunking(latest_output_folder, pages_data=None):
    """
    DOCUMENT CHUNKING (TAB 5 STRICT) from prompt4.txt
    """
    if pages_data:
        pages = pages_data
    else:
        pre_path = os.path.join(latest_output_folder, "cleaned_pages.json")
        if not os.path.exists(pre_path): return None, "cleaned_pages.json missing."
        try:
            with open(pre_path, 'r', encoding='utf-8') as f:
                pages = json.load(f)
        except Exception as e: return None, f"JSON Error: {str(e)}"

    all_chunks = []
    
    for page_data in pages:
        text = page_data.get("text", "")
        p_val = page_data.get("page", "?")
        
        sentences = split_sentences(text)
        if not sentences: continue
        
        chunks_this_page = []
        current_chunk_sentences = []
        
        # SLIDING WINDOW LOGIC
        for i, s in enumerate(sentences):
            current_chunk_sentences.append(s)
            
            # Grouping Logic: 2-5 sentences OR max tokens (approx 500)
            token_est = sum(len(sen.split()) * 1.3 for sen in current_chunk_sentences)
            
            # TRIGGER NEW CHUNK
            should_split = False
            if len(current_chunk_sentences) >= 5: should_split = True
            if token_est >= 400: should_split = True
            
            if should_split or i == len(sentences) - 1:
                chunk_text = " ".join(current_chunk_sentences)
                chunks_this_page.append(chunk_text)
                
                # SLIDING WINDOW: Overlap last sentence for next chunk
                if i < len(sentences) - 1:
                    current_chunk_sentences = [current_chunk_sentences[-1]]
                else:
                    current_chunk_sentences = []

        # Convert to final structure
        for idx, content in enumerate(chunks_this_page):
            header = content.split(".")[0][:60] if content else "General"
            all_chunks.append({
                "page": f"Page {p_val}", # MUST BE "Page X" for Step 6
                "content": content,
                "metadata": {
                    "section": header,
                    "logical_label": p_val
                }
            })

    output_path = os.path.join(latest_output_folder, "chunks.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
        
    return output_path, f"Created {len(all_chunks)} chunks with sliding window overlap."
