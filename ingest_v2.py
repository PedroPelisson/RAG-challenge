from langchain_community.document_loaders import PyPDFLoader
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from config import (
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME_EMBEDDINGS, VECTOR_STORE_PATH
)
import shutil
import os

def get_embeddings():
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME_EMBEDDINGS
    )
    return embeddings

def load_and_split_pdf_semantic(pdf_path: str):
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    embeddings = get_embeddings()

    semantic_splitter = SemanticChunker (
        embeddings= embeddings,
        breakpoint_threshold_type = 'percentile',
        breakpoint_threshold_amount= 80
    )

    chunks = semantic_splitter.split_documents(documents)
    return chunks

def create_vector_store_v2(documents):
    '''if os.path.exists(VECTOR_STORE_PATH):
        shutil.rmtree(VECTOR_STORE_PATH)'''

    embeddings = get_embeddings()

    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=VECTOR_STORE_PATH
    )

    return vector_store

def create_hybrid_retriever(vector_store, documents):
    semantic_retriever = vector_store.as_retriever(search_kwargs={'k': 5})
    
    bm25_retriver = BM25Retriever.from_documents(documents)
    bm25_retriver.k = 5

    hybrid_retriever = EnsembleRetriever(
        retrievers = [semantic_retriever, bm25_retriver],
        weights = [0.3, 0.7]
    )

    return hybrid_retriever