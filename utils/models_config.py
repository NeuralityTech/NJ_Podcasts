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
SERVICE_ACCOUNT_FILE = "gen-lang-client-0270986555-0ed5b1a8f0f3.json"
SERVICE_ACCOUNT_NOTICE = "Service account detected and configured: gen-lang-client-0270986555-0ed5b1a8f0f3.json"

def get_gemini_client(api_key=None):
    """
    Returns a unified Gemini/VertexAI client based on service account status.
    Uses explicit credential loading and private key cleaning to resolve JWT signature issues.
    """
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            from google.oauth2 import service_account
            
            with open(SERVICE_ACCOUNT_FILE, 'r') as f:
                info = json.load(f)
            
            # CRITICAL FIX: Ensure the private key has real newlines, not literal '\n' strings
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n")
            
            # Explicitly load from info to ensure full control over the parameters
            creds = service_account.Credentials.from_service_account_info(
                info,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            project_id = info.get("project_id", "gen-lang-client-0270986555")
            
            # Set the environment variable for vertexai=True mode
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(SERVICE_ACCOUNT_FILE)
            
            return genai.Client(vertexai=True, project=project_id, location="us-central1")
        except Exception as e:
            print(f"DEBUG: Service Account Auth Failure: {e}")
            
    if api_key:
        return genai.Client(api_key=api_key)
        
    return None
