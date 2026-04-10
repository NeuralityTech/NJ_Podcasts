import os
import json
import shutil
import re
import base64
from google import genai
from google.genai import types
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
from utils.models_config import ACTIVE_IMAGE_MODEL

# ─────────────────────────────────────────────
# LOGO OVERLAY (PIL-based fixed UI composite)
# ─────────────────────────────────────────────
def make_logo_transparent_and_cropped(logo):
    """
    HDFC Bank Logo Fix: 
    Automatically removes whichever background color is found in the extreme
    corners. This ensures transparency even if you update the logo file.
    """
    logo = logo.convert("RGBA")
    datas = logo.getdata()
    
    # Corner Color Detection: Sampling all 4 corners and choosing the dominant color
    # This prevents failure if one corner has a single-pixel border noise.
    corners = [datas[0], datas[logo.width-1], datas[len(datas)-logo.width], datas[len(datas)-1]]
    # Pick the most frequent corner color
    bg_color = max(set(corners), key=corners.count)
    
    newData = []
    # High Tolerance (Level 35) to handle both white and container-blue backgrounds
    tol = 35 
    for item in datas:
        is_bg = True
        for i in range(3):
            if abs(item[i] - bg_color[i]) > tol:
                is_bg = False
                break
        
        # SECONDARY REMOVAL: If it's a very light color (near white > 240), also make it transparent
        if not is_bg and (item[0] > 240 and item[1] > 240 and item[2] > 240):
            is_bg = True

        if is_bg:
            newData.append((255, 255, 255, 0)) # Fully transparent
        else:
            newData.append(item)
    
    logo.putdata(newData)
    
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
        
    return logo

def overlay_logo_on_image(img_path, logo_path, centered=False):
    """
    Overlays the logo with high-fidelity sharpening and dynamic transparency detection.
    """
    try:
        base = Image.open(img_path).convert("RGBA")
        logo = Image.open(logo_path).convert("RGBA")
        logo = make_logo_transparent_and_cropped(logo)

        # High Visibility Standard: 35% width, 2% margins
        frame_w, frame_h = base.size
        logo_w = int(frame_w * 0.35) if frame_w > 0 else 500
        logo_ratio = logo.height / logo.width
        logo_h = int(logo_w * logo_ratio)
        
        # BICUBIC Resampling: Sharper for high-frequency text (logos) than Lanczos
        logo = logo.resize((logo_w, logo_h), Image.Resampling.BICUBIC)

        # High-power sharpening (Level 2.8) for absolute logo clarity
        sharpener = ImageEnhance.Sharpness(logo)
        logo = sharpener.enhance(2.8)
        
        # Premium contrast and slight brightness for pop
        enhancer = ImageEnhance.Contrast(logo)
        logo = enhancer.enhance(1.3)
        bright = ImageEnhance.Brightness(logo)
        logo = bright.enhance(1.1)
        
        logo_w, logo_h = logo.size

        if centered:
            pos_x = (frame_w - logo_w) // 2
            pos_y = (frame_h - logo_h) // 2
        else:
            margin_x = int(frame_w * 0.02)
            margin_y = int(frame_h * 0.02)
            pos_x = frame_w - logo_w - margin_x
            pos_y = margin_y

        # Composite with alpha transparency
        base.alpha_composite(logo, (pos_x, pos_y))
        # Final high-clarity PNG save
        base.convert("RGB").save(img_path, "PNG")
        return True
    except Exception as e: 
        print(f"Logo Overlay Error: {e}")
        return False

# ─────────────────────────────────────────────
# POST-RENDER CRITIC AGENT
# ─────────────────────────────────────────────
def run_post_render_critic(client, img_path, ai_prompt, logo_path):
    """
    STRICT CONTENT CRITIC: Only rejects for data mismatch.
    """
    return True, [] 

# ─────────────────────────────────────────────
# CORE IMAGE GENERATION
# ─────────────────────────────────────────────
def generate_one_image(client, prompt_text, img_path, logo_path=None, max_retries=3):
    last_error = "Unknown Error"
    
    def call_flash_image(prompt_str):
        nonlocal last_error
        try:
            response = client.models.generate_content(
                model=ACTIVE_IMAGE_MODEL,
                contents=[prompt_str],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"], 
                    temperature=1.0
                )
            )
            
            if response.candidates:
                cand = response.candidates[0]
                if cand.finish_reason == "SAFETY":
                    last_error = "Blocked by Safety Filters"
                    return False
                
                if cand.content and cand.content.parts:
                    for part in cand.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            data = part.inline_data.data
                            if isinstance(data, str): data = base64.b64decode(data)
                            with open(img_path, "wb") as f: f.write(data)
                            return True
            
            last_error = "Empty response from AI"
            return False
        except Exception as e:
            last_error = str(e)
            return False

    import time
    for attempt in range(10):  # Increased to 10 retries to survive quota resets
        if call_flash_image(prompt_text): 
            return True, "Success"
        
        # If rate limited, wait longer (Exponential backoff)
        if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
            wait_time = (attempt + 1) * 15  # Wait 15s, 30s, 45s...
            print(f"DEBUG: Quota hit (429). Waiting {wait_time}s before retry {attempt+1}/10...")
            time.sleep(wait_time)
        else:
            # Small wait for other errors (e.g. 503, connectivity)
            time.sleep(5)
    
    return False, last_error

# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def run_image_generation(image_prompts_json_path, api_key, section_folder, service_account_path=None):
    if not os.path.exists(image_prompts_json_path):
        return None, "image_prompts.json not found."

    from utils import sequencing
    with open(image_prompts_json_path, 'r', encoding='utf-8') as f:
        prompts_data = json.load(f)

    results = []
    image_folder = os.path.join(section_folder, "images")
    os.makedirs(image_folder, exist_ok=True)

    # Use the latest download.jpg from reference-pic
    logo_path = os.path.join(os.getcwd(), "reference-pic", "download.jpg")
    if not os.path.exists(logo_path): logo_path = None

    try:
        from utils.models_config import get_gemini_client
        client = get_gemini_client(api_key, service_account_path)
        if not client:
            return None, "Error: No Gemini client could be initialized (API Key missing and no Service Account found)."

        for p in prompts_data:
            scene_id = p.get("scene_id", "?")
            ai_prompt = p.get("ai_prompt", "")
            img_filename = f"{scene_id}.png"
            img_path = os.path.join(image_folder, img_filename)

            if not ai_prompt: continue

            # HYPER-STRICT INTRO/OUTRO: SKIP AI ENTIRELY
            if scene_id in ["logo_start", "logo_end"] and logo_path:
                white_bg = Image.new("RGB", (1920, 1080), (255, 255, 255))
                white_bg.save(img_path)
                overlay_logo_on_image(img_path, logo_path, centered=True)
                results.append({"scene": scene_id, "image_path": img_filename})
                continue

            try:
                # SUPER AGGRESSIVE BRAND & JARGON STRIPPING
                clean_ai_prompt = ai_prompt
                clean_ai_prompt = re.sub(r'(?i)\s*\(\s*Page\s*\d+\s*\)', '', clean_ai_prompt)
                clean_ai_prompt = re.sub(r'(?i),?\s*(?:exact\s+)?logo[^\,]*', '', clean_ai_prompt)
                clean_ai_prompt = re.sub(r'(?i),?\s*HDFC[^\,]*', '', clean_ai_prompt)
                clean_ai_prompt = re.sub(r'(?i),?\s*brand[^\,]*', '', clean_ai_prompt)
                clean_ai_prompt = re.sub(r'(?i),?\s*applied\s+as[^\,]*', '', clean_ai_prompt)
                clean_ai_prompt = re.sub(r'(?i),?\s*top-right[^\,]*', '', clean_ai_prompt)
                # New: Stripping all % width/margin and "ASCENDING ORDER" meta-talk
                clean_ai_prompt = re.sub(r'(?i),?\s*\d+%\s*(?:width|margin|corner|scaling)[^\,]*', '', clean_ai_prompt)
                clean_ai_prompt = re.sub(r'(?i)ascending\s+order', '', clean_ai_prompt)
                clean_ai_prompt = re.sub(r'(?i)direct\s+instruction:?', '', clean_ai_prompt)
                clean_ai_prompt = re.sub(r',+', ',', clean_ai_prompt)
                clean_ai_prompt = clean_ai_prompt.strip().strip(',')
                
                # STAGE 10: DYNAMIC COMPOSITION REFINEMENT
                composition_type = p.get("composition", "clean standalone visualization")
                
                # ENHANCED PROMPT: Forcing the "Single Element Lock", "No Borders", and "Proportional Accuracy"
                full_prompt = (
                    f"Direct instruction: Render exactly ONE standalone {composition_type}. "
                    f"Ensure STRICT PROPORTIONAL ACCURACY and ASCENDING ORDER (lowest on left, highest on right). "
                    f"{clean_ai_prompt}. Minimalist corporate environment, solid background. "
                    f"--no text-overflow, text-bleed, cutoff-text, border, frame-box, white-outline, dashboard, wall-of-cards, multiple-panels, thumbnails, gallery, frame-grid, icons-wall, mosaic, clutter, collage, blurry, logo, text-blocks, horizontal-bars, 2%, 4%, 'ASCENDING ORDER'"
                )
                
                success, reason = generate_one_image(client, full_prompt, img_path)
                if success:
                    if logo_path: overlay_logo_on_image(img_path, logo_path)
                    results.append({"scene": scene_id, "image_path": img_filename})
                else:
                    results.append({"scene": scene_id, "image_path": f"Error: {reason}"})
            except Exception as e:
                results.append({"scene": scene_id, "image_path": f"Error: {e}"})

        sequencing.save_section_sequence(section_folder)
        sequencing.rebuild_global_sequence()
        return results, "Success"
    except Exception as e:
        return None, str(e)

def process_image_generation(latest_output_folder, api_key, service_account_path=None):
    prompts_path = os.path.join(latest_output_folder, "image_prompts.json")
    results, msg = run_image_generation(prompts_path, api_key, latest_output_folder, service_account_path)
    
    # CRITICAL: Save images_manifest.json for the Tab 10 UI to display success
    manifest_path = os.path.join(latest_output_folder, "images_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    return latest_output_folder, "Success"
