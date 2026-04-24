import hashlib
import json
import os
from config import HASHES_FILE

def calculate_hash(file_path):  
    #Le o arquivo em pedaços e calcula o hash SHA-256.
    
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()

def load_hashes():
    #Le hashes e retorna dicionario com nome do arquivo, empresa e chunk ids

    #Se o json ainda nao existe, retorna o dic vazio
    if not os.path.exists(HASHES_FILE):
        return{}
    with open(HASHES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def save_hashes(hashes_dict):
    #Salva dic de hashes no JSON
    #ensure_ascii=False perimite salvar caracteres especiais como ç e ã
    #indent=2 deixa o arquivo visualmente melhor

    with open(HASHES_FILE, 'w', encoding='utf-8') as f:
        json.dump(hashes_dict, f, ensure_ascii=False, indent=2)

def hash_verification(file_hash):
    #retorna true ou false

    hashes = load_hashes()
    return file_hash in hashes

def new_hash(file_hash, filename, company='', chunks_ids=None):
    #Adicina novo hash no json
    #Salva com nome, empresa e chunks ids

    hashes = load_hashes()
    hashes[file_hash] = {
        'filename': filename,
        'company': company,
        'chunks_ids': chunks_ids or []
    }
    save_hashes(hashes)

def search_hash(file_hash):
    #Retorna infos de um hash

    hashes = load_hashes()
    return hashes.get(file_hash, None)