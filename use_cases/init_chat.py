import json

from core.mediator import Mediator


async def init_chat_use_case(mediator: Mediator, websocket, client_id, chat_id):
    await mediator.init_chat(client_id, chat_id)
    await websocket.send_text(json.dumps({"type": "chat_initialized", "content": None}))