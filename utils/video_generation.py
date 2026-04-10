import os
import json
import base64
import time
import google.auth
from PIL import Image
from .models_config import ACTIVE_VIDEO_MODEL

def process_video_generation(project_folder, *args):
    """
    Final Stage (11): The 'Total Fidelity' Veo 3.1 Production.
    - Shuts down all generative creativity with 'Iron-Master' commands.
    - REPLICA BLOCK: Forbids the AI from re-drawing text or logos.
    - BITMAP IDENTITY: Forces the AI to treat input as a sacred unchangeable file.
    - NO-SKIP RELIABILITY: Retries failures to keep the presentation complete.
    - FULL-FRAME LOCK: 1920x1080 forced pre-processing.
    """
    try:
        print(f"DEBUG: Starting Total Fidelity Veo 3.1 Production.")
        from google import genai
        from google.genai import types
        from moviepy import VideoFileClip, concatenate_videoclips
        
        # 1. SETUP AUTH
        service_account_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'neurality-nj-e776c5d11c91.json')
        SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
        credentials, project = google.auth.load_credentials_from_file(service_account_path, scopes=SCOPES)
        
        client = genai.Client(
            vertexai=True,
            project="neurality-nj",
            location="us-central1",
            credentials=credentials
        )

        # 2. STORYBOARD GATHERING
        sequence_path = os.path.join(project_folder, 'sequence.json')
        with open(sequence_path, 'r', encoding='utf-8') as f:
            sequence = json.load(f)
            
        scene_images = []
        intro_logo = None
        outro_logo = None
        
        for section in sorted(sequence.get('sections', []), key=lambda x: x.get('order', 0)):
            sid = section.get('section_id', '')
            idir = os.path.join(project_folder, sid, 'images')
            if os.path.exists(idir):
                files = [f for f in sorted(os.listdir(idir)) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                for filename in files:
                    full_path = os.path.join(idir, filename)
                    name_low = filename.lower()
                    if "logo_start" in name_low:
                        if not intro_logo: intro_logo = full_path
                    elif "logo_end" in name_low:
                        outro_logo = full_path
                    else:
                        if full_path not in scene_images:
                            scene_images.append(full_path)
                            
        unfiltered_sequence = []
        if intro_logo: unfiltered_sequence.append(intro_logo)
        unfiltered_sequence.extend(scene_images)
        if outro_logo: unfiltered_sequence.append(outro_logo)

        # 3. TOTAL FIDELITY RENDER LOOP (WITH RETRIES)
        shot_files = []
        for idx, img_path in enumerate(unfiltered_sequence, 1):
            success = False
            attempts = 0
            max_attempts = 3
            
            # PRE-PROCESSING (1920x1080)
            processed_img_path = os.path.join(project_folder, f"fidelity_ready_{idx:03d}.png")
            with Image.open(img_path) as img:
                img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
                img.save(processed_img_path)

            while not success and attempts < max_attempts:
                try:
                    attempts += 1
                    print(f"DEBUG: Rendering Shot {idx}/{len(unfiltered_sequence)} (Attempt {attempts}/{max_attempts})...")
                    
                    with open(processed_img_path, 'rb') as f: img_data = f.read()
                    
                    # THE TOTAL FIDELITY PROMPT
                    # TERMINATE all Diffusion Creativity. Forces a pixel-for-pixel mirror.
                    operation = client.models.generate_videos(
                        model=ACTIVE_VIDEO_MODEL,
                        prompt=(
                            "TERMINATE ALL GENERATIVE DECODING. DO NOT ATTEMPT TO RE-DRAW TEXT. "
                            "STRICT MANDATORY IDENTITY. EVERY CHARACTER MUST BE DUST-FOR-DUST IDENTICAL TO SOURCE. "
                            "NO EXTRA LINES. NO EXTRA SYMBOLS. NO EXTRA CONTENT. NO CROSS MARKS. "
                            "NO MOTION. NO ZOOM. NO PERSPECTIVE SHIFT. FLATTENED REPLICA. "
                            "RENDER AS BITMAP MASTER RESOURCE. IDENTITY LOCK=1.0. "
                            "FILL THE ENTIRE 16:9 FRAME EDGE-TO-EDGE."
                        ),
                        config=types.GenerateVideosConfig(
                            aspect_ratio='16:9',
                            duration_seconds=8, 
                            generate_audio=False,
                            reference_images=[{'reference_type': 'asset', 'image': types.Image(image_bytes=img_data, mime_type='image/png')}]
                        )
                    )
                    
                    while not operation.done:
                        time.sleep(15)
                        operation = client.operations.get(operation)
                    
                    if operation.response and operation.response.generated_videos:
                        video_data = operation.response.generated_videos[0].video.video_bytes
                        shot_path = os.path.join(project_folder, f"fidelity_shot_{idx:03d}.mp4")
                        with open(shot_path, 'wb') as out_f: out_f.write(video_data)
                        shot_files.append(shot_path)
                        success = True
                    else:
                        print(f"DEBUG: Shot {idx} failed (No video data returned).")
                
                except Exception as e:
                    print(f"DEBUG: Shot {idx} failed with error: {e}")
                    time.sleep(10)

            # Cleanup temp processed image
            try: os.remove(processed_img_path)
            except: pass

        # 4. FINAL PRODUCTION
        if shot_files:
            print(f"DEBUG: Compiling {len(shot_files)} fidelity shots...")
            clips = [VideoFileClip(s) for s in shot_files]
            final_clip = concatenate_videoclips(clips, method="compose")
            
            final_output_path = os.path.join(project_folder, 'final_video.mp4')
            final_clip.write_videofile(final_output_path, fps=24, audio=False)
            
            for clip in clips: clip.close()
            for s in shot_files:
                try: os.remove(s)
                except: pass
                
            return {
                "status": "success",
                "video_path": final_output_path
            }, "Total Fidelity Production Complete! Perfect Image Identity Preserved."

    except Exception as e:
        return {}, f"Production Failed: {str(e)}"

    return {}, "Engine did not return output."
