# services/mongo_service.py

from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

class MongoService:
    """
    The MongoService handles interactions with MongoDB to store client states.
    """

    def __init__(self):
        # Replace with your MongoDB connection string
        self.client = AsyncIOMotorClient('mongodb+srv://illiashkurenko98:3JYbiCLJXhLhJK5u@cluster0.66i1z.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
        self.db = self.client['chatbot_db']
        self.collection = self.db['client_states']

    async def get_state(self, client_id: str, chat_id: str):
        """
        Retrieves the state for a given client.

        Args:
            client_id (str): The unique client identifier.

        Returns:
            dict: The client state.
        """
        state = await self.collection.find_one({'client_id': client_id, 'chat_id': chat_id})
        if state:
            state.pop('_id', None)
            return state
        else:
            return {'client_id': client_id}

    async def update_state(self, client_id: str, chat_id: str, state: dict):
        """
        Updates the state for a given client.

        Args:
            client_id (str): The unique client identifier.
            state (dict): The state to update.
        """
        await self.collection.update_one({'client_id': client_id, 'chat_id': chat_id}, {'$set': state}, upsert=True)

    async def delete_message(self, client_id: str, chat_id: str, message_content: str):
        """
        Deletes a message from the conversation history.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
            message_content (str): The content of the message to delete.
        """
        await self.collection.update_one({'client_id': client_id, 'chat_id': chat_id}, {'$pull': {'conversation_history': {'content': message_content}}})
