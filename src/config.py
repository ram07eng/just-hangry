"""
Configuration settings for Date Night AI
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VECTORSTORE_DIR = PROJECT_ROOT / "vectorstore"

# Data paths
IMDB_DATA_PATH = DATA_DIR / "imdb"
RECIPES_DATA_PATH = DATA_DIR / "recipes"
FOOD_PAIRINGS_PATH = DATA_DIR / "food_pairings"

# LLM Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")

# OpenAI (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ChromaDB
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(VECTORSTORE_DIR))

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast and good quality

# Create directories if they don't exist
for directory in [DATA_DIR, VECTORSTORE_DIR, IMDB_DATA_PATH, RECIPES_DATA_PATH, FOOD_PAIRINGS_PATH]:
    directory.mkdir(parents=True, exist_ok=True)

print(f"✅ Config loaded! Project root: {PROJECT_ROOT}")