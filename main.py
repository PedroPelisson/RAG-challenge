from config import *
from ingest import load_and_split_pdf, create_vector_store
from rag_chain import create_rag_chain

pdf_path = "arquivos/complexos/NVIDIA-ComTabelas.pdf"

print("\nPDF fragmentado em:")
docs = load_and_split_pdf(pdf_path)
print(f"{len(docs)} chunks.\n")

print("\nVector DB:")
vector_store = create_vector_store(docs)
print("Funcionando\n")

print("\nRAG chain:")
conversation = create_rag_chain(vector_store)
print("Pronto\n")

session_id = "Pedro1"
print(f'\nSession id: {session_id}\n')

print('\n\n')

question1 = 'Qual o lucro bruto total da NVIDIA nos três meses anteriores a 28 de abril de 2024?'
print(f"Pergunta: {question1}")
res = conversation.invoke(
    {'input': question1},
    config = {'configurable':{"session_id": session_id}}
)
print(f"Resposta: {res['answer']}\n\n")

question2 = 'Exiba uma comparação deste dado com o mesmo em outro ano'
print(f"Pergunta: {question2}")
res = conversation.invoke(
    {'input': question2},
    config = {'configurable':{"session_id": session_id}}
)
print(f"Resposta: {res['answer']}\n\n")