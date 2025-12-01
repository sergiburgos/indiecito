// Service Worker Registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/service-worker.js').then(registration => {
      console.log('ServiceWorker registration successful with scope: ', registration.scope);
    }, err => {
      console.log('ServiceWorker registration failed: ', err);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const chatMessages = document.getElementById('chat-messages');
    let chatHistory = [];
    let lastFoundEventId = null; // Variable para almacenar el último event_id encontrado
    let loadingTimerId = null; // Para el temporizador de respuesta lenta
    let slowResponseWarningElement = null; // Para el mensaje de advertencia

    // --- Funciones principales de la interfaz ---

    function addMessage(sender, text, messageId = '') {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', sender);
        if (messageId) {
            messageElement.id = messageId;
        }
        messageElement.innerHTML = marked.parse(text);
        chatMessages.appendChild(messageElement);
        scrollToBottom();
        return messageElement;
    }

    function showLoadingIndicator() {
        if (!document.getElementById('loading-indicator')) {
            const loadingElement = document.createElement('div');
            loadingElement.classList.add('message', 'bot', 'loading');
            loadingElement.id = 'loading-indicator';
            loadingElement.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
            chatMessages.appendChild(loadingElement);
            scrollToBottom();

            // Iniciar temporizador para el mensaje de respuesta lenta
            loadingTimerId = setTimeout(() => {
                if (document.getElementById('loading-indicator')) { // Asegurarse de que el indicador siga visible
                    if (!slowResponseWarningElement) {
                        slowResponseWarningElement = document.createElement('div');
                        slowResponseWarningElement.classList.add('message', 'bot', 'warning');
                        slowResponseWarningElement.textContent = 'Por favor, espera. Estamos gestionando tu petición, puede tardar un poco.';
                        chatMessages.appendChild(slowResponseWarningElement);
                        scrollToBottom();
                    }
                }
            }, 10000); // 10 segundos
        }
    }

    function hideLoadingIndicator() {
        const loadingIndicator = document.getElementById('loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
        // Limpiar temporizador y mensaje de respuesta lenta
        if (loadingTimerId) {
            clearTimeout(loadingTimerId);
            loadingTimerId = null;
        }
        if (slowResponseWarningElement) {
            slowResponseWarningElement.remove();
            slowResponseWarningElement = null;
        }
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // --- Lógica principal del Chat ---

    chatForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const messageText = messageInput.value.trim();
        if (messageText === '') return;

        handleUserMessage(messageText);
        messageInput.value = '';
        messageInput.focus();
    });
    
    async function handleUserMessage(messageText, isSystemMessage = false) {
        // Añade el mensaje del usuario/sistema a la UI y al historial
        if (!isSystemMessage) {
            addMessage('user', messageText);
        }
        // Solo añade el mensaje al historial si no es un mensaje del sistema
        // y se utilizará para futuras interacciones del modelo.
        // El último mensaje del usuario se envía directamente en la petición al bot.
        if (!isSystemMessage) {
            chatHistory.push({ role: 'user', parts: [{ text: messageText }] });
        }
        
        showLoadingIndicator();
        
        try {
            // Se pasa messageText y el historial. Si es un mensaje de sistema,
            // messageText será el mensaje del sistema para el bot.
            const botResponse = await getBotResponse(messageText, chatHistory);
            await handleBotResponse(botResponse);
        } catch (error) {
            console.error('Error en el flujo principal:', error);
            addMessage('bot', 'Lo siento, hubo un error de conexión con el servidor.');
        } finally {
            hideLoadingIndicator();
        }
    }

    async function getBotResponse(messageText, currentHistory) {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText, history: currentHistory }),
        });
        if (!response.ok) {
            throw new Error(`Error del servidor de chat: ${response.statusText}`);
        }
        return await response.json();
    }

    async function handleBotResponse(responseJson) {
        console.log('handleBotResponse received:', responseJson); // Debug log
        
        if (responseJson && typeof responseJson === 'object') { // Asegura que sea un objeto
            if (responseJson.action) {
                console.log('Bot solicitó acción:', responseJson.action, responseJson.payload); // Debug log
                await performCalendarAction(responseJson.action, responseJson.payload);
            } else if (responseJson.reply) {
                console.log('Bot respondió:', responseJson.reply); // Debug log
                addMessage('bot', responseJson.reply);
                chatHistory.push({ role: 'model', parts: [{ text: responseJson.reply }] });
            } else {
                console.error('Error: Estructura de respuesta inesperada del bot:', responseJson); // Debug log
                addMessage('bot', 'Error: Respuesta inesperada del bot.');
                chatHistory.push({ role: 'model', parts: [{ text: 'Error: Respuesta inesperada del bot.' }] });
            }
        } else {
             console.error('Error: La respuesta del bot no es un objeto JSON válido:', responseJson); // Debug log
             addMessage('bot', 'Error: La respuesta del bot no es un objeto JSON válido.');
             chatHistory.push({ role: 'model', parts: [{ text: 'Error: La respuesta del bot no es un objeto JSON válido.' }] });
        }
    }

    async function performCalendarAction(action, payload) {
        let endpoint = '';
        switch (action) {
            case 'create_event': endpoint = '/api/create_event'; break;
            case 'find_events': endpoint = '/api/find_events'; break;
            case 'cancel_event': endpoint = '/api/cancel_event'; break;
            case 'update_event': endpoint = '/api/update_event'; break;
            default:
                addMessage('bot', 'Error: El bot intentó realizar una acción desconocida.');
                return;
        }

        if (action === 'cancel_event' || action === 'update_event') {
            // Regex para un ID de evento de Google Calendar (26 caracteres alfanuméricos)
            const googleEventIdRegex = /^[a-z0-9]{26}$/;

            if (payload.event_id && !googleEventIdRegex.test(payload.event_id) && lastFoundEventId) {
                console.warn(`ADVERTENCIA: Bot envió un event_id '${payload.event_id}' que no parece válido para la acción ${action}. Usando lastFoundEventId: '${lastFoundEventId}'`);
                payload.event_id = lastFoundEventId;
            } else if (!payload.event_id && lastFoundEventId) {
                console.warn(`ADVERTENCIA: Bot no envió event_id para la acción ${action}. Usando lastFoundEventId: '${lastFoundEventId}'`);
                payload.event_id = lastFoundEventId;
            } else if (!payload.event_id && !lastFoundEventId) {
                // Si el bot no envía ID y no tenemos uno guardado, lanzamos un error
                throw new Error(`No se pudo obtener un ID de evento válido para la acción ${action}.`);
            }
        }

        try {
            const actionResponse = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await actionResponse.json();

            if (!actionResponse.ok) {
                throw new Error(result.detail || 'La acción falló sin detalles.');
            }

            let systemMessage;
            if (action === 'find_events' && result.events && result.events.length > 0) {
                // Si encontramos eventos, extraemos el ID del primero para que el bot lo use
                const firstEventId = result.events[0].id;
                console.log('firstEventId extraído de find_events:', firstEventId); // Debug log
                lastFoundEventId = firstEventId; // Almacenamos el ID válido
                systemMessage = `Sistema: La acción '${action}' fue ejecutada. El resultado es: ${JSON.stringify(result)}. ID de evento relevante: ${firstEventId}. Informa al usuario de manera conversacional.`;
            } else { // Para create_event, cancel_event, update_event y cualquier otra acción de calendario
                if (result.status === 'success') {
                    systemMessage = `Sistema: La acción '${action}' con payload ${JSON.stringify(payload)} fue ejecutada exitosamente. El resultado es: ${JSON.stringify(result)}. Confirma al usuario de manera conversacional.`;
                } else { // Si result.status es "error" o no es "success"
                    // Construir el mensaje de error personalizado
                    let gestionType = "";
                    if (action === 'create_event') gestionType = "reserva";
                    else if (action === 'update_event') gestionType = "modificación";
                    else if (action === 'cancel_event') gestionType = "cancelación";
                    
                    const customErrorMessage = `No hemos podido gestionar su ${gestionType} por problemas técnicos temporales. Puede probar de realizar la gestión más tarde o enviar un WhatsApp a Ingrid Villar al 3751 546964 para que le gestione su ${gestionType}.`;
                    
                    systemMessage = `Sistema: ${customErrorMessage} (Detalle técnico: ${result.message || 'Error desconocido'}). Informa al usuario de este mensaje personalizado.`;
                }
            }
            await handleUserMessage(systemMessage, true);

        } catch (error) {
            console.error(`Error al ejecutar la acción '${action}':`, error);
            // Mensaje de error personalizado para fallos de red/frontend
            let gestionType = "";
            if (action === 'create_event') gestionType = "reserva";
            else if (action === 'update_event') gestionType = "modificación";
            else if (action === 'cancel_event') gestionType = "cancelación";

            const customErrorMessage = `No hemos podido gestionar su ${gestionType} por problemas técnicos temporales del sistema. Puede probar de realizar la gestión más tarde o enviar un WhatsApp a Ingrid Villar al 3751 546964 para que le gestione su ${gestionType}.`;
            
            const systemMessage = `Sistema: ${customErrorMessage} (Detalle técnico: ${error.message}). Informa al usuario de este mensaje personalizado.`;
            await handleUserMessage(systemMessage, true);
        }
    }

    // --- Mensaje de Bienvenida ---
    function initializeChat() {
        const welcomeMessage = "Hola, Mi nombre es Indio-Bot, Tu agente de IA para reservas de Heladeria y Cafeteria El Indiecito.";
        addMessage('bot', welcomeMessage);
        chatHistory.push({ role: 'model', parts: [{ text: welcomeMessage }] });
    }

    initializeChat();
});
