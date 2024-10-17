# core/mediator.py

import random
from typing import Any, List, Optional, Union
from core.base_agent import BaseAgent
from models.mediator_state_model import MediatorStateModel
from services.mongo_service import MongoService
from pyee.asyncio import AsyncIOEventEmitter
import json
import time
from pprint import pprint

from services.neo4j_service import Neo4jService

class Mediator:
    """
    The Mediator class manages the flow between agents and maintains client states.
    """

    def __init__(self):
        self.agents = {}
        self.mongo_service = MongoService()
        self.default_agent = 'init_agent'
        self.call_stack = []
        self.event_emitter = AsyncIOEventEmitter()
        self.neo4j_service = Neo4jService(uri="neo4j+s://e9eac158.databases.neo4j.io", user="neo4j", password="W9GvvgDF2RYDrTtifjvAcbMK4-ukDCd4essDNxus3R4")
        self.agent_plans = []
        self.agents_tasks = {}
        self.current_agent_name = None

    def set_client_data(self, client_id: str, chat_id: str):
        """
        Sets the client data for the mediator.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
        """
        self.mediator_state_model = MediatorStateModel(client_id, chat_id, self.default_agent)

    def register_agent(self, agent: BaseAgent):
        """
        Registers an agent with the mediator.

        Args:
            agent (BaseAgent): The agent to register.
        """
        self.agents[agent.name] = agent

    def get_agent_id_by_name(self, agent_name: str) -> Optional[str]:
        for task in self.agent_plans:
            if task['tool'] == agent_name:
                return task['id']
        return None

    def update_agent_plans(self, agent_name: str, plan: list[dict], description: str):
        # If the agent_name is the default agent and the list is empty, add the default agent entry
            if agent_name == self.default_agent and not self.agent_plans:
                self.agent_plans.extend(plan)

                default_agent_entry = {
                    "tool": self.default_agent,
                    "description": description,
                    "id": random.randint(10**7, 10**8 - 1),
                    "arguments": [],
                    "dependencies": [plan[-1]['id']]
                }
                self.agent_plans.append(default_agent_entry)
                return

            # Find the index of the first element where 'tool' matches agent_name
            found_index = next((i for i, task in enumerate(self.agent_plans) if task['tool'] == agent_name), None)
            dependencies_to_remove = set([])
            if found_index is not None:
                # Update dependencies for the agent
                last_task = plan[-1]
            
                matching_task = next((task for task in self.agent_plans if task['tool'] == last_task['tool']), None)
                # Insert the new plan at the position of the old one
                self.agent_plans[found_index:found_index] = plan
                if matching_task:
                    matching_task_id = matching_task['id']
                    dependencies_to_remove = set([matching_task_id])
                    def collect_dependencies(task_id):
                        for task in self.agent_plans:
                            if task['id'] == task_id:
                                dependencies_to_remove.update(task.get('dependencies', []))
                                for dep_id in task.get('dependencies', []):
                                    collect_dependencies(dep_id)

                    collect_dependencies(matching_task_id)

                    dependencies = self.agent_plans[found_index + len(plan)].get('dependencies', [])
                    if matching_task_id in dependencies:
                        dependencies.remove(matching_task_id)

                self.agent_plans[found_index + len(plan)]['dependencies'].append(last_task['id'])

            else:
                # If the agent doesn't exist, simply append the plan at the end
                self.agent_plans.extend(plan)
            
            if dependencies_to_remove:
                self.agent_plans = [task for task in self.agent_plans if task['id'] not in dependencies_to_remove]

    def emit_message(self, message_type: str, content: Optional[Any] = None):
        """
        Emits a message to all subscribers, such as WebSocket handlers.

        Args:
            message_type (str): The type of the message (e.g., 'message_response').
            content (str): The message content.
        """
        print('in mediator emitMessage')
        self.event_emitter.emit('message-response', { "content": content, "type": message_type })
        
    async def emit_plan(self, plan: List[dict], summary: str, agent_name: str):
        """
        Receives the agent's plan and summary, and updates the overall plan and knowledge graph.

        Args:
            plan (List[dict]): The agent's plan.
            summary (str): Summary of the plan.
            agent_name (str): The agent's name.
            agent_description (str): Description of the agent.
        """
        # Remove the agent's previous actions from the plan and the graph
        start_time = time.time()
        self.neo4j_service.clear_nodes_with_connections()
        # return
        end_time = time.time()
        print(f"Time taken to clear nodes: {end_time - start_time} seconds")
        # self.neo4j_service.delete_agent_actions(agent_name)
        start_time = time.time()
        self.update_agent_plans(agent_name, plan, summary)
        print('Plans:')
        pprint(self.agent_plans)
        print('task id',self.get_agent_id_by_name(agent_name))
        # self.neo4j_service.create_or_update_agent(agent_name, self.agents[agent_name].description, summary, task_id=self.get_agent_id_by_name(agent_name))
        # Update the knowledge graph
        for task in self.agent_plans:
            action_id = task['id']
            description = task['description']
            tool_name = task['tool']
            arguments = task['arguments']
            dependencies = task['dependencies']
            is_agent = 'agent' in tool_name.lower()
            # Create or update nodes
            if is_agent:
                # print('agent',tool_name)
                await self.neo4j_service.create_or_update_agent(tool_name, self.agents[tool_name].description, "", task_id=action_id)
            else:
                await self.neo4j_service.create_or_update_tool(tool_name, description, task_id=action_id)
            # self.neo4j_service.create_action(action_id, description, arguments)
            await self.create_tool_to_agent_relationships(tool_name, dependencies)

        # Create relationships
        # self.create_tool_to_agent_relationships(tool_name, dependencies)
        # self.neo4j_service.create_relationships(agent_name, tool_name, action_id, dependencies)
        end_time = time.time()
        print(f"Time taken to update nodes: {end_time - start_time} seconds")


    async def create_tool_to_agent_relationships(self, tool_name: str, dependencies: List[str]):
        for dep_id in dependencies:
            dep_task = next((task for task in self.agent_plans if task['id'] == dep_id), None)
            # print('dep_task',dep_task)
            if dep_task:
                dep_tool_name = dep_task['tool']
                await self.neo4j_service.create_relationship(tool_name, dep_tool_name, "USES")
                # is_agent = 'agent' in dep_tool_name.lower()

                # if is_agent:
                #     self.neo4j_service.create_relationship(tool_name, dep_tool_name, "USES")

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
        if not self.mediator_state_model:
            raise ValueError("Client data not set")
        
        # if not self.call_stack:
        #     self.current_agent_name = await self.get_current_agent_name()
        #     self.call_stack.append(self.current_agent_name)

        start_time = time.time()
        current_agent_name = await self.mediator_state_model.get_current_agent()
        end_time = time.time()
        print(f"Time taken to get current agent: {end_time - start_time} seconds")
        agent: Union[BaseAgent, None] = self.agents.get(current_agent_name)

        if not agent:
            raise ValueError(f"Agent {current_agent_name} not found")
        start_time = time.time()
        await agent.set_client_data(client_id, chat_id)
        end_time = time.time()
        print(f"Time taken to set client data: {end_time - start_time} seconds")
        start_time = time.time()
        response = await agent.execute(message=message)
        end_time = time.time()
        print(f"Time taken to execute agent: {end_time - start_time} seconds")
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
        nodes = await self.neo4j_service.get_all_nodes_and_relationships()
        print('nodes')
        pprint(nodes)
        state = await self.mongo_service.get_agent_state(client_id, chat_id)
        if not state:
            return []
        conversation_history = state.get('conversation_history')

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
