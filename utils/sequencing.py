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
    Scans project/ for section_XX folders.
    Detects gaps in numbering (e.g. 01, 03, 05).
    If gaps exist, renames them sequentially (01, 02, 03) and updates their internal sequence.json.
    """
    root = get_project_root()
    
    # 1. Scan and Extract
    existing = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    if not existing:
        return
    
    # 2. Extract numeric indices to check for gaps
    indices = []
    for f in existing:
        try:
            indices.append(int(f.split("_")[1]))
        except (ValueError, IndexError):
            continue
    
    indices.sort()
    
    # Check if continuous (1, 2, 3...)
    is_continuous = all(indices[i] == i + 1 for i in range(len(indices)))
    
    if is_continuous:
        return # Everything is fine
    
    # 3. Trigger Full Reindexing (Controlled Rename)
    # We must rename them one by one to avoid collisions or data loss.
    # Approach: Rename to a temp name first if needed, but since we are always moving "down" (e.g. 03 -> 02), 
    # we just need to ensure we don't overwrite. Indices are sorted, so we can process them sequentially.
    
    for i, old_name in enumerate(existing, 1):
        new_name = f"section_{i:02d}"
        if old_name == new_name:
            continue
        
        old_path = os.path.join(root, old_name)
        new_path = os.path.join(root, new_name)
        
        # Rename the folder
        shutil.move(old_path, new_path)
        
        # 4. Internal Path Update (only sequence.json)
        # Immutability rule: ONLY sequence.json is editable
        seq_json_path = os.path.join(new_path, "sequence.json")
        if os.path.exists(seq_json_path):
            try:
                with open(seq_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                data["section_id"] = new_name
                # Update image paths
                for img_data in data.get("images", []):
                    # Old path: old_section/images/img.png -> New path: new_section/images/img.png
                    if "path" in img_data:
                        parts = img_data["path"].split("/")
                        if len(parts) >= 3:
                            parts[0] = new_name
                            img_data["path"] = "/".join(parts)
                
                with open(seq_json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error updating sequence.json in {new_name}: {e}")

def get_next_section_folder():
    """Finds the highest index N and returns section_(N+1)."""
    root = get_project_root()
    existing = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    
    if not existing:
        return os.path.join(root, "section_01")
    
    last_section = existing[-1]
    last_num = int(last_section.split("_")[1])
    next_num = last_num + 1
    return os.path.join(root, f"section_{next_num:02d}")

def init_new_section():
    """
    1. Normalizes existing sections (fixes gaps).
    2. Creates the next sequential section folder.
    """
    normalize_sections()
    section_path = get_next_section_folder()
    os.makedirs(section_path, exist_ok=True)
    os.makedirs(os.path.join(section_path, "images"), exist_ok=True)
    return section_path

def save_section_sequence(section_path):
    """
    Generates section-level sequence.json for a NEW section.
    Initial duration is set to 0 (will be updated globally).
    """
    images_dir = os.path.join(section_path, "images")
    if not os.path.exists(images_dir):
        return None
    
    image_files = sorted([f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    section_id = os.path.basename(section_path)
    
    sequence_data = {
        "section_id": section_id,
        "images": []
    }
    
    for i, img in enumerate(image_files, 1):
        sequence_data["images"].append({
            "path": f"{section_id}/images/{img}",
            "order": i,
            "duration": 0 # Placeholder
        })
    
    output_path = os.path.join(section_path, "sequence.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sequence_data, f, indent=2, ensure_ascii=False)
    
    return output_path

def apply_dynamic_timing():
    """
    Calculates time per image (180 / total_images) and updates ALL sequence.json files.
    """
    root = get_project_root()
    sections = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    
    total_images = 0
    section_data_list = []
    
    # 1. Count total images
    for section_id in sections:
        seq_path = os.path.join(root, section_id, "sequence.json")
        if os.path.exists(seq_path):
            with open(seq_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                count = len(data.get("images", []))
                total_images += count
                section_data_list.append((seq_path, data))
    
    if total_images == 0:
        return 0
    
    # 2. Compute time_per_image
    time_per_image = 180.0 / total_images
    
    # 3. Apply timing to each file
    for seq_path, data in section_data_list:
        for img_entry in data.get("images", []):
            img_entry["duration"] = time_per_image
        
        with open(seq_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    return time_per_image

def rebuild_global_sequence():
    """
    Rebuilds project/sequence.json after timing distribution.
    """
    root = get_project_root()
    
    # Trigger timing calculation
    time_per_image = apply_dynamic_timing()
    
    sections = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    
    global_sequence = {
        "total_duration": 180,
        "time_per_image": time_per_image,
        "sections": []
    }
    
    for i, section_id in enumerate(sections, 1):
        global_sequence["sections"].append({
            "section_id": section_id,
            "sequence_file": f"{section_id}/sequence.json",
            "order": i
        })
        
    global_path = os.path.join(root, "sequence.json")
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
