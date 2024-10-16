# tools/caption_tool.py

import openai
import os
from core.base_component import BaseComponent

from pydantic import BaseModel, Field, create_model
from typing import Optional, Literal

class AssistantResponse(BaseModel):
    imageUrl: Optional[str] = Field(None, description="Image url for the post if provided")
    videoUrl: Optional[str] = Field(None, description="Video url for the post if provided")
    caption: Optional[str] = Field(None, description="Caption for the post if provided")
    hashtags: Optional[str] = Field(None, description="Hashtags for the post if provided")
    
# Load the prompt
init_prompt_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'create_post_prompt.txt')
with open(init_prompt_file_path, 'r') as file:
    INIT_PROMPT = file.read()
    
class CreatePostTool(BaseComponent):
    """
    Tool that combines hashtags, caption and image/video into one post.
    """

    @property
    def name(self):
        return "create_post_tool"

    @property
    def description(self):
        return "Tool for combining hashtags, caption and image/video into one post."

    async def execute(self, state: dict):
        """
        Returns a post with visual part, caption and hashtags.
        """
        history = state.get('conversation_history', [])
        message = "Create a post with the following image, caption and hashtags: "
        assistant_response = await self.openai_service.get_response(conversation_history=history, system_prompt=INIT_PROMPT, message=message, response_schema=AssistantResponse)
        return assistant_response
        
