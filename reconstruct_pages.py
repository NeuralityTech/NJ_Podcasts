import json
import os
import sys
import traceback
from PIL import Image, ImageDraw, ImageFont

def reconstruct(json_path, page_list=None, output_dir=None):
    """
    Robust Hifi Page Reconstruction.
    Improved Asset Search & Error Logging.
    """
    print(f"[RECON] Processing: {os.path.basename(json_path)}")
    if not os.path.exists(json_path):
        print(f"[ERROR] JSON not found: {json_path}")
        return

    json_dir = os.path.dirname(json_path)
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read JSON: {e}")
        return

    pages = data.get("pdf_info", [])
    if not pages:
        print("[ERROR] No pdf_info block in JSON.")
        return
    
    target_output_dir = output_dir or r"E:\mineru_new\output\reconstructed_pages"
    os.makedirs(target_output_dir, exist_ok=True)

    SCALE = 2
    
    # Font setup
    font_candidates = [r"C:\Windows\Fonts\arial.ttf", "arial.ttf", r"C:\Windows\Fonts\times.ttf", r"C:\Windows\Fonts\msgothic.ttc"]
    fonts = {
        "sans": next((p for p in [r"C:\Windows\Fonts\arial.ttf", "arial.ttf"] if os.path.exists(p)), None),
        "serif": next((p for p in [r"C:\Windows\Fonts\times.ttf", "times.ttf"] if os.path.exists(p)), None)
    }

    for page in pages:
        page_idx = page.get("page_idx", 0)
        p_num = page_idx + 1
        if page_list and p_num not in page_list: continue

        canvas_size = page.get("page_size", [1200, 1600])
        width, height = canvas_size
        
        all_elements = []
        seen_assets = set()

        # Phase 1: Exhaustive Asset Extraction (Images, Tables, Figures, Equations)
        asset_keys = ["image_blocks", "figure_blocks", "table_blocks", "equation_blocks"]
        for key in asset_keys:
            blocks = page.get(key, [])
            for b in blocks:
                bbox = b.get("bbox")
                img_path = b.get("image_path")
                if not bbox: continue
                
                if img_path:
                    # HEAVY SEARCH LOGIC for images
                    # 1. Direct path from JSON
                    # 2. Relative to JSON folder
                    # 3. Specifically in images/ or tables/ subfolders
                    # 4. Same pattern but relative to JSON directory's parent
                    img_name = os.path.basename(img_path)
                    candidates = [
                        img_path, # Absolute or literal relative
                        os.path.abspath(os.path.join(json_dir, img_path)),
                        os.path.abspath(os.path.join(json_dir, "images", img_name)),
                        os.path.abspath(os.path.join(json_dir, "tables", img_name)),
                        os.path.abspath(os.path.join(os.path.dirname(json_dir), img_path)),
                        os.path.abspath(os.path.join(os.path.dirname(json_dir), "images", img_name)),
                        os.path.abspath(os.path.join(os.path.dirname(json_dir), "tables", img_name))
                    ]
                    
                    found_asset = False
                    for c_path in candidates:
                        if os.path.exists(c_path):
                            all_elements.append({"type": "image", "path": c_path, "bbox": bbox})
                            seen_assets.add(tuple(round(v, 2) for v in bbox))
                            found_asset = True
                            break
                    if not found_asset:
                        print(f"[WARN] Image not found for: {img_path} (Page {p_num})")

        # Phase 2: Text Extraction (Avoiding Asset Overlap)
        text_keys = ["para_blocks", "title_blocks", "footnote_blocks", "header_blocks", "footer_blocks"]
        for key in text_keys:
            for b in page.get(key, []):
                bbox = b.get("bbox")
                if not bbox: continue
                if tuple(round(v, 2) for v in bbox) in seen_assets: continue
                
                # Title uses Serif, others Sans
                f_type = "serif" if key == "title_blocks" else "sans"
                
                if "lines" in b:
                    for line in b["lines"]:
                        for span in line.get("spans", []):
                            s_bbox = span.get("bbox")
                            if s_bbox:
                                all_elements.append({
                                    "type": "text", "content": span.get("content", ""),
                                    "bbox": s_bbox, "size": span.get("size", 12),
                                    "font": fonts[f_type] or fonts["sans"]
                                })
                elif b.get("content"):
                    all_elements.append({
                        "type": "text", "content": b["content"], 
                        "bbox": bbox, "size": b.get("size", 12),
                        "font": fonts[f_type] or fonts["sans"]
                    })

        if not all_elements: continue

        # Dynamic Dimensions Calculation
        max_x, max_y = width, height
        try:
            temp_img = Image.new("RGB", (1, 1))
            td = ImageDraw.Draw(temp_img)
            for el in all_elements:
                b = el["bbox"]
                if el["type"] == "text":
                    try:
                        f = ImageFont.truetype(el["font"], int(el["size"] * SCALE)) if el["font"] else ImageFont.load_default()
                        rw = td.textlength(el["content"], font=f) / SCALE
                        max_x = max(max_x, b[0] + rw)
                    except: max_x = max(max_x, b[2])
                else: max_x = max(max_x, b[2])
                max_y = max(max_y, b[3])
        except: pass

        # Canvas Creation
        f_w, f_h = int((max_x + 100) * SCALE), int((max_y + 100) * SCALE)
        canvas = Image.new("RGB", (f_w, f_h), "white")
        draw = ImageDraw.Draw(canvas)

        # Rendering Order: Images Bottom -> Text Top
        all_elements.sort(key=lambda x: (1 if x["type"] == "text" else 0, x["bbox"][1], x["bbox"][0]))

        for el in all_elements:
            bx = el["bbox"]
            x1, y1, x2, y2 = [int(v * SCALE) for v in bx]
            bw, bh = x2 - x1, y2 - y1
            
            if el["type"] == "text":
                txt = el["content"].strip()
                if not txt: continue
                # Hifi Font Size
                fs = int(el["size"] * SCALE)
                if bh > 0: fs = min(fs, int(bh * 1.5)) # Natural height ceiling
                
                try:
                    f = ImageFont.truetype(el["font"], fs) if el["font"] else ImageFont.load_default()
                    draw.text((x1, y1), txt, fill="black", font=f)
                except:
                    draw.text((x1, y1), txt, fill="black", font=ImageFont.load_default())
            
            elif el["type"] == "image":
                try:
                    with Image.open(el["path"]) as img:
                        if bw > 0 and bh > 0:
                            ri = img.resize((bw, bh), Image.Resampling.LANCZOS)
                            if ri.mode in ('RGBA', 'LA') or (ri.mode == 'P' and 'transparency' in img.info):
                                canvas.paste(ri, (x1, y1), ri.convert('RGBA'))
                            else:
                                canvas.paste(ri, (x1, y1))
                except Exception as ex:
                    print(f"[ERROR] Failed to render image at {el['path']}: {ex}")

        out_path = os.path.join(target_output_dir, f"clean_page_{p_num}.png")
        canvas.save(out_path)
        print(f"[RECON] Success: Page {p_num} -> {out_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1: reconstruct(sys.argv[1])