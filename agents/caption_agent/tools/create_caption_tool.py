# tools/caption_tool.py

import openai
from pydantic import BaseModel, Field

from core.base_component import BaseComponent
from services.openai_service import OpenAIService

class AssistantResponse(BaseModel):
    caption: str = Field(None)

class CreateCaptionTool(BaseComponent):
    """
    Tool that generates captions based on the current state.
    """

    @property
    def name(self):
        return "create_caption_tool"

    @property
    def description(self):
        return "Tool for generating captions based on user input."
    
    def __init__(self):
        self.openai_service = OpenAIService(agent_name=self.name)

    async def execute(self, message: str, conversation_history: list):
        """
        Generates a caption based on the state provided.
        """

        prompt = f"Generate a caption for with the following details: {message}."

        response = await self.openai_service.get_response(
            conversation_history=conversation_history,
            system_prompt="You are an AI assistant that specializes in generating captions for social media posts. Provide a caption without any explanations or comments.",
            message=prompt,
            response_schema=AssistantResponse
        )
        return response.caption, conversation_history