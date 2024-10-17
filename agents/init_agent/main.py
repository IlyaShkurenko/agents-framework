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
import time
import asyncio

class UserRequirements(BaseModel):
    content_uploaded: bool = Field(..., description="Whether the user has uploaded content like image or vide")
    visual_content_action: Literal['edit', 'generate', 'no_needed'] = Field(..., description="Action on visual content. Suggest edit only if user has uploaded content like image or video")
    create_post: bool = Field(..., description="Whether the user wants to create a post")
    caption_needed: bool = Field(..., description="Whether the user needs a caption")
    hashtags_needed: bool = Field(..., description="Whether the user needs hashtags")
    summary: str = Field(..., description="Brief Summary of the user's requirements. This info will be used by next agent to create a plan. If user mentioned sequence of actions then include it in summary so plan can be correct. Change it only if new requirements are provided otherwise leave it as is. Start with 'User decided to'")

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
    def description(self):
        return "Agent responsible for initial interaction with the user. Collects user requirements and creates a plan for creation a social media content."
    
    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        self.create_post_tool = CreatePostTool()
        super().__init__(mediator, [self.create_post_tool] + (tools or []))
        
        self.openai_service = OpenAIService(agent_name=self.name)
    
    async def handle_message(self, message: str):
        start_time = time.time()    
        plan = [
            {
                "id": "32412460",
                "description": "Call the create_caption_agent with the appropriate prompt to generate a caption for the Instagram post.",
                "dependencies": [],
                "tool": "create_caption_agent",
                "arguments": [
                    {
                        "name": "prompt",
                        "value": "Generate a creative and engaging caption for an Instagram post about a vacation to Bali"
                }
            ]
        },
        {
            "id": "32412461",
            "description": "Use the create_hashtags_agent to generate relevant hashtags for the Instagram post. Ensure that the hashtags are generated using the caption from the previous step (ID: 32412460) to provide better context and coherence between the caption and hashtags.",
            "dependencies": [32412460],
            "tool": "create_hashtags_agent",
            "arguments": [
			    {
                        "name": "prompt",
                        "value": "Generate relevant hashtags for an Instagram post about a vacation to Bali."
                    }
                ]
            },
            {
                "id": "32412462",
                "description": "Call the create_post_tool with the caption and hashtags to create the final Instagram post.",
                "dependencies": ["32412460", "32412461"],
                "tool": "create_post_tool",
                "arguments": [
                    {
                        "name": "prompt",
                        "value": "Create an Instagram post using the generated caption and hashtags."
                    }
                ]
            }
]
        asyncio.create_task(self.mediator.emit_plan(plan=plan, summary='Generates a post with hashtags and caption', agent_name=self.name))
        end_time = time.time()
        print(f"Time taken to emit plan: {end_time - start_time} seconds")
        return 'Start questionnaire'
        assistant_response = await self.run_questionnaire(message)
        print('assistant_response', assistant_response)

        if assistant_response.user_requirements:

            if assistant_response.message:
                self.mediator.emit_message('message', assistant_response.message)

            need_replan = self.state_model.is_requirements_changed(assistant_response.user_requirements.dict())

            self.state_model.save_user_requirements(assistant_response.user_requirements.dict())
            print('plan approved', getattr(assistant_response, 'plan_approved', False))
            print('need_replan', need_replan)
            print('message', assistant_response.message)
            plan_approved = getattr(assistant_response, 'plan_approved', False)
            if not plan_approved or need_replan:
                # Create a plan or replan based on the user requirements
                self.mediator.emit_message('planning_started')
                planner = Planner(tools=self.tools,
                                include_overview=True,
                                replan=need_replan,
                                examples=PLANNER_EXAMPLE)

                user_requirements = self.state_model.get_user_requirements()
                planner_conversation_history = self.state_model.get_agent_planner_conversation_history()

                planner_conversation_history, planner_response = await planner.create_plan(conversation_history=planner_conversation_history, user_requirements=user_requirements)

                self.mediator.emit_message('planning_ended')

                # Update planner conversation history which includes overview and tasks
                self.state_model.save_agent_planner_history(planner_conversation_history)
                plan_response_dict = planner_response.dict()
    
                # Update agent conversation history which includes only overview
                self.state_model.add_message_to_conversation_history(plan_response_dict['overview'])

                self.state_model.save_agent_plan(plan_response_dict)

                self.mediator.emit_plan(plan=plan_response_dict, summary=user_requirements['summary'], agent_name=self.name, agent_description=self.description)

                return plan_response_dict['overview']

            return 'Start execution'
            # Execute the plan
            executor = Executor(self.mediator, state)
            final_response = executor.execute_plan()

            return final_response
        else:
            # Return the assistant's message to the user
            return assistant_response.message or 'Sorry, I did not understand your request.'

    async def run_questionnaire(self, message: str):
        """
        Runs the questionnaire to collect user requirements.

        Args:
            message (str): The message from the user.

        Returns:
            dict: The assistant's response.
        """
        
        history = self.state_model.get_conversation_history()
        print('is plan exists', self.state_model.is_plan_exists())
        response_model = create_dynamic_response_model(include_plan_action=self.state_model.is_plan_exists())
        print('response_model',response_model)
        assistant_response = await self.openai_service.get_response(conversation_history=history, system_prompt=INIT_PROMPT, message=message, response_schema=response_model)

        # self.state_model.add_to_conversation_history(history)
        # print(json.dumps(history, indent=4, ensure_ascii=False))


        return assistant_response