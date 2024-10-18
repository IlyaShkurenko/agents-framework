from core.base_agent import BaseAgent
from core.base_component import BaseComponent
from core.executor import Executor
from core.planner.main import Planner
from services.openai_service import OpenAIService
from .tools.create_caption_tool import CreateCaptionTool
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Literal, Union
import os
import asyncio

# Load the prompt
file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'create_caption_prompt.txt')
planner_example_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'planner_example.txt')

with open(planner_example_file_path, 'r') as file:
    PLANNER_EXAMPLE = file.read()
with open(file_path, 'r') as file:
    CAPTION_PROMPT = file.read()

class UserRequirements(BaseModel):
    topic: Optional[str] = Field(
        None,
        description="The main topic or subject of the post (e.g., 'travel', 'fitness', 'technology')."
    )
    tone: Optional[Literal['formal', 'informal', 'humorous', 'inspirational', 'sarcastic']] = Field(
        None,
        description="The tone or style of the caption (e.g., 'humorous', 'inspirational', 'sarcastic')."
    )
    storytelling: Optional[bool] = Field(
        None,
        description="Whether the caption should use storytelling to engage the audience."
    )
    interaction_type: Optional[Literal['question', 'poll', 'call_to_action', 'none']] = Field(
        None,
        description="How the caption should engage users (e.g., asking a question, running a poll, or including a call to action)."
    )
    length: Optional[Literal['short', 'medium', 'long']] = Field(
        None,
        description="The desired length of the caption (e.g., 'short', 'medium', 'long')."
    )
    emojis: Optional[bool] = Field(
        None,
        description="Whether the caption should include emojis."
    )
    keywords: Optional[List[str]] = Field(
        default_factory=list,
        description="Specific keywords to include in the caption for SEO or emphasis."
    )
    summary: str = Field(
        ...,
        description="Brief summary of the user's requirements for the caption. If the user has provided a specific requirements, include them here. Start with 'User decided to...'"
    )
class AssistantResponse(BaseModel):
    redirect: bool = Field(False, description="If user asks non related to caption generation, set redirect to True.")
    user_requirements: Optional[UserRequirements] = Field(None, description="User's requirements in structured form, only if all information is provided, otherwise None")
    message: str = Field(None, description="Assistant's message to the user. Do not mention structured information. Should be empty '' if user_requirements is provided or redirect is True")

class CaptionAgent(BaseAgent):
    """
    The CaptionAgent handles caption generation.
    """

    @property
    def name(self):
        return "create_caption_agent"

    @property
    def description(self):
        return "An agent that handles caption generation with various styles."

    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        self.create_caption_tool = CreateCaptionTool()
        super().__init__(mediator, [self.create_caption_tool] + (tools or []))
        self.openai_service = OpenAIService(agent_name=self.name)
        self.planner = Planner(tools=self.tools, examples=PLANNER_EXAMPLE)
        self.include_overview = False
        self.executor = Executor(tools=[self.create_caption_tool], agent=self)
        self.status = None
        self.questionnaire_prompt = CAPTION_PROMPT
        self.questionnaire_response_schema = AssistantResponse