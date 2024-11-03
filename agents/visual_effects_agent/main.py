from agents.visual_effects_agent.tools.joiner import Joiner
from core.base_agent import BaseAgent
from core.base_agent_with_plan_approve import BaseAgentWithPlanApprove
from core.base_component import BaseComponent
from core.executor import Executor
from core.planner.main import Planner
from services.openai_service import OpenAIService
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Literal, Type, Union
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
    # content_uploaded: bool = Field(...)
    visual_content_action: Literal['edit', 'generate', 'no_needed'] = Field(...)
    generate_image: bool = Field(...)
    # generate_video: bool = Field(...)
    # edit_video: bool = Field(...)
    # edit_image: bool = Field(...)
    # combine_images: bool = Field(...)
    # combine_videos: bool = Field(...)
    # add_text_overlay: bool = Field(...)
    # add_special_effect: bool = Field(...)
    # add_music: bool = Field(...)
    # add_voice_over: bool = Field(...)
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
    
    # @property
    # def user_requirements_schema(self) -> Type[BaseModel]:
    #     return UserRequirements
    
    @property
    def questionnaire_prompt(self) -> str:
        return VISUAL_EFFECTS_PROMPT
    
    @property
    def include_overview(self) -> bool:
        return True

    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        super().__init__(mediator, tools or [])
        joiner_tool = Joiner()
        all_tools = [joiner_tool] + (tools or [])
        self.planner = Planner(tools=all_tools, examples=PLANNER_EXAMPLE)
        self.executor = Executor(tools=all_tools, agent=self)
        # We don't want to emit message on agent done for visual effects agent since it have only image agent as a dependency for now
        self.emit_message_on_agent_done = False
    
    def get_questionnaire_response_model(self):
        # Add custom field `redirect` for this agent
        extra_fields = {
            # "redirect": (bool, Field(..., description="If user asks non-related to visual effects generation or editing, set redirect to True."))
        }
        user_requirements_fields = {
            "visual_content_action": (Literal['edit', 'generate', 'no_needed'], Field(
                ...,
                description="Specifies the action on visual content. Options: 'edit' if content already exists, 'generate' to create new content, 'no_needed' if no visual content is required."
            )),
            "generate_image": (bool, Field(
                ...,
                description="Indicates whether an image should be generated."
            ))
        }

        # Create dynamic response model with extra fields
        return self._create_dynamic_response_model(extra_fields=extra_fields, user_requirements_fields=user_requirements_fields)