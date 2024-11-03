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
    
# Load the prompt
init_prompt_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'joiner_prompt.txt')
with open(init_prompt_file_path, 'r') as file:
    INIT_PROMPT = file.read()
    
class Joiner(BaseComponent):
    """
    Tool that combines image/video into one json object.
    """

    @property
    def name(self):
        return "join"

    @property
    def description(self):
        return "Tool for combining image or video into one object. Must always be the last tool in the plan."
    
    def __init__(self):
        self.openai_service = OpenAIService(agent_name=self.name)

    async def execute(self, message: str, plan: list[dict]):
        """
        Returns a post with visual part, caption and hashtags.
        """     
        print("\033[34mMessage in joiner:\033[0m", message)

        assistant_response = await self.openai_service.get_response(conversation_history=[], system_prompt=INIT_PROMPT, message=message, response_schema=AssistantResponse)
        response_dict = assistant_response.dict()
        response_dict['is_done'] = True
        return response_dict
        