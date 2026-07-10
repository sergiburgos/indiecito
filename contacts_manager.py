"""
Módulo de registro de contactos WhatsApp para Indio-Bot.
Almacena números de WhatsApp de clientes para futuras referencias.
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

CONTACTS_FILE = "contacts.json"


def _ensure_contacts_file() -> None:
    """Asegura que el archivo de contactos existe."""
    if not os.path.exists(CONTACTS_FILE):
        with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_contacts() -> List[Dict]:
    """Carga todos los contactos del archivo."""
    _ensure_contacts_file()
    try:
        with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_contacts(contacts: List[Dict]) -> None:
    """Guarda la lista completa de contactos en el archivo."""
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=False)


def find_contact_by_phone(phone: str) -> Optional[Dict]:
    """Busca un contacto por su número de WhatsApp."""
    contacts = load_contacts()
    # Normalizamos el número para comparación (quitamos espacios y +)
    normalized_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    
    for contact in contacts:
        stored_phone = contact.get("phone", "").replace("+", "").replace(" ", "").replace("-", "")
        if stored_phone == normalized_phone:
            return contact
    return None


def find_contact_by_name(name: str) -> Optional[Dict]:
    """Busca un contacto por su nombre (búsqueda parcial)."""
    contacts = load_contacts()
    name_lower = name.lower()
    for contact in contacts:
        if name_lower in contact.get("name", "").lower():
            return contact
    return None


def add_or_update_contact(
    name: str,
    phone: str,
    event_id: Optional[str] = None,
    reservation_date: Optional[str] = None
) -> Dict:
    """
    Agrega un nuevo contacto o actualiza uno existente.
    
    Args:
        name: Nombre del cliente
        phone: Número de WhatsApp (con código de país)
        event_id: ID del evento de Calendar asociado
        reservation_date: Fecha de la reserva (ISO format)
    
    Returns:
        El contacto guardado
    """
    _ensure_contacts_file()
    contacts = load_contacts()
    
    # Normalizamos el número
    normalized_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    formatted_phone = f"+{normalized_phone}" if not normalized_phone.startswith("+") else phone
    
    existing = find_contact_by_phone(phone)
    
    if existing:
        # Actualizar contacto existente
        existing["name"] = name
        existing["phone"] = formatted_phone
        if event_id:
            existing["event_ids"] = existing.get("event_ids", [])
            if event_id not in existing["event_ids"]:
                existing["event_ids"].append(event_id)
        existing["updated_at"] = datetime.now().isoformat()
        contact = existing
    else:
        # Crear nuevo contacto
        contact = {
            "id": len(contacts) + 1,
            "name": name,
            "phone": formatted_phone,
            "event_ids": [event_id] if event_id else [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        contacts.append(contact)
    
    save_contacts(contacts)
    return contact


def get_contact_history(phone: str) -> List[Dict]:
    """Obtiene el historial de reservas de un contacto."""
    contact = find_contact_by_phone(phone)
    if not contact or "event_ids" not in contact:
        return []
    
    # Los event_ids están guardados, pero para obtener detalles
    # necesitaríamos consultar Google Calendar
    # Por ahora devolvemos los IDs
    return [{"event_id": eid} for eid in contact.get("event_ids", [])]


def extract_whatsapp_from_description(description: str) -> Optional[str]:
    """
    Extrae el número de WhatsApp de una descripción de evento.
    
    Args:
        description: Texto de descripción del evento
    
    Returns:
        Número de WhatsApp o None si no se encuentra
    """
    if not description:
        return None
    
    # Busca "WhatsApp: [número]"
    import re
    match = re.search(r'WhatsApp:\s*([+\d\s-]+)', description, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_name_from_description(description: str) -> Optional[str]:
    """
    Extrae el nombre del cliente de una descripción de evento.
    
    Args:
        description: Texto de descripción del evento
    
    Returns:
        Nombre del cliente o None si no se encuentra
    """
    if not description:
        return None
    
    # Busca "Reserva para [N] personas a nombre de [Nombre]"
    import re
    # Formato esperado: "a nombre de [Nombre]." o "a nombre de [Nombre]. WhatsApp: [número]"
    match = re.search(r'a nombre de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\s]+?)(?:\.|WhatsApp|$)', description, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


# Endpoint de integración con Google Calendar
def register_reservation_contact(
    summary: str,
    description: str,
    event_id: str
) -> Optional[Dict]:
    """
    Registra el contacto de una reserva en el archivo de contactos.
    
    Args:
        summary: Summary del evento (ej: "Reserva: Juan (4 personas)")
        description: Descripción del evento (contiene WhatsApp)
        event_id: ID del evento en Google Calendar
    
    Returns:
        El contacto guardado o None
    """
    phone = extract_whatsapp_from_description(description)
    name = extract_name_from_description(description)
    
    if not phone or not name:
        return None
    
    return add_or_update_contact(name=name, phone=phone, event_id=event_id)


# Ejemplo de uso
if __name__ == "__main__":
    # Probar el registro
    test_contact = add_or_update_contact(
        name="Juan Pérez",
        phone="+5491112345678",
        event_id="test_event_123"
    )
    print(f"Contacto guardado: {test_contact}")
    
    # Buscar contacto
    found = find_contact_by_phone("+5491112345678")
    print(f"Contacto encontrado: {found}")