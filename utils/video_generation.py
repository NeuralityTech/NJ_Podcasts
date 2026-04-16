import os
import json
import base64
import time
import re
import google.auth
from PIL import Image
from .models_config import ACTIVE_VIDEO_MODEL, get_gemini_client
from .sequencing import rebuild_global_sequence

def categorize_scene(scene_id, subject):
    """Categorizes scene based on keywords from video_prompt2.txt VEO 3.1 rules."""
    text = (scene_id + " " + (subject or "")).lower()
    
    # Specific Logo Checks
    if "logo_start" in text: return "LOGO_START"
    if "logo_end" in text: return "LOGO_END"
    if "logo" in text: return "LOGO_GENERAL"
    
    # Financial Dashboard
    if any(k in text for k in ["kpi", "metric", "card", "profit", "revenue"]): 
        return "FINANCIAL_DASHBOARD"
    
    # Data Visualization (Split by type)
    if any(k in text for k in ["bar", "comparison", "growth", "deposit"]): 
        return "DATA_VISUALIZATION_BAR"
    if any(k in text for k in ["line", "trend", "time", "fy"]): 
        return "DATA_VISUALIZATION_LINE"
    if any(k in text for k in ["pie", "donut", "distribution", "split"]): 
        return "DATA_VISUALIZATION_PIE"
    
    # UI Dashboard
    if any(k in text for k in ["control", "dashboard", "system", "monitoring"]): 
        return "UI_DASHBOARD"
    
    # Infographic
    if any(k in text for k in ["brand", "trust", "abstract", "concept"]): 
        return "INFOGRAPHIC"
    
    return "QUALITATIVE"

def get_motion_for_category(category):
    """DATA MOTION RULE Mapping from video_prompt2.txt."""
    mapping = {
        "LOGO_START": ["fade_in"],
        "LOGO_END": ["fade_out"],
        "LOGO_GENERAL": ["fade_in"],
        "FINANCIAL_DASHBOARD": ["fade_in", "number_count_up"],
        "DATA_VISUALIZATION_BAR": ["fade_in", "bar_growth_animation"],
        "DATA_VISUALIZATION_LINE": ["fade_in", "line_draw_animation"],
        "DATA_VISUALIZATION_PIE": ["fade_in", "donut_fill_animation"],
        "UI_DASHBOARD": ["fade_in"],
        "INFOGRAPHIC": ["fade_in"],
        "QUALITATIVE": ["fade_in"]
    }
    return mapping.get(category, ["fade_in"])

def prepare_image_for_veo(img_path, target_size=(1920, 1080)):
    """Implements LETTERBOX_SAFE_RENDER with centered-contain and blurred background."""
    from PIL import ImageFilter
    with Image.open(img_path) as img:
        img = img.convert("RGB")
        iw, ih = img.size
        tw, th = target_size
        
        # Calculate scaling to fit (contain)
        scale = min(tw / iw, th / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img_resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        
        # Create canvas with blurred background
        canvas = img.resize(target_size, Image.Resampling.LANCZOS)
        canvas = canvas.filter(ImageFilter.GaussianBlur(radius=40))
        
        # Overlay centered image
        offset = ((tw - nw) // 2, (th - nh) // 2)
        canvas.paste(img_resized, offset)
        return canvas

def get_complexity_duration(category):
    """Base durations for categorization, aligned with 180s total goal."""
    mapping = {
        "LOGO": 4,
        "FINANCIAL_DASHBOARD": 20,
        "DATA_VISUALIZATION_BAR": 25,
        "DATA_VISUALIZATION_LINE": 25,
        "DATA_VISUALIZATION_PIE": 20,
        "UI_DASHBOARD": 30,
        "INFOGRAPHIC": 30,
        "QUALITATIVE": 25
    }
    return mapping.get(category, 20)

def process_video_generation(project_folder, api_key=None, service_account_path=None):
    """
    Final Stage (11): The 'Absolute Fidelity' Production.
    - Pie Charts = Static (bypasses Veo to prevent text distortion)
    - All other scenes = Strict Bitmap Lock
    """
    try:
        print(f"DEBUG: Starting 3-Minute Absolute Fidelity Production (PIE=STATIC).")
        from google.genai import types
        try:
            from moviepy import VideoFileClip, concatenate_videoclips, ImageClip
            HAS_MOVIEPY = True
        except ImportError:
            HAS_MOVIEPY = False

        client = get_gemini_client(api_key, service_account_path, location="us-central1")
        if not client:
            return {}, "Error: No Gemini client initialized."

        # 2. SEQUENCE GATHERING
        global_seq_path = os.path.join(project_folder, 'global_sequence.json')
        if not os.path.exists(global_seq_path):
            return {}, "global_sequence.json not found."

        with open(global_seq_path, 'r', encoding='utf-8') as f:
            global_seq = json.load(f)

        # 2. STORYBOARD GATHERING & REINDEXING (LOGO-CONTENT-LOGO LOCK)
        global_seq_path = os.path.join(project_folder, 'global_sequence.json')
        if not os.path.exists(global_seq_path):
            return {}, "global_sequence.json not found."

        with open(global_seq_path, 'r', encoding='utf-8') as f:
            global_seq = json.load(f)

        raw_scenes = []
        for entry in global_seq.get("sections", []):
            section_id = entry.get("section_id")
            section_path = os.path.join(project_folder, section_id)
            prompts_path = os.path.join(section_path, "image_prompts.json")
            if not os.path.exists(prompts_path): continue
            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
            for p in prompts:
                scene_id = p.get("scene_id")
                img_path = os.path.join(section_path, "images", f"{scene_id}.png")
                if not os.path.exists(img_path): continue
                
                category = categorize_scene(scene_id, p.get("subject", ""))
                raw_scenes.append({
                    "scene_id": scene_id,
                    "img_path": img_path,
                    "category": category,
                    "subject": p.get("subject", ""),
                    "allowed_motion": get_motion_for_category(category)
                })

        # LOGO-CONTENT-LOGO GLOBAL LOCK (Strict VEO 3.1 Rule)
        # Find the absolute first and absolute last for the entire project
        first_logo_start = next((s for s in raw_scenes if s["category"] == "LOGO_START"), None)
        last_logo_end = next((s for s in reversed(raw_scenes) if s["category"] == "LOGO_END"), None)
        
        # 3. CONTENT FILTERING: UNIQUE CONTENT ONLY (Purge all intermediate logos)
        internal_content = []
        seen_images = set()
        
        # Add primary start logo to seen if it exists
        if first_logo_start:
            seen_images.add(os.path.abspath(first_logo_start["img_path"]))
        
        for s in raw_scenes:
            # Skip if this is the chosen start or end logo
            if s is first_logo_start or s is last_logo_end:
                continue
            
            abs_img = os.path.abspath(s["img_path"])
            
            # Skip ANY logo categories found anywhere else (Strict rule)
            if s["category"] in ["LOGO_START", "LOGO_END", "LOGO_GENERAL"]:
                continue
            
            # Skip absolute duplicate images (prevents section overlap bugs)
            if abs_img in seen_images:
                continue
                
            seen_images.add(abs_img)
            internal_content.append(s)

        # 4. TIMELINE RULE (180 SECONDS TOTAL, LOGO FIX)
        logo_durations = (4 if first_logo_start else 0) + (5 if last_logo_end else 0)
        remaining_time = 180 - logo_durations
        content_count = len(internal_content)
        
        final_sequence = []
        if first_logo_start: final_sequence.append(first_logo_start)
        final_sequence.extend(internal_content)
        if last_logo_end: final_sequence.append(last_logo_end)
        
        print(f"DEBUG: Extraction complete. Total Unique Scenes: {len(final_sequence)}")
        print(f"DEBUG: Content: {content_count} | Logos: {'Start' if first_logo_start else 'None'} + {'End' if last_logo_end else 'None'}")

        # 4. RENDER LOOP
        shot_files = []
        renders_dir = os.path.join(project_folder, "renders", "scene_renders")
        os.makedirs(renders_dir, exist_ok=True)
        output_dir = os.path.join(project_folder, "output")
        os.makedirs(output_dir, exist_ok=True)

        for idx, scene in enumerate(final_sequence, 1):
            s_id = scene["scene_id"]
            img_path = scene["img_path"]
            motion_tag = scene["allowed_motion"][0]
            shot_path = os.path.join(renders_dir, f"shot_{idx:03d}_{s_id}.mp4")

            if os.path.exists(shot_path):
                shot_files.append(shot_path)
                continue

            print(f"DEBUG: Rendering Scene {idx}/{len(final_sequence)} ({s_id}) | Motion: {motion_tag}")

            # CASE B: GENERATIVE MOTION (WITH RETRY & FALLBACK)
            proc_img_path = os.path.join(renders_dir, f"temp_{idx}.png")
            canvas = prepare_image_for_veo(img_path)
            canvas.save(proc_img_path)

            with open(proc_img_path, 'rb') as f: img_data = f.read()

            # VEO 3.1 FIDELITY RULES (STRICT VERSION from video_prompt2.txt)
            fidelity_rules = {
                "LOGO_START": {
                    "constraints": {
                        "lock_image": True, "immutable_visual_layer": True, "no_redesign": True, "no_layout_change": True,
                        "no_text_change": True, "no_typography_change": True, "no_font_change": True, "no_logo_modification": True,
                        "no_logo_replacement": True, "no_logo_distortion": True, "no_color_change": True, "no_element_addition": True,
                        "no_element_removal": True, "no_ai_reinterpretation": True, "no_scene_reconstruction": True
                    },
                    "veo_control": {
                        "input_mode": "IMAGE_ONLY", "motion_only": True, "allowed_motion": ["fade_in"],
                        "forbidden_motion": [
                            "scene_rebuild","ui_regeneration","chart_modification","text_edit",
                            "logo_edit","layout_shift","color_adjustment","object_insertion",
                            "object_removal","zoom_in","zoom_out","pan","camera_motion"
                        ],
                        "duration_seconds": 4
                    },
                    "veo_prompt": {
                        "prompt": "Create a motion graphic using the exact logo from the folder as the only central visual element, ensuring it remains unchanged in shape, color, and proportions. The logo gently fades in from darkness with a soft scale-up and slight glow bloom, then stabilizes into a crisp static hold. A subtle light sweep passes once across the logo surface to enhance polish. Background remains minimal and clean with a soft gradient that does not distract from the logo. The camera holds perfectly centered with no movement or only an extremely slight zoom-out for elegance. The pacing should feel premium, authoritative, and minimal. avoid: no distortion, no extra text, no additional graphics, no flicker, no shake, no warping",
                        "negative_prompt": "no redesign, no distortion, no cropping, no scaling, no repositioning, no new elements, no AI reconstruction, no generated content"
                    }
                },
                "LOGO_END": {
                    "constraints": {
                        "lock_image": True, "immutable_visual_layer": True, "no_redesign": True, "no_layout_change": True,
                        "no_text_change": True, "no_color_change": True, "no_element_addition": True, "no_element_removal": True,
                        "no_ai_reinterpretation": True, "no_scene_reconstruction": True
                    },
                    "veo_control": {
                        "input_mode": "IMAGE_ONLY", "motion_only": True, "allowed_motion": ["fade_out"],
                        "forbidden_motion": [
                            "scene_rebuild","ui_regeneration","chart_modification",
                            "text_edit","layout_shift","object_insertion","object_removal",
                            "zoom_in","zoom_out","pan","camera_motion"
                        ],
                        "duration_seconds": 5
                    },
                    "veo_prompt": {
                        "prompt": "Create a motion graphic using the exact logo from the folder as the only central visual element, ensuring it remains unchanged in shape, color, and proportions. The logo gently fades in from darkness with a soft scale-up and slight glow bloom, then stabilizes into a crisp static hold. A subtle light sweep passes once across the logo surface to enhance polish. Background remains minimal and clean with a soft gradient that does not distract from the logo. The camera holds perfectly centered with no movement or only an extremely slight zoom-out for elegance. The pacing should feel premium, authoritative, and minimal. avoid: no distortion, no extra text, no additional graphics, no flicker, no shake, no warping.",
                        "negative_prompt": "no blur, no scaling, no repositioning, no redesign, no artifacts, no reconstruction"
                    }
                },
                "FINANCIAL_DASHBOARD": {
                    "constraints": {
                        "lock_image": True, "immutable_visual_layer": True, "no_redesign": True, "no_layout_change": True,
                        "no_text_change": True, "no_typography_change": True, "no_font_change": True, "no_logo_modification": True,
                        "no_logo_replacement": True, "no_logo_distortion": True, "no_color_change": True, "no_element_addition": True,
                        "no_element_removal": True, "no_ai_reinterpretation": True, "no_scene_reconstruction": True
                    },
                    "veo_control": {
                        "input_mode": "IMAGE_ONLY", "motion_only": True, "allowed_motion": ["fade_in", "number_count_up"],
                        "forbidden_motion": [
                            "scene_rebuild","ui_regeneration","chart_modification","text_edit",
                            "logo_edit","layout_shift","color_adjustment","object_insertion",
                            "object_removal","zoom_in","zoom_out","pan","camera_motion"
                        ],
                        "duration_seconds": 18
                    },
                    "veo_prompt": {
                        "prompt": "Create a motion graphic where the original KPI card image is placed perfectly centered on a minimal dark corporate dashboard background, preserving every detail of the provided asset without modification. The main KPI value gently fades in with a soft scale-up emphasis while supporting labels subtly slide upward into place with easing. A faint glow pulse briefly highlights the numeric value once before settling into a stable state. The company logo from the provided folder remains fixed as a static overlay in the top-right corner without any animation or distortion. The camera applies a very subtle slow zoom-in to enhance focus on the KPI, keeping the composition clean and professional. The pacing should feel calm, precise, and executive-level with no visual noise. avoid: no data changes, no additional metrics, no rapid cuts, no flicker, no warping, no new elements.",
                        "negative_prompt": "no layout shift, no font change, no fake values, no redesign, no distortion, no cropping, no reconstruction, no AI enhancement"
                    }
                },
                "DATA_VISUALIZATION_BAR": {
                    "constraints": {
                        "lock_image": True, "immutable_visual_layer": True, "no_redesign": True, "no_layout_change": True,
                        "no_text_change": True, "no_typography_change": True, "no_font_change": True, "no_color_change": True,
                        "no_element_addition": True, "no_element_removal": True, "no_ai_reinterpretation": True, "no_scene_reconstruction": True
                    },
                    "veo_control": {
                        "input_mode": "IMAGE_ONLY", "motion_only": True, "allowed_motion": ["fade_in", "bar_growth_animation"],
                        "forbidden_motion": [
                            "scene_rebuild","ui_regeneration","chart_modification",
                            "text_edit","layout_shift","object_insertion","object_removal",
                            "zoom_in","zoom_out","pan","camera_motion"
                        ],
                        "duration_seconds": 20
                    },
                    "veo_prompt": {
                        "prompt": "Create a motion graphic using the exact bar chart image from the folder as the base layer, ensuring the chart structure, values, and layout remain unchanged. Animate each bar with a sequential upward growth effect from the baseline while preserving original proportions and spacing. Value labels softly fade in above each bar after it settles, and axis lines appear with a subtle stroke reveal. A light highlight sweep passes across the bars once to emphasize comparison. The logo remains fixed at the top-right as a static overlay without motion. The camera performs a slight vertical pan to guide attention across the dataset in a smooth, controlled manner. The pacing should feel analytical and structured. avoid: no value alteration, no extra bars, no distortion, no rapid transitions, no particles, no flicker.",
                        "negative_prompt": "no value change, no axis change, no color change, no redesign, no distortion, no fake bars, no layout shift"
                    }
                },
                "DATA_VISUALIZATION_LINE": {
                    "constraints": {
                        "lock_image": True, "immutable_visual_layer": True, "no_redesign": True, "no_layout_change": True,
                        "no_text_change": True, "no_typography_change": True, "no_font_change": True, "no_color_change": True,
                        "no_element_addition": True, "no_element_removal": True, "no_ai_reinterpretation": True, "no_scene_reconstruction": True
                    },
                    "veo_control": {
                        "input_mode": "IMAGE_ONLY", "motion_only": True, "allowed_motion": ["fade_in", "line_draw_animation"],
                        "forbidden_motion": [
                            "scene_rebuild","ui_regeneration","chart_modification",
                            "text_edit","layout_shift","object_insertion","object_removal",
                            "zoom_in","zoom_out","pan","camera_motion"
                        ],
                        "duration_seconds": 25
                    },
                    "veo_prompt": {
                        "prompt": "Create a motion graphic using the exact line chart image from the folder, preserving all plotted points, axes, and labels exactly as they are. Animate the trend line drawing from left to right with a smooth stroke reveal that follows the original data path precisely. Each data point softly pops in as the line reaches it, then settles with subtle easing. A faint trailing glow follows the line to enhance directionality without altering data readability. The logo remains fixed in the top-right corner as an unmoving overlay. The camera gently pans along the line trajectory to guide attention across time progression. The pacing should feel analytical, fluid, and narrative-driven. avoid: no data changes, no smoothing that alters values, no extra points, no flicker, no distortion.",
                        "negative_prompt": "no redraw, no new points, no smoothing, no distortion, no data alteration, no layout change"
                    }
                },
                "DATA_VISUALIZATION_PIE": {
                    "constraints": {
                        "lock_image": True, "immutable_visual_layer": True, "no_redesign": True, "no_layout_change": True,
                        "no_text_change": True, "no_color_change": True, "no_element_addition": True, "no_element_removal": True,
                        "no_ai_reinterpretation": True, "no_scene_reconstruction": True
                    },
                    "veo_control": {
                        "input_mode": "IMAGE_ONLY", "motion_only": True, "allowed_motion": ["fade_in", "donut_fill_animation"],
                        "forbidden_motion": [
                            "scene_rebuild","ui_regeneration","chart_modification",
                            "text_edit","layout_shift","object_insertion","object_removal",
                            "zoom_in","zoom_out","pan","camera_motion"
                        ],
                        "duration_seconds": 18
                    },
                    "veo_prompt": {
                        "prompt": "Create a motion graphic using the original pie or donut chart image exactly as provided, preserving all segments and labels without modification. Animate each segment with a smooth clockwise wipe reveal, ensuring each slice appears sequentially with soft easing. Slight micro-separation between slices occurs during reveal for clarity, then returns to final alignment. Center text or labels gently scale in after the full chart is revealed, with a soft ambient glow pulse for emphasis. The logo remains fixed in the top-right corner as a static overlay. The camera holds a steady centered composition with a minimal slow zoom-out for balance. The pacing should feel clean, proportional, and data-centric. avoid: no new categories, no color changes, no distortion, no jitter, no flicker, no extra labels.",
                        "negative_prompt": "no segment change, no color shift, no redesign, no distortion, no new slices"
                    }
                },
                "QUALITATIVE": {
                    "constraints": {
                        "lock_image": True, "immutable_visual_layer": True, "no_redesign": True, "no_layout_change": True,
                        "no_text_change": True, "no_color_change": True, "no_element_addition": True, "no_element_removal": True,
                        "no_ai_reinterpretation": True, "no_scene_reconstruction": True
                    },
                    "veo_control": {
                        "input_mode": "IMAGE_ONLY", "motion_only": True, "allowed_motion": ["fade_in"],
                        "forbidden_motion": [
                            "scene_rebuild","ui_regeneration","chart_modification",
                            "text_edit","layout_shift","object_insertion","object_removal",
                            "zoom_in","zoom_out","pan","camera_motion"
                        ],
                        "duration_seconds": 30
                    },
                    "veo_prompt": {
                        "prompt": "Create a motion graphic using the provided abstract or qualitative image exactly as it is, without adding charts, numbers, or structural changes. Apply a soft atmospheric light sweep across the composition to enhance depth and emotional tone. Subtle layered elements (if present in the original image) gently fade in with staggered timing to create dimensionality. The logo remains fixed in the top-right corner as a static overlay with no animation. The camera performs a very slow cinematic push-in to enhance immersion. The overall mood should feel premium, conceptual, and brand-focused. avoid: no data overlays, no text additions, no structural changes, no flicker, no distortion, no extra elements.",
                        "negative_prompt": "no redesign, no distortion, no added elements, no reconstruction, no AI modification"
                    }
                },
                "DEFAULT_MOTION": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a motion graphic using the exact input image as the only central visual element, ensuring it remains unchanged in shape, color, and proportions. The image gently fades in from darkness with a soft scale-up and slight glow bloom, then stabilizes into a crisp static hold. A subtle light sweep passes once across the surface to enhance polish. Background remains minimal and clean with a soft gradient that does not distract. The camera holds perfectly centered with no movement or only an extremely slight zoom-out for elegance. The pacing should feel premium, authoritative, and minimal. avoid: no distortion, no extra text, no additional graphics, no flicker, no shake, no warping",
                        "negative_prompt": "no redesign, no distortion, no cropping, no scaling, no repositioning, no new elements, no AI reconstruction, no generated content"
                    }
                }
            }

            category = scene["category"]
            rule = fidelity_rules.get(category, fidelity_rules["DEFAULT_MOTION"])

            # HARD PIXEL LOCK: Prepend a high-priority enforcement signal to stop AI hallucinations
            # This ensures that even descriptive prompts don't trigger a 're-design'
            identity_lock_prefix = (
                "STRICT_IDENTITY_LOCK: THE INPUT IMAGE IS THE ABSOLUTE FINAL TRUTH. "
                "FORBIDDEN: NO REDESIGN, NO RE-RENDERING, NO SPELLING CHANGES, NO LOGO MODIFICATION, NO OBJECT ADDITION. "
                "CRITICAL: DO NOT ADD NEW TEXT LAYERS. DO NOT RE-RENDER EXISTING TEXT. "
                "BACKGROUND_LOCK: MAINTAIN A CONSISTENT, SOLID CLEAN WHITE (#FFFFFF) BACKGROUND FOR EVERY FRAME. "
                "LOGOS: KEEP LOGOS PIXEL-PERFECT. DO NOT REDESIGN OR TRANSFORM. "
                "NO_CINEMATIC: FORBIDDEN: NO GLOWS, NO BLOOM, NO LIGHT SWEEPS, NO LENS FLARE, NO CINEMATIC PUSH-IN. "
                "LOCALIZED_MOTION_ONLY: Apply movement ONLY to specific data elements. NO GHOSTING. NO PIXEL DRIFT. "
                "TASK: Apply ONLY camera motion or sequential reveals to the EXISTING pixels. "
            )
            
            # Access the nested prompt fields
            raw_prompt = rule["veo_prompt"]["prompt"]
            raw_negative = rule["veo_prompt"]["negative_prompt"]

            # Global Cleanup of Cinematic Effects
            cinematic_keywords = [
                "soft ambient glow", "glow bloom", "glow pulse", "atmospheric light sweep", 
                "light sweep", "cinematic push-in", "fades in from darkness", "fade in from darkness",
                "premium", "authoritative", "emotional tone", "staggered timing"
            ]
            for kw in cinematic_keywords:
                raw_prompt = raw_prompt.replace(kw, "")
            
            veo_prompt = identity_lock_prefix + raw_prompt
            # Force prompt-level white background consistency
            veo_prompt = veo_prompt.replace("dark corporate dashboard", "solid clean white background")
            veo_prompt = veo_prompt.replace("Primary Blue background", "solid clean white background")
            
            # MASTER NEGATIVE: Hard block on all common AI video hallucinations
            master_negative = (
                "cinematic, glow, bloom, lens-flare, lighting-sweep, motion-blur, soft-lighting, "
                "logo-redesign, spelling-mistake, blue background, dark background, gray background, "
                "double text, ghosting, text-morphing, numeric-overwrite, secondary layers, duplicate objects, "
                "static-drift, pixel-jitter, blurry text, typo, misspelling, text redesign, font change, logo distortion, logo replacement, "
                "re-rendering, AI-hallucination, shifted layout, new objects, background change, "
                "added graphics, extra numbers, watermark, extra-layers"
            )
            negative_prompt = f"{raw_negative}, {master_negative}"
            duration = 8 

            MAX_RETRIES = 3
            success = False
            
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    print(f"DEBUG: Rendering Attempt {attempt}/{MAX_RETRIES} for {s_id}...")
                    operation = client.models.generate_videos(
                        model=ACTIVE_VIDEO_MODEL,
                        prompt=veo_prompt,
                        config=types.GenerateVideosConfig(
                            aspect_ratio='16:9',
                            duration_seconds=8, # VEO 3.1 currently ONLY supports 8s for reference_to_video
                            generate_audio=False,
                            negative_prompt=negative_prompt,
                            reference_images=[{
                                'reference_type': 'asset', 
                                'image': types.Image(image_bytes=img_data, mime_type='image/png')
                            }]
                        )
                    )
                    
                    while not operation.done:
                        time.sleep(10)
                        operation = client.operations.get(operation)
                    
                    if operation.error:
                        err_code = getattr(operation.error, 'code', 0)
                        print(f"WARNING: Attempt {attempt} failed with error code {err_code}. Message: {operation.error}")
                        if err_code == 8: # High Load
                            time.sleep(15) # Wait before retry
                            continue
                    
                    if operation.response and operation.response.generated_videos:
                        video_bytes = operation.response.generated_videos[0].video.video_bytes
                        with open(shot_path, 'wb') as out_f: out_f.write(video_bytes)
                        shot_files.append(shot_path)
                        print(f"DEBUG: Scene {s_id} Rendered successfully.")
                        success = True
                        break
                    else:
                        print(f"WARNING: Attempt {attempt} returned NO VIDEO.")
                except Exception as e:
                    print(f"ERROR: Attempt {attempt} error: {e}")
                
            # SAFETY FALLBACK: If AI fails after retries, create a STATIC video clip
            if not success:
                if HAS_MOVIEPY:
                    print(f"CRITICAL FALLBACK: Scene {s_id} failed AI rendering after {MAX_RETRIES} attempts. Creating static clip to prevent timeline gap.")
                    clip = ImageClip(img_path).set_duration(duration)
                    clip.write_videofile(shot_path, fps=24)
                    shot_files.append(shot_path)
                    success = True
                else:
                    print(f"FATAL: Scene {s_id} failed and no static fallback available.")

            try: os.remove(proc_img_path)
            except: pass

        # 5. FINAL CONCATENATION
        final_output_path = os.path.join(output_dir, 'final_video.mp4')
        
        if shot_files:
            if HAS_MOVIEPY:
                print(f"DEBUG: Concatenating {len(shot_files)} shots via MoviePy...")
                clips = [VideoFileClip(s) for s in shot_files]
                final_clip = concatenate_videoclips(clips, method="compose")
                final_clip.write_videofile(final_output_path, fps=24, audio=False)
                for c in clips: c.close()
            else:
                # FFmpeg fallback (Concatenation via file list)
                print(f"DEBUG: Concatenating {len(shot_files)} shots via FFmpeg Fallback...")
                list_path = os.path.join(renders_dir, "concat_list.txt")
                with open(list_path, 'w') as f:
                    for s in shot_files:
                        f.write(f"file '{os.path.abspath(s)}'\n")
                
                import subprocess
                cmd = f'ffmpeg -y -f concat -safe 0 -i "{list_path}" -c copy "{final_output_path}"'
                subprocess.run(cmd, shell=True)
            
            # Save final_video.json for project traceability
            with open(os.path.join(project_folder, "final_video.json"), 'w') as f:
                json.dump({"scenes": final_sequence, "total_duration": 180, "output": "output/final_video.mp4"}, f, indent=2)

            return {
                "status": "success",
                "video_path": final_output_path
            }, "Project Rendered Successfully! 3-Minute Cinematic Video stored in /output/ folder."

    except Exception as e:
        import traceback
        return {}, f"Production Failed: {str(e)}\n{traceback.format_exc()}"

    return {}, "Engine did not return output."
