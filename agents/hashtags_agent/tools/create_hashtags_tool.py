# tools/caption_tool.py

from typing import List
from pydantic import BaseModel, Field

from core.base_component import BaseComponent

class AssistantResponse(BaseModel):
    hashtags: List[str] = Field(default_factory=list)

class CreateHashtagsTool(BaseComponent):
    """
    Tool that generates hashtags based on the current state.
    """

    @property
    def name(self):
        return "create_hashtags_tool"

    @property
    def description(self):
        return "Tool for generating hashtags based on LLM."

    async def execute(self, message: str):
        """
        Generates hashtags based on the state provided.
        """
        prompt = f"Generate hashtags for with the following details: {message}."

        response = await self.openai_service.get_response(
            conversation_history=[],
            system_prompt="You are an AI assistant that specializes in generating hashtags for social media posts. Provide a list of hashtags without any explanations or comments.",
            message=prompt,
            response_schema=AssistantResponse
        )
        return response.hashtags
