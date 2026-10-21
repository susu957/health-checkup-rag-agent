# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-flash")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "cpu")

JAVA_BASE_URL = os.getenv("JAVA_BASE_URL", "http://localhost:8080")