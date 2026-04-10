import os
import json
from google import genai

# Configuration for AI Models used across the pipeline
MODELS = {
    "nano_banana_pro": "gemini-3-pro-image-preview",
    "nano_banana_2": "gemini-3.1-flash-image-preview",
    "nano_banana": "gemini-2.5-flash-image",
    "rag_engine": "gemini-2.5-flash",
    "video_engine": "veo-3.1-generate-001"
}

# Active Models for specific tasks
ACTIVE_IMAGE_MODEL = MODELS["nano_banana"]
ACTIVE_TEXT_MODEL = MODELS["rag_engine"]
ACTIVE_VIDEO_MODEL = MODELS["video_engine"]

# SERVICE ACCOUNT AUTHENTICATION (CENTRAL)
SERVICE_ACCOUNT_FILE = "neurality-nj-e776c5d11c91.json"
SERVICE_ACCOUNT_NOTICE = "Service account detected and configured: neurality-nj-e776c5d11c91.json"

def get_gemini_client(api_key=None, service_account_path=None, location="global"):
    """
    Returns a unified Gemini/VertexAI client prioritized by JSON credentials.
    Supports regional switching (e.g. 'global' for images, 'us-central1' for video).
    """
    # Prioritize manually provided path, then default, then env var
    creds_path = service_account_path if service_account_path else SERVICE_ACCOUNT_FILE
    
    if creds_path and os.path.exists(creds_path):
        try:
            abs_creds_path = os.path.abspath(creds_path)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = abs_creds_path
            
            with open(abs_creds_path, 'r') as f:
                info = json.load(f)
            
            project_id = info.get("project_id", "neurality-nj")
            
            return genai.Client(
                vertexai=True, 
                project=project_id, 
                location=location
            )
        except Exception as e:
            print(f"DEBUG: Service Account Initialization failed ({creds_path}): {e}")
    
    if api_key:
        return genai.Client(api_key=api_key)
        
    return None
