import json
import os
import time
from datetime import datetime # Importa datetime
from typing import List, Dict, Any
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

import traceback

# Importar las funciones de Google Calendar
from google_calendar import create_calendar_event, list_calendar_events, update_calendar_event, cancel_calendar_event

# --- Carga del Prompt de Sistema desde archivo ---
def load_system_prompt():
    """Lee el contenido del prompt desde el archivo prompt_indiecito.md."""
    try:
        # Construye una ruta absoluta al archivo para que sea robusto en Vercel
        base_path = os.path.dirname(os.path.abspath(__file__))
        prompt_file_path = os.path.join(base_path, 'prompt_indiecito.md')
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo 'prompt_indiecito.md' en la ruta esperada: {prompt_file_path}")
        return "Eres un asistente servicial." # Un prompt de fallback

INDIECITO_PROMPT = load_system_prompt()

# Carga las variables de entorno del archivo .env
load_dotenv()

# --- Configuración de la API de Gemini ---
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except Exception as e:
    print(f"Error configuring Gemini API: {e}")

# --- Helper para extraer texto de la respuesta de forma segura ---
def get_text_from_response(response: genai.types.GenerateContentResponse) -> str:
    """Extrae de forma segura el contenido de texto de una respuesta de Gemini."""
    if not response.parts:
        return ""
    # Itera sobre las partes y concatena solo el texto, ignorando otros tipos.
    return "".join(part.text for part in response.parts if hasattr(part, "text"))

# --- Rate Limiting por IP de cliente ---
REQUEST_INTERVAL_SECONDS = 30
client_last_request_times: Dict[str, float] = {}

# --- Modelo de Datos para la Petición ---
class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]]

# --- Modelos de Datos para Endpoints de Acciones ---
class CreateEventRequest(BaseModel):
    summary: str
    start_datetime_str: str
    end_datetime_str: str
    description: str = None

class FindEventsRequest(BaseModel):
    time_min_str: str
    time_max_str: str
    query: str = None

class UpdateEventRequest(BaseModel):
    event_id: str
    new_start_str: str = None
    new_end_str: str = None
    new_summary: str = None
    new_description: str = None

class CancelEventRequest(BaseModel):
    event_id: str

# --- Inicialización de la Aplicación FastAPI ---
app = FastAPI()

# --- Endpoint de la API del Chat ---
@app.post("/api/chat")
async def chat_handler(fastapi_request: FastAPIRequest, request: ChatRequest):
    """
    Este endpoint recibe un mensaje y un historial, mantiene el contexto 
    y devuelve una respuesta de la IA, pudiendo usar herramientas.
    """
    # --- PRUEBA DE DIAGNÓSTICO ---
    # Se ignora completamente la API de Gemini y se devuelve una respuesta fija.
    # Si ves esta respuesta, el servidor y las rutas de FastAPI funcionan.
    response_json = {"reply": "Respuesta de prueba: El servidor está funcionando."}
    return JSONResponse(content=response_json)

# --- Endpoints de Acciones del Calendario ---
@app.post("/api/create_event")
async def api_create_event(request: CreateEventRequest):
    try:
        result = create_calendar_event(
            summary=request.summary,
            start_datetime_str=request.start_datetime_str,
            end_datetime_str=request.end_datetime_str,
            description=request.description,
            attendees_emails=["indioreservas@gmail.com"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/find_events")
async def api_find_events(request: FindEventsRequest):
    try:
        result = list_calendar_events(
            time_min_str=request.time_min_str,
            time_max_str=request.time_max_str,
            query=request.query
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/update_event")
async def api_update_event(request: UpdateEventRequest):
    try:
        result = update_calendar_event(
            event_id=request.event_id,
            new_start_str=request.new_start_str,
            new_end_str=request.new_end_str,
            new_summary=request.new_summary,
            new_description=request.new_description
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cancel_event")
async def api_cancel_event(request: CancelEventRequest):
    try:
        result = cancel_calendar_event(event_id=request.event_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoint para servir el archivo HTML principal ---
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# --- Montar la carpeta 'static' para servir otros archivos estáticos (CSS, JS, etc.) ---
app.mount("/static", StaticFiles(directory="static"), name="static_assets")
