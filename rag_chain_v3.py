from langchain_openai import AzureChatOpenAI
from langchain_community.chat_message_histories import ChatMessageHistory
from ingest_v3 import get_all_companies
from ingest_v2 import load_existing_vector_store
from config import (
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME_CHAT
)
conversation_history_v3 = {}

def get_session_history(session_id:str):
    if session_id not in conversation_history_v3:
        conversation_history_v3[session_id] = ChatMessageHistory()
    return conversation_history_v3[session_id]

def _get_llm():
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME_CHAT,
        api_version="2023-12-01-preview",
        temperature=0
    )



def identify_companies_in_query(query:str, all_companies:list) -> list:
    llm = _get_llm()
    companies_list = ', '.join(all_companies)

    prompt = (
        f'Empresas disponíveis no banco: {companies_list}\n\n'
        'Analise a pergunta abaixo.\n'
        "Se a pergunta mencionar empresas específicas, responda APENAS com esses nomes separados por vírgula.\n"
        f"Se a pergunta for genérica (ex: 'todas', 'comparar', 'resumo geral', ou não citar nenhuma empresa), "
        f"responda exatamente: TODAS\n"
        "Responda APENAS com os nomes ou 'TODAS'. Sem explicações.\n\n"
        f"Pergunta: {query}"
    )

    response = llm.invoke(prompt)
    raw = response.content.strip()

    if raw.upper() == 'TODAS':
        return all_companies, True
    
    mentioned = [name.strip() for name in raw.split(',')]
    valid = [name for name in mentioned if name in all_companies]

    #Se nao reconhecer nenhuma empresa, trta como pergunta generica e retorna todas.
    if not valid:
        return all_companies, True
    
    return valid, False


def reformulate_query_for_company(query: str, company:str) -> str:
    llm = _get_llm()

    prompt = (
        "Você recebeu uma pergunta genérica sobre empresas.\n"
        f"Reformule a pergunta para que ela se refira APENAS à empresa: {company}.\n"
        "Mantenha o sentido original. Responda APENAS com a pergunta reformulada.\n\n"
        f"Pergunta original: {query}\n"
        f"Pergunta reformulada para {company}:"
    )

    response = llm.invoke(prompt)
    return response.content.strip()

def search_company_chunks(vector_store, query:str, company:str, top_k:int = 3):
    results = vector_store.similarity_search(
        query, 
        k=top_k,
        filter= {'company': company}
    )
    return results

def generate_answer_for_company(query:str, company:str, chunks:list, session_id:str) -> str:
    llm = _get_llm()
    context_text = '\n\n'.join([doc.page_content for doc in chunks])

    history = get_session_history(session_id)
    history_messages = history.messages

    messages=[]

    system_prompt=(
        "Você é um especialista financeiro chamado Greg.\n"
        "Sua função é extrair informações financeiras e apresentar de maneira simples e direta.\n\n"
        f"IMPORTANTE: Responda APENAS sobre a empresa {company}. "
        "Use somente os dados do contexto abaixo.\n\n"
        "Instruções de raciocínio:\n"
        "1. Identifique quais trechos do contexto são relevantes para a pergunta.\n"
        "2. Extraia os números e dados específicos desses trechos.\n"
        "3. Verifique se sua resposta é consistente com os dados do contexto.\n\n"
        "FORMATO DE RESPOSTA:\n"
        "<pensamento>\nSeu raciocínio aqui...\n</pensamento>\n"
        "<resposta>\nResposta final aqui.\n</resposta>\n\n"
        "Se a informação não estiver no contexto, diga que não encontrou nos documentos.\n"
        "Não invente dados.\n\n"
        f"Contexto dos documentos de {company}:\n{context_text}"
    )
    messages.append(('system', system_prompt))

    for msg in history_messages[-6:]: #HISTORICO DE MENSAGENS. Pra não estourar ou confundir o contexto, deixei 3 perguntas e respostas
        if msg.type == 'human':
            messages.append(('human', msg.content))

        else:
            messages.append(('assistant', msg.content))

    messages.append(('human', query))

    response = llm.invoke(messages)
    answer = response.content

    return answer

def ask_v3(question: str, session_id:str, all_companies:list):
    #Identifica empresas > pra cada emrpesa roda um loop > se for generico roda todas as emrpesas > retorna lista de respostas
    vector_store = load_existing_vector_store()
    target_companies, is_generic = identify_companies_in_query(question, all_companies)

    results=[]

    for company in target_companies:
        if is_generic:
            search_query = reformulate_query_for_company(question, company)
        else:
            search_query = question

        chunks = search_company_chunks(vector_store, search_query, company)

        if chunks:
            answer = generate_answer_for_company(search_query, company, chunks, session_id)
        else:
            answer = f'Não encontrei informações sobre {company} nos documentos.'

        context_docs = []

        for doc in chunks:
            context_docs.append({
                'content': doc.page_content[:500],
                'company': doc.metadata.get('company', ''),
                'source': doc.metadata.get('source', '')
            })
        
        results.append({
            'company': company,
            'answer': answer,
            'context_docs': context_docs
        })
            

    history = get_session_history(session_id)
    history.add_user_message(question)

    combined = "\n\n".join([f"**{r['company']}**: {r['answer']}" for r in results])
    history.add_ai_message(combined)

    return results