# services/mongo_service.py

from motor.motor_asyncio import AsyncIOMotorClient

class MongoService:
    """
    The MongoService handles interactions with MongoDB to store client states.
    """

    def __init__(self):
        # Replace with your MongoDB connection string
        self.client = AsyncIOMotorClient('mongodb+srv://illiashkurenko98:3JYbiCLJXhLhJK5u@cluster0.66i1z.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
        self.db = self.client['chatbot_db']
        self.agent_collection = self.db['agent_states']
        self.mediator_collection = self.db['mediator_states']

    def _get_collection(self, collection_name: str):
        if collection_name == 'agent_states':
            return self.agent_collection
        elif collection_name == 'mediator_states':
            return self.mediator_collection
        else:
            raise ValueError(f"Invalid collection name: {collection_name}")

    async def _get_state(self, client_id: str, chat_id: str, collection_name: str) -> dict:
        """
        Retrieves the state for a given client from the specified collection.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
            collection_name (str): The name of the collection to query.

        Returns:
            dict: The client state.
        """
        collection = self._get_collection(collection_name)
        state = await collection.find_one({'client_id': client_id, 'chat_id': chat_id})
        if state:
            state.pop('_id', None)
            return state
        return None

    async def _update_state(self, client_id: str, chat_id: str, state: dict, collection_name: str):
        """
        Updates the state for a given client in the specified collection.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
            state (dict): The state to update.
            collection_name (str): The name of the collection to update.
        """
        collection = self._get_collection(collection_name)
        await collection.update_one(
            {'client_id': client_id, 'chat_id': chat_id}, 
            {'$set': state}, 
            upsert=True
        )

    async def get_agent_state(self, client_id: str, chat_id: str):
        """
        Retrieves the state for a given client.

        Args:
            client_id (str): The unique client identifier.

        Returns:
            dict: The client state.
        """
        return await self._get_state(client_id, chat_id, 'agent_states')

    async def update_agent_state(self, client_id: str, chat_id: str, state: dict):
        """
        Updates the state for a given client.

        Args:
            client_id (str): The unique client identifier.
            state (dict): The state to update.
        """
        await self._update_state(client_id, chat_id, state, 'agent_states')

    async def get_mediator_state(self, client_id: str, chat_id: str):
        """
        Retrieves the state for a given client.

        Args:
            client_id (str): The unique client identifier.

        Returns:
            dict: The client state.
        """
        return await self._get_state(client_id, chat_id, 'mediator_states')

    async def update_mediator_state(self, client_id: str, chat_id: str, state: dict):
        """
        Updates the state for a given client.

        Args:
            client_id (str): The unique client identifier.
            state (dict): The state to update.
        """
        await self._update_state(client_id, chat_id, state, 'mediator_states')      

    async def delete_message(self, client_id: str, chat_id: str, message_content: str):
        """
        Deletes a message from the conversation history.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
            message_content (str): The content of the message to delete.
        """
        await self.agent_collection.update_one({'client_id': client_id, 'chat_id': chat_id}, {'$pull': {'conversation_history': {'content': message_content}}})
