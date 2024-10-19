# core/mediator.py

import asyncio
import random
from typing import Any, List, Optional, Union
from core.base_agent import BaseAgent
from models.mediator_state_model import MediatorStateModel
from models.task_state_model import TasksStateModel
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
        self.client_id = None
        self.chat_id = None
        self.dependency_tree = {}

    def set_client_data(self, client_id: str, chat_id: str):
        """
        Sets the client data for the mediator.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
        """
        self.mediator_state_model = MediatorStateModel(client_id, chat_id, self.default_agent)
        self.mediator_tasks_state_model = TasksStateModel(client_id, chat_id)

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
        #We need to add the last agent task to the dependencies of the previous agent to connect them
        agent_name = self.call_stack[-1]
        agent = self.agents.get(agent_name)
        agent.add_agent_task_to_dependencies(plan[-1]['id'])
        # Remove the agent's previous actions from the plan and the graph
        start_time = time.time()
        self.neo4j_service.clear_nodes_with_connections()
        # return
        end_time = time.time()
        print(f"Time taken to clear nodes: {end_time - start_time} seconds")
        # self.neo4j_service.delete_agent_actions(agent_name)
        start_time = time.time()
        self.update_agent_plans(agent_name, plan, summary)
        print("\033[31mPlans:\033[0m")
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

    async def handle_message(self, client_id: str, chat_id: str, message: str) -> str:
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

        self.client_id = client_id
        self.chat_id = chat_id

        # If the call stack is empty, get the current agent and push it onto the stack
        if not self.call_stack:
            print('initialize call stack')
            await self.initialize_call_stack()
        # Execute the next agent in the stack
        return await self.execute_next_in_stack(message)

    async def initialize_call_stack(self):
        """Initializes the call stack with the current agent if it is empty."""
        start_time = time.time()
        self.current_agent_name = await self.mediator_state_model.get_current_agent()
        self.call_stack.append(self.current_agent_name)
        print("\033[31mStack initialized:\033[0m")
        pprint(self.call_stack)
        end_time = time.time()
        print(f"Time taken to get current agent: {end_time - start_time} seconds")

    async def execute_next_in_stack(self, message: str) -> str:
        """
        Triggers the execution of the top agent on the stack.

        Args:
            message (str): The message to be processed by the agent.

        Returns:
            str: The response from the executed agent.
        """
        if not self.call_stack:
            return "No agents in the stack."

        agent_name = self.call_stack[-1]
        agent = self.agents.get(agent_name)

        if not agent:
            raise ValueError(f"Agent {agent_name} not found")

        # Set client data in the agent
        await self.set_agent_client_data(agent)
        print('setting current agent', agent_name)
        asyncio.create_task(self.mediator_state_model.set_current_agent(agent_name))

        # Execute the agent's task
        response = await self.run_agent_task(agent, message)

        # If more agents remain, execute the next one
        # if self.call_stack:
        #     return await self.execute_next_in_stack(message)

        return response

    async def set_agent_client_data(self, agent):
        """Sets the client data for the given agent."""
        start_time = time.time()
        await agent.set_client_data(self.client_id, self.chat_id)
        end_time = time.time()
        print(f"Time taken to set client data: {end_time - start_time} seconds")

    async def run_agent_task(self, agent, message: str) -> str:
        """Runs the given agent's task and removes it from the stack."""
        start_time = time.time()
        print(f"before execute {agent.name}")
        response = await agent.execute(message=message)
        print(f"after execute {agent.name}")
        end_time = time.time()
        print(f"Time taken to execute agent: {end_time - start_time} seconds")
        return response
    
    def on_agent_done(self, agent_name: str):
        """
        Called when the agent is executed.
        """
        for i, agent in enumerate(self.call_stack):
            if agent == agent_name:
                self.call_stack.pop(i)
                print(f"Removed {agent_name} from the call stack.")
                return 
        print(f"Agent {agent_name} not found in the call stack.")

    def on_agent_execute(self, agent_name: str):
        agent = self.agents.get(agent_name)
        agent.on_agent_execute()

        
    async def add_agent_to_call_stack(self, parent_agent: str, agent_name: str, task_id: str, message: str):
        """
        Adds a new agent to the call stack and triggers its execution.

        Args:
            agent_name (str): The name of the agent to add.
            message (str): The message to pass to the agent.
        """
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered.")

        self.call_stack.append(agent_name)
        print("\033[31mNew call stack after adding agent:\033[0m")
        pprint(self.call_stack)

        # Add the agent to the dependency tree
        if parent_agent == self.default_agent:
            # If it's the first agent, initialize the root of the tree
            # self.initialize_dependency_tree(agent_name)
            print("\033[31mDependency tree after initialization:\033[0m")
            pprint(self.dependency_tree)
        else:
            # Otherwise, add the agent as a dependency of the parent agent
            self.add_dependency(parent_agent, agent_name, task_id)
            print("\033[31mDependency tree after adding dependency:\033[0m")
            pprint(self.dependency_tree)

        await self.handle_message(self.client_id, self.chat_id, message)
        print('5')

    def add_dependency(self, parent_agent: str, agent_name: str, task_id: str):
        """
        Adds a new agent as a dependency of the specified parent agent.

        Args:
            parent_agent (str): The name of the parent agent.
            agent_name (str): The name of the new agent.
            task_id (str): The task ID associated with the new agent.
        """
        parent_node = self.find_node_in_tree(self.dependency_tree, parent_agent)
        if not parent_node:
            raise ValueError(f"Parent agent {parent_agent} not found in the dependency tree.")

        # Add the new agent as a dependency of the parent agent
        parent_node["dependencies"].append({
            "agent_name": agent_name,
            "task_id": task_id,
            "dependencies": []
        })  

    def initialize_dependency_tree(self, agent_name: str):
        """
        Initializes the dependency tree with the first agent.

        Args:
            agent_name (str): The name of the agent.
            task_id (str): The task ID associated with the agent.
        """
        task_id = next(
        (plan["id"] for plan in self.agent_plans if plan["tool"] == agent_name),
            None
        )
        if task_id is None:
            raise ValueError(f"Task ID for agent {agent_name} not found in agent_plans.")
        self.dependency_tree = {
            "agent_name": agent_name,
            "task_id": task_id,
            "dependencies": []
        }

    def find_node_in_tree(self, current_node: dict, target_agent: str) -> Optional[dict]:
        """
        Recursively searches for a node in the dependency tree by agent name.

    Args:
            current_node (dict): The current node being searched.
            target_agent (str): The name of the agent to find.

        Returns:
            Optional[dict]: The node if found, otherwise None.
        """
        if current_node["agent_name"] == target_agent:
            return current_node

        # Recursively search in the dependencies
        for child in current_node["dependencies"]:
            result = self.find_node_in_tree(child, target_agent)
            if result:
                return result

        return None

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
        # print('nodes')
        # pprint(nodes)
        conversation_history = await self.mongo_service.get_history(client_id, chat_id)

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
