# agents/init_agent.py

from core.base_component import BaseComponent
from .tools.create_post_tool import CreatePostTool
from core.base_agent import BaseAgent
from core.planner.main import Planner
from core.executor import Executor
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Literal, Union
from services.openai_service import OpenAIService
import os
import json

class UserRequirements(BaseModel):
    content_uploaded: bool = Field(..., description="Whether the user has uploaded content like image or vide")
    visual_content_action: Literal['edit', 'generate', 'no_needed'] = Field(..., description="Action on visual content. Suggest edit only if user has uploaded content like image or video")
    create_post: bool = Field(..., description="Whether the user wants to create a post")
    caption_needed: bool = Field(..., description="Whether the user needs a caption")
    hashtags_needed: bool = Field(..., description="Whether the user needs hashtags")
    summary: str = Field(..., description="Summary of the user's requirements, 2-3 sentences. This info will be used by next agent. Change it only if new requirements are provided otherwise leave it as is")

class AssistantResponse(BaseModel):
    message: str = Field(None, description="Assistant's message to the user. Do not mention structured information. Should be empty '' if user_requirements is provided")
    user_requirements: Optional[UserRequirements] = Field(None, description="User's requirements in structured form, only if all information is provided, otherwise None")

def create_dynamic_response_model(include_plan_action: bool = False):
    if include_plan_action:
        return create_model(
            'AssistantResponseWithReplan',
            plan_approved=(bool, Field(..., description="True if the user explicitly confirms that he want to proceed with the plan as is. False if the user asks any questions, requests clarifications, or indicates that he wants to adjust the plan.")),
            __base__=AssistantResponse
        )
    else:
        return AssistantResponse

# Load the prompt
init_prompt_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'init_prompt.txt')
planner_example_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'planner_example.txt')
with open(init_prompt_file_path, 'r') as file:
    INIT_PROMPT = file.read()
with open(planner_example_file_path, 'r') as file:
    PLANNER_EXAMPLE = file.read()

class InitAgent(BaseAgent):
    """
    The InitAgent handles the initial interaction with the user.
    """

    @property
    def name(self):
        return "init_agent"
    
    @property
    def planner_name(self):
        return  f"{self.name}_plan"

    @property
    def description(self):
        return "Agent responsible for initial interaction with the user."
    
    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        self.create_post_tool = CreatePostTool()
        super().__init__(mediator, [self.create_post_tool] + (tools or []))
        
        self.openai_service = OpenAIService(agent_name=self.name)
    
    async def handle_message(self, message: str, state: dict):
        # Use OpenAI API to process the questionnaire
        assistant_response = await self.run_questionnaire(message, state)

        # Update conversation history
        # conversation_history = state.get('conversation_history', [])
        # conversation_history.append({"role": "assistant", "content": assistant_response.message, "agent": self.name})
        # state['conversation_history'] = conversation_history
        print('assistant_response', assistant_response)
        if assistant_response.user_requirements:

            if assistant_response.message:
                self.mediator.emitMessage('message', assistant_response.message)

            existing_requirements = state.get('user_requirements')

            need_replan = False

            if existing_requirements:
                for field, new_value in assistant_response.user_requirements.dict().items():
                    old_value = existing_requirements.get(field)
                    if old_value != new_value:
                        need_replan = True
                        break

            state['user_requirements'] = assistant_response.user_requirements.dict()
            print('plan approved', getattr(assistant_response, 'plan_approved', False))
            print('need_replan', need_replan)
            print('message', assistant_response.message)
            plan_approved = getattr(assistant_response, 'plan_approved', False)
            if not plan_approved:
                # Create a plan or replan based on the user requirements
                self.mediator.emitMessage('planning_started')
                planner = Planner(tools=self.tools,
                                include_overview=True,
                                replan=need_replan,
                                planner_agent_name=self.planner_name,
                                examples=PLANNER_EXAMPLE)

                planner_conversation_history, planner_response = await planner.create_plan(conversation_history=state.get(f"{self.planner_name}_conversation_history", []), user_requirements=state['user_requirements'])

                self.mediator.emitMessage('planning_ended')

                # Update planner conversation history which includes overview and tasks
                state[f"{self.planner_name}_conversation_history"] = planner_conversation_history
                assistant_response_dict = planner_response.dict()
    
                # Update agent conversation history which includes only overview
                agent_conversation_history = state.get('conversation_history', [])
                agent_conversation_history.append({"role": "assistant", "content": assistant_response_dict['overview'], "agent": self.name})
                state['conversation_history'] = agent_conversation_history

                if self.planner_name not in state:
                    state[self.planner_name] = [assistant_response_dict]
                else:
                    state[self.planner_name].append(assistant_response_dict)

                return assistant_response_dict['overview']

            return 'Start execution'
            # Execute the plan
            executor = Executor(self.mediator, state)
            final_response = executor.execute_plan()

            return final_response
        else:
            # Return the assistant's message to the user
            return assistant_response.message or 'Sorry, I did not understand your request.'

    async def run_questionnaire(self, message: str, state: dict):
        """
        Runs the questionnaire to collect user requirements.

        Args:
            message (str): The message from the user.

        Returns:
            dict: The assistant's response.
        """
        
        history = state.get('conversation_history', [])
        response_model = create_dynamic_response_model(include_plan_action=self.planner_name in state)
        print('response_model',response_model)
        assistant_response = await self.openai_service.get_response(conversation_history=history, system_prompt=INIT_PROMPT, message=message, response_schema=response_model)


        # print(json.dumps(history, indent=4, ensure_ascii=False))


        return assistant_response
