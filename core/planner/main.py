# core/planner.py

import openai
from typing import List

from services.openai_service import OpenAIService
from pydantic import BaseModel, Field, create_model
from typing import Optional, Literal
from .prompts.planner_prompt import PLANNER_PROMPT
import json

class Argument(BaseModel):
    name: str = Field(..., description="The name of the argument.")
    value: str | int = Field(..., description="The value of the argument.")

class Task(BaseModel):
    idx: str = Field(..., description="Unique 8-digit index for the task.")
    tool: str = Field(..., description="The name of the tool to be used for this task.")
    arguments: List[Argument] = Field(..., description="List of arguments for the tool.")
    dependencies: List[str] = Field(..., description="Array of strings representing task dependencies. Should be other tasks ids")
    description: str = Field(..., description="A description of the task.")

class AssistantResponse(BaseModel):
    tasks: List[Task]

def create_dynamic_response_model(include_overview: bool = False):
    if include_overview:
        return create_model(
            'AssistantResponseWithOverview',
            overview = (str, Field(..., description="A short summary of the planned actions, starting with 'I will...' and describing the exact steps clearly and concisely, as if directly addressing the user. Avoid using phrases like 'the user' and do not introduce opinions, tools, assumptions, or extra details beyond the original request. Keep the response within 3-4 sentences, and conclude by asking for approval or if any changes are needed.")),
            __base__=AssistantResponse
        )
    else:
        return AssistantResponse


class Planner:
    """
    The Planner uses the LLM to generate a plan (list of tasks) based on the user's query.
    """

    def __init__(self, 
                 tools: List,
                 include_overview: bool = False,
                 replan: bool = False,
                 examples: str = "",
                 planner_agent_name: str = "planner",
                 model: str = "gpt-4o"):
        self.tools = tools
        self.include_overview = include_overview
        self.replan = replan
        self.model = model
        self.examples = examples
        self.planner_agent_name = planner_agent_name
        self.openai_service = OpenAIService(agent_name=self.planner_agent_name)

    async def create_plan(self, conversation_history: List, user_requirements: dict) -> tuple[List[dict], dict]:
        """
        Creates a plan by prompting the LLM and parsing the output.

        Args:
            messages (List[dict]): The conversation history.

        Returns:
            List[Task]: A list of Task objects representing the plan.
        """
        tool_descriptions = "\n".join(
            f"{i+1}. {tool.description}" for i, tool in enumerate(self.tools)
        )

        # additional_context_section = f"\n{self.additional_context}" if self.additional_context else ""
    
        prompt = PLANNER_PROMPT.format(
            num_tools=len(self.tools) + 1,  # Including join()
            tool_descriptions=tool_descriptions,
            examples=self.examples
        )

        print('prompt', prompt)

        response_schema = create_dynamic_response_model(self.include_overview)
        message = "Re-plan based on new requirements:" if self.replan else "Generate a plan based on user requirements:"
        message += f"\n{str(user_requirements)}"

        assistant_response = await self.openai_service.get_response(conversation_history=conversation_history, system_prompt=prompt, message=message, response_schema=response_schema)

        print('tasks', json.dumps([task.dict() for task in assistant_response.tasks], indent=4, ensure_ascii=False))
        return conversation_history, assistant_response
