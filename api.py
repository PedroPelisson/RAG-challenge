from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from config import *
from ingest import load_and_split_pdf, create_vector_store
from ingest_v2 import load_and_split_pdf_semantic, create_vector_store_v2, create_hybrid_retriever, identify_company, load_existing_vector_store
from ingest_v3 import get_all_companies
from rag_chain import create_rag_chain
from rag_chain_v2 import create_rag_chain_v2
from rag_chain_v3 import ask_v3
from hash_utils import calculate_hash, hash_verification, new_hash, search_hash, delete_hashes_by_company
from langchain_core.documents import Document
import os
import uuid

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

class DecideRequest(BaseModel):
    session_id:str
    decision: str #Reaproveitar ou continuar

#v1 e v2
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
    filenames = []
    hash_conflicts = []
    all_chunk_ids = []

    #Salva arquivos e calcula a hash
    for f in files:
        file_path = os.path.join(UPLOAD_FOLDER, f'{session_id}_{f.filename}')
        with open(file_path, 'wb') as dest:
            content = await f.read()
            dest.write(content)

        file_hash = calculate_hash(file_path)

        #hash que ja existe
        if hash_verification(file_hash):
            if strategy == 'v1':
                sessions[session_id] = {
                    'pending_files': [{
                        'file_path': file_path,
                        'filename': f.filename,
                        'file_hash': file_hash
                    }],
                    'strategy': 'v1'
                }
                hash_info = search_hash(file_hash)
                hash_conflicts.append({
                    'filename': f.filename,
                    'file_hash': file_hash,
                    'already_processed_as': hash_info['company'] if hash_info else ''
                })
            elif strategy == 'v2':
                hash_info = search_hash(file_hash)
                existing_chunk_ids = hash_info.get('chunks_ids', []) if hash_info else []

                if existing_chunk_ids:
                    vector_store = load_existing_vector_store()
                    # Recupera os documentos existentes pelo chunk_id
                    result = vector_store.get(
                        ids=existing_chunk_ids,
                        include=['documents', 'metadatas']
                    )
                    for i, text in enumerate(result['documents']):
                        doc = Document(page_content=text, metadata=result['metadatas'][i])
                        all_docs.append(doc)
                    all_chunk_ids.extend(existing_chunk_ids)
                
                filenames.append(f.filename)
        #hash novo
        else:
            if strategy == 'v1':
                docs = load_and_split_pdf(file_path)
                all_docs.extend(docs)
                filenames.append(f.filename)
            elif strategy == 'v2':
                docs = load_and_split_pdf_semantic(file_path)
                company = identify_company(docs)

                vector_store, chunk_ids = create_vector_store_v2(docs, company)
                new_hash(file_hash, f.filename, company, chunk_ids)

                all_docs.extend(docs)
                filenames.append(f.filename)
                all_chunk_ids.extend(chunk_ids)
            else:
                docs = load_and_split_pdf_semantic(file_path)
                company = identify_company(docs)

                vector_store, chunk_ids = create_vector_store_v2(docs, company)
                new_hash(file_hash, f.filename, company, chunk_ids)

                all_docs.extend(docs)
                all_chunk_ids.extend(chunk_ids)  # ← nova lista
                filenames.append(f.filename)

    #v1 com hash existente
    if hash_conflicts and strategy == 'v1':
        if all_docs:
            sessions[session_id]['new_docs'] = all_docs
            sessions[session_id]['new_filenames'] = filenames
        return {
            'session_id': session_id,
            'status': 'pending_decision',
            'hash_conflicts': hash_conflicts,
            'message': 'Arquivo já processado. Deseja reutilizar (semantic) ou continuar (recursive)?'
        }

    try:
        if strategy == 'v1':
            vector_store = create_vector_store(all_docs)
            conversation = create_rag_chain(vector_store)
        elif strategy == 'v2':
            vector_store = load_existing_vector_store()
            hybrid_retriever = create_hybrid_retriever(vector_store, all_docs, all_chunk_ids)
            conversation = create_rag_chain_v2(hybrid_retriever)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'erro ao processar: {str(e)}')

    sessions[session_id] = {
        'conversation': conversation,
        'strategy': strategy,
        'filenames': filenames,
        'chunks': len(all_docs)
    }

    return {
        'session_id': session_id,
        'status': 'ready',
        'strategy': strategy,
        'filenames': filenames,
        'file_count': len(filenames),
        'chunks': len(all_docs)
    }

@app.post('/upload/decide')
async def upload_decide(request: DecideRequest):
    session_id = request.session_id
    decision = request.decision

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail='Sessão não encontrada')
    
    session = sessions[session_id]

    if 'pending_files' not in session:
        raise HTTPException(status_code=400, detail='Nenhuma decisão pendente.')
    
    try:
        if decision == 'reuse':
            vector_store = load_existing_vector_store()
            all_docs = []
            all_chunk_ids = []
            for pending in session['pending_files']:
                hash_info = search_hash(pending['file_hash'])
                existing_chunk_ids = hash_info.get('chunks_ids', []) if hash_info else []
                if existing_chunk_ids:
                    result = vector_store.get(
                        ids=existing_chunk_ids,
                        include=['documents', 'metadatas']
                    )
                    for i, text in enumerate(result['documents']):
                        doc = Document(page_content=text, metadata=result['metadatas'][i])
                        all_docs.append(doc)
                    all_chunk_ids.extend(existing_chunk_ids)

            hybrid_retriever = create_hybrid_retriever(vector_store, all_docs, all_chunk_ids)
            conversation = create_rag_chain_v2(hybrid_retriever)
            final_strategy = 'v2'
        
        else:
            #continua com o recursive
            all_docs = []
            filenames = []
            for pending in session['pending_files']:
                docs = load_and_split_pdf(pending['file_path'])
                all_docs.extend(docs)
                filenames.append(pending['filename'])

            if 'new_docs' in session:
                all_docs.extend(session['new_docs'])
            
            vector_store = create_vector_store(all_docs)
            conversation = create_rag_chain(vector_store)
            final_strategy = 'v1'

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Erro ao processar: {str(e)}')
    
    sessions[session_id] = {
        'conversation': conversation,
        'strategy': final_strategy,
        'chunks': len(all_docs) if decision == 'continue' else 0
    }

    return {
        'session_id': session_id,
        'status': 'ready',
        'strategy': final_strategy,
        'decision': decision
    }

@app.post('/start-v3')
async def strat_v3():
    session_id = str(uuid.uuid4())

    try:
        companies = get_all_companies()

        if not companies:
            raise HTTPException(status_code=400, detail='Nenhum documento no banco. Processe arquivos pela v2 primeiro.')

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Erro ao iniciar v3: {str(e)}')
    
    sessions[session_id] = {
        'strategy': 'v3',
        'companies': companies
    }

    return {
        'session_id': session_id,
        'status': 'ready',
        'strategy': 'v3',
        'companies': companies,
        'message': 'Pronto!'
    }

class DeleteCompanyRequest(BaseModel):
    company:str
@app.post('/delete-company')
async def delete_company(request: DeleteCompanyRequest):
    company = request.company

    try:
        chunk_ids = delete_hashes_by_company(company)

        if chunk_ids:
            vector_store = load_existing_vector_store()
            vector_store.delete(ids=chunk_ids)

        remaining_companies = get_all_companies()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Erro ao deletar empresa: {str(e)}')

    return {
        'status': 'deleted',
        'company': company,
        'chunks_removed': len(chunk_ids),
        'remaining_companies': remaining_companies
    }

@app.post('/chat')
async def chat(request: ChatRequest):
    session_id = request.session_id
    question = request.question

    #Verifica se a sessao existe
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail='Sessão não encontrada. Upload do PDF primeiro.')
    
    strategy = sessions[session_id]['strategy']

    if strategy == 'v3':
        companies = sessions[session_id]['companies']

        try:
            results = ask_v3(question, session_id, companies)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'Erro em gerar resposta: {str(e)}')
        
        return {
            'session_id': session_id,
            'strategy': 'v3',
            'results': results
        }


    #pega a chain da sessao
    conversation = sessions[session_id]['conversation']

    try:
        result = conversation.invoke(
            {'input': question},
            config = {'configurable': {'session_id': session_id}}
        )
        answer = result['answer']

        context_docs = []
        if strategy in ['v2', 'v3'] and 'context' in result:
            for doc in result['context']:
                context_docs.append({
                    'content': doc.page_content[:500],
                    'company': doc.metadata.get('company', ''),
                    'source': doc.metadata.get('source', '') 
                })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Erro ao gerar resposta: {str(e)}')
    
    return {
        'answer': answer,
        'session_id': session_id,
        'strategy': strategy,
        'context_docs': context_docs
    }