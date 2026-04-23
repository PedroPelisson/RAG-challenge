from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from ingest_v2 import get_embeddings
import numpy as np
from typing import List
from langchain_openai import AzureChatOpenAI
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from config import (
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME_CHAT
)

class ClusteredRetriever(BaseRetriever):
    vector_store: object
    centroids:object
    n_clusters:int
    top_clusters: int = 2 # QUANTO CLUISTERS CONSULTAR
    top_k: int = 5 # CHUNKS QUE RETORNA, TIPO KWARGS = 5

    class Config:
        arbitrary_types_allowed = True # PERMITE NUMPY ARRAYS. PRECISA PRO KMEANS

    #=======================================================================================
    #                                   ESTUDAR MAIS
    #=======================================================================================

    def _get_relevant_documents(self, query: str) -> List[Document]:
        #PRIMEIRO PRECISO DESCOBRIR QUAL CLUSTER É RELEVANTE
        #CONVERTE A PERGUNTA EM VETOR
        embeddings_model=get_embeddings()
        query_vector=embeddings_model.embed_query(query)
        query_array=np.array(query_vector)

        #AGORA CALCULAR A DISTANCIA DO VETOR DA PERGUNTA
        distances = []
        for i, centroid in enumerate(self.centroids):
            dist = np.linalg.norm(query_array - centroid)
            distances.append((i, dist))

        #ORDENAR AS DISTANCIAS
        distances.sort(key=lambda x: x[1])
        best_clusters = [cluster_id for cluster_id, dist in distances [:self.top_clusters]]

        #BUSCAR AS CHUNKS DOS BEST CLUSTERS
        results = self.vector_store.similarity_search(
            query,
            k=self.top_k,
            filter={'cluster_id': {"$in": best_clusters}}
        )

        return results

conversation_history_v3 = {}

def create_rag_chain_v3(clustered_retriever):
    llm = AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME_CHAT,
        api_version="2023-12-01-preview",
        temperature=0
    )

    question_reformulate = (
        "Considerando as ultimas perguntas do usuário e histórico do chat, que podem conter informações e contexto,"
        "formule uma pergunta standalone que possa ser entendida."
        "Não responda a pergunta. Apenas reformule se necessário. Caso não seja necessário, retorne a pergunta sem alterações."
    )

    contextualize_prompt = ChatPromptTemplate.from_messages([
        ("system", question_reformulate),
        MessagesPlaceholder('chat_history'),
        ('human', '{input}')
    ])

    history_aware_retriever = create_history_aware_retriever(
        llm, clustered_retriever, contextualize_prompt
    )

    bot_persona_cot = (
        "Voce é um especialista financeiro."
        "Seu nome é Greg."
        "Sua função é extrair informações financeiras de dados e apresentar de maneira simples e direta."
        "\n\n"
        "Instruções de raciocínio(chain of thought): \n"
        "Antes de responder, siga estes passos:\n"
        "1. Identifique quais trechos do contexto são relevantes para a pergunta.\n"
        "2. Extraia os números e dados específicos desses trechos.\n"
        "3. Se a pergunta envolver comparação, organize os dados lado a lado.\n"
        "4. Verifique se sua resposta é consistente com os dados do contexto.\n"
        "5. Apresente a resposta final de forma clara, em tópicos quando possível.\n"
        "\n"
        "Se a informação não estiver no contexto, diga que não encontrou nos documentos.\n"
        "Não invente dados\n"
        "\n"
        "Contexto dos documentos: \n"
        "{context}"
    )

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", bot_persona_cot),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])

    qa_chain = create_stuff_documents_chain(llm, qa_prompt)
    chain = create_retrieval_chain(history_aware_retriever, qa_chain)

    def get_session_history(session_id):
        if session_id not in conversation_history_v3:
            conversation_history_v3[session_id] = ChatMessageHistory()
        return conversation_history_v3[session_id]

    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer"
    )

    return chain_with_history