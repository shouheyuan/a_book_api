import json
import os
from fastapi import Request

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")
_translations = {}

def load_locales():
    global _translations
    if not os.path.exists(LOCALES_DIR):
        return
    for filename in os.listdir(LOCALES_DIR):
        if filename.endswith(".json"):
            lang = filename[:-5]
            with open(os.path.join(LOCALES_DIR, filename), "r", encoding="utf-8") as f:
                try:
                    _translations[lang] = json.load(f)
                except Exception as e:
                    print(f"Error loading locale {lang}: {e}")

load_locales()

def get_language(request: Request) -> str:
    """Dependency to extract language from request headers."""
    # 1. Check custom header
    lang = request.headers.get("X-App-Language")
    if lang:
        return lang.split("-")[0].lower() # e.g., 'zh-Hans' -> 'zh'
        
    # 2. Check Accept-Language
    accept_language = request.headers.get("Accept-Language")
    if accept_language:
        # Simplistic parsing: take the first language before comma and drop territory (e.g. 'zh-CN' -> 'zh')
        primary_lang = accept_language.split(",")[0].split(";")[0].strip()
        return primary_lang.split("-")[0].lower()
        
    return "en" # default fallback

def t(key: str, lang: str = "en", **kwargs) -> str:
    """Translate key to specified language."""
    # Try specified language, fallback to english, fallback to key
    lang_dict = _translations.get(lang) or _translations.get("en") or {}
    text = lang_dict.get(key, key)
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
