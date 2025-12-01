import os
import google.generativeai as genai
from dotenv import load_dotenv

# Carga las variables de entorno para obtener la clave de API
load_dotenv()

def check_available_models():
    """
    Este script se conecta a la API de Google y lista los modelos
    disponibles que soportan el método 'generateContent'.
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "YOUR_API_KEY":
            print("Error: No se ha encontrado la GOOGLE_API_KEY en el archivo .env.")
            print("Por favor, asegúrate de que el archivo .env está en la misma carpeta y contiene tu clave.")
            return

        print("Conectando a la API de Google para listar modelos...\n")
        genai.configure(api_key=api_key)

        print("Modelos disponibles que soportan generación de contenido:")
        print("-------------------------------------------------------")
        
        model_found = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_found = True
                print(f"- {m.name}")
        
        if not model_found:
            print("No se encontraron modelos compatibles. Esto podría ser un problema con la clave de API o los permisos de tu cuenta.")

        print("\n-------------------------------------------------------")
        print("Copia la lista de arriba y pégala en el chat para que podamos usar el nombre correcto.")

    except Exception as e:
        print(f"\nHa ocurrido un error inesperado al intentar conectar con la API de Google:")
        print(f"Error: {e}")
        print("\nPor favor, verifica que tu clave de API sea correcta y no haya expirado.")

if __name__ == "__main__":
    check_available_models()
