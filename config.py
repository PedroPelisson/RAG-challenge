import os
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME_CHAT = "gpt-4.1-mini"
AZURE_OPENAI_DEPLOYMENT_NAME_EMBEDDINGS = "text-embedding-3-small"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

VECTOR_STORE_PATH = 'chroma_db'

UPLOAD_FOLDER = "uploads"

if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
    print("Problema com a chave ou endpoint.")