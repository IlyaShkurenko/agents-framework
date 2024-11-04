# core/mediator.py

import asyncio
import random
import re
from typing import Any, List, Optional, Union
from core.base_agent import BaseAgent
from models.mediator_state_model import MediatorStateModel
from models.task_state_model import TasksStateModel
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
        self.default_agent = 'init_agent'
        self.call_stack = []
        self.event_emitter = AsyncIOEventEmitter()
        # self.neo4j_service = Neo4jService(uri=os.getenv('NEO4J_URI'),
        #     user=os.getenv('NEO4J_USER'),
        #     password=os.getenv('NEO4J_PASSWORD'))
        self.neo4j_service = Neo4jService(uri="neo4j+s://e9eac158.databases.neo4j.io", user="neo4j", password="W9GvvgDF2RYDrTtifjvAcbMK4-ukDCd4essDNxus3R4")
        self.client_chats = {}
        self.agents_tasks = {}
        self.client_id = None
        self.chat_id = None
        self.initializing = False

    async def init_chat(self, client_id: str, chat_id: str):
        """
        Sets the client data for the mediator.

        Args:
            client_id (str): The unique client identifier.
            chat_id (str): The unique chat identifier.
        """
        print(chat_id)
        self.initializing = True
        # we need to clear data on init new chat
        if not self.client_id:
            self.client_id = client_id

        if self.chat_id != chat_id:
            print('new mediator state model')
            self.chat_id = chat_id
            self.mediator_state_model = MediatorStateModel(client_id, chat_id, self.default_agent)

        if client_id not in self.client_chats:
            self.client_chats[client_id] = {}

        if chat_id not in self.client_chats[client_id]:
            self.client_chats[client_id][chat_id] = {'tasks': []}

        state = await self.mediator_state_model.load_state()

        self.call_stack = state.get('call_stack', [])
        print(self.call_stack)
        if self.call_stack:
            for agent_name in self.call_stack:
                agent = self._get_agent_by_name(agent_name)
                await agent.initialize_agent(client_id=self.client_id, chat_id=self.chat_id, called_agents=self.call_stack)
                
        tasks = state.get('tasks', [])
        if tasks:
            self.chat_tasks = tasks
        print(self.chat_tasks)
        self.initializing = False

    @property
    def chat_tasks(self):
        return self.client_chats.get(self.client_id, {}).get(self.chat_id, {}).get('tasks', [])
    
    @chat_tasks.setter
    def chat_tasks(self, value: list):
        if self.client_id in self.client_chats and self.chat_id in self.client_chats[self.client_id]:
            self.client_chats[self.client_id][self.chat_id]['tasks'] = value

            if not self.initializing:
                self.mediator_state_model.set_tasks(self.chat_tasks)
                task = asyncio.create_task(self.mediator_state_model.save_state())
                task.add_done_callback(
                    lambda t: print("\033[32mMediator state saved\033[0m") 
                    if not t.exception() 
                    else print(f"\033[31mMediator state save failed with error:\033[0m {t.exception()}")
                )

    def _get_agent_by_name(self, agent_name: str) -> BaseAgent:
        agent = self.agents.get(agent_name)

        if not agent:
            raise ValueError(f"Agent {agent_name} not found")
        return agent
    
    def _is_tool_dependency(self, all_dependencies, dep: int) -> bool:
        """
        Check if a dependency ID corresponds to a tool.

        Args:
            dep (int): Dependency ID.

        Returns:
            bool: True if the dependency is a tool, otherwise False.
        """
        task = next((task for task in all_dependencies if task["id"] == dep), None)
        return bool(task and ("tool" in task["tool"].lower() or task["tool"].lower() == 'join'))

    def update_agent_plans(self, agent_name: str, plan: list[dict], summary: str):
        chat_tasks = self.chat_tasks.copy()

        print("\033[34mPlans before:\033[0m", chat_tasks)
        last_plan_id = plan[-1]['id']
        # Keep the initial part as is
        if agent_name == self.default_agent and not chat_tasks:
            chat_tasks.extend(plan)

            default_agent_entry = {
                "tool": self.default_agent,
                "summary": summary,
                "id": random.randint(10**7, 10**8 - 1),
                "arguments": [],
                "dependencies": [last_plan_id]
            }
            chat_tasks.append(default_agent_entry)
            self.chat_tasks = chat_tasks
            return

        # Find the task where 'tool' == agent_name
        agent_task = next((task for task in chat_tasks if task['tool'] == agent_name))
        dependencies_to_remove = set()

        # Function to recursively collect dependencies of tasks where 'tool' == agent_name
        def collect_dependencies_to_remove(task_ids):
            for dep_id in task_ids:
                dep_task = next((t for t in chat_tasks if t['id'] == dep_id), None)
                if dep_task and dep_task['id'] not in dependencies_to_remove:
                    dependencies_to_remove.add(dep_task['id'])
                    collect_dependencies_to_remove(dep_task.get('dependencies', []))

        # Start collecting dependencies from the agent_task, only tools
        task_dependencies = agent_task.get('dependencies', [])
        tool_dependencies = [dep for dep in task_dependencies if self._is_tool_dependency(self.chat_tasks, dep)]
        collect_dependencies_to_remove(tool_dependencies)

        agent_task['dependencies'] = [dep for dep in task_dependencies if dep not in tool_dependencies]

        chat_tasks = [task for task in chat_tasks if task['id'] not in dependencies_to_remove]

        agent_task['dependencies'].append(last_plan_id)

        agent_task['summary'] = summary

        agent_task_index = chat_tasks.index(agent_task)

        chat_tasks[agent_task_index:agent_task_index] = plan

        self.chat_tasks = chat_tasks

        # self.mediator_state_model.set_tasks(self.chat_tasks)
        # await self.mediator_state_model.save_state()

    def get_task_id_by_name(self, agent_name: str) -> Optional[str]:
        for task in self.chat_tasks:
            if task['tool'] == agent_name:
                return task['id']
        return None

    def register_agent(self, agent: BaseAgent):
        """
        Registers an agent with the mediator.

        Args:
            agent (BaseAgent): The agent to register.
        """
        self.agents[agent.name] = agent

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
        # print("\033[32mIn Init plan mediator:\033[0m")
        # pprint(plan)

        if len(self.call_stack) >=2:
            parent_agent_name = self.call_stack[-2]
            agent = self._get_agent_by_name(parent_agent_name)
            last_task = plan[-1]
            await agent.link_final_task_to_dependencies(agent_name, last_task['id'], last_task['tool'])
            print(parent_agent_name, agent_name)

        # Remove the agent's previous actions from the plan and the graph
        start_time = time.time()
        await self._delete_current_plan()
        end_time = time.time()
        print(f"Time taken to clear nodes: {end_time - start_time} seconds")
        # self.neo4j_service.delete_agent_actions(agent_name)
        start_time = time.time()
        self.update_agent_plans(agent_name, plan, summary)
        print("\033[31mPlans:\033[0m")
        pprint(self.chat_tasks)
        print('task id',self.get_task_id_by_name(agent_name))
        # self.neo4j_service.create_or_update_agent(agent_name, self.agents[agent_name].description, summary, task_id=self.get_task_id_by_name(agent_name))
        # Update the knowledge graph
        await self.neo4j_service.create_or_update_client_chat(client_id=self.client_id, chat_id=self.chat_id)
        for index, task in enumerate(self.chat_tasks):
            task_id = task['id']
            description = task.get('description', '')
            plan_summary = task.get('summary', '')
            tool_name = task['tool']
            # arguments = task['arguments']
            dependencies = task['dependencies']
            is_agent = 'agent' in tool_name.lower()
            # Create or update nodes
            if is_agent:
                # print('agent',tool_name)
                await self.neo4j_service.create_or_update_agent(agent_name=tool_name, description=self.agents[tool_name].description, plan_summary=plan_summary, task_id=task_id)
            else:
                await self.neo4j_service.create_or_update_tool(tool_name=tool_name, description=description, task_id=task_id)
            # self.neo4j_service.create_action(task_id, description, arguments)
            if index == len(self.chat_tasks) - 1:
                await self.neo4j_service.create_chat_to_agent_relationships(
                    chat_id=self.chat_id, 
                    agent_id=task_id
                )
            await self._create_tool_to_agent_relationships(task_id, dependencies)

        # Create relationships
        # self.neo4j_service.create_relationships(agent_name, tool_name, action_id, dependencies)
        end_time = time.time()
        print(f"Time taken to update nodes: {end_time - start_time} seconds")


    async def _delete_current_plan(self):
        for task in self.chat_tasks:
            tool_name = task['tool']
            task_id = task['id']
            await self.neo4j_service.delete_agent_or_tool_node(tool_name, task_id)
    
        await self.neo4j_service.delete_client_chat(self.chat_id)

    async def _create_tool_to_agent_relationships(self, task_id: str, dependencies: List[str]):
        for dep_id in dependencies:
            dep_task = next((task for task in self.chat_tasks if task['id'] == dep_id), None)
            if dep_task:
                await self.neo4j_service.create_tool_to_agent_relationships(task_id, dep_id, "USES")

    async def handle_message(self, message: str):
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
        
        await self.execute_next_in_stack(message=message, dependencies_message="")

    async def execute_next_in_stack(self, message: str, dependencies_message: str):
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
        agent = self._get_agent_by_name(agent_name)

        # Set client data in the agent
        if not agent.is_initialized(client_id=self.client_id, chat_id=self.chat_id):
            await agent.initialize_agent(client_id=self.client_id, chat_id=self.chat_id)
        # Execute the agent's task
        await self.run_agent_task(agent, message, dependencies_message)

    async def run_agent_task(self, agent: BaseAgent, message: str, dependencies_message: str):
        """Runs the given agent's task and removes it from the stack."""
        start_time = time.time()
        print(f"before execute {agent.name}")
        await agent.execute(message=message, dependencies_message=dependencies_message)
        print(f"after execute {agent.name}")
        end_time = time.time()
        print(f"Time taken to execute agent: {end_time - start_time} seconds")
    
    async def on_agent_done(self, agent_name: str, result: Union[str, dict], task_id: str):
        """
        Called when the agent is executed.
        """
        for i, agent in enumerate(self.call_stack):
            if agent == agent_name:
                self.call_stack.pop(i)
                print(f"Removed {agent_name} from the call stack.")
                await self.mediator_state_model.remove_agent_from_call_stack(agent_name)
                break

        if len(self.call_stack) > 0:
            next_agent = self.call_stack[-1]
            agent = self._get_agent_by_name(next_agent)
            agent.on_child_agent_done({ "result": result, "id": task_id })
            await self.execute_next_in_stack(message="", dependencies_message="")
        
    async def add_agent_to_call_stack(self, parent_agent: str, agent_name: str, task_id: str, message: str, dependencies_message: str):
        """
        Adds a new agent to the call stack and triggers its execution.

        Args:
            agent_name (str): The name of the agent to add.
            message (str): The message to pass to the agent.
        """
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered.")

        self.call_stack.append(agent_name)

        await self.mediator_state_model.add_agent_to_call_stack(agent_name)

        print("\033[31mNew call stack after adding agent:\033[0m")
        pprint(self.call_stack)

        await self.execute_next_in_stack(message=message, dependencies_message=dependencies_message)
    
    async def redirect(self, client_id: str, new_agent_name: str, message: str, state: dict):
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
        # nodes = await self.neo4j_service.get_all_nodes_and_relationships()
        # print('nodes')
        # pprint(nodes)
        new_agent = self._get_agent_by_name(new_agent_name)
        if new_agent:
            state['currentAgentName'] = new_agent_name
            response = new_agent.handle_message(client_id, message, state)
            return response
        else:
            return "Sorry, I cannot assist with that request."
