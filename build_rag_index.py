# -*- coding: utf-8 -*-
"""
Script de construcción del índice RAG para Indio-Bot.
Usa sentence-transformers para embeddings (sin Google API).
"""
import os
import pickle
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

print("--- Iniciando el script de construcción del índice RAG ---")

# --- Configuración ---
KNOWLEDGE_BASE_DIR = "knowledge_base"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'  # Modelo ligero (384 dimensiones)
FAISS_INDEX_FILE = "faiss_index.bin"
CHUNKS_FILE = "chunks.pkl"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

# --- Cargar modelo de embeddings ---
print(f"Cargando modelo de embeddings: {EMBEDDING_MODEL_NAME}")
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

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

# --- 3. Creación de Embeddings ---
def create_embeddings(chunks: List[Dict[str, str]]) -> np.ndarray:
    """
    Genera embeddings para una lista de chunks de texto usando sentence-transformers.
    """
    print(f"Generando embeddings para {len(chunks)} chunks...")
    contents = [chunk["content"] for chunk in chunks]
    
    # sentence-transformers procesa todo el lote de una vez
    embeddings = embedding_model.encode(contents, show_progress_bar=True)
    
    return np.array(embeddings).astype("float32")

# --- 4. Construcción y guardado del Índice FAISS ---
def build_and_save_index(embeddings: np.ndarray, chunks: List[Dict[str, str]]) -> None:
    """
    Construye un índice FAISS con los embeddings y lo guarda en disco.
    """
    if embeddings.size == 0:
        print("ERROR: No se generaron embeddings, no se puede construir el índice.")
        return

    print("Construyendo el índice FAISS...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    
    # Añade los embeddings al índice
    index.add(embeddings)
    
    # Guarda el índice FAISS
    print(f"Guardando el índice FAISS en '{FAISS_INDEX_FILE}'...")
    faiss.write_index(index, FAISS_INDEX_FILE)
    
    # Guarda los chunks de texto para poder recuperarlos después
    print(f"Guardando los chunks de texto en '{CHUNKS_FILE}'...")
    with open(CHUNKS_FILE, "wb") as f:
        pickle.dump(chunks, f)
        
    print(f"Índice y chunks guardados exitosamente. Total de vectores en el índice: {index.ntotal}")

# --- Flujo Principal ---
if __name__ == "__main__":
    # Cargar documentos
    docs = load_documents_from_directory(KNOWLEDGE_BASE_DIR)
    
    if docs:
        # Dividir en chunks
        text_chunks = split_documents_into_chunks(docs)
        
        if text_chunks:
            # Crear embeddings
            doc_embeddings = create_embeddings(text_chunks)
            
            # Construir y guardar el índice
            build_and_save_index(doc_embeddings, text_chunks)
            print("--- Proceso completado. Tu base de conocimiento está lista para ser usada. ---")
        else:
            print("--- Proceso detenido: no se pudieron generar chunks de los documentos. ---")
    else:
        print("--- Proceso detenido: no se encontraron documentos para procesar. ---")