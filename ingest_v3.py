from ingest import load_and_split_pdf
from ingest_v2 import get_embeddings, create_vector_store_v2
from sklearn.cluster import KMeans
import numpy as np
import math

def generate_embeddings(documents):
    embeddings_model = get_embeddings()

    #Cada doc do langchain tem um texto em .page_content
    texts = [doc.page_content for doc in documents]

    #Envia p a api da azure os textos e recebe uma lista de vetores.
    vectors = embeddings_model.embed_documents(texts)

    return vectors

def cluster_chunks(documents, vectors):
    n_chunks = len(documents)

    #Quantos clusters criar. Minimo 2
    n_clusters = max(2, min(n_chunks, int(math.sqrt(n_chunks))))

    #Preciso converter pra numpy array por causa do KMEANS
    vectors_array = np.array(vectors)

    '''
    Oq eu entendi do KMeans
    init
        Ele vai definir 'sementes' que são os pontos de inicio da análise usando o 
            Padrão: k-means++
                Faz uma escolha inteligente das 'sementes'
    n_init
        é quantas vezes esse loop vai rodar pra chegar num resultado definitivo.
    random_state
        ao setar um numero, evita a aleatoridade ao iniciar
    centroids = sementes
    '''
    kmeans = KMeans(n_clusters=n_clusters, random_state=1, n_init=10)
    kmeans.fit(vectors_array)
    for i, doc in enumerate(documents):
        doc.metadata['cluster_id'] = int(kmeans.labels_[i])

    centroids = kmeans.cluster_centers_

    return documents, centroids, n_clusters

def create_clustered_store(documents):
    vectors = generate_embeddings(documents)

    documents, centroids, n_clusters = cluster_chunks(documents, vectors)

    vector_store = create_vector_store_v2(documents)

    return vector_store, centroids, n_clusters