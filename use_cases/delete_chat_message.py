import json

from services.mongo_service import MongoService

async def delete_message_use_case(mongo_service: MongoService, websocket, client_id, chat_id, message_content):
    """
        Deletes a message from the conversation history.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
            message_content (str): The content of the message to delete.
        """
    await mongo_service.delete_message(client_id, chat_id, message_content)
    await websocket.send_text(json.dumps({"type": "message_deleted", "content": None}))