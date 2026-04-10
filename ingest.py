from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from config import (
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME_EMBEDDINGS,
    CHUNK_SIZE, CHUNK_OVERLAP, VECTOR_STORE_PATH
)
import shutil
import os

def load_and_split_pdf(pdf_path: str):
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = CHUNK_SIZE,
        chunk_overlap = CHUNK_OVERLAP 
    )
    return text_splitter.split_documents(documents)


def create_vector_store(documents):

    if os.path.exists(VECTOR_STORE_PATH):
        shutil.rmtree(VECTOR_STORE_PATH)

    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint = AZURE_OPENAI_ENDPOINT,
        api_key = AZURE_OPENAI_API_KEY,
        deployment = AZURE_OPENAI_DEPLOYMENT_NAME_EMBEDDINGS
    )

    vector_store = Chroma.from_documents(
        documents = documents,
        embedding = embeddings,
        persist_directory = VECTOR_STORE_PATH
    )

    return vector_store