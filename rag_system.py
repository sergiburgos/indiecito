# -*- coding: utf-8 -*-
"""
Módulo RAG (Retrieval-Augmented Generation) para Indio-Bot.
Versión ligera usando búsqueda por palabras clave (sin PyTorch).
Compatible con Vercel sin exceder límites de tamaño.
"""
import os
import pickle
import re
from typing import List, Dict, Optional
from collections import Counter

# --- Configuración ---
CHUNKS_FILE = "chunks.pkl"

# --- Variables globales ---
rag_chunks: Optional[List[Dict[str, str]]] = None


def _tokenize(text: str) -> List[str]:
    """Tokeniza texto simple para búsqueda."""
    # Normalizar y tokenizar
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return [t for t in text.split() if len(t) > 2]  # Palabras > 2 chars


def _calculate_score(query_tokens: List[str], content_tokens: List[str]) -> float:
    """Calcula puntuación simple de coincidencia."""
    if not query_tokens:
        return 0.0
    query_counter = Counter(query_tokens)
    content_counter = Counter(content_tokens)
    score = 0.0
    for token, count in query_counter.items():
        if token in content_counter:
            score += min(count, content_counter[token])
    return score / len(query_tokens)


def load_rag_system() -> bool:
    """
    Carga los chunks al inicio de la aplicación (sin modelo de embeddings).
    
    Returns:
        True si se cargó correctamente, False en caso contrario.
    """
    global rag_chunks
    
    try:
        # Cargar chunks
        if os.path.exists(CHUNKS_FILE):
            with open(CHUNKS_FILE, "rb") as f:
                rag_chunks = pickle.load(f)
            print(f"Chunks cargados: {len(rag_chunks)} fragmentos")
            return True
        else:
            print(f"ADVERTENCIA: No se encontró '{CHUNKS_FILE}'")
            return False
            
    except Exception as e:
        print(f"ERROR al cargar sistema RAG: {e}")
        return False


async def get_rag_context(query: str, top_k: int = 3) -> str:
    """
    Busca chunks relevantes usando coincidencia de palabras clave (sin embeddings).
    
    Args:
        query: Texto de consulta del usuario
        top_k: Número de resultados más relevantes a devolver
        
    Returns:
        Texto con el contexto concatenado o mensaje de error vacío si no hay resultados.
    """
    global rag_chunks
    
    if rag_chunks is None:
        return ""
    
    try:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return ""
        
        # Calcular puntuaciones
        scored_chunks = []
        for i, chunk in enumerate(rag_chunks):
            content_tokens = _tokenize(chunk["content"])
            score = _calculate_score(query_tokens, content_tokens)
            if score > 0:
                scored_chunks.append((score, i, chunk))
        
        # Ordenar por puntuación y tomar top_k
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored_chunks[:top_k]
        
        if top_chunks:
            context_chunks = []
            for score, idx, chunk in top_chunks:
                context_chunks.append(f"--- Documento: {chunk['source']} ---\n{chunk['content']}")
            return "\n\nContexto de la base de conocimiento:\n" + "\n\n".join(context_chunks)
        else:
            return ""  # No se encontró contexto relevante
            
    except Exception as e:
        print(f"ERROR en la búsqueda RAG: {e}")
        return ""


def is_rag_available() -> bool:
    """
    Verifica si el sistema RAG está listo para usar.
    """
    return rag_chunks is not None