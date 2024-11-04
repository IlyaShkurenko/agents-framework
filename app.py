from pprint import pprint
import random
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from agents.hashtags_agent.main import HashtagsAgent
from agents.image_agent.main import ImageAgent
from agents.image_agent.tools.generate_image_tool import GenerateImageTool
from agents.visual_effects_agent.main import VisualEffectsAgent
from core.mediator import Mediator
from agents.init_agent.main import InitAgent
from agents.caption_agent.main import CaptionAgent
from rich.traceback import install
from typing import List
import json
import asyncio
import traceback

from core.utils.parse_message import parse_message
from services.generative_ai_service import GenerativeAIServiceClient
from services.mongo_service import MongoService
from use_cases.delete_chat_message import delete_message_use_case
from use_cases.get_chat_history import get_history_use_case
from use_cases.init_chat import init_chat_use_case
from use_cases.send_chat_message import send_chat_message_use_case

install()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

generative_ai_service_client = GenerativeAIServiceClient("ws://localhost:8001/ws/generative_ai_api")

# Initialize the mediator
mediator = Mediator()
mongo_service = MongoService()

# Register agents
caption_agent = CaptionAgent(mediator)
hashtags_agent = HashtagsAgent(mediator)
image_agent = ImageAgent(mediator)
visual_effects_agent = VisualEffectsAgent(mediator, [image_agent])
init_agent = InitAgent(mediator, [caption_agent, hashtags_agent, visual_effects_agent])

mediator.register_agent(init_agent)
mediator.register_agent(caption_agent)
mediator.register_agent(hashtags_agent)
mediator.register_agent(visual_effects_agent)
mediator.register_agent(image_agent)

class ConnectionManager:
    def __init__(self):
        self.default_agent = 'init_agent'
        self.chat_tasks = []
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

@app.on_event("startup")
async def startup_event():
    """Connect to the WebSocket service on startup."""
    await generative_ai_service_client.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Close the WebSocket connection on shutdown."""
    await generative_ai_service_client.close()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)

    async def handle_message_response(response):
        try:
            if websocket.application_state == "DISCONNECTED" or websocket.client_state == "DISCONNECTED":
                print("WebSocket is closed, skipping message sending")
                return
            await manager.send_message(json.dumps({"type": response['type'], "content": response['content']}), websocket)
            
        except Exception as e:
            print(f"Weird error: {str(e)}")
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

                if message_type == "init_chat":
                    await init_chat_use_case(mediator, websocket, client_id, chat_id)

                elif message_type == "message":
                    await send_chat_message_use_case(mediator, websocket, message_content)


                elif message_type == "get_history":
                    await get_history_use_case(mongo_service, websocket, client_id, chat_id)


                elif message_type == "delete_message":
                    await delete_message_use_case(mongo_service, websocket, client_id, chat_id, message_content)


                else:
                    await manager.send_message(json.dumps({"type": "error", "content": "Unknown message type"}), websocket)

            except json.JSONDecodeError as e:
                await manager.send_message(json.dumps({"type": "error", "content": "Invalid JSON format: " + str(e)}), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)