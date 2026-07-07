# Tutorial de Mantenimiento y Despliegue: Indio-Bot

Este documento sirve como una guía de referencia rápida para gestionar, actualizar y solucionar problemas comunes del proyecto Indio-Bot.

## 1. Conceptos Fundamentales

### Entorno Local vs. Producción (Vercel)

*   **Local:** Es tu propia PC. Usas este entorno para hacer y probar cambios en el código. Se ejecuta con el comando `uvicorn`.
*   **Producción:** Es el servidor de Vercel donde la aplicación está en vivo para los usuarios. Los cambios llegan aquí solo cuando los subes a GitHub.

### Variables de Entorno y el archivo `.env`

Las "Variables de Entorno" son una forma segura de guardar datos secretos (como claves de API) sin escribirlos directamente en el código.

*   **Archivo `.env` (SOLO LOCAL):** Este archivo solo existe en tu PC. Contiene las claves para que la aplicación funcione en tu entorno local. **NUNCA debe subirse a GitHub.**
*   **Variables de Entorno en Vercel:** Para que la aplicación funcione en producción, debes configurar estas mismas variables manualmente en el panel de tu proyecto en Vercel.

---

## 2. Credenciales Clave y Cómo Obtenerlas

Necesitas 3 claves secretas para que el proyecto funcione (la IA ahora usa Poolside).

### a) `POOLSIDE_API_KEY` (Para la IA laguna-m.1)

*   **Propósito:** Permite que el bot se comunique con el modelo de lenguaje Poolside (laguna-m.1) para poder chatear.
*   **Dónde se consigue:**
    1.  Ve al [dashboard de Poolside](https://poolside.ai) o usa la API key que ya tienes configurada.
    2.  Obtén tu **Clave de API** de Poolside.
*   **IMPORTANTE:** Si esta clave se expone (por ejemplo, al subir el archivo `.env` a GitHub), Poolside la bloqueará y el chat dejará de funcionar, devolviendo un error.

### b) `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` (Para Google Calendar)

*   **Propósito:** Identifican a tu aplicación ante Google para permitirle pedir permiso para usar el calendario.
*   **Dónde se consiguen:**
    1.  En la [Consola de Google Cloud](https://console.cloud.google.com/apis/credentials), dentro de tu proyecto, haz clic en **"+ CREAR CREDENCIALES"**.
    2.  Selecciona **"ID de cliente de OAuth"**.
    3.  Elige **"Aplicación de escritorio"** como tipo de aplicación.
    4.  Tras crearla, haz clic en **"DESCARGAR JSON"**.
    5.  Renombra el archivo descargado a `credentials.json` y guárdalo en la raíz de tu proyecto. Los valores están dentro de este archivo.

### c) `GOOGLE_REFRESH_TOKEN` (Para Google Calendar)

*   **Propósito:** Es una "llave maestra" que permite a tu aplicación obtener acceso continuo al calendario sin tener que pedir permiso cada vez.
*   **Cómo se genera (proceso local):**
    1.  Asegúrate de que el archivo `credentials.json` del paso anterior esté en la carpeta de tu proyecto.
    2.  **Elimina cualquier archivo `token.json` antiguo** que tengas en la carpeta.
    3.  Abre una terminal, activa el entorno virtual (`.\venv\Scripts\activate`) y ejecuta:
        ```bash
        python google_calendar.py
        ```
    4.  Se abrirá un navegador. Inicia sesión con la cuenta de Google que gestionará el calendario y concede los permisos.
    5.  Al terminar, se creará un **nuevo archivo `token.json`** en tu carpeta.
    6.  Abre `token.json`. El contenido será extraño (formato `pickle`), pero dentro encontrarás el `refresh_token`. Cópialo con cuidado.

---

## 3. Ejecutar el Proyecto en tu PC

1.  **Activa el entorno virtual:**
    ```bash
    .\venv\Scripts\activate
    ```
2.  **Instala las dependencias (si es necesario):**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Crea tu archivo `.env`:**
    *   En la raíz del proyecto, crea un archivo llamado `.env`.
    *   Dentro de él, pon las 3 claves que obtuviste:
        ```
        POOLSIDE_API_KEY="tu_api_key_de_poolside"
        GOOGLE_CLIENT_ID="...apps.googleusercontent.com"
        GOOGLE_CLIENT_SECRET="GOCSPX-..."
        GOOGLE_REFRESH_TOKEN="1//04g..."
        ```
4.  **Inicia el servidor:**
    ```bash
    uvicorn main:app --reload
    ```
5.  Abre [http://127.0.0.1:8000](http://127.0.0.1:8000) en tu navegador.

---

## 4. Flujo de Actualización (GitHub y Vercel)

1.  **Haz tus cambios** en el código.
2.  **Guarda los cambios en Git:**
    ```bash
    git add .
    git commit -m "Un mensaje que describa tu cambio"
    ```
3.  **Sube los cambios a GitHub:**
    ```bash
    git push origin master
    ```
4.  **Vercel se despliega automáticamente:** Al recibir los cambios, Vercel iniciará un nuevo despliegue. Puedes verlo en tu dashboard.

---

## 5. Solución de Problemas Comunes

### Problema: El chat no responde y da un error.

*   **Causa más probable:** Tu `POOLSIDE_API_KEY` no está configurada o está incorrecta.
*   **Solución:**
    1.  Verifica que tienes una `POOLSIDE_API_KEY` válida.
    2.  Actualiza la variable de entorno en el **dashboard de Vercel**.
    3.  En Vercel, ve a la pestaña "Deployments" y haz clic en "Redeploy" en el último despliegue.

### Problema: El chat funciona, pero las reservas fallan con un error `403 Forbidden`.

*   **Causa más probable:** La "Google Calendar API" no está habilitada en tu proyecto de Google Cloud.
*   **Solución:**
    1.  Ve a la [Biblioteca de APIs de Google Cloud](https://console.cloud.google.com/apis/library).
    2.  Busca "Google Calendar API".
    3.  Haz clic en "Habilitar". No necesitas redesplegar en Vercel, el cambio es inmediato.

### Problema: Las reservas fallan con otros errores.

*   **Causa más probable:** Las credenciales de Google Calendar (`CLIENT_ID`, `SECRET` o `REFRESH_TOKEN`) son incorrectas en las variables de entorno de Vercel.
*   **Solución:**
    1.  Sigue el **Paso 2c** de este tutorial para generar un `refresh_token` nuevo y fresco.
    2.  Verifica con mucho cuidado que los 3 valores en el dashboard de Vercel coinciden con los que acabas de generar.
    3.  Redespliega la aplicación en Vercel.

### Problema: He subido cambios pero no los veo en la web.

*   **Causa más probable:** La caché de tu navegador o del Service Worker.
*   **Solución:**
    1.  Abre la web en un navegador de escritorio.
    2.  Presiona `F12` para abrir las herramientas de desarrollador.
    3.  Ve a la pestaña "Application" -> "Clear storage".
    4.  Haz clic en "Clear site data".
    5.  Recarga la página.

---

## 6. Gestión de Contactos WhatsApp

### ¿Qué es?

Cuando se crea una reserva y el cliente proporciona su número de WhatsApp, este se guarda automáticamente en `contacts.json` para futuras referencias.

### Endpoints de Contactos

- **GET `/api/contacts`** - Lista todos los contactos registrados
- **POST `/api/contacts/search`** - Busca un contacto por nombre o teléfono
- **GET `/api/contacts/phone/{phone}`** - Obtiene un contacto específico con su historial

### Formato del archivo contacts.json

```json
[
  {
    "id": 1,
    "name": "Juan Pérez",
    "phone": "+5491112345678",
    "event_ids": ["abc123", "def456"],
    "created_at": "2025-12-01T10:00:00",
    "updated_at": "2025-12-01T10:00:00"
  }
]
```

### Nota Importante

El archivo `contacts.json` está en `.gitignore` y **no se sube a GitHub**. Si necesitas persistencia en producción, considera usar una base de datos (PostgreSQL, MongoDB) en lugar de este archivo local.
