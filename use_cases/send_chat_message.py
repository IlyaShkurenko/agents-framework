import json
from pydantic import ValidationError

from core.mediator import Mediator

async def send_chat_message_use_case(mediator: Mediator, websocket, message_content):
    try:
        await mediator.handle_message(message_content)
    except ValidationError as ve:
        print(ve)
        await websocket.send_text(json.dumps({"type": "validation_error", "content": str(ve)}))
    except Exception as e:
        print(e)
        await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))