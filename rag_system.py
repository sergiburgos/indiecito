# -*- coding: utf-8 -*-
"""
Módulo RAG (Retrieval-Augmented Generation) para Indio-Bot.
Provee funciones para buscar contexto relevante en base de conocimiento.
"""
import os
import pickle
from typing import List, Dict, Optional
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# --- Configuración ---
FAISS_INDEX_FILE = "faiss_index.bin"
CHUNKS_FILE = "chunks.pkl"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'  # Modelo ligero (384 dimensiones)

# --- Variables globales ---
rag_index: Optional[faiss.Index] = None
rag_chunks: Optional[List[Dict[str, str]]] = None
embedding_model: Optional[SentenceTransformer] = None


def load_rag_system() -> bool:
    """
    Carga el índice FAISS y los chunks al inicio de la aplicación.
    
    Returns:
        True si se cargó correctamente, False en caso contrario.
    """
    global rag_index, rag_chunks, embedding_model
    
    try:
        # Cargar modelo de embeddings (solo una vez)
        print(f"Cargando modelo de embeddings: {EMBEDDING_MODEL_NAME}")
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        
        # Cargar índice FAISS
        if os.path.exists(FAISS_INDEX_FILE):
            rag_index = faiss.read_index(FAISS_INDEX_FILE)
            print(f"Índice FAISS cargado: {rag_index.ntotal} vectores")
        else:
            print(f"ADVERTENCIA: No se encontró '{FAISS_INDEX_FILE}'")
            return False
        
        # Cargar chunks
        if os.path.exists(CHUNKS_FILE):
            with open(CHUNKS_FILE, "rb") as f:
                rag_chunks = pickle.load(f)
            print(f"Chunks cargados: {len(rag_chunks)} fragmentos")
        else:
            print(f"ADVERTENCIA: No se encontró '{CHUNKS_FILE}'")
            return False
            
        return True
        
    except Exception as e:
        print(f"ERROR al cargar sistema RAG: {e}")
        return False


async def get_rag_context(query: str, top_k: int = 3) -> str:
    """
    Busca en el índice RAG los chunks más relevantes para una consulta dada.
    
    Args:
        query: Texto de consulta del usuario
        top_k: Número de resultados más relevantes a devolver
        
    Returns:
        Texto con el contexto concatenado o mensaje de error vacío si no hay resultados.
    """
    global rag_index, rag_chunks, embedding_model
    
    if rag_index is None or rag_chunks is None or embedding_model is None:
        return "ADVERTENCIA: El sistema RAG no está disponible. Ejecuta 'python build_rag_index.py' para crear el índice."
    
    try:
        # Generar embedding para la consulta
        query_embedding = embedding_model.encode([query], convert_to_numpy=True).astype("float32")
        
        # Buscar en el índice FAISS
        distances, indices = rag_index.search(query_embedding, top_k)
        
        context_chunks = []
        for idx in indices[0]:
            if idx >= 0 and idx < len(rag_chunks):
                chunk = rag_chunks[idx]
                context_chunks.append(f"--- Documento: {chunk['source']} ---\n{chunk['content']}")
        
        if context_chunks:
            return "\n\nContexto de la base de conocimiento:\n" + "\n\n".join(context_chunks)
        else:
            return ""  # No se encontró contexto relevante
            
    except Exception as e:
        print(f"ERROR en la búsqueda RAG: {e}")
        return f"ADVERTENCIA: Falló la búsqueda en la base de conocimiento ({e})."


def is_rag_available() -> bool:
    """
    Verifica si el sistema RAG está listo para usar.
    """
    return rag_index is not None and rag_chunks is not None and embedding_model is not None