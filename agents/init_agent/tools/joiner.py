# tools/caption_tool.py

import openai
import os
from core.base_component import BaseComponent

from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Literal

from services.openai_service import OpenAIService

class AssistantResponse(BaseModel):
    imageUrl: Optional[str] = Field(None, description="Image url for the post if provided")
    videoUrl: Optional[str] = Field(None, description="Video url for the post if provided")
    caption: Optional[str] = Field(None, description="Caption for the post if provided")
    hashtags: Optional[List[str]] = Field(None, description="Hashtags for the post if provided")
    message: Optional[str] = Field(None, description="Assistant message to user")
    
# Load the prompt
init_prompt_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'joiner_prompt.txt')
with open(init_prompt_file_path, 'r') as file:
    INIT_PROMPT = file.read()
    
class JoinerTool(BaseComponent):
    """
    Tool that combines hashtags, caption and visual content into one post. Must always be the last tool in the plan.
    """

    @property
    def name(self):
        return "join"

    @property
    def description(self):
        return "Tool for combining hashtags, caption and image/video into one post."
    
    def __init__(self):
        self.openai_service = OpenAIService(agent_name=self.name)

    async def execute(self, message: str, plan: list[dict]):
        """
        Returns a post with visual part, caption and hashtags.
        """     
        print("\033[34mMessage in create_post_tool:\033[0m", message)

        assistant_response = await self.openai_service.get_response(conversation_history=[], system_prompt=INIT_PROMPT, message=message, response_schema=AssistantResponse)
        response_dict = assistant_response.dict()
        response_dict['is_done'] = True
        return response_dict
        