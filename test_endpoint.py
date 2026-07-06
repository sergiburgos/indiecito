# -*- coding: utf-8 -*-
import os
import json
import traceback
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from poolside_client import chat_with_poolside, get_poolside_api_key

api_key = get_poolside_api_key()
print('API Key check:', 'OK' if api_key else 'MISSING')

with open('prompt_base.md', 'r', encoding='utf-8') as f:
    SISTEMA_PROMPT = f.read()

print('Prompt loaded, length:', len(SISTEMA_PROMPT))

current_date_str = datetime.now().strftime('Hoy es %A, %d de %B de %Y.')
message = 'hola'
message_with_context = f'Contexto de la fecha actual: {current_date_str}. Mensaje del usuario: "{message}"'

import asyncio

async def test():
    result = await chat_with_poolside(
        message=message_with_context,
        history=[],
        system_prompt=SISTEMA_PROMPT
    )
    # Usar encoding seguro para imprimir
    safe_result = result.encode('utf-8', errors='replace').decode('utf-8')
    print(f'Result: {safe_result[:200]}')
    return result

asyncio.run(test())