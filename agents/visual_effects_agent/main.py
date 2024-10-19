from core.base_agent import BaseAgent
from core.base_agent_with_plan_approve import BaseAgentWithPlanApprove
from core.base_component import BaseComponent
from core.executor import Executor
from core.joiner import Joiner
from core.planner.main import Planner
from services.openai_service import OpenAIService
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Literal, Union
import os
import asyncio

# Load the prompt
file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'create_visual_effects_prompt.txt')
planner_example_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'planner_example.txt')

with open(planner_example_file_path, 'r') as file:
    PLANNER_EXAMPLE = file.read()
with open(file_path, 'r') as file:
    VISUAL_EFFECTS_PROMPT = file.read()

# class UserRequirements(BaseModel):
#     content_uploaded: bool = Field(..., description="Whether the user has uploaded content like image or vide")
#     visual_content_action: Literal['edit', 'generate', 'no_needed'] = Field(..., description="Action on visual content. Suggest edit only if user has uploaded content like image or video")
#     generate_image: bool = Field(..., description="Whether the user wants to generate a new image")
#     generate_video: bool = Field(..., description="Whether the user wants to generate a new video")
#     edit_video: bool = Field(..., description="Whether the user wants to edit a video")
#     edit_image: bool = Field(..., description="Whether the user wants to edit an image")
#     combine_images: bool = Field(..., description="Whether the user wants to combine images")
#     combine_videos: bool = Field(..., description="Whether the user wants to combine videos")
#     add_text_overlay: bool = Field(..., description="Whether the user wants to add a text overlay")
#     add_special_effect: bool = Field(..., description="Whether the user wants to add a special effect")
#     add_music: bool = Field(..., description="Whether the user wants to add music")
#     add_voice_over: bool = Field(..., description="Whether the user wants to add voice over")
#     summary: str = Field(..., description="Brief Summary of the user's requirements. This info will be used by next agent to create a plan. If user mentioned sequence of actions then include it in summary so plan can be correct. Change it only if new requirements are provided otherwise leave it as is. Start with 'User decided to'")

class UserRequirements(BaseModel):
    content_uploaded: bool = Field(False)
    visual_content_action: Literal['edit', 'generate', 'no_needed'] = Field(..., description="Action on visual content. Suggest edit only if user has uploaded content like image or video")
    generate_image: bool = Field(False)
    generate_video: bool = Field(False)
    edit_video: bool = Field(False)
    edit_image: bool = Field(False)
    combine_images: bool = Field(False)
    combine_videos: bool = Field(False)
    add_text_overlay: bool = Field(False)
    add_special_effect: bool = Field(False)
    add_music: bool = Field(False)
    add_voice_over: bool = Field(False)
    summary: str = Field(..., description="Brief Summary of the user's requirements. This info will be used by next agent to create a plan. If user mentioned sequence of actions then include it in summary so plan can be correct. Change it only if new requirements are provided otherwise leave it as is. Start with 'User decided to'")

class VisualEffectsAgent(BaseAgentWithPlanApprove):
    """
    The VisualEffectsAgent handles visual effects generation or editing.
    """

    @property
    def name(self):
        return "create_visual_effects_agent"

    @property
    def description(self):
        return "An agent that handles visual effects generation or editing."

    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        super().__init__(mediator, tools or [])
        self.openai_service = OpenAIService(agent_name=self.name)
        self.planner_example = PLANNER_EXAMPLE
        self.planner = Planner(tools=self.tools, examples=self.planner_example)
        self.include_overview = True
        self.executor = Executor(tools=self.tools, agent=self)
        self.status = None
        self.questionnaire_prompt = VISUAL_EFFECTS_PROMPT
        self.initial_message = None
        self.joiner = Joiner()
        self.has_joiner = True
        self.user_requirements_schema = UserRequirements
        self.include_plan_action = False

    def get_response_model(self):
        # Add custom field `redirect` for this agent
        extra_fields = {
            "redirect": (bool, Field(..., description="If user asks non-related to visual effects generation or editing, set redirect to True."))
        }
        # Create dynamic response model with extra fields
        return self._create_dynamic_response_model(extra_fields=extra_fields)