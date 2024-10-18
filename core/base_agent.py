from core.base_component import BaseComponent
from abc import ABC, abstractmethod
import asyncio
from core.joiner import Joiner
from models.agent_state_model import AgentStateModel
import json
import pprint
class BaseAgent(BaseComponent):
    """
    Base class for all agents.
    """

    def __init__(self, mediator, tools=None):
        self.mediator = mediator
        self.tools = tools or []
        self.tasks = []
        self.agents_done = set()
        self.joiner = Joiner()
        self.initial_message = None

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
        print('message', message)
        if message is None:
            raise ValueError("Missing 'message' in kwargs")
        response = await self.handle_message(message)
        await self.state_model.save_state()
        return response
    
    def save_initial_message(self, message: str):
        if not self.initial_message:
            self.initial_message = message
        print(f"\033[34mMessage in {self.name}:\033[0m", message)

    async def handle_message(self, message: str):
        """
        Handles the incoming message and processes it according to the agent's logic.

        Args:
            message (str): The incoming message from the user.
        """
        if not self.initial_message:
            self.initial_message = message

        print(f"\033[34mMessage in {self.name}:\033[0m", message)
        assistant_response = await self.run_questionnaire(message)
        print('assistant_response', assistant_response)

        if assistant_response.user_requirements:
            # Save the caption preferences in the state model
            if assistant_response.message:
                self.mediator.emit_message('message', assistant_response.message)

            need_replan = self.state_model.is_requirements_changed(assistant_response.user_requirements.dict())

            self.state_model.save_user_requirements(assistant_response.user_requirements.dict())
            print('plan approved', getattr(assistant_response, 'plan_approved', False))
            print('need_replan', need_replan)
            print('message', assistant_response.message)
            self.mediator.emit_message('planning_started')
        
            user_requirements = self.state_model.get_user_requirements()
            planner_conversation_history = self.state_model.get_agent_planner_conversation_history()
            self.state_model.save_agent_status("planning")
            planner_conversation_history, planner_response = await self.planner.create_plan(conversation_history=planner_conversation_history, user_requirements=user_requirements, replan=need_replan, include_overview=self.include_overview)

            # Update planner conversation history which includes overview and tasks
            self.state_model.save_agent_planner_history(planner_conversation_history)
            plan_response_dict = planner_response.dict()
            self.tasks = plan_response_dict['tasks']

            self.state_model.save_agent_plan(plan_response_dict)

            self.mediator.emit_plan(plan=plan_response_dict, summary=user_requirements['summary'], agent_name=self.name)
            # return 'Start execution'
            # Execute the plan
            self.executor.set_tasks_state_model(self.mediator.mediator_tasks_state_model)
            self.state_model.save_agent_status("execution")
            self.mediator.emit_message('execution_started')
            final_response = await self.executor.execute_plan()
            # self.state_model.save_agent_status("completed")

            friendly_response = self.joiner.join(initial_message=self.initial_message, final_response=final_response)
            self.state_model.add_message_to_conversation_history(friendly_response)
            self.state_model.save_agent_status('waiting_for_approval')

            return friendly_response

        return assistant_response.message or 'Sorry, I did not understand your request.'
    
    async def run_questionnaire(self, message: str):
        """
        Runs the questionnaire to collect caption preferences.

        Args:
            message (str): The message from the user.

        Returns:
            AssistantResponse: The parsed response from the assistant.
        """
        self.state_model.save_agent_status("questionnaire")
        history = self.state_model.get_conversation_history()

        assistant_response = await self.openai_service.get_response(
            conversation_history=history,
            system_prompt=self.questionnaire_prompt,
            message=message,
            response_schema=self.questionnaire_response_schema
        )

        return assistant_response

    async def process_agent_task(self, task_id, agent_name, arguments: dict):
        """
        Process the task arguments and delegate to the mediator.

        Args:
            task_id (str): The task ID.
            agent_name (str): The name of the agent to process.
            message (str): The message to pass to the agent.

        Returns:
            str: The response from the agent.
        """
        message = f"Use these arguments as context: {json.dumps(arguments)}"

        asyncio.create_task(
            self.mediator.add_agent_to_call_stack(
                parent_agent=self.name,
                agent_name=agent_name,
                task_id=task_id,
                message=message
            )
        )
        self.state_model.save_agent_status("pending")
        self.mediator.emit_message('redirecting')
        return f"Task for {agent_name} added to call stack with message {message}"
    
    def add_agent_task_to_dependencies(self, task_id: int):
        """
        Add the agent task to the dependencies.
        """
        self.executor.add_agent_task_to_dependencies(self.name, task_id)

    # def on_agent_execute(self, agent_name: str):
    #     """
    #     Called when the agent is executed.
    #     """
    #     self.agents_done.add(agent_name)
    #     self.mediator.on_agent_execute(agent_name)
    #     agent_tasks = {
    #         task["tool"] for task in self.tasks if "agent" in task["tool"].lower()
    #     }
    #     print("\033[34mAgents done:\033[0m")
    #     pprint(self.agents_done)
    #     print("\033[34mAgent tasks:\033[0m")
    #     pprint(agent_tasks)
    #     if agent_tasks.issubset(self.agents_done):
    #         self.state_model.save_agent_status("completed")
    #         self.mediator.on_agents_done(self.name)
