import os
import google.generativeai as genai
from google.generativeai.types.safety_types import HarmCategory, HarmBlockThreshold
from dotenv import load_dotenv

load_dotenv()

# Disable all safety filters
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
}

MODELS = {
    "gemini-1.5-pro": {
        "name": "gemini-1.5-pro",
        "model": "gemini-1.5-pro",
        "type": "text"
    },
    "gemini-1.5-flash": {
        "name": "gemini-1.5-flash",
        "model": "gemini-1.5-flash",
        "type": "vision"
    },
    "gemini-1.5-flash-8b": {
            "name": "gemini-1.5-flash-8b",
            "model": "gemini-1.5-flash-8b",
            "type": "vision"
    },
}

class LLMManager:
    def __init__(self):
        self.current_model = "gemini-1.5-pro"
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self._init_models()

    def _init_models(self):
        self.models = {}
        for model_id, config in MODELS.items():
            self.models[model_id] = genai.GenerativeModel(
                config["model"],
                safety_settings=SAFETY_SETTINGS
            )

    def get_current_model(self):
        return self.models[self.current_model]

    def switch_model(self, model_id):
        if model_id in MODELS:
            self.current_model = model_id
            return True
        return False

    def get_available_models(self):
        return MODELS

llm_manager = LLMManager()
model = llm_manager.get_current_model()
