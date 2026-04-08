import os
import json
import shutil

def get_project_root():
    """Returns the absolute path to the project root folder."""
    return os.path.join(os.getcwd(), "project")

def get_next_section_folder():
    """Calculates the next available section folder name (section_01, section_02, etc.)."""
    root = get_project_root()
    if not os.path.exists(root):
        os.makedirs(root, exist_ok=True)
        return os.path.join(root, "section_01")
    
    existing = [f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))]
    if not existing:
        return os.path.join(root, "section_01")
    
    # Extract numbers and find max
    nums = []
    for f in existing:
        try:
            num = int(f.split("_")[1])
            nums.append(num)
        except (ValueError, IndexError):
            continue
    
    next_num = max(nums) + 1 if nums else 1
    return os.path.join(root, f"section_{next_num:02d}")

def init_new_section():
    """Creates a new section folder and its internal images directory."""
    section_path = get_next_section_folder()
    os.makedirs(section_path, exist_ok=True)
    os.makedirs(os.path.join(section_path, "images"), exist_ok=True)
    return section_path

def save_section_sequence(section_path):
    """
    Generates section-level sequence.json.
    Scans the images/ folder and builds the path relative to the project root.
    """
    images_dir = os.path.join(section_path, "images")
    if not os.path.exists(images_dir):
        return None
    
    # Get all images sorted by name
    image_files = sorted([f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    section_id = os.path.basename(section_path)
    sequence_data = {
        "section_id": section_id,
        "images": []
    }
    
    for i, img in enumerate(image_files, 1):
        # Path relative to 'project' parent
        rel_path = f"{section_id}/images/{img}"
        sequence_data["images"].append({
            "path": rel_path,
            "order": i
        })
    
    output_path = os.path.join(section_path, "sequence.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sequence_data, f, indent=2, ensure_ascii=False)
    
    return output_path

def rebuild_global_sequence():
    """
    Scans all existing section folders and rebuilds the global project/sequence.json from scratch.
    """
    root = get_project_root()
    sections = sorted([f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))])
    
    global_sequence = {
        "total_duration": 0, # Placeholder or calculated if needed later
        "sections": []
    }
    
    for i, section_id in enumerate(sections, 1):
        seq_file_rel = f"{section_id}/sequence.json"
        # Check if sequence file exists in that section
        if os.path.exists(os.path.join(root, seq_file_rel)):
             global_sequence["sections"].append({
                 "section_id": section_id,
                 "sequence_file": seq_file_rel,
                 "order": i
             })
    
    # Calculate estimated duration (e.g. 5 seconds per image across all sections)
    total_images = 0
    for s in global_sequence["sections"]:
        seq_path = os.path.join(root, s["sequence_file"])
        try:
            with open(seq_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_images += len(data.get("images", []))
        except:
            continue
    global_sequence["total_duration"] = total_images * 5 # Standard 5 sec/image
    
    global_path = os.path.join(root, "sequence.json")
    with open(global_path, "w", encoding="utf-8") as f:
        json.dump(global_sequence, f, indent=2, ensure_ascii=False)
    
    return global_path, global_sequence
