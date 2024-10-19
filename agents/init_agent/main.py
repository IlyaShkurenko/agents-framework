# agents/init_agent.py

from agents.hashtags_agent.tools.create_hashtags_tool import CreateHashtagsTool
from core.base_agent_with_plan_approve import BaseAgentWithPlanApprove
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

# def create_dynamic_response_model(include_plan_action: bool = False, include_result_accepted: bool = False):
#     if include_plan_action:
#         return create_model(
#             'AssistantResponseWithReplan',
#             plan_approved=(bool, Field(..., description="True if the user explicitly confirms that he want to proceed with the plan as is. False if the user asks any questions, requests clarifications, or indicates that he wants to adjust the plan.")),
#             __base__=AssistantResponse
#         )
#     elif include_result_accepted:
#         return create_model(
#             'AssistantResponseWithResultAccepted',
#             result_accepted=(bool, Field(..., description="True if the user explicitly confirms that he want to proceed with the result as is. False if the user asks any questions, requests clarifications, or indicates that he wants to adjust the result.")),
#             changes_to_apply=(str, Field(..., description="Changes to apply to the result if the user wants to adjust the result. Otherwise, it should be empty ''. Exists only if result_accepted is False")),
#             __base__=AssistantResponse
#         )
#     else:
#         return AssistantResponse

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
    
    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        create_post_tool = CreatePostTool()
        create_hashtags_tool = CreateHashtagsTool()

        all_tools = [create_post_tool] + (tools or [])
        super().__init__(mediator, all_tools)
        self.executor = Executor(tools=[create_post_tool, create_hashtags_tool], agent=self)
        self.openai_service = OpenAIService(agent_name=self.name)
        self.planner_example = PLANNER_EXAMPLE
        self.planner = Planner(tools=all_tools, examples=self.planner_example)
        self.questionnaire_prompt = INIT_PROMPT
        self.has_joiner = False
        self.status = None     
        self.user_requirements_schema = UserRequirements
        self.include_overview = True
        self.include_plan_action = False

    def get_response_model(self):
        extra_fields = {
            "redirect": (bool, Field(..., description="If user asks non related to image generation, set redirect to True"))
        }
        return self._create_dynamic_response_model(extra_fields=extra_fields)
    


# start_time = time.time()    
#         plan = [
#{
#                 "id": "32412469",
#                 "description": "Call the create_caption_tool with the appropriate prompt to generate a caption for the Instagram post.",
#                 "dependencies": [],
#                 "tool": "create_caption_tool",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "Generate a creative and engaging caption for an Instagram post about a vacation to Bali"
#                 }
#             ]
#         },
#             {
#                 "id": "32412460",
#                 "description": "Call the create_caption_agent with the appropriate prompt to generate a caption for the Instagram post.",
#                 "dependencies": [32412469],
#                 "tool": "create_caption_agent",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "Generate a creative and engaging caption for an Instagram post about a vacation to Bali"
#                 }
#             ]
#         },
#         {
#             "id": "32412461",
#             "description": "Use the create_hashtags_agent to generate relevant hashtags for the Instagram post. Ensure that the hashtags are generated using the caption from the previous step (ID: 32412460) to provide better context and coherence between the caption and hashtags.",
#             "dependencies": [32412460],
#             "tool": "create_hashtags_agent",
#             "arguments": [
# 			    {
#                         "name": "prompt",
#                         "value": "Generate relevant hashtags for an Instagram post about a vacation to Bali."
#                     }
#                 ]
#             },
#             {
#                 "id": "32412462",
#                 "description": "Call the create_post_tool with the caption and hashtags to create the final Instagram post.",
#                 "dependencies": ["32412460", "32412461"],
#                 "tool": "create_post_tool",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "Create an Instagram post using the generated caption and hashtags."
#                     }
#                 ]
#             }
# ]
#         asyncio.create_task(self.mediator.emit_plan(plan=plan, summary='Generates a post with hashtags and caption', agent_name=self.name))
#         end_time = time.time()
#         print(f"Time taken to emit plan: {end_time - start_time} seconds")
#         return 'Start questionnaire'    