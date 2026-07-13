# -*- coding: utf-8 -*-
"""
Script de construcción del índice RAG para Indio-Bot.
Versión ligera sin embeddings ni FAISS (solo chunking).
Usa coincidencia de palabras clave simple.
"""
import os
import pickle
from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter

print("--- Iniciando el script de construcción del índice RAG (versión ligera) ---")

# --- Configuración ---
KNOWLEDGE_BASE_DIR = "knowledge_base"
CHUNKS_FILE = "chunks.pkl"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

# --- 1. Carga de Documentos ---
def load_documents_from_directory(directory_path: str) -> List[Dict[str, str]]:
    """
    Carga y extrae texto de archivos .txt y .md en un directorio.
    """
    documents = []
    print(f"Buscando documentos en el directorio: '{directory_path}'...")
    
    if not os.path.exists(directory_path):
        print(f"ADVERTENCIA: El directorio '{directory_path}' no existe.")
        return documents
    
    for filename in os.listdir(directory_path):
        filepath = os.path.join(directory_path, filename)
        content = ""
        
        if filename.endswith((".txt", ".md")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                print(f"  - Cargado archivo de texto: {filename}")
            except Exception as e:
                print(f"  - ERROR al leer el archivo de texto {filename}: {e}")
        
        if content:
            documents.append({"source": filename, "content": content})
            
    if not documents:
        print("ADVERTENCIA: No se encontraron documentos en la base de conocimiento.")
    return documents

# --- 2. División del Texto (Chunking) ---
def split_documents_into_chunks(documents: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Divide el contenido de los documentos en trozos más pequeños (chunks).
    """
    print("Dividiendo documentos en trozos (chunks)...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    
    chunks = []
    for doc in documents:
        split_texts = text_splitter.split_text(doc["content"])
        for text in split_texts:
            chunks.append({"source": doc["source"], "content": text})
            
    print(f"Se generaron {len(chunks)} chunks en total.")
    return chunks

# --- 3. Guardado de Chunks ---
def save_chunks(chunks: List[Dict[str, str]]) -> None:
    """
    Guarda los chunks de texto en disco.
    """
    if not chunks:
        print("ERROR: No se generaron chunks, no se puede guardar.")
        return

    print(f"Guardando los chunks de texto en '{CHUNKS_FILE}'...")
    with open(CHUNKS_FILE, "wb") as f:
        pickle.dump(chunks, f)
        
    print(f"Chunks guardados exitosamente. Total de fragmentos: {len(chunks)}")

# --- Flujo Principal ---
if __name__ == "__main__":
    # Cargar documentos
    docs = load_documents_from_directory(KNOWLEDGE_BASE_DIR)
    
    if docs:
        # Dividir en chunks
        text_chunks = split_documents_into_chunks(docs)
        
        if text_chunks:
            # Guardar chunks (sin embeddings ni FAISS)
            save_chunks(text_chunks)
            print("--- Proceso completado. Tu base de conocimiento está lista para ser usada. ---")
        else:
            print("--- Proceso detenido: no se pudieron generar chunks de los documentos. ---")
    else:
        print("--- Proceso detenido: no se encontraron documentos para procesar. ---")