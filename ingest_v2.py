from langchain_community.document_loaders import PyPDFLoader
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from config import (
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME_EMBEDDINGS, AZURE_OPENAI_DEPLOYMENT_NAME_CHAT,
    VECTOR_STORE_PATH
)
import uuid

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

def identify_company(documents):
    #Pega só o começp do doc pra economizar tokens
    sample_text = ''
    for doc in documents[:3]:
        sample_text += doc.page_content + '\n'

    llm = AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME_CHAT,
        api_version="2023-12-01-preview",
        temperature=0
    )

    prompt = (
        "Leia o trecho abaixo e identifique o nome da empresa principal mencionada. "
        "Responda APENAS com o nome da empresa, sem explicações.\n\n"
        f"{sample_text}"
    )

    response = llm.invoke(prompt)
    company = response.content.strip()
    return company

def create_vector_store_v2(documents, company=''):
    embeddings = get_embeddings()

    #adiciona a empresa no metadata do chunk
    chunk_ids = []
    for doc in documents:
        doc.metadata['company'] = company
        chunk_id = str(uuid.uuid4())
        doc.metadata['chunk_id'] = chunk_id
        chunk_ids.append(chunk_id)


    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=VECTOR_STORE_PATH,
        ids = chunk_ids
    )

    return vector_store, chunk_ids

def load_existing_vector_store():
    embeddings = get_embeddings()
    vector_store = Chroma(
        persist_directory=VECTOR_STORE_PATH,
        embedding_function=embeddings
    )
    return vector_store

def create_hybrid_retriever(vector_store, documents):
    semantic_retriever = vector_store.as_retriever(search_kwargs={'k': 5})
    
    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = 5

    hybrid_retriever = EnsembleRetriever(
        retrievers = [semantic_retriever, bm25_retriever],
        weights = [0.3, 0.7]
    )

    return hybrid_retriever