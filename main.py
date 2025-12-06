# Archivo principal de la aplicación FastAPI para Indio-Bot
# Comentario trivial para forzar un redespliegue.

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
from google_calendar import create_calendar_event, list_calendar_events, update_calendar_event, cancel_calendar_event, get_calendar_service

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
        # Este print es útil para la depuración local
        print(f"Error: No se encontró el archivo 'prompt_indiecito.md'")
        return "Eres un asistente servicial." # Un prompt de fallback

INDIECITO_PROMPT = load_system_prompt()

# Carga las variables de entorno del archivo .env
load_dotenv()

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
    try:
        # --- Configuración de la API de Gemini (Just-in-Time) ---
        # Se mueve aquí para ser más robusto en entornos serverless.
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "YOUR_API_KEY":
            raise HTTPException(status_code=500, detail="Error: La clave de API de Google no está configurada en el entorno del servidor.")
        genai.configure(api_key=api_key)

        client_ip = fastapi_request.client.host
        current_time = time.time()

        # --- Lógica de Rate Limiting por IP ---
        # Limpieza de IPs antiguas para no llenar la memoria
        for ip, last_time in list(client_last_request_times.items()):
            if current_time - last_time > (REQUEST_INTERVAL_SECONDS * 2):
                del client_last_request_times[ip]
                
        last_request_time = client_last_request_times.get(client_ip, 0)
        time_since_last_request = current_time - last_request_time
        
        if time_since_last_request < REQUEST_INTERVAL_SECONDS:
            sleep_time = REQUEST_INTERVAL_SECONDS - time_since_last_request
            time.sleep(sleep_time)
        
        client_last_request_times[client_ip] = time.time()

        # --- Prepara el mensaje con el contexto de la fecha actual ---
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        message_with_context = f"Fecha actual: {current_date_str}. Mensaje del usuario: '{request.message}'"

        # El modelo ahora no usa tools, solo responde con texto o JSON de acción
        model = genai.GenerativeModel('models/gemini-flash-latest', system_instruction=INDIECITO_PROMPT)
        chat = model.start_chat(history=request.history)
        response = await chat.send_message_async(message_with_context)
        
        reply_text = get_text_from_response(response)

        if not reply_text:
            reply_text = json.dumps({"reply": "Lo siento, no pude generar una respuesta. Por favor, intenta reformular tu pregunta."})
        
        # Intentar encontrar un JSON de acción, incluso si viene mezclado con texto
        action_json = None
        try:
            start_idx = reply_text.find('{')
            end_idx = reply_text.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                potential_json_str = reply_text[start_idx : end_idx + 1]
                parsed_potential_json = json.loads(potential_json_str)
                if "action" in parsed_potential_json and "payload" in parsed_potential_json:
                    action_json = parsed_potential_json
                    reply_text = reply_text.replace(potential_json_str, "").strip()
        except json.JSONDecodeError:
            pass

        if action_json:
            return JSONResponse(content=action_json)
        
        if not reply_text.strip().startswith('{') or not reply_text.strip().endswith('}'):
            reply_text = json.dumps({"reply": reply_text})
        else:
            try:
                temp_parsed = json.loads(reply_text)
                if "reply" not in temp_parsed:
                    reply_text = json.dumps({"reply": reply_text})
            except json.JSONDecodeError:
                 reply_text = json.dumps({"reply": reply_text})

        return JSONResponse(content=json.loads(reply_text))

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

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

# --- Endpoint de Depuración para Google Calendar ---
@app.get("/api/debug_calendar")
async def debug_calendar_connection():
    """
    Un endpoint de depuración para probar la conexión con Google Calendar.
    """
    try:
        # Llama a la función que realiza la autenticación
        service = get_calendar_service()
        
        # Si la obtención del servicio fue exitosa, lo confirmamos.
        return {
            "status": "SUCCESS",
            "message": "La conexión y autenticación con Google Calendar funcionan correctamente."
        }

    except Exception as e:
        # Si hay cualquier error durante la autenticación, lo capturamos.
        import traceback
        error_details = traceback.format_exc()
        
        # Devolvemos el error detallado para poder verlo en el navegador.
        return {
            "status": "ERROR",
            "message": "Falló la autenticación con Google Calendar.",
            "error_type": str(type(e)),
            "error_details": str(e),
            "traceback": error_details
        }

# --- Endpoint para servir el archivo HTML principal ---
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# --- Montar la carpeta 'static' para servir otros archivos estáticos (CSS, JS, etc.) ---
app.mount("/static", StaticFiles(directory="static"), name="static_assets")
