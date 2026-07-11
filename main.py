# Archivo principal de la aplicación FastAPI para Indio-Bot

import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import traceback
import locale

# --- Diccionario de traducción para fechas (fallback universal) ---
SPANISH_DAYS = {
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
}
SPANISH_MONTHS = {
    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril',
    'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto',
    'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
}

def get_spanish_date() -> str:
    """Devuelve la fecha actual en español, funciona en cualquier sistema."""
    now = datetime.now()
    day_name = SPANISH_DAYS.get(now.strftime('%A'), now.strftime('%A'))
    month_name = SPANISH_MONTHS.get(now.strftime('%B'), now.strftime('%B'))
    return f"Hoy es {day_name}, {now.strftime('%d')} de {month_name} de {now.strftime('%Y')}."

# --- Configuración Regional para Fechas en Español ---
# Intenta configurar el locale a español de España. Si falla, usa el genérico.
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'es')
    except locale.Error:
        # Usar fallback de diccionario en lugar de imprimir advertencia
        pass

# Importar Poolside en lugar de Gemini
from poolside_client import chat_with_poolside, get_poolside_api_key


# Importar las funciones de Google Calendar
from google_calendar import (
    create_calendar_event, 
    list_calendar_events, 
    update_calendar_event, 
    cancel_calendar_event, 
    get_calendar_service,
    test_calendar_connection
)

# --- Configuración y Estado Global ---
# Carga las variables de entorno del archivo .env
load_dotenv()

# Variable para determinar si la funcionalidad de reservas está activada por configuración
RESERVAS_ACTIVAS = os.getenv("RESERVAS_ACTIVAS", "False").lower() in ("true", "1", "t")

# Variable de estado que indica si el calendario es realmente accesible (se verifica al inicio)
CALENDARIO_DISPONIBLE = False

# El prompt del sistema se construirá dinámicamente al inicio
SISTEMA_PROMPT = ""

# --- Lifespan de la Aplicación (Manejo de Inicio y Apagado) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación. Se ejecuta al iniciar 
    para configurar el prompt y verificar la conexión con el calendario.
    """
    global SISTEMA_PROMPT, CALENDARIO_DISPONIBLE

    print("--- Iniciando la aplicación Indio-Bot ---")
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Cargar el prompt base siempre
    try:
        with open(os.path.join(base_path, 'prompt_base.md'), "r", encoding="utf-8") as f:
            SISTEMA_PROMPT = f.read()
        print("Prompt base cargado exitosamente.")
    except FileNotFoundError:
        SISTEMA_PROMPT = "Eres un asistente servicial."
        print("ADVERTENCIA: No se encontró 'prompt_base.md'. Usando prompt de fallback.")

    # 2. Verificar si las reservas están activadas por configuración
    if RESERVAS_ACTIVAS:
        print("Configuración de reservas activada. Intentando verificar conexión con Google Calendar...")
        # 3. Si están activadas, chequear la conexión real con Google Calendar
        if test_calendar_connection():
            print("Conexión con Google Calendar exitosa.")
            CALENDARIO_DISPONIBLE = True
            # 4. Si la conexión es exitosa, añadir las herramientas de calendario al prompt
            try:
                with open(os.path.join(base_path, 'prompt_herramientas_calendario.md'), "r", encoding="utf-8") as f:
                    SISTEMA_PROMPT += "\n\n" + f.read()
                print("Prompt de herramientas de calendario añadido.")
            except FileNotFoundError:
                print("ADVERTENCIA: Reservas activas, pero no se encontró 'prompt_herramientas_calendario.md'.")
                CALENDARIO_DISPONIBLE = False # No se puede operar sin el prompt de herramientas
        else:
            print("ERROR: La verificación de conexión con Google Calendar falló. La función de reservas estará deshabilitada.")
            CALENDARIO_DISPONIBLE = False
    else:
        print("Configuración de reservas desactivada. El bot operará en modo de solo consulta.")

    yield
    # Código de limpieza al apagar la aplicación (si es necesario)
    print("--- Apagando la aplicación Indio-Bot ---")


# --- Helper para extraer texto de la respuesta (compatibilidad Poolside) ---
def get_text_from_response(response_text: str) -> str:
    """Devuelve el texto de respuesta directamente (Poolside ya devuelve texto)."""
    return response_text if response_text else ""

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

# --- Modelos para Contactos ---
class ContactRequest(BaseModel):
    name: str
    phone: str

class ContactsSearchRequest(BaseModel):
    query: str

# --- Inicialización de la Aplicación FastAPI ---
app = FastAPI(lifespan=lifespan)

# --- Endpoint de la API del Chat ---
@app.post("/api/chat")
async def chat_handler(fastapi_request: FastAPIRequest, request: ChatRequest):
    """
    Este endpoint recibe un mensaje y un historial, mantiene el contexto 
    y devuelve una respuesta de la IA, pudiendo usar herramientas.
    """
    try:
        # --- Configuración de la API de Poolside (Just-in-Time) ---
        api_key = get_poolside_api_key()
        if not api_key or api_key == "YOUR_POOLSIDE_API_KEY":
            raise HTTPException(status_code=500, detail="Error: La clave de API de Poolside no está configurada en el entorno del servidor.")

        client_ip = fastapi_request.client.host
        current_time = time.time()

        # --- Lógica de Rate Limiting por IP ---
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
        current_date_str = get_spanish_date()
        message_with_context = f"Contexto de la fecha actual: {current_date_str}. Mensaje del usuario: '{request.message}'"

        # Usa el prompt global construido dinámicamente al inicio con Poolside
        reply_text = await chat_with_poolside(
            message=message_with_context,
            history=request.history,
            system_prompt=SISTEMA_PROMPT
        )
        
        reply_text = get_text_from_response(reply_text)

        if not reply_text:
            reply_text = json.dumps({"reply": "Lo siento, no pude generar una respuesta. Por favor, intenta reformular tu pregunta."})
        
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

# --- Endpoints de Acciones del Calendario ---
@app.post("/api/create_event")
async def api_create_event(request: CreateEventRequest):
    if not CALENDARIO_DISPONIBLE:
        raise HTTPException(status_code=403, detail="La función de creación de eventos está deshabilitada.")
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
    if not CALENDARIO_DISPONIBLE:
        raise HTTPException(status_code=403, detail="La función de búsqueda de eventos está deshabilitada.")
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
    if not CALENDARIO_DISPONIBLE:
        raise HTTPException(status_code=403, detail="La función de actualización de eventos está deshabilitada.")
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
    if not CALENDARIO_DISPONIBLE:
        raise HTTPException(status_code=403, detail="La función de cancelación de eventos está deshabilitada.")
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
        service = get_calendar_service()
        return {
            "status": "SUCCESS",
            "message": "La conexión y autenticación con Google Calendar funcionan correctamente."
        }
    except Exception as e:
        error_details = traceback.format_exc()
        return {
            "status": "ERROR",
            "message": "Falló la autenticación con Google Calendar.",
            "error_type": str(type(e)),
            "error_details": str(e),
            "traceback": error_details
        }

@app.get("/api/debug")
async def debug():
    """Endpoint de diagnóstico para verificar configuración."""
    from poolside_client import get_poolside_api_key
    api_key = get_poolside_api_key()
    return {
        "poolside_api_key_configured": bool(api_key and api_key != "YOUR_POOLSIDE_API_KEY"),
        "reservas_activas": RESERVAS_ACTIVAS,
        "calendario_disponible": CALENDARIO_DISPONIBLE,
        "prompt_length": len(SISTEMA_PROMPT)
    }

# --- Endpoints de Gestión de Contactos WhatsApp ---
@app.post("/api/contacts/register")
async def register_contact(request: ContactRequest):
    """
    Registra manualmente un contacto de WhatsApp.
    """
    from contacts_manager import add_or_update_contact
    contact = add_or_update_contact(name=request.name, phone=request.phone)
    return {"status": "success", "contact": contact}

@app.get("/api/contacts")
async def list_all_contacts():
    """
    Lista todos los contactos registrados.
    """
    from contacts_manager import load_contacts
    contacts = load_contacts()
    return {"contacts": contacts}

@app.post("/api/contacts/search")
async def search_contact(request: ContactsSearchRequest):
    """
    Busca contactos por nombre o teléfono.
    """
    from contacts_manager import find_contact_by_name, find_contact_by_phone
    contact = find_contact_by_name(request.query)
    if not contact:
        contact = find_contact_by_phone(request.query)
    if contact:
        return {"status": "success", "contact": contact}
    return {"status": "not_found", "message": "No se encontró el contacto."}

@app.get("/api/contacts/phone/{phone}")
async def get_contact_by_phone(phone: str):
    """
    Obtiene un contacto por su número de teléfono.
    """
    from contacts_manager import find_contact_by_phone, get_contact_history
    contact = find_contact_by_phone(phone)
    if contact:
        history = get_contact_history(phone)
        return {"status": "success", "contact": contact, "history": history}
    return {"status": "not_found", "message": "No se encontró el contacto."}

# --- Endpoint para servir el archivo HTML principal ---
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# --- Montar la carpeta 'static' para servir otros archivos estáticos (CSS, JS, etc.) ---
app.mount("/static", StaticFiles(directory="static"), name="static_assets")
