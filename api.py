from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from config import *
from ingest import load_and_split_pdf, create_vector_store
from ingest_v2 import load_and_split_pdf_semantic, create_vector_store_v2, create_hybrid_retriever
from rag_chain import create_rag_chain
from rag_chain_v2 import create_rag_chain_v2
from ingest_v3 import create_clustered_store
from rag_chain_v3 import create_rag_chain_v3, ClusteredRetriever
import os
import uuid



# Configuração do FastAPI



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_methods=['*'],
    allow_headers=['*']
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

sessions = {}

class ChatRequest(BaseModel):
    session_id: str
    question: str



'''
Primeiro endpoint: Upload de PDF
Preciso enviar a lista de arquivos e estrategia.
Ver se é PDF.
    status_code=400
Criar uma sessao unica.
    uuid4()
Processar docs.
    load_and_split_pdf/_sematic(file_path)
Criar DB.
    create_vector_store/v2(all_docs)
Criar RAG.
    v1:
        create_rag_chain(vector_store)
    v2:
        create_hybrid_retriever(vector_store, all_docs)
        create_rag_chain_v2(hybrid_retriever)
Retornar: session, historico, estrategia, chunks
    Dentro de session adicionar o rag com historico e session id
'''



@app.post('/upload')
async def upload_pdf(
    files: List[UploadFile] = File(...),
    strategy: str = Form(default='v1')
):
    #Validação dos docs.
    for f in files:
        if not f.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Apenas PDF")
    
    #Cria um id aleatorio com o uuid4 e cria listas
    session_id = str(uuid.uuid4())

    all_docs = []
    filename = []

    #Pra n dar problema de arquivos com o msm nome.
    for f in files:
        file_path = os.path.join(UPLOAD_FOLDER, f"{session_id}_{f.filename}")
        with open(file_path, 'wb') as dest:
            content = await f.read()
            dest.write(content)

        #Processamento
        if strategy == 'v1':
            docs = load_and_split_pdf(file_path)
        else:
            docs = load_and_split_pdf_semantic(file_path)
        
        all_docs.extend(docs)
        filename.append(f.filename)

    #Cria o store e chain
    try: 
        if strategy == 'v1':
            vector_store = create_vector_store(all_docs)
            conversation = create_rag_chain(vector_store)
        elif strategy == 'v2':
            vector_store = create_vector_store_v2(all_docs)
            hybrid_retriever = create_hybrid_retriever(vector_store, all_docs)
            conversation = create_rag_chain_v2(hybrid_retriever)
        else:
            vector_store, centroids, n_clusters = create_clustered_store(all_docs)
            clustered_retriever = ClusteredRetriever(
                vector_store=vector_store,
                centroids=centroids,
                n_clusters=n_clusters
            )
            conversation = create_rag_chain_v3(clustered_retriever)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Erro com o PDF: {str(e)}')

    #Salva na memoria
    sessions[session_id] = {
        'conversation': conversation,
        'strategy': strategy,
        'filename': f.filename,
        'chunks': len(all_docs)
    }

    return {
        'session_id': session_id,
        'strategy': strategy,
        'filenames': filename,
        'file_count': len(filename),
        'chunks': len(all_docs)
    }



'''
Segundo endpoint: Chat
Recebe JSON com session e pergunta
Valida a sessao
    status_code=404
Invoke conversation com input
    input: question
    config com session id p manter historico
    status_code=500
'''



@app.post('/chat')
async def chat(request: ChatRequest):
    session_id = request.session_id
    question = request.question

    #Verifica se a sessao existe
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail='Sessão não encontrada. Upload do PDF primeiro.')
    
    #pega a chain da sessao
    conversation = sessions[session_id]['conversation']

    try:
        result = conversation.invoke(
            {'input': question},
            config = {'configurable': {'session_id': session_id}}
        )
        answer = result['answer']
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Erro ao gerar resposta: {str(e)}')
    
    return {
        'answer': answer,
        'session_id': session_id,
        'strategy': sessions[session_id]['strategy']
    }