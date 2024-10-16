# # app.py

# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware  # Импортируем CORS Middleware
# from pydantic import BaseModel
# from core.mediator import Mediator
# from agents.init_agent.main import InitAgent
# from agents.caption_agent.main import CaptionAgent
# from rich.traceback import install
# install()

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Initialize the mediator
# mediator = Mediator()

# # Register agents
# caption_agent = CaptionAgent(mediator)
# init_agent = InitAgent(mediator, [caption_agent])

# mediator.register_agent(init_agent)
# mediator.register_agent(caption_agent)

# class MessageRequest(BaseModel):
#     clientId: str
#     message: str
#     chatId: str

# @app.post("/message")
# async def handle_send_message(request: MessageRequest):
#     client_id = request.clientId
#     message = request.message
#     chat_id = request.chatId
#     response = mediator.handle_message(client_id, chat_id, message)
#     return {"response": response}

# @app.get("/messages")
# async def handle_get_messages(request: Request):  # Accepting the Request object
#     clientId = request.query_params.get("clientId")
#     chatId = request.query_params.get("chatId")
#     response = mediator.get_conversation_history(clientId, chatId)
#     return {"response": response}

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from agents.hashtags_agent.main import HashtagsAgent
from agents.visual_effects_agent.main import VisualEffectsAgent
from core.mediator import Mediator
from agents.init_agent.main import InitAgent
from agents.caption_agent.main import CaptionAgent
from rich.traceback import install
from typing import List
import json

install()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the mediator
mediator = Mediator()

# Register agents
caption_agent = CaptionAgent(mediator)
hashtags_agent = HashtagsAgent(mediator)
visual_effects_agent = VisualEffectsAgent(mediator)
init_agent = InitAgent(mediator, [caption_agent, hashtags_agent, visual_effects_agent])

mediator.register_agent(init_agent)
mediator.register_agent(caption_agent)
mediator.register_agent(hashtags_agent)
mediator.register_agent(visual_effects_agent)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)

    async def handle_message_response(response):
        try:
            print('response', response)
            
            if websocket.application_state == "DISCONNECTED" or websocket.client_state == "DISCONNECTED":
                print("WebSocket is closed, skipping message sending")
                return
            
            await manager.send_message(json.dumps({"type": response['type'], "content": response['content']}), websocket)
        except Exception as e:
            # print(f"Error occurred: {str(e)}")
            try:
                if websocket.application_state != "DISCONNECTED" and websocket.client_state != "DISCONNECTED":
                    await manager.send_message(json.dumps({"type": "error", "content": str(e)}), websocket)
            except Exception as inner_e:
                print(f"Error occurred while sending error message: {str(inner_e)}")

    mediator.event_emitter.on('message-response', handle_message_response)

    try:
        while True:
            try:
                data = await websocket.receive_text()

                parsed_data = json.loads(data)
                message_type = parsed_data.get('type')
                message_content = parsed_data.get('content')
                chat_id = parsed_data.get('chatId')

                if message_type == "message":
                    try:
                        response = await mediator.handle_message(client_id, chat_id, message_content)
                        await manager.send_message(json.dumps({"type": "message", "content": response}), websocket)
                    except ValidationError as ve:
                        print(ve)
                        await manager.send_message(json.dumps({"type": "validation_error", "content": str(ve)}), websocket)
                    except Exception as e:
                        print(e)
                        await manager.send_message(json.dumps({"type": "error", "content": str(e)}), websocket)

                elif message_type == "get_history":
                    response = await mediator.get_conversation_history(client_id, chat_id)
                    await manager.send_message(json.dumps({"type": "history", "content": response}), websocket)

                elif message_type == "delete_message":
                    response = await mediator.delete_message(client_id, chat_id, message_content)
                    await manager.send_message(json.dumps({"type": "message_deleted", "content": None}), websocket)

                else:
                    await manager.send_message(json.dumps({"type": "error", "content": "Unknown message type"}), websocket)

            except json.JSONDecodeError as e:
                await manager.send_message(json.dumps({"type": "error", "content": "Invalid JSON format: " + str(e)}), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
