import os
import json
import shutil

def get_project_root():
    """Returns the absolute path to the project root folder."""
    root = os.path.join(os.getcwd(), "project")
    if not os.path.exists(root):
        os.makedirs(root, exist_ok=True)
    return root

def normalize_sections():
    """
    HEALING ENGINE: Implements DYNAMIC SECTION & SCENE REINDEXING.
    - Detects and fixes gaps in section numbering (e.g., 01, 03 -> 01, 02).
    - Detects and fixes gaps in scene numbering (e.g., scene_01, scene_03 -> scene_01, scene_02).
    - Updates ALL internal references (image_prompts.json, sequence.json).
    """
    root = get_project_root()
    
    # 1. SCAN AND HEAL SECTIONS
    existing_sections = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    
    for i, old_section_name in enumerate(existing_sections, 1):
        new_section_name = f"section_{i:02d}"
        old_section_path = os.path.join(root, old_section_name)
        new_section_path = os.path.join(root, new_section_name)
        
        # Rename section folder if needed
        if old_section_name != new_section_name:
            shutil.move(old_section_path, new_section_path)
        
        # 2. SCAN AND HEAL SCENES WITHIN SECTION
        images_dir = os.path.join(new_section_path, "images")
        if not os.path.exists(images_dir):
            os.makedirs(images_dir, exist_ok=True)
            continue
            
        all_images = sorted([f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        
        # Identify scenes (excluding anchors like logos)
        scene_files = [f for f in all_images if f.startswith("scene_")]
        logo_files = [f for f in all_images if f.startswith("logo_")]
        
        # Reindex scenes to be continuous
        scene_map = {} # Old name -> New name
        for j, old_scene_name in enumerate(scene_files, 1):
            ext = os.path.splitext(old_scene_name)[1]
            new_scene_name = f"scene_{j:02d}{ext}"
            if old_scene_name != new_scene_name:
                shutil.move(os.path.join(images_dir, old_scene_name), os.path.join(images_dir, new_scene_name))
            scene_map[os.path.splitext(old_scene_name)[0]] = os.path.splitext(new_scene_name)[0]

        # 3. UPDATE INTERNAL JSON REFERENCES
        prompts_path = os.path.join(new_section_path, "image_prompts.json")
        if os.path.exists(prompts_path):
            try:
                with open(prompts_path, 'r', encoding='utf-8') as f:
                    prompts = json.load(f)
                
                # Update scene IDs in prompts
                updated_prompts = []
                for p in prompts:
                    if not isinstance(p, dict): continue
                    old_sid = p.get("scene_id")
                    if old_sid in scene_map:
                        p["scene_id"] = scene_map[old_sid]
                    updated_prompts.append(p)
                
                with open(prompts_path, 'w', encoding='utf-8') as f:
                    json.dump(updated_prompts, f, indent=2, ensure_ascii=False)
            except: pass

        # Regenerate section-level sequence.json (Complete Rebuild)
        save_section_sequence(new_section_path)
        
        # 4. PERMANENT FIX: METADATA INTEGRITY GUARD
        # Auto-create missing JSON entries if images exist on disk
        ensure_metadata_integrity(new_section_path)

def ensure_metadata_integrity(section_path):
    """
    PERMANENT SOLUTION: Synchronizes image_prompts.json with the physical images folder.
    Ensures that every file in images/ has a corresponding entry in the JSON.
    """
    images_dir = os.path.join(section_path, "images")
    prompts_path = os.path.join(section_path, "image_prompts.json")
    if not os.path.exists(images_dir): return
    
    # 1. Gather files from disk
    all_files = [os.path.splitext(f)[0] for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    # 2. Read existing prompts
    prompts = []
    if os.path.exists(prompts_path):
        try:
            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
        except: prompts = [] # If corrupted/truncated, start clean from disk

    existing_ids = {p.get("scene_id") for p in prompts if p.get("scene_id")}
    
    # 3. Audit and Auto-fill
    changed = False
    new_prompts = []
    seen_ids = set()
    
    # PRESERVATION LOCK: Keep all engineered prompts (even if images aren't on disk yet)
    for p in prompts:
        sid = p.get("scene_id")
        if sid and sid not in seen_ids:
            new_prompts.append(p)
            seen_ids.add(sid)
            
    # Then add missing files (Growth Only)
    for fid in all_files:
        if fid not in seen_ids:
            # AUTO-REPAIR: Add missing entry
            p_type = "LOGO" if "logo" in fid else "QUALITATIVE"
            new_entry = {
                "scene_id": fid,
                "scene_name": fid.replace("_", " ").title(),
                "prompt_type": p_type,
                "ai_prompt": f"Professional corporate visual for {fid}, high resolution, consistent style."
            }
            new_prompts.append(new_entry)
            seen_ids.add(fid)
            changed = True
            
    # Check if we removed any duplicates
    if len(new_prompts) != len(prompts):
        changed = True

    # 4. Atomic Save (Prevents Truncation during crash)
    if changed or not os.path.exists(prompts_path):
        temp_path = prompts_path + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(new_prompts, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, prompts_path)

def get_next_section_folder():
    """Finds the next logical index (N+1) after healing."""
    normalize_sections() # Ensure current state is clean
    root = get_project_root()
    existing = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    next_num = len(existing) + 1
    return os.path.join(root, f"section_{next_num:02d}")

def save_section_sequence(section_path):
    """Generates a clean sequence.json for the section."""
    images_dir = os.path.join(section_path, "images")
    if not os.path.exists(images_dir): return None
    
    image_files = sorted([f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    section_id = os.path.basename(section_path)
    
    sequence_data = {"section_id": section_id, "images": []}
    for i, img in enumerate(image_files, 1):
        sequence_data["images"].append({
            "path": f"{section_id}/images/{img}",
            "order": i,
            "duration": 0 # Rebalanced later
        })
    
    output_path = os.path.join(section_path, "sequence.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sequence_data, f, indent=2, ensure_ascii=False)
    return output_path

def init_new_section():
    """
    1. Normalizes existing sections (fixes gaps).
    2. Creates the next sequential section folder.
    """
    section_path = get_next_section_folder() # Already calls normalize_sections()
    os.makedirs(section_path, exist_ok=True)
    os.makedirs(os.path.join(section_path, "images"), exist_ok=True)
    return section_path

def run_sequencing_automation(script_path, scene_path, image_prompts_path, images_source_dir):
    """
    Main entry point for the automation.
    Integrates all steps for a single run.
    """
    # 1. Initialize section
    section_path = init_new_section()
    section_id = os.path.basename(section_path)
    
    # 2. Copy source files (script, scene, prompts)
    target_script = os.path.join(section_path, "script.txt")
    target_scene = os.path.join(section_path, "scene.json")
    target_prompts = os.path.join(section_path, "image_prompts.json")
    
    if os.path.exists(script_path): shutil.copy(script_path, target_script)
    if os.path.exists(scene_path): shutil.copy(scene_path, target_scene)
    if os.path.exists(image_prompts_path): shutil.copy(image_prompts_path, target_prompts)
    
    # 3. Copy images
    target_images_dir = os.path.join(section_path, "images")
    if os.path.exists(images_source_dir):
        for img in os.listdir(images_source_dir):
            if img.lower().endswith(('.png', '.jpg', '.jpeg')):
                shutil.copy(os.path.join(images_source_dir, img), os.path.join(target_images_dir, img))
    
    # 4. Generate section-level sequence
    save_section_sequence(section_path)
    
    # 5. Global Reconstruction & Timing
    global_path, global_data = rebuild_global_sequence()
    
    # 6. Read back current section sequence for the final output
    with open(os.path.join(section_path, "sequence.json"), 'r', encoding='utf-8') as f:
        section_sequence = json.load(f)
        
    return {
        "section_created": section_id,
        "section_sequence": section_sequence,
        "global_sequence": global_data
    }

def apply_dynamic_timing():
    """Calculates time per image (180 / total_images)."""
    root = get_project_root()
    sections = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    
    total_images = 0
    section_data_list = []
    
    for sid in sections:
        seq_path = os.path.join(root, sid, "sequence.json")
        if os.path.exists(seq_path):
            with open(seq_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_images += len(data.get("images", []))
                section_data_list.append((seq_path, data))
    
    time_per_image = 180.0 / total_images if total_images > 0 else 0
    
    for seq_path, data in section_data_list:
        for img in data.get("images", []):
            img["duration"] = time_per_image
        with open(seq_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    return time_per_image

def rebuild_global_sequence():
    """Triggers healing and rebuilds the global timeline."""
    normalize_sections() # Step 1: Fix gaps
    time_per_image = apply_dynamic_timing() # Step 2: Distribution
    
    root = get_project_root()
    sections = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    
    global_sequence = {
        "total_duration": 180,
        "time_per_image": time_per_image,
        "sections": []
    }
    
    for i, sid in enumerate(sections, 1):
        global_sequence["sections"].append({
            "section_id": sid,
            "sequence_file": f"{sid}/sequence.json",
            "order": i
        })
        
    global_path = os.path.join(root, "global_sequence.json")
    with open(global_path, "w", encoding="utf-8") as f:
        json.dump(global_sequence, f, indent=2, ensure_ascii=False)
        
    return global_path, global_sequence

def run_sequencing_automation(script_path, scene_path, image_prompts_path, images_source_dir):
    """
    Main entry point for the automation.
    Integrates all steps for a single run.
    Returns the final output JSON as required.
    """
    # 1. Initialize section
    section_path = init_new_section()
    section_id = os.path.basename(section_path)
    
    # 2. Copy source files (script, scene, prompts)
    target_script = os.path.join(section_path, "script.txt")
    target_scene = os.path.join(section_path, "scene.json")
    target_prompts = os.path.join(section_path, "image_prompts.json")
    
    if os.path.exists(script_path): shutil.copy(script_path, target_script)
    if os.path.exists(scene_path): shutil.copy(scene_path, target_scene)
    if os.path.exists(image_prompts_path): shutil.copy(image_prompts_path, target_prompts)
    
    # 3. Copy images
    target_images_dir = os.path.join(section_path, "images")
    if os.path.exists(images_source_dir):
        for img in os.listdir(images_source_dir):
            if img.lower().endswith(('.png', '.jpg', '.jpeg')):
                shutil.copy(os.path.join(images_source_dir, img), os.path.join(target_images_dir, img))
    
    # 4. Generate section-level sequence
    save_section_sequence(section_path)
    
    # 5. Global Reconstruction & Timing
    global_path, global_data = rebuild_global_sequence()
    
    # 6. Read back current section sequence for the final output
    with open(os.path.join(section_path, "sequence.json"), 'r', encoding='utf-8') as f:
        section_sequence = json.load(f)
        
    return {
        "section_created": section_id,
        "section_sequence": section_sequence,
        "global_sequence": global_data
    }
