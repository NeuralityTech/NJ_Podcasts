import os
import json

def get_next_section_folder(project_root="project"):
    """Finds the next available section folder name (e.g., section_01)."""
    if not os.path.exists(project_root):
        os.makedirs(project_root)
    
    existing = [d for d in os.listdir(project_root) if os.path.isdir(os.path.join(project_root, d)) and d.startswith("section_")]
    if not existing:
        return os.path.join(project_root, "section_01")
    
    indices = []
    for d in existing:
        try:
            idx = int(d.split("_")[1])
            indices.append(idx)
        except:
            pass
    
    next_idx = max(indices) + 1 if indices else 1
    return os.path.join(project_root, f"section_{next_idx:02d}")

def create_section_sequence(section_folder):
    """Generates a sequence.json inside the specific section folder."""
    images_dir = os.path.join(section_folder, "images")
    if not os.path.exists(images_dir):
        return None, "Images directory not found."
    
    section_id = os.path.basename(section_folder)
    images_list = []
    
    # Files are named img_001.png, img_002.png etc. 
    # We sort them to ensure consistent order
    files = sorted([f for f in os.listdir(images_dir) if f.lower().endswith('.png') or f.lower().endswith('.jpg')])
    
    for i, f in enumerate(files, 1):
        # The path should be relative to project root or absolute? 
        # sequence_images.txt says: "path": "section_01/images/img_001.png"
        rel_path = f"{section_id}/images/{f}"
        images_list.append({
            "path": rel_path,
            "order": i
        })
    
    data = {
        "section_id": section_id,
        "images": images_list
    }
    
    output_path = os.path.join(section_folder, "sequence.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return output_path, "Section sequence generated."

def update_master_sequence(section_folder, project_root="project"):
    """Appends the new section entry into the master sequence.json."""
    master_path = os.path.join(project_root, "sequence.json")
    section_id = os.path.basename(section_folder)
    
    data = {"total_duration": 0, "sections": []}
    if os.path.exists(master_path):
        try:
            with open(master_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            pass
    
    # Check if already exists to avoid duplicates
    if any(s["section_id"] == section_id for s in data["sections"]):
        return master_path, "Section already in master sequence."
    
    order = len(data["sections"]) + 1
    data["sections"].append({
        "section_id": section_id,
        "sequence_file": f"{section_id}/sequence.json",
        "order": order
    })
    
    # Sort sections by order
    data["sections"].sort(key=lambda s: s["order"])
    
    with open(master_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return master_path, "Master sequence updated."
