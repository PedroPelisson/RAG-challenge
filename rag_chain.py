from langchain_openai import AzureChatOpenAI
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_classic.memory import ChatMessageHistory
from config import (
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME_CHAT
)

conversation_histories = {}

def create_rag_chain(vector_store):
    llm = AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME_CHAT,
        api_version="2023-12-01-preview",
        temperature=0
    )

    retriever = vector_store.as_retriever(search_kwargs={"k": 5})

    question_reformulate = (
        "Considerando as ultimas perguntas do usuário e histórico do chat, que podem conter informações e contexto,"
        "formule uma pergunta standalone que possa ser entendida."
        "Não responda a pergunta. Apenas reformule se necessário. Caso não seja necessário, retorne a pergunta sem alterações."
        )

    contextualize_prompt = ChatPromptTemplate.from_messages(
        [("system", question_reformulate),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")]
    )

    history_aware_retriever = create_history_aware_retriever (
        llm, retriever, contextualize_prompt
    )

    
    bot_persona = (
        "Voce é um especialista financeiro."
        "Seu nome é Greg."
        "Sua função é extrair informações financeiras de dados e apresentar de maneira simples e direta."
        "Priorize apresentação em tópicos."
        "{context}"
    )

    qa_prompt = ChatPromptTemplate.from_messages (
        [("system", bot_persona),
         MessagesPlaceholder("chat_history"),
         ("human", "{input}")]
    )

    qa_chain = create_stuff_documents_chain(llm, qa_prompt)
    chain = create_retrieval_chain(history_aware_retriever, qa_chain)

    def get_session_history(session_id):
        if session_id not in conversation_histories:
            conversation_histories[session_id] = ChatMessageHistory()
        return conversation_histories[session_id]
    
    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer"
    )

    return chain_with_history