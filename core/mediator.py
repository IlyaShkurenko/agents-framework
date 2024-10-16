# core/mediator.py

from typing import Any, Optional
from core.base_agent import BaseAgent
from services.mongo_service import MongoService
from pyee.asyncio import AsyncIOEventEmitter
import json

class Mediator:
    """
    The Mediator class manages the flow between agents and maintains client states.
    """

    def __init__(self):
        self.agents = {}
        self.mongo_service = MongoService()
        self.default_agent = 'init_agent'
        self.event_emitter = AsyncIOEventEmitter()

    def register_agent(self, agent: BaseAgent):
        """
        Registers an agent with the mediator.

        Args:
            agent (BaseAgent): The agent to register.
        """
        self.agents[agent.name] = agent

    def emitMessage(self, message_type: str, content: Optional[Any] = None):
        """
        Emits a message to all subscribers, such as WebSocket handlers.

        Args:
            message_type (str): The type of the message (e.g., 'message_response').
            content (str): The message content.
        """
        print('in mediator emitMessage')
        self.event_emitter.emit('message-response', { "content": content, "type": message_type })

    async def handle_message(self, client_id: str, chat_id: str, message: str):
        """
        Handles incoming messages from clients.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
            message (str): The message from the client.

        Returns:
            str: The response to the client.
        """
        state = await self.mongo_service.get_state(client_id, chat_id)
        current_agent_name = state.get('current_agent', self.default_agent)
        print(current_agent_name)
        agent = self.agents.get(current_agent_name)
        state['current_agent'] = current_agent_name

        conversation_history = state.get('conversation_history', [])
        state['conversation_history'] = conversation_history
        state['chat_id'] = chat_id
        state['client_id'] = client_id

        response = await agent.execute(message=message, state=state)

        # Update conversation history with assistant's response (already handled in agents)
        await self.mongo_service.update_state(client_id, chat_id, state)
        return response
    
    async def get_conversation_history(self, client_id: str, chat_id: str):
        """
        Retrieves the conversation history for a given client and chat.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.

        Returns:
            list: The conversation history.
        """
        state = await self.mongo_service.get_state(client_id, chat_id)
        conversation_history = state.get('conversation_history', [])

        filtered_history = []
        for message in conversation_history:
            if message['role'] == 'system':
                continue

            content = message['content']

            try:
                parsed_content = json.loads(content)
                if isinstance(parsed_content, dict) and 'message' in parsed_content and not parsed_content['message']:
                    continue
            except (json.JSONDecodeError, TypeError):
                parsed_content = content

            filtered_history.append({
                'sender': 'ai' if message['role'] == 'assistant' else 'user',
                'content': parsed_content,
                'agent': message['agent']
            })

        return filtered_history

    async def delete_message(self, client_id: str, chat_id: str, message_content: str):
        """
        Deletes a message from the conversation history.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
            message_content (str): The content of the message to delete.
        """
        await self.mongo_service.delete_message(client_id, chat_id, message_content)
    
    def redirect(self, client_id: str, new_agent_name: str, message: str, state: dict):
        """
        Redirects the client to a new agent.

        Args:
            client_id (str): The unique client identifier.
            new_agent_name (str): The name of the agent to redirect to.
            message (str): The message from the client.
            state (dict): The current state of the client.

        Returns:
            str: The response from the new agent.
        """
        new_agent = self.agents.get(new_agent_name)
        if new_agent:
            state['currentAgentName'] = new_agent_name
            response = new_agent.handle_message(client_id, message, state)
            return response
        else:
            return "Sorry, I cannot assist with that request."
