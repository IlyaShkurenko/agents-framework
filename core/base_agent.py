from core.base_component import BaseComponent
from abc import ABC, abstractmethod

class BaseAgent(BaseComponent):
    """
    Base class for all agents.
    """

    def __init__(self, mediator, tools=None):
        self.mediator = mediator
        self.tools = tools or []

    async def execute(self, **kwargs):
        """
        Executes the agent's pipeline, which may include using tools.
        """
        message = kwargs.get('message')
        state = kwargs.get('state')
        if message is None or state is None:
            raise ValueError("Missing 'message' or 'state' in kwargs")

        return await self.handle_message(message, state)  # await the async handle_message

    @abstractmethod
    async def handle_message(self, message: str, state: dict):
        """
        Abstract method for handling client messages.
        """
       
