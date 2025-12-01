import datetime
import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Any
from google.oauth2.credentials import Credentials as UserCredentials # Importar para usar con ENV vars

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# --- Helper para formatear fechas ---
def _ensure_utc_format(dt_str: str) -> str:
    """Asegura que la fecha esté en formato ISO 8601 con 'Z' al final."""
    if not dt_str:
        return None
    try:
        # Intenta parsear la fecha, el offset de zona puede o no estar.
        dt_obj = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        # Convierte a UTC, formatea a ISO y añade 'Z'
        return dt_obj.astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    except (ValueError, TypeError):
        # Si falla el parseo, retorna None para ser manejado más adelante
        return None

# --- Autenticación y Servicio de Google Calendar ---
def get_calendar_service():
    """
    Maneja la autenticación y devuelve el objeto de servicio de Google Calendar.
    Prioriza las credenciales de variables de entorno para despliegue serverless.
    """
    creds = None

    # Intentar cargar credenciales de variables de entorno (para Vercel)
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    token_uri = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token") # Default

    if client_id and client_secret and refresh_token:
        try:
            creds = UserCredentials(
                token=None,  # No necesitamos un token inicial, solo refresh_token
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri=token_uri,
                scopes=SCOPES
            )
            # Refrescar el token para obtener uno válido si es necesario
            creds.refresh(Request())
            print("Autenticación de Google Calendar exitosa usando variables de entorno.")
        except Exception as e:
            print(f"Error al autenticar con variables de entorno: {e}")
            creds = None # Fallback a archivo si falla ENV

    # Si no se pudo autenticar con ENV, intentar con archivos locales (para desarrollo)
    if not creds or not creds.valid:
        if os.path.exists("token.json"):
            with open("token.json", "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # El flujo interactivo solo debe usarse en desarrollo local
                if os.path.exists("credentials.json"):
                    print("Autenticación con Google Calendar usando archivos locales (interactivo si es necesario).")
                    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                    creds = flow.run_local_server(port=0)
                    # Guardar el token si se generó uno nuevo localmente
                    with open("token.json", "wb") as token:
                        pickle.dump(creds, token)
                else:
                    raise Exception("No se encontraron credenciales de Google Calendar (ni variables de entorno ni archivos locales).")
        else:
            print("Autenticación de Google Calendar exitosa usando token.json.")
    
    return build("calendar", "v3", credentials=creds)

# --- Funciones de Interacción con el Calendario ---
def create_calendar_event(
    summary: str,
    start_datetime_str: str,
    end_datetime_str: str,
    attendees_emails: List[str] = None,
    description: str = None,
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    """Crea un evento en Google Calendar."""
    try:
        service = get_calendar_service()

        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_datetime_str, "timeZone": "America/Argentina/Buenos_Aires"},
            "end": {"dateTime": end_datetime_str, "timeZone": "America/Argentina/Buenos_Aires"},
            "attendees": [{"email": email} for email in attendees_emails] if attendees_emails else [],
            "reminders": {"useDefault": False, "overrides": [{"method": "email", "minutes": 24 * 60}, {"method": "popup", "minutes": 30}]},
            "guestsCanModify": False,
            "guestsCanInviteOthers": False,
            "guestsCanSeeOtherGuests": False,
        }

        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        
        return {
            "status": "success",
            "id": created_event.get("id"), # Añadido el ID del evento
            "summary": created_event.get("summary"),
            "start": created_event["start"].get("dateTime"),
            "end": created_event["end"].get("dateTime"),
        }

    except HttpError as error:
        return {"status": "error", "message": f"Error de la API de Google al crear evento: {error.resp.status} {error.resp.reason}"}
    except Exception as e:
        return {"status": "error", "message": f"Error inesperado al crear evento: {str(e)}"}

def list_calendar_events(
    time_min_str: str = None,
    time_max_str: str = None,
    query: str = None,
    max_results: int = 10,
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    """
    Lista eventos en Google Calendar, con opción de búsqueda por texto.

    Args:
        time_min_str (str, optional): Fecha y hora mínima (ISO 8601).
        time_max_str (str, optional): Fecha y hora máxima (ISO 8601).
        query (str, optional): Texto para buscar en los campos del evento (ej. nombre).
        max_results (int): Número máximo de eventos a devolver.
        calendar_id (str): ID del calendario a consultar.

    Returns:
        Dict[str, Any]: Un diccionario que contiene una lista de eventos.
    """
    try:
        service = get_calendar_service()

        clean_time_min = _ensure_utc_format(time_min_str) if time_min_str else datetime.datetime.utcnow().isoformat() + "Z"
        clean_time_max = _ensure_utc_format(time_max_str) if time_max_str else None

        if not clean_time_min:
             return {"status": "error", "message": "El formato de la fecha y hora de inicio no es válido."}

        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=clean_time_min,
                timeMax=clean_time_max,
                q=query, # <--- AÑADIDO PARÁMETRO DE BÚSQUEDA
                maxResults=int(max_results) if max_results else 10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        formatted_events = [
            {
                "id": event.get("id"), # <-- MUY IMPORTANTE: Devolver el ID
                "summary": event.get("summary"),
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
            }
            for event in events
        ]
        return {"events": formatted_events}

    except HttpError as error:
        return {"status": "error", "message": f"Error de la API de Google: {error.resp.status} {error.resp.reason}. Revisa que las fechas sean correctas."}
    except Exception as e:
        return {"status": "error", "message": f"Error inesperado al listar eventos: {str(e)}"}

def cancel_calendar_event(event_id: str, calendar_id: str = "primary") -> Dict[str, str]:
    """
    Cancela o elimina un evento del Google Calendar.

    Args:
        event_id (str): El ID del evento a cancelar.
        calendar_id (str): El ID del calendario del que se eliminará el evento.

    Returns:
        Dict[str, str]: Un diccionario confirmando el estado de la operación.
    """
    try:
        service = get_calendar_service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return {"status": "success", "message": "El evento ha sido cancelado exitosamente."}
    except HttpError as error:
        print(f"Ocurrió un error al cancelar el evento: {error}")
        # Si el evento ya no existe (410 Gone), lo consideramos un éxito.
        if error.resp.status == 410:
            return {"status": "success", "message": "El evento ya había sido cancelado."}
        return {"status": "error", "message": f"Error de la API de Google: {error.resp.status} {error.resp.reason}"}
    except Exception as e:
        print(f"Ocurrió un error inesperado al cancelar el evento: {e}")
        return {"status": "error", "message": f"Error inesperado: {str(e)}"}

def update_calendar_event(
    event_id: str,
    calendar_id: str = "primary",
    new_start_str: str = None,
    new_end_str: str = None,
    new_summary: str = None,
    new_description: str = None,
) -> Dict[str, Any]:
    """
    Actualiza un evento existente en Google Calendar.
    Permite actualizaciones parciales.
    """
    try:
        service = get_calendar_service()
        
        # Primero, obtén el evento existente
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        # Actualiza los campos solo si se proporcionan nuevos valores
        if new_start_str:
            event["start"]["dateTime"] = new_start_str
        if new_end_str:
            event["end"]["dateTime"] = new_end_str
        if new_summary:
            event["summary"] = new_summary
        if new_description:
            event["description"] = new_description

        updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        
        return {
            "status": "success",
            "summary": updated_event.get("summary"),
            "start": updated_event["start"].get("dateTime"),
            "end": updated_event["end"].get("dateTime"),
        }

    except HttpError as error:
        return {"status": "error", "message": f"Error de la API de Google al actualizar evento: {error.resp.status} {error.resp.reason}"}
    except Exception as e:
        return {"status": "error", "message": f"Error inesperado al actualizar evento: {str(e)}"}

# Ejemplo de uso
if __name__ == "__main__":
    print("Obteniendo servicio de calendario...")
    service = get_calendar_service()
    print("Servicio de calendario obtenido.")

    print("\nListando los próximos 5 eventos...")
    try:
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        result = list_calendar_events(time_min_str=now, max_results=5)
        events = result.get("events", [])
        if events:
            for event in events:
                print(f"  {event['summary']} ({event['start']})")
            
            # Intentar cancelar el primer evento de la lista como prueba
            first_event_id = events[0].get("id")
            if first_event_id:
                print(f"\nIntentando cancelar el primer evento (ID: {first_event_id})...")
                cancel_result = cancel_calendar_event(event_id=first_event_id)
                print(f"  Resultado de la cancelación: {cancel_result}")

        elif "status" in result and result["status"] == "error":
             print(f"  Error: {result['message']}")
        else:
            print("  No se encontraron eventos.")
    except Exception as e:
        print(f"\nError al listar eventos de ejemplo: {e}")

