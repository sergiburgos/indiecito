"""
Cliente de integración con la API de Poolside.
Modelo: laguna-m.1
"""
import os
import json
from typing import List, Dict, Any, Optional
import httpx

# Configuración del modelo y endpoint
# Endpoint correcto para la API de inferencia de Poolside
POOLSIDE_API_BASE = "https://inference.poolside.ai/v1"  # Endpoint correcto (OpenAI-compatible)
POOLSIDE_MODEL = "poolside/laguna-m.1"  # Modelo Laguna M.1

# Almacenamiento para historial de chat (simulando el comportamiento de Gemini)
_chat_sessions: Dict[str, List[Dict[str, Any]]] = {}

def get_poolside_client() -> httpx.AsyncClient:
    """Crea un cliente HTTP configurado para la API de Poolside."""
    api_key = os.getenv("POOLSIDE_API_KEY")
    if not api_key or api_key == "YOUR_POOLSIDE_API_KEY":
        raise ValueError("La clave de API de Poolside no está configurada.")
    
    return httpx.AsyncClient(
        base_url=POOLSIDE_API_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(60.0)
    )

def _format_messages_for_poolside(messages: List[Dict[str, Any]], system_prompt: str) -> List[Dict[str, str]]:
    """
    Formatea los mensajes para el formato esperado por Poolside.
    Gemini usa 'parts' con estructura diferente a OpenAI/Poolside.
    """
    formatted = [{"role": "system", "content": system_prompt}]
    
    for msg in messages:
        role = msg.get("role", "")
        parts = msg.get("parts", [])
        
        content = ""
        for part in parts:
            if isinstance(part, dict) and "text" in part:
                content += part["text"]
            elif isinstance(part, str):
                content += part
        
        if role == "user":
            formatted.append({"role": "user", "content": content})
        elif role == "model":
            formatted.append({"role": "assistant", "content": content})
    
    return formatted

async def chat_with_poolside(
    message: str,
    history: List[Dict[str, Any]],
    system_prompt: str
) -> str:
    """
    Envía un mensaje y historial a la API de Poolside y devuelve la respuesta.
    
    Args:
        message: Mensaje actual del usuario
        history: Historial de conversación en formato Gemini
        system_prompt: Prompt de sistema para la IA
    
    Returns:
        Texto de respuesta de la IA
    """
    async with get_poolside_client() as client:
        messages = _format_messages_for_poolside(history, system_prompt)
        messages.append({"role": "user", "content": message})
        
        response = await client.post(
            "/chat/completions",
            json={
                "model": POOLSIDE_MODEL,
                "messages": messages,
                "stream": False,
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Error en la API de Poolside: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]

# Mantener compatibilidad con funciones existentes si se necesita fallback
def get_poolside_api_key() -> Optional[str]:
    """Obtiene la API key de Poolside del entorno."""
    return os.getenv("POOLSIDE_API_KEY")