# core/planner.py

import os
import openai
from typing import List, Union

from services.openai_service import OpenAIService
from pydantic import BaseModel, Field, create_model
from typing import Optional, Literal
from .prompts.planner_prompt import PLANNER_PROMPT
import json

class Argument(BaseModel):
    name: str = Field(..., description="The name of the argument.")
    value: str | int = Field(..., description="The value of the argument.")

class Task(BaseModel):
    id: str = Field(..., description="Unique 8-digit index for the task.")
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
            overview = (str, Field(..., description="A short summary of the planned actions, starting with 'I will...' and clearly describing the exact steps, indicating which actions will be done in parallel and which step-by-step. Use a conversational tone without referring to the user indirectly or adding opinions, tools, assumptions, or extra details beyond the request. Keep the response within 3-4 sentences, and conclude by asking for approval or any needed changes. It's strictly prohibited to mention any tools or agents")),
            __base__=AssistantResponse
        )
    else:
        return AssistantResponse


joiner_instructions_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'joiner_instructions.txt')
with open(joiner_instructions_file_path, 'r') as file:
    JOINER_INSTRUCTIONS = file.read()

class Planner:
    """
    The Planner uses the LLM to generate a plan (list of tasks) based on the user's query.
    """

    def __init__(self, tools: List, examples: str = ""):
        self.tools = tools
        self.examples = examples
        self.agent_state_model = None
        self.openai_service = OpenAIService(agent_name='planner')

    def set_agent_state_model(self, agent_state_model: BaseModel):
        self.agent_state_model = agent_state_model

    async def create_plan(self, conversation_history: List, user_requirements: dict, replan: bool = False, include_overview: bool = False, replan_after_execution: Union[bool, None] = None, tasks_with_results: Union[List[dict], None] = None, executed_user_requirements: Union[dict, None] = None) -> tuple[List[dict], dict]:
        """
        Creates a plan by prompting the LLM and parsing the output.

        Args:
            messages (List[dict]): The conversation history.

        Returns:
            List[Task]: A list of Task objects representing the plan.
        """
        tool_descriptions = "\n".join(
            f"{i+1}: {tool.name} - {tool.description}" for i, tool in enumerate(self.tools)
        )
        existing_tasks_ids = await self.agent_state_model.get_all_tasks_ids()

        join_included = any("join" in tool.name for tool in self.tools)

        prompt = PLANNER_PROMPT.format(
            num_tools=len(self.tools),
            tool_descriptions=tool_descriptions,
            examples=self.examples,
            existing_tasks_ids=existing_tasks_ids,
            joiner_instructions=JOINER_INSTRUCTIONS if join_included else ""
        )

        print('executed_user_requirements', executed_user_requirements)

        if replan_after_execution:
            replan_context = f"""
            The previous plan was executed based on the following requirements:
            {json.dumps(executed_user_requirements, indent=4)}

            Here is the previous plan with results:
            {json.dumps(tasks_with_results, indent=4)}

            However, the user wants to make changes to the plan. Your task is to update the previous plan according to the new user requirements. 
            - You can add, remove, or modify elements in the plan with new arguments based on the user's updated needs.
            - Any elements that do not require changes **MUST keep their original ID**.
            - If an element needs to be modified, **you MUST assign it a new ID**.
            """

            prompt += f"\n\n{replan_context}"

        print("\033[33mPlanner Prompt:\033[0m", prompt)

        response_schema = create_dynamic_response_model(include_overview)
        message = "Re-plan based on new requirements:" if replan else "Generate a plan based on user requirements:"
        message += f"\n{str(user_requirements)}"

        print("\033[33mMessage:\033[0m", message)

        assistant_response = await self.openai_service.get_response(conversation_history=conversation_history, system_prompt=prompt, message=message, response_schema=response_schema)

        print('tasks', json.dumps([task.dict() for task in assistant_response.tasks], indent=4, ensure_ascii=False))
        return conversation_history, assistant_response
