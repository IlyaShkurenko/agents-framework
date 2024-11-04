from typing import Any, List, Literal, Optional, Type, Union
from pydantic import BaseModel, Field, create_model
from core.base_component import BaseComponent
from abc import ABC, abstractmethod
import asyncio
from core.executor import Executor
from core.joiner.main import Joiner
from core.planner.main import Planner
from models.agent_state_model import AgentStateModel
import json
import copy

from models.task_state_model import TasksStateModel
from services.openai_service import OpenAIService
class BaseAgent(BaseComponent, ABC):
    """
    Base class for all agents.
    """

    @abstractmethod
    def get_questionnaire_response_model(self):
        pass

    # @property
    # @abstractmethod
    # def user_requirements_schema(self) -> Type[BaseModel]:
    #     pass

    @property
    @abstractmethod
    def questionnaire_prompt(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def include_overview(self) -> bool:
        return False

    def __init__(self, mediator, tools=None):
        self.mediator = mediator
        self.tools = tools or []
        self.tasks = []
        self.agents_done = set()
        self.initial_message = None
        self.result = None
        self.initialized = False
        self.executor: Executor
        self.planner: Planner
        self.openai_service = OpenAIService(agent_name=self.name)
        self.emit_message_on_agent_done = True
        self.dependencies_message = ""

    async def initialize_agent(self, client_id: str, chat_id: str, called_agents: List[str] = []):
        """
        Sets the client data for the agent.
        """
        self.client_id = client_id
        self.chat_id = chat_id
        self.state_model = AgentStateModel(client_id, chat_id, self.name)
        
        await self.state_model.load_state()
        self.tasks = self.state_model.get_tasks()
        print('tasks loaded in state', self.name, self.tasks)

        await self.executor.initialize(client_id=self.client_id, chat_id=self.chat_id, tasks=self.tasks, called_agents=called_agents)

        agent_status = self._get_agent_status()

        if self.tasks and not self.result and (agent_status == "waiting_for_approval" or agent_status == "completed"):
            task_id = self.tasks[-1]['id']
            result = await self.executor.get_task_result(task_id)
            self.result = { "result": result, "id": task_id }
            print('result loaded', self.result)
            
        self.initialized = True
    
    def is_initialized(self, client_id: str, chat_id: str):
        return self.initialized and self.client_id == client_id and self.chat_id == chat_id

    async def execute(self, **kwargs):
        """
        Executes the agent's pipeline, which may include using tools.
        """
        message = kwargs.get('message')
        print('message', message)
        dependencies_message = kwargs.get('dependencies_message')
        if message is None:
            raise ValueError("Missing 'message' in kwargs")
        if dependencies_message:
            self.dependencies_message = dependencies_message
            
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
            assistant_response = await self._run_questionnaire(message)
            return await self._handle_assistant_response(assistant_response)
        else:
            return await self._execute_plan_and_finalize(tasks=self.tasks)

    async def process_agent_task(self, task_id, agent_name, arguments: str, dependencies_message: str):
        """
        Process the task arguments and delegate to the mediator.

        Args:
            task_id (str): The task ID.
            agent_name (str): The name of the agent to process.
            message (str): The message to pass to the agent.

        Returns:
            str: The response from the agent.
        """
        print("\033[34min process agent task:\033[0m", agent_name, task_id, arguments)

        await self.mediator.add_agent_to_call_stack(
            parent_agent=self.name,
            agent_name=agent_name,
            task_id=task_id,
            message=arguments,
            dependencies_message=dependencies_message
        )
        return f"Task for {agent_name} added to call stack with message"
    
    def on_child_agent_done(self, previous_agent_result):
        self.executor.set_child_agent_result(previous_agent_result)

    def get_tool_conversation_history(self, tool_name):
        return self._get_tool_conversation_history(tool_name)
    
    def on_tool_execute(self, tool_name, result, conversation_history):
        # print('on tool execute', tool_name, result, conversation_history)
        self._save_tool_conversation_history(tool_name, conversation_history)
        
    async def link_final_task_to_dependencies(self, agent_name, task_id: int, task_name: str):
        """
        Add the agent task to the dependencies.
        """
        print('add agent task to dependencies')
        self.tasks = self.executor.link_final_task_to_dependencies(agent_name, task_id, task_name)
        await self.state_model.update_agent_plan(self.tasks)
        
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

    def _get_user_requirements(self):
        return self.state_model.get_user_requirements()
    
    def _get_planner_conversation_history(self):
        return self.state_model.get_agent_planner_conversation_history()
    
    def _save_agent_planner_history(self, history):
        self.state_model.save_agent_planner_history(history)

    def _save_tool_conversation_history(self, tool_name, history):
        self.state_model.save_tool_conversation_history(tool_name, history)
    
    def _save_plan(self, plan):
        print(plan)
        self.state_model.save_agent_plan(plan)

    def _save_agent_status(self, status):
        self.state_model.save_agent_status(status)

    def _is_plan_exists(self):
        return self.state_model.is_plan_exists()
    
    def _get_agent_status(self):
        return self.state_model.get_agent_status()

    def _get_conversation_history(self):
        return self.state_model.get_conversation_history()
    
    def _get_tool_conversation_history(self, tool_name):
        return self.state_model.get_tool_conversation_history(tool_name)
    
    def _add_message_to_conversation_history(self, message):
        self.state_model.add_message_to_conversation_history(message)

    async def _save_state(self):
        print('in save state')
        await self.state_model.save_state()

    def _is_executing(self):
        return self._get_agent_status() == "execution" and len(self.tasks) > 0
        
    def _if_result_accepted(self, assistant_response):
        if getattr(assistant_response, 'result_accepted', False):
            self._on_agent_done()
            return True
        return False
    
    def _on_agent_execute(self, result):
        self.result = result
        # print('result', self.result)
        self._save_agent_status('waiting_for_approval')
    
    def _on_agent_done(self):
        self._save_agent_status('completed')
        if self.result:
            task = asyncio.create_task(self.mediator.on_agent_done(self.name, self.result['result'], self.result['id']))
            task.add_done_callback(
                lambda t: print("\033[32mMediator agent done\033[0m") 
                if not t.exception() 
                else print(f"\033[31mMediator agent done failed with error:\033[0m {t.exception()}")
            )

    async def _run_questionnaire(self, message: str):
        """
        Runs the questionnaire to collect caption preferences.

        Args:
            message (str): The message from the user.

        Returns:
            AssistantResponse: The parsed response from the assistant.
        """
        print('in run questionnaire')
        history = self._get_conversation_history()
        response_model = self.get_questionnaire_response_model()

        assistant_response = await self.openai_service.get_response(
            conversation_history=history,
            system_prompt=self.questionnaire_prompt,
            message=message,
            response_schema=response_model
        )
        self._save_agent_status("questionnaire")
        print('"\033[31mAssistant_response\033[0m"', assistant_response)
        return assistant_response
    
    async def _handle_assistant_response(self, assistant_response):
        if self._if_result_accepted(assistant_response):
            print('result accepted')
            if assistant_response.message:
                self._emit_assistant_message(assistant_response.message)
            return
        
        if assistant_response.message:
            self._emit_assistant_message(assistant_response.message)
            #question from assistant
            if '?' in assistant_response.message:
                print("\033[34mQuestion from assistant:\033[0m")
                return
                
        if assistant_response.user_requirements:
            return await self._process_user_requirements(assistant_response)
        
    def _parse_assistant_response(self, assistant_response):
        need_replan = False
        # previous_user_requirements = None
        
        if assistant_response.user_requirements:
            need_replan = self._need_replan(assistant_response)
            # previous_user_requirements = copy.deepcopy(self._get_user_requirements())
            # self._save_user_requirements(assistant_response)

        print('need_replan', need_replan)
        print('message', assistant_response.message)
        result_accepted = getattr(assistant_response, 'result_accepted', False)
        replan_after_execution = hasattr(assistant_response, 'result_accepted') and not assistant_response.result_accepted and need_replan

        print('result_accepted', result_accepted)

        print('replan_after_execution', replan_after_execution)

        user_requirements = None 
        if assistant_response.user_requirements:
            user_requirements = assistant_response.user_requirements.dict()

        return need_replan, replan_after_execution, user_requirements
        
    async def _process_user_requirements(self, assistant_response):

        need_replan, replan_after_execution, user_requirements = self._parse_assistant_response(assistant_response)

        await self._create_and_save_plan(need_replan=need_replan, replan_after_execution=replan_after_execution, user_requirements=user_requirements)
        
        final_response = await self._execute_plan_and_finalize(tasks=self.tasks)
        return final_response
    
    async def _create_and_save_plan(self, need_replan, replan_after_execution, user_requirements):
        print('Start Planing')
        self.mediator.emit_message('planning_started')

        executed_user_requirements = self._get_user_requirements()

        planner_conversation_history = self._get_planner_conversation_history()

        self._save_agent_status("planning")

        existing_tasks_ids = await self.state_model.get_all_tasks_ids()

        tasks_with_results=self.executor.get_tasks_with_results()

        user_requirements_for_plan = user_requirements.get('adjustments', user_requirements)

        planner_conversation_history, planner_response = await self.planner.create_plan(
            conversation_history=planner_conversation_history,
            user_requirements=user_requirements_for_plan,
            replan=need_replan,
            replan_after_execution=replan_after_execution,
            tasks_with_results=tasks_with_results,
            previous_user_requirements=executed_user_requirements,
            include_overview=self.include_overview,
            dependencies_message=self.dependencies_message,
            existing_tasks_ids=existing_tasks_ids
        )

        # Update planner conversation history which includes overview and tasks
        self._save_agent_planner_history(planner_conversation_history)

        self.tasks = planner_response['tasks']
        planner_response['user_requirements'] = user_requirements
        self._save_plan(planner_response)
        task = asyncio.create_task(self.mediator.emit_plan(
            plan=copy.deepcopy(planner_response['tasks']),
            summary=user_requirements['summary'],
            agent_name=self.name
        ))
        task.add_done_callback(
            lambda t: print("\033[32mTask completed successfully\033[0m") 
            if not t.exception() 
            else print(f"\033[31mTask emit_plan failed with error:\033[0m {t.exception()}")
        )
        return planner_response
    
    async def _execute_plan_and_finalize(self, tasks: List[dict]):

        if self._get_agent_status() != 'execution':
            print('in execute plan and finalize')
            self._save_agent_status("execution")
            self.mediator.emit_message('execution_started')

        final_response = await self.executor.execute_plan(tasks)
        
        print("\033[31mThis final response\033[0m", final_response)
        if final_response:
            self._on_agent_execute(final_response)
            result = final_response["result"]

            if isinstance(result, str):
                self._emit_assistant_message(result)
                self._add_message_to_conversation_history(result)
            elif isinstance(result, dict):
                if result.get('is_done'):
                    self._on_agent_done()
                if(self.emit_message_on_agent_done):
                    self._emit_assistant_message(result)
                    self._add_message_to_conversation_history(json.dumps(result, indent=4))
            return result
        
    def _create_dynamic_user_requirements_response_model(self, extra_fields = {}, include_adjustments: bool = False):
        dynamic_fields = extra_fields or {}

        dynamic_fields['summary'] = (str, Field(..., description="Concise summary of the user's requirements. This summary will guide the next agent in creating a plan. Analyze all relevant parts of the conversation to capture the primary task and include all requirements the user has provided, not just the latest changes. Start the summary with 'User decided to'."))

        if include_adjustments:
            dynamic_fields['adjustments'] = (str, Field(..., description="If result_accepted is False, include the specific changes requested by the user. Avoid rephrasing, summarizing, or omitting details; include the requested changes with all errors corrected. It should reflect exactly what the user has asked to modify."))
        
        response_model = create_model(
            'DynamicUserRequirementsResponse',
            **dynamic_fields,
        )
        print("\033[33mUser requirements response model fields:\033[0m")
        for field_name, field_info in response_model.model_fields.items():
            print(f"Field: {field_name}, Description: {field_info.description}")
        return response_model
    
    def _create_dynamic_response_model(self, extra_fields: dict[str, Any] = {}, user_requirements_fields: dict[str, Any] = {}, message_field_description=""):
        dynamic_fields = extra_fields or {}
        
        print("\033[34mIs plan exists:\033[0m", self._is_plan_exists())
        print(self._get_agent_status())
        print("\033[34mIs waiting for approval:\033[0m", self._get_agent_status() == 'waiting_for_approval')

        user_requirements_description = (
            "Exists only if all information is provided, otherwise None. Update it only if user have changed something otherwise return previous user_requirements if they exists.Always exists if user_requirements_status is 'changed' or 'approved' or 'unchanged'. None if user_requirements_status is 'incomplete'. Remember to only update user_requirements if user_requirements_status is changed and leave it unchanged otherwise."
        )  

        is_waiting_for_approval = self._get_agent_status() == 'waiting_for_approval'
        if is_waiting_for_approval:
            dynamic_fields['result_accepted'] = (bool, Field(..., description="True if the user explicitly confirms that he want to proceed with the result as is. False if the user asks any questions, requests clarifications, or indicates that he wants to adjust the result."))
            user_requirements_description += " If result_accepted is False then be sure to provide a new requirements and in 'summary' field include whole task request."

        message_description = message_field_description if message_field_description else "Assistant message. Must exist if user_requirements_status is 'incomplete' or user_requirements is None. It is forbidden to return any social media content which user requests. Remember to include message if user_requirements is None."

        if self.dependencies_message:
            dynamic_fields['other_results_of_tasks_exists'] = (bool, Field(..., description="True if in history you see 'Here are the results of the tasks that you depend on:' otherwise False"))
            message_description += " If 'other_results_of_tasks_exists' is True then ask user if he wants to use that context"

        # Create a new model with dynamic fields first, followed by the base fields
        response_model = create_model(
            'DynamicAssistantResponse',
            **dynamic_fields,  # Insert dynamic fields first
            user_requirements_status=(Literal["incomplete", "changed", "approved", "unchanged"], Field(None, description="Status of the requirements. Can be 'changed' if the user modified requirements, 'approved' if they were accepted, 'unchanged' if nothing was changed, or 'incomplete' if the requirements are not gathered or missing information.")),
            user_requirements=(Optional[self._create_dynamic_user_requirements_response_model(user_requirements_fields, is_waiting_for_approval)], Field(None, description=user_requirements_description)),
            message=(Optional[str], Field(None, description=message_description)),
        )
        print("\033[33mResponse model fields:\033[0m")
        for field_name, field_info in response_model.model_fields.items():
            print(f"Field: {field_name}, Description: {field_info.description}")
        return response_model
