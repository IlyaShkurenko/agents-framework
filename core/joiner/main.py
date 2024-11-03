# # core/joiner.py
# from services.openai_service import OpenAIService


# class Joiner:
#     """
#     The Joiner collects and combines results from prior actions.
#     """

#     def __init__(self):
#         self.openai_service = OpenAIService(agent_name="joiner")

#     async def join(self, initial_message, final_response):
#         """
#         Joins the observations to form the final response.
#         """
#         message = f"Your task is to create a friendly response to the user request: {initial_message}. Request finished with results: {final_response}. You should ask if user liked the results or wants to change something."
#         print("\033[33mJoiner Prompt:\033[0m", message)
#         assistant_response = await self.openai_service.get_response(conversation_history=[], system_prompt="", message=message)
#         print("\033[33mJoiner Response:\033[0m", assistant_response)
#         return assistant_response

# tools/caption_tool.py

import json
from typing import Union
import openai
from pydantic import BaseModel, Field

from core.base_component import BaseComponent
from core.joiner.prompts.joiner_prompt import JOINER_PROMPT
from services.openai_service import OpenAIService

class AssistantResponse(BaseModel):
    caption: str = Field(None)

class Joiner(BaseComponent):
    """
    Tool that generates captions based on the current state.
    """

    @property
    def name(self):
        return "join"

    @property
    def description(self):
        return "Tool for join results of other tools"
    
    def __init__(self, example: str = ""):
        self.openai_service = OpenAIService(agent_name=self.name)
        self.example = example

    async def execute(self, message: str, plan: list[dict]):
        """
        Generates a caption based on the state provided.
        """
        print('in joiner')

        prompt = JOINER_PROMPT.format(plan=json.dumps(plan, indent=2), example=self.example)

        print("\033[33mJoiner Prompt:\033[0m", prompt)

        print("\033[33mJoiner Message:\033[0m", message)
        response = await self.openai_service.get_response(
            conversation_history=[],
            system_prompt=prompt,
            message=message
        )
        # print("\033[33mJoiner Response:\033[0m", response)
        return response

