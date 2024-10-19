from typing import Any, List, Optional
from pydantic import Field, create_model
from core.base_component import BaseComponent
from abc import ABC, abstractmethod
import asyncio
from core.joiner import Joiner
from models.agent_state_model import AgentStateModel
import json
import copy
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
        self.include_result_accepted = False
        self.include_plan_action = False
        self.initial_message = None

    async def set_client_data(self, client_id: str, chat_id: str):
        """
        Sets the client data for the agent.
        """
        self.client_id = client_id
        self.chat_id = chat_id
        self.state_model = AgentStateModel(client_id, chat_id, self.name)
        await self._load_state()

    # Helper method to save initial message
    def _save_initial_message(self, message: str):
        if not self.initial_message:
            self.initial_message = message
        print(f"\033[34mMessage in {self.name}:\033[0m", message)

    # Helper method to emit assistant's message
    def _emit_assistant_message(self, assistant_response):
        self.mediator.emit_message('message', assistant_response)
            

    # Helper method to check if replan is needed
    def _need_replan(self, assistant_response):
        return self.state_model.is_requirements_changed(assistant_response.user_requirements.dict())

    # Helper method to save user requirements
    def _save_user_requirements(self, assistant_response):
        self.state_model.save_user_requirements(assistant_response.user_requirements.dict())

    def _get_user_requirements(self):
        return self.state_model.get_user_requirements()
    
    def _get_planner_conversation_history(self):
        return self.state_model.get_agent_planner_conversation_history()
    
    def _save_agent_planner_history(self, history):
        self.state_model.save_agent_planner_history(history)
    
    def _save_plan(self, plan):
        self.state_model.save_agent_plan(plan)

    def _save_agent_status(self, status):
        if status == 'waiting_for_approval':
            self.include_result_accepted = True
        else:
            self.include_result_accepted = False  
        self.state_model.save_agent_status(status)

    def _is_plan_exists(self):
        return self.state_model.is_plan_exists()
    
    def _get_agent_status(self):
        return self.state_model.get_agent_status()

    def _get_conversation_history(self):
        return self.state_model.get_conversation_history()
    
    def _add_message_to_conversation_history(self, message):
        self.state_model.add_message_to_conversation_history(message)

    async def _save_state(self):
        await self.state_model.save_state()

    def _is_executing(self):
        return self.state_model.get_agent_status() == "execution" or self.state_model.get_agent_status() == "pending" and len(self.tasks) > 0

    async def _load_state(self):
        await self.state_model.load_state()
        self.tasks = self.state_model.get_tasks()
        print('tasks in load state', self.tasks)


    async def execute(self, **kwargs):
        """
        Executes the agent's pipeline, which may include using tools.
        """
        message = kwargs.get('message')
        print('message', message)
        if message is None:
            raise ValueError("Missing 'message' in kwargs")
        response = await self.handle_message(message)
        await self._save_state()
        return response

    async def handle_message(self, message: str):
        """
        Handles the incoming message and processes it according to the agent's logic.
        """
        self._save_initial_message(message)
        print('is_executing', self._is_executing())
        if not self._is_executing():
            assistant_response = await self.run_questionnaire(message)
            return await self.handle_assistant_response(assistant_response)
        else:
            return await self._execute_plan_and_finalize(self.tasks)
    
    async def handle_assistant_response(self, assistant_response):
        if assistant_response.message:
            self._emit_assistant_message(assistant_response.message)
        if assistant_response.user_requirements:
            return await self.process_user_requirements(assistant_response)
        
    def _parse_assistant_response(self, assistant_response):
        need_replan = False
        previous_user_requirements = None
        
        if assistant_response.user_requirements:
            need_replan = self._need_replan(assistant_response)
            previous_user_requirements = copy.deepcopy(self._get_user_requirements())
            self._save_user_requirements(assistant_response)

        print('need_replan', need_replan)
        print('message', assistant_response.message)
        result_accepted = getattr(assistant_response, 'result_accepted', False)
        replan_after_execution = hasattr(assistant_response, 'result_accepted') and not assistant_response.result_accepted and need_replan

        print('result_accepted', result_accepted)

        print('replan_after_execution', replan_after_execution)
        if result_accepted:
            self._save_agent_status('completed')
            self.mediator.on_agent_done(self.name)
            return assistant_response.message
            
        return need_replan, replan_after_execution, previous_user_requirements
        
    async def process_user_requirements(self, assistant_response):

        need_replan, replan_after_execution, previous_user_requirements = self._parse_assistant_response(assistant_response)

        await self._create_and_save_plan(need_replan=need_replan, 
                                         replan_after_execution=replan_after_execution, tasks_with_results=self.executor.get_tasks_with_results(), executed_user_requirements=previous_user_requirements)
        
        final_response = await self._execute_plan_and_finalize(self.tasks)
        return final_response
    
    async def _create_and_save_plan(self, need_replan, replan_after_execution, tasks_with_results, executed_user_requirements):
        print('Start Planing')
        self.mediator.emit_message('planning_started')

        user_requirements = self._get_user_requirements()

        planner_conversation_history = self._get_planner_conversation_history()

        self._save_agent_status("planning")

        planner_conversation_history, planner_response = await self.planner.create_plan(
            conversation_history=planner_conversation_history,
            user_requirements=user_requirements,
            replan=need_replan,
            replan_after_execution=replan_after_execution,
            tasks_with_results=tasks_with_results,
            executed_user_requirements=executed_user_requirements,
            include_overview=self.include_overview
        )

        # Update planner conversation history which includes overview and tasks
        self._save_agent_planner_history(planner_conversation_history)

        plan_response_dict = planner_response.dict()

        self.tasks = plan_response_dict['tasks']

        self._save_plan(plan_response_dict)

        asyncio.create_task(self.mediator.emit_plan(
            plan=plan_response_dict,
            summary=user_requirements['summary'],
            agent_name=self.name
        ))
        await asyncio.sleep(0)

        return plan_response_dict

    async def _execute_plan_and_finalize(self, tasks: List[dict]):
        self.executor.set_tasks_state_model(self.mediator.mediator_tasks_state_model)
        self._save_agent_status("execution")
        self.mediator.emit_message('execution_started')
        final_response = await self.executor.execute_plan(tasks)

        if self.has_joiner:
            final_response = await self.joiner.join(initial_message=self.initial_message, final_response=final_response)
        print('in execute plan and finalize')
        print('final_response', final_response)
        self._add_message_to_conversation_history(final_response)
        # self._save_agent_status('waiting_for_approval')

        if isinstance(final_response, str):
            self._emit_assistant_message(final_response)

        return final_response
    
    def on_agent_execute(self):
        self._save_agent_status('waiting_for_approval')
    
    async def run_questionnaire(self, message: str):
        """
        Runs the questionnaire to collect caption preferences.

        Args:
            message (str): The message from the user.

        Returns:
            AssistantResponse: The parsed response from the assistant.
        """
        self._save_agent_status("questionnaire")
        history = self._get_conversation_history()
        response_model = self.get_response_model()

        print("\033[34mResponse model:\033[0m", response_model)

        assistant_response = await self.openai_service.get_response(
            conversation_history=history,
            system_prompt=self.questionnaire_prompt,
            message=message,
            response_schema=response_model
        )
        print('assistant_response', assistant_response)
        return assistant_response

    async def process_agent_task(self, task_id, agent_name, arguments: str):
        """
        Process the task arguments and delegate to the mediator.

        Args:
            task_id (str): The task ID.
            agent_name (str): The name of the agent to process.
            message (str): The message to pass to the agent.

        Returns:
            str: The response from the agent.
        """

        print('in process agent task', agent_name, task_id, arguments)

        asyncio.create_task(
            self.mediator.add_agent_to_call_stack(
                parent_agent=self.name,
                agent_name=agent_name,
                task_id=task_id,
                message=arguments
            )
        )
        await asyncio.sleep(0)
        # await self.mediator.add_agent_to_call_stack(
        #         parent_agent=self.name,
        #         agent_name=agent_name,
        #         task_id=task_id,
        #         message=arguments
        #     )
        self._save_agent_status("pending")
        self.mediator.emit_message('redirecting')
        return f"Task for {agent_name} added to call stack with message"
    
    def add_agent_task_to_dependencies(self, task_id: int):
        """
        Add the agent task to the dependencies.
        """
        self.executor.add_agent_task_to_dependencies(self.name, task_id)

    def _create_dynamic_response_model(self, extra_fields: dict[str, Any] = None):
        dynamic_fields = extra_fields or {}
        
        print("\033[34mIs plan exists:\033[0m", self._is_plan_exists())

        print("\033[34mIs waiting for approval:\033[0m", self._get_agent_status() == 'waiting_for_approval')

        user_requirements_description = (
            "User's requirements in structured form. "
            "only if all information is provided, otherwise None. Update it only if user have changed something otherwise return previous user_requirements if they exists. Remember to always return if was provided before"
        )   

        # print('include_plan_action', self.include_plan_action)

        # if self.include_plan_action:
        #     dynamic_fields['plan_approved'] = (bool, Field(..., description="True if the user explicitly confirms that he want to proceed with the plan as is. False if the user asks any questions, requests clarifications, or indicates that he wants to adjust the plan."))
        if self.include_result_accepted:
            dynamic_fields['result_accepted'] = (bool, Field(..., description="True if the user explicitly confirms that he want to proceed with the result as is. False if the user asks any questions, requests clarifications, or indicates that he wants to adjust the result."))
            # dynamic_fields['changes_to_apply'] = (str, Field(..., description="Changes to apply to the result if the user wants to adjust the result. Otherwise, it should be empty ''. Exists only if result_accepted is False"))
            user_requirements_description += " If result_accepted is False then be sure to provide a new requirements."
        

        # Create a new model with dynamic fields first, followed by the base fields
        response_model = create_model(
            'DynamicAssistantResponse',
            **dynamic_fields,  # Insert dynamic fields first
            user_requirements=(Optional[self.user_requirements_schema], Field(None, description=user_requirements_description)),
            message=(Optional[str], Field(None, description="Assistant's message to the user.")),
        )
        print("\033[33mResponse model fields:\033[0m")
        for field_name, field_info in response_model.model_fields.items():
            print(f"Field: {field_name}, Description: {field_info.description}")
        return response_model

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
