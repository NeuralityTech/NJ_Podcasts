import os
import json
from google import genai

# Configuration for AI Models used across the pipeline
MODELS = {
    "nano_banana_pro": "gemini-3-pro-image-preview",
    "nano_banana_2": "gemini-3.1-flash-image-preview",
    "nano_banana": "gemini-2.5-flash-image",
    "rag_engine": "gemini-2.5-flash"
}

# Active Models for specific tasks
ACTIVE_IMAGE_MODEL = MODELS["nano_banana"]
ACTIVE_TEXT_MODEL = MODELS["rag_engine"]

# SERVICE ACCOUNT AUTHENTICATION (CENTRAL)
SERVICE_ACCOUNT_FILE = "neurality-nj-e776c5d11c91.json"
SERVICE_ACCOUNT_NOTICE = "Service account detected and configured: neurality-nj-e776c5d11c91.json"

def get_gemini_client(api_key=None):
    """
    Returns a unified Gemini/VertexAI client prioritized by JSON credentials.
    Uses 'global' location to match working reference implementation for this project.
    """
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            abs_creds_path = os.path.abspath(SERVICE_ACCOUNT_FILE)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = abs_creds_path
            
            with open(abs_creds_path, 'r') as f:
                info = json.load(f)
            
            project_id = info.get("project_id", "neurality-nj")
            
            # Use 'global' location as per reference code in C:\Users\SumaSriMaramreddy\OneDrive - IDANeurality Technologies Pvt Ltd\Neurality\NJ
            return genai.Client(
                vertexai=True, 
                project=project_id, 
                location="global"
            )
        except Exception as e:
            print(f"DEBUG: Service Account Initialization failed: {e}")
    
    if api_key:
        return genai.Client(api_key=api_key)
        
    return None
