from ingest_v2 import load_existing_vector_store

def get_all_companies():
    #faz um .get que pega os metadados
    #retorna lista

    vector_store = load_existing_vector_store()

    #retorna tudo
    result = vector_store.get(include=['metadatas'])

    companies = set()
    for metadata in result['metadatas']:
        if 'company' in metadata:
            companies.add(metadata['company'])

    return list(companies)