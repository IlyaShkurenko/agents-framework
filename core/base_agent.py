from core.base_component import BaseComponent
from abc import ABC, abstractmethod

from models.agent_state_model import AgentStateModel

class BaseAgent(BaseComponent):
    """
    Base class for all agents.
    """

    def __init__(self, mediator, tools=None):
        self.mediator = mediator
        self.tools = tools or []

    async def set_client_data(self, client_id: str, chat_id: str):
        """
        Sets the client data for the agent.
        """
        self.client_id = client_id
        self.chat_id = chat_id
        self.state_model = AgentStateModel(client_id, chat_id, self.name)
        await self.state_model.load_state()

    async def execute(self, **kwargs):
        """
        Executes the agent's pipeline, which may include using tools.
        """
        message = kwargs.get('message')
        if message is None:
            raise ValueError("Missing 'message' in kwargs")
        response = await self.handle_message(message)
        await self.state_model.save_state()
        return response

    @abstractmethod
    async def handle_message(self, message: str):
        """
        Abstract method for handling client messages.
        """
       
