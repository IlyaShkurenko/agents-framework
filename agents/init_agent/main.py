# agents/init_agent.py

from agents.hashtags_agent.tools.create_hashtags_tool import CreateHashtagsTool
from core.base_agent_with_plan_approve import BaseAgentWithPlanApprove
from core.base_component import BaseComponent
from .tools.joiner import JoinerTool
from core.base_agent import BaseAgent
from core.planner.main import Planner
from core.executor import Executor
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Literal, Type, Union
from services.openai_service import OpenAIService
import os
import json
import time
import asyncio

# Load the prompt
init_prompt_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'init_prompt.txt')
planner_example_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'planner_example.txt')
with open(init_prompt_file_path, 'r') as file:
    INIT_PROMPT = file.read()
with open(planner_example_file_path, 'r') as file:
    PLANNER_EXAMPLE = file.read()

class InitAgent(BaseAgentWithPlanApprove):
    """
    The InitAgent handles the initial interaction with the user.
    """

    @property
    def name(self):
        return "init_agent"

    @property
    def description(self):
        return "Agent responsible for initial interaction with the user. Collects user requirements and creates a plan for creation a social media content."

    # @property
    # def user_requirements_schema(self) -> Type[BaseModel]:
    #     return UserRequirements
    
    @property
    def questionnaire_prompt(self) -> str:
        return INIT_PROMPT
    
    @property
    def include_overview(self) -> bool:
        return True
    
    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        joiner_tool = JoinerTool()
        all_tools = [joiner_tool] + (tools or [])
        super().__init__(mediator, all_tools)
        self.executor = Executor(tools=all_tools, agent=self)
        self.planner = Planner(tools=all_tools, examples=PLANNER_EXAMPLE)

    def get_questionnaire_response_model(self):
        extra_fields = {
            # "redirect": (bool, Field(..., description="If user asks non related to image generation, set redirect to True"))
        }

        user_requirements_fields = {
            "content_uploaded": (bool, Field(
                ...,
                description="Whether the user has uploaded content like an image or video."
            )),
            "visual_content_action": (Literal['edit', 'generate', 'none'], Field(
                ...,
                description="Action on visual content. 'edit' only if the user has uploaded content like an image or video. 'edit' or 'generate' only if the user required visual part in the message; otherwise, 'none'."
            )),
            "caption_needed": (bool, Field(
                ...,
                description="Whether the user needs a caption."
            )),
            "hashtags_needed": (bool, Field(
                ...,
                description="Whether the user needs hashtags."
            ))
        }

        # message_field_description = "Assistant message. Must exist if user_requirements_status is 'incomplete' or user_requirements is None. It is forbidden to return any social media content which user requests. Remember to include message if user_requirements is None. If user wants to edit visual content or generate a caption based on visual content then ensure he provided links in chat dialogue like .png, jpg, .mov, etc. Otherwise require user to provide it"

        return self._create_dynamic_response_model(extra_fields=extra_fields, user_requirements_fields=user_requirements_fields)
  