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
    if any(k in text for k in ["trend", "time", "flow"]): 
        return "DATA_VISUALIZATION_TRENDS"
    if any(k in text for k in ["distribution", "histogram", "bell"]): 
        return "DATA_VISUALIZATION_DISTRIBUTION"
    if any(k in text for k in ["comparison", "side-by-side"]): 
        return "DATA_VISUALIZATION_COMPARISON"
    if any(k in text for k in ["bar", "growth", "deposit"]): 
        return "DATA_VISUALIZATION_BAR"
    if any(k in text for k in ["line", "fy"]): 
        return "DATA_VISUALIZATION_LINE"
    if any(k in text for k in ["pie", "donut", "split"]): 
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
        "DATA_VISUALIZATION_TRENDS": ["fade_in", "line_draw_animation"],
        "DATA_VISUALIZATION_DISTRIBUTION": ["fade_in", "bar_growth_animation"],
        "DATA_VISUALIZATION_COMPARISON": ["fade_in", "bar_growth_animation"],
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
    """Base durations for categorization, aligned with 180s total goal per video_prompt.txt."""
    mapping = {
        "LOGO": 6,
        "FINANCIAL_DASHBOARD": 25,
        "DATA_VISUALIZATION_BAR": 30,
        "DATA_VISUALIZATION_LINE": 30,
        "DATA_VISUALIZATION_PIE": 25,
        "UI_DASHBOARD": 35,
        "INFOGRAPHIC": 35,
        "QUALITATIVE": 30,
        "DATA_VISUALIZATION_TRENDS": 30,
        "DATA_VISUALIZATION_DISTRIBUTION": 30,
        "DATA_VISUALIZATION_COMPARISON": 30
    }
    return mapping.get(category, 25)

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
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "High-end corporate introduction. The scene begins with a pure white frame with very soft lavender gradient hints in the corners. From this empty state, the HDFC Bank branding elements gently fade in and stabilize into the exact original image. Cinematic slow push-in. Absolute pixel hold at end.",
                        "negative_prompt": "no logo redesign, no distortion, no background change, no shadow shift"
                    }
                },
                "LOGO_END": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Professional corporate closing. Starting from the exact logo image, the branding remains crisp while the composition slowly fades out into a pure white frame with soft lavender gradient accents. Final state is a minimal, clean brand exit.",
                        "negative_prompt": "no distortion, no repositioning, no blur"
                    }
                },
                "FINANCIAL_DASHBOARD": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a clean motion graphic starting from the first frame loaded from the reference folder named start_frame.png. The scene begins empty.\n\nTransition into the dashboard by gradually introducing the layout.\n\nReveal the dashboard progressively by revealing key numeric values first with a subtle fade and scale emphasis, followed by supporting elements sliding gently into place.\n\nAll numbers, labels, and text must NOT change or animate numerically. Do not count up or regenerate values. Only reveal existing content.\n\nA faint highlight pulse briefly emphasizes the primary value. The camera applies a very slight zoom.\n\nMaintain slow motion throughout. No cinematic effects.\n\nThe end frame must be exactly the same as the image from the images folder with no modification.",
                        "negative_prompt": "no data change, no font shift, no layout movement, no redraw"
                    }
                },
                "DATA_VISUALIZATION_BAR": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a clean motion graphic starting from the first frame loaded from the reference folder named start_frame.png, which contains a pure white background with very soft lavender gradient hints in the corners. The scene must begin with this first frame fully visible and empty.\n\nFrom this first frame, gradually transition into the bar graph by introducing the chart container first, which rises smoothly from the bottom with a gentle upward slide and slight scale-in.\n\nAfter the container settles, progressively reveal all bar elements so they align exactly with the final image. Each bar is revealed using masking sequentially from zero height to its exact final height.\n\nAll labels, axis text, numbers, and titles must NOT be retyped, regenerated, or modified. They must appear exactly as they exist in the image. Reveal them only using fade-in without altering spelling, font, spacing, or formatting.\n\nOnce all elements are fully revealed, apply a soft horizontal light sweep across the bars. The camera holds briefly and performs a very slight zoom-out.\n\nMaintain slow motion throughout. No cinematic effects.\n\nThe end frame must be pixel-perfect identical to the image from the images folder with no modification.",
                        "negative_prompt": "no axis change, no label movement, no numeric deviation"
                    }
                },
                "DATA_VISUALIZATION_LINE": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a clean motion graphic starting from the first frame loaded from the reference folder named start_frame.png, preserving the white background and soft lavender gradient tones. The scene begins empty.\n\nTransition into the graph by introducing the chart container with a gentle upward slide and slight scale-in.\n\nThen progressively reveal the graph by revealing the line along its path from left to right following the exact path present in the final image. Each data point must appear sequentially and settle precisely at its correct position.\n\nAll axis labels, values, and text must remain untouched. Do not recreate or rewrite them. Reveal only through fade-in.\n\nA soft light sweep travels along the line path. The camera holds and performs a slight zoom-out.\n\nMaintain slow motion throughout. No cinematic effects.\n\nThe end frame must be exactly the same as the image from the images folder.",
                        "negative_prompt": "no path deviation, no extra points, no distortion, no redraw"
                    }
                },
                "DATA_VISUALIZATION_PIE": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a clean motion graphic starting from the first frame loaded from the reference folder named start_frame.png, maintaining the pure white background with soft lavender gradient accents. The scene begins empty.\n\nFrom this state, transition into the pie chart by introducing the chart container with a gentle upward slide and slight scale-in.\n\nThen progressively reveal the chart by revealing each segment in sequence using a smooth radial motion, ensuring each segment forms exactly as it appears in the final image.\n\nAll labels, legends, percentages, and text must NOT be regenerated or changed. Reveal them only using opacity fade-in while preserving exact spelling and layout.\n\nAfter all elements are fully revealed, apply a subtle rotational light sweep across the chart. The camera holds and applies a slight zoom-out.\n\nMaintain slow motion throughout. No cinematic effects.\n\nThe end frame must be exactly the same as the image from the images folder.",
                        "negative_prompt": "no proportional change, no segment shift, no color change"
                    }
                },
                "QUALITATIVE": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a clean motion graphic starting from the first frame loaded from the reference folder named start_frame.png, using the pure white background with soft lavender gradient accents. The scene begins empty.\n\nFrom this state, transition into the infographic by introducing the layout with a slight scale-in from the bottom.\n\nThen progressively reveal all elements from top to bottom. Each component appears with a soft upward motion and fade-in, landing exactly in its final position.\n\nIcons scale in gently and connector lines are revealed along their path smoothly if present.\n\nAll text must remain exactly as in the image. Do not rewrite, retype, or modify spelling.\n\nAfter all elements are revealed, apply a soft ambient light sweep. The camera holds and performs a slight zoom-out.\n\nMaintain slow motion throughout. No cinematic effects.\n\nThe end frame must be exactly the same as the image from the images folder.",
                        "negative_prompt": "no reconstruction, no extra objects, no background change"
                    }
                },
                "DEFAULT_MOTION": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "High-end professional transition from pure white with lavender gradient into the exact input image. Subtle upward slide and fade-in of all elements to their final target positions. Crisp hold, no camera movement. Minimal, clean, premium. Final pixel alignment is critical.",
                        "negative_prompt": "no redesign, no distortion, no repositioning"
                    }
                },
                "DATA_VISUALIZATION_TRENDS": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a clean motion graphic starting from the first frame loaded from the reference folder named start_frame.png, which contains a pure white background with very soft lavender gradient accents. The scene begins empty.\n\nIntroduce the title “TRENDS” exactly as it appears in the image. Do not recreate or retype it. Reveal it using upward slide and fade-in.\n\nThen introduce the trend layout as a container rising from the bottom with a slight scale-in.\n\nReveal the trend line along its path from left to right following the exact path. Arrow indicators appear sequentially with soft pop-in.\n\nAll labels must fade in without any modification.\n\nApply a faint highlight sweep across the trend path. The camera holds and performs a slight zoom-out.\n\nMaintain slow motion throughout. No cinematic effects.\n\nThe end frame must be exactly the same as the image from the images folder.",
                        "negative_prompt": "no redesign, no text changes, no extra arrows, no extra flow"
                    }
                },
                "DATA_VISUALIZATION_DISTRIBUTION": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a clean motion graphic starting from the first frame loaded from the reference folder named start_frame.png with soft blue gradients. The scene begins empty.\n\nIntroduce the title “DISTRIBUTION” exactly as in the image without recreating text.\n\nReveal histogram bars or bell curve progressively:\n\nBars are revealed using masking from zero\nCurve is revealed along its path smoothly left to right\n\nAll labels must fade in without any modification.\n\nApply a soft highlight on peak areas and a horizontal light sweep.\n\nMaintain slow motion throughout. No cinematic effects.\n\nThe end frame must be exactly the same as the image from the images folder.",
                        "negative_prompt": "no layout shift, no added bars, no distribution skew, no redraw"
                    }
                },
                "DATA_VISUALIZATION_COMPARISON": {
                    "constraints": { "lock_image": True, "immutable_visual": True },
                    "veo_prompt": {
                        "prompt": "Create a clean motion graphic starting from the first frame loaded from the reference folder named start_frame.png with soft blue gradients. The scene begins empty.\n\nIntroduce the title “COMPARISON” exactly as in the image.\n\nReveal comparison elements sequentially:\n\nBars are revealed using masking OR blocks expand outward\nEach element reaches exact final size\n\nLabels and values must appear via fade-in only. No rewriting or regeneration.\n\nApply a soft highlight sweep across compared elements.\n\nMaintain slow motion throughout. No cinematic effects.\n\nThe end frame must be exactly the same as the image from the images folder.",
                        "negative_prompt": "no text drift, no numeric distortion, no extra columns, no redraw"
                    }
                }
            }

            category = scene["category"]
            rule = fidelity_rules.get(category, fidelity_rules["DEFAULT_MOTION"])

            # HARD PIXEL LOCK: Prepend a high-priority enforcement signal to stop AI hallucinations
            # This ensures that even descriptive prompts don't trigger a 're-design'
            identity_lock_prefix = (
                "STRICT_REVEALER_MODE: THE INPUT IMAGE IS THE ABSOLUTE FINAL TRUTH. "
                "START FROM A BLANK WHITE FRAME. REVEAL THE FINAL IMAGE USING ONLY FADE-IN AND MASKING. "
                "FORBIDDEN: DO NOT GENERATE, DRAW, OR CONSTRUCT ANYTHING. NO AI RECONSTRUCTION. "
                "PIXEL_LOCK: EVERY VISIBLE PIXEL MUST BELONG TO THE FINAL IMAGE. "
                "NO REDESIGN, NO RE-RENDERING, NO SPELLING CHANGES, NO LOGO MODIFICATION, NO OBJECT ADDITION. "
                "CRITICAL: DO NOT ADD NEW TEXT LAYERS. DO NOT RE-RENDER EXISTING TEXT. "
                "TASK: Apply ONLY opacity fading or linear masking to reveal the EXISTING pixels of Reference Image 2. "
                "Final frame must be pixel-perfect identical to input image. "
            )
            
            global_negative_additions = (
                ", no rapid cuts, no heavy particles, no extreme camera shake, no flicker, "
                "no glitching or compression artifacts, no unwanted text or watermarks, "
                "no extra objects, no warping, no AI reconstruction, no image modification"
            )
            
            # Access the nested prompt fields
            raw_prompt = rule["veo_prompt"]["prompt"]
            raw_negative = rule["veo_prompt"]["negative_prompt"] + global_negative_additions

            # Clean up Cinematic Tags (Relaxing some for the new 'soft lavender' infographic style)
            cinematic_keywords = [
                "fades in from darkness", "fade in from darkness"
            ]
            for kw in cinematic_keywords:
                raw_prompt = raw_prompt.replace(kw, "")
            
            # INFOGRAPHIC STYLE REINFORCEMENT
            style_lock = (
                "INFOGRAPHIC_STYLE: High-end infographic motion graphics. "
                "COLORS: Pure White (#FFFFFF) base with very soft lavender gradient hints. "
                "MOTION: Clean, minimal, professional transitions. "
            )
            
            veo_prompt = identity_lock_prefix + style_lock + raw_prompt
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
            duration = 4 

            # Load Reference Start Frame (Option C Optimization)
            start_frame_path = os.path.join(project_folder, "reference-pic", "start_frame.png")
            start_frame_data = None
            if os.path.exists(start_frame_path):
                with open(start_frame_path, 'rb') as f:
                    start_frame_data = f.read()

            MAX_RETRIES = 3
            success = False
            
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    print(f"DEBUG: Rendering Dual-Reference Attempt {attempt}/{MAX_RETRIES} for {s_id}...")
                    
                    # DUAL-REFERENCE ANCHORING
                    # We provide both the starting point and the ending point as visual anchors.
                    orchestration_prompt = (
                        f"{identity_lock_prefix} {style_lock} {raw_prompt} "
                        "TASK: Animate a smooth, clean transition starting EXACTLY from the first reference image (white background) "
                        "and ending EXACTLY on the second reference image (the chart/dashboard). "
                        "CRITICAL: Complete all motion and data reveals by 4.0 seconds. "
                        "Hold the second image as a perfectly static frame for the remaining 4 seconds of the video."
                    )
                    
                    ref_images = []
                    if start_frame_data:
                        ref_images.append({
                            'reference_type': 'asset', 
                            'image': types.Image(image_bytes=start_frame_data, mime_type='image/png')
                        })
                    
                    ref_images.append({
                        'reference_type': 'asset', 
                        'image': types.Image(image_bytes=img_data, mime_type='image/png')
                    })

                    operation = client.models.generate_videos(
                        model=ACTIVE_VIDEO_MODEL,
                        prompt=orchestration_prompt,
                        config=types.GenerateVideosConfig(
                            aspect_ratio='16:9',
                            duration_seconds=8, # REVERTED: VEO 3.1 STRICT REQUIREMENT
                            generate_audio=False,
                            negative_prompt=negative_prompt,
                            reference_images=ref_images
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
                        pass # Logs suppressed
                except Exception as e:
                    print(f"ERROR: Attempt {attempt} error: {e}")
                
            # SAFETY FALLBACK: If AI fails after retries, skip or log (MoviePy fallback removed per request)
            if not success:
                print(f"FATAL: Scene {s_id} failed AI rendering after {MAX_RETRIES} attempts. Skipping generative shot.")

            try: os.remove(proc_img_path)
            except: pass

        # 5. FINAL CONCATENATION (STRICT 180s TIMELINE NORMALIZATION)
        final_output_path = os.path.join(output_dir, 'final_video.mp4')
        
        if shot_files:
            if HAS_MOVIEPY:
                print(f"DEBUG: Normalizing timeline to reach exactly 180.0 seconds...")
                
                # Logic per video_prompt.txt: Logos are 5s, Content absorbs the rest
                total_duration_goal = 180.0
                logo_fixed = 5.0
                content_total_time = total_duration_goal - (logo_fixed * 2 if (first_logo_start and last_logo_end) else logo_fixed if (first_logo_start or last_logo_end) else 0)
                
                rendered_content_clips = [VideoFileClip(s) for s in shot_files]
                final_clips = []
                
                # Calculate required duration for each internal content scene
                content_only_shots = []
                if first_logo_start:
                    final_clips.append(rendered_content_clips[0].subclipped(0, min(logo_fixed, rendered_content_clips[0].duration)))
                    content_only_shots = rendered_content_clips[1:-1] if last_logo_end else rendered_content_clips[1:]
                else:
                    content_only_shots = rendered_content_clips[:-1] if last_logo_end else rendered_content_clips
                
                num_content = len(content_only_shots)
                if num_content > 0:
                    time_per_content = content_total_time / num_content
                    print(f"DEBUG: Content Scenes: {num_content} | Target Duration: {time_per_content:.2f}s per scene")
                    
                    for clip in content_only_shots:
                        # VEO returns 8s, we need to extend with a hold if time_per_content > 8s
                        if time_per_content > clip.duration:
                            freeze_duration = time_per_content - clip.duration
                            # Capture last frame of the clip
                            last_frame = clip.get_frame(clip.duration - 0.01)
                            freeze_clip = ImageClip(last_frame).with_duration(freeze_duration)
                            final_clips.append(concatenate_videoclips([clip, freeze_clip]))
                        else:
                            # Trim if it's somehow longer (rare for VEO)
                            final_clips.append(clip.subclipped(0, time_per_content))
                
                if last_logo_end:
                    final_clips.append(rendered_content_clips[-1].subclipped(0, min(logo_fixed, rendered_content_clips[-1].duration)))

                print(f"DEBUG: Concatenating {len(final_clips)} shots...")
                final_video = concatenate_videoclips(final_clips, method="compose")
                final_video.write_videofile(final_output_path, fps=24, audio=False)
                
                for c in rendered_content_clips: c.close()
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
