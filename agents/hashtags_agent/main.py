from agents.hashtags_agent.tools.create_hashtags_tool import CreateHashtagsTool
from core.base_agent import BaseAgent
from core.base_component import BaseComponent
from core.executor import Executor
from core.joiner.main import Joiner
from core.planner.main import Planner
from services.openai_service import OpenAIService
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Literal, Union
import os
import asyncio

# Load the prompt
file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'create_hashtags_prompt.txt')
planner_example_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'planner_example.txt')
joiner_example_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'joiner_example.txt')
with open(planner_example_file_path, 'r') as file:
    PLANNER_EXAMPLE = file.read()
with open(file_path, 'r') as file:
    HASHTAGS_PROMPT = file.read()
with open(joiner_example_file_path, 'r') as file:
    JOINER_EXAMPLE = file.read()

class UserRequirements(BaseModel):
    topic: Optional[str] = Field(
        None,
        description="The main topic or subject for which hashtags should be generated (e.g., 'travel', 'fitness', 'technology')."
    )
    target_audience: Optional[str] = Field(
        None,
        description="The specific audience the hashtags should target (e.g., 'millennials', 'tech enthusiasts', 'yoga lovers')."
    )
    keywords: Optional[List[str]] = Field(
        default_factory=list,
        description="Specific keywords to include in the hashtags (e.g., 'travel', 'adventure', 'nature')."
    )
    summary: str = Field(
        ...,
        description="Brief Summary of the user's requirements for hashtag generation. If the user has provided a specific requirements, include them here. Start with 'User decided to...'"
    )

class HashtagsAgent(BaseAgent):
    """
    The HashtagsAgent handles caption generation.
    """

    @property
    def name(self):
        return "create_hashtags_agent"

    @property
    def description(self):
        return "An agent that handles hashtags generation."
    
    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        create_hashtags_tool = CreateHashtagsTool()
        joiner = Joiner(JOINER_EXAMPLE)
        agent_tools = [create_hashtags_tool, joiner]
        super().__init__(mediator, agent_tools + (tools or []))
        self.openai_service = OpenAIService(agent_name=self.name)
        self.executor = Executor(tools=agent_tools, agent=self)
        self.include_overview = False
        self.planner = Planner(tools=self.tools, examples=PLANNER_EXAMPLE)
        self.questionnaire_prompt = HASHTAGS_PROMPT
        self.user_requirements_schema = UserRequirements
        self.status = None

    def get_response_model(self):
        # extra_fields = {
        #     "redirect": (bool, Field(..., description="If user asks non related to hashtags generation, set redirect to True"))
        # }
        return self._create_dynamic_response_model(extra_fields={})
