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

# class Task(BaseModel):
#     id: str = Field(..., description="Unique 8-digit index for the task.")
#     tool: str = Field(..., description="The name of the tool to be used for this task.")
#     arguments: List[Argument] = Field(..., description="List of arguments for the tool.")
#     dependencies: List[str] = Field(..., description="Array of strings representing task dependencies. Should be other tasks ids")
#     description: str = Field(..., description="A description of the task.")

# class AssistantResponse(BaseModel):
#     tasks: List[Task]

def create_argument_model(plan_was_executed: bool = False):
    arguments_value_description = "The value of the argument. Detailed as possible. If other tasks results exists, use them as context here"
    
    if plan_was_executed:
        # arguments_value_description += " If result_action_feedback is 'adjust', start the 'value' with 'Adjust previous result with...' followed by the user's exact change request."
        arguments_value_description = "start with 'Adjust previous result to...' followed by the user's exact change request"
        # arguments_value_description = "result_action_feedback field value"

    print("\033[1;33mPlanner arguments prompt\033[0m", arguments_value_description)
    

    return create_model(
        'Argument',
        name=(str, Field(..., description="The name of the argument.")),
        value=(str, Field(..., description=arguments_value_description)),
        __base__=BaseModel
    )

def create_task_model(plan_was_executed: bool = False):
    arguments_description = "List of arguments for the tool."
    
    # if plan_was_executed:
    #     arguments_description += " If result_action_feedback is 'adjust', for arguments where name is 'prompt', start the 'value' with 'Adjust previous result with...' followed by the user's exact change request."

    print("\033[1;33mPlanner arguments prompt\033[0m", arguments_description)

    ArgumentModel = create_argument_model(plan_was_executed)
    
    return create_model(
        'Task',
        id=(str, Field(..., description="Unique 8-digit index for the task.")),
        tool=(str, Field(..., description="The name of the tool to be used for this task.")),
        arguments=(List[ArgumentModel], Field(..., description=arguments_description)),
        dependencies=(List[str], Field(..., description="Array of strings representing task dependencies. Should be other tasks ids")),
        description=(str, Field(..., description="A description of the task.")),
        __base__=BaseModel
    )

def create_dynamic_response_model(include_overview: bool = False, plan_was_executed: bool = False):
        dynamic_fields = {}
    
        if include_overview:
            dynamic_fields['overview'] = (str, Field(..., description="A short summary of the planned actions, starting with 'I will...' and clearly describing the exact steps, indicating which actions will be done in parallel and which step-by-step. Use a conversational tone without referring to the user indirectly or adding opinions, tools, assumptions, or extra details beyond the request. Keep the response within 3-4 sentences, and conclude by asking for approval or any needed changes. It's strictly prohibited to mention any tools or agents"))

        # if plan_was_executed:
        #     dynamic_fields['result_action_feedback'] = (Literal["adjust", "recreate"], Field(None, description="Indicates user's feedback after initial results. Set to 'adjust' if the user wants to refine, modify, or add specific elements to the existing results. Use 'recreate' if the user prefers to discard current results entirely and start fresh from the beginning."))

        TaskModel = create_task_model(plan_was_executed=plan_was_executed)

        response_model = create_model(
            'DynamicAssistantResponse',
            **dynamic_fields, 
            tasks=(List[TaskModel], ...)
        )
        print("\033[33mPlanner response model fields:\033[0m")
        for field_name, field_info in response_model.model_fields.items():
            print(f"Field: {field_name}, Description: {field_info.description}")
        return response_model

# def create_dynamic_response_model(include_overview: bool = False, plan_was_executed: bool = False):
#     if include_overview:
#         return create_model(
#             'AssistantResponseWithOverview',
#             overview = (str, Field(..., description="A short summary of the planned actions, starting with 'I will...' and clearly describing the exact steps, indicating which actions will be done in parallel and which step-by-step. Use a conversational tone without referring to the user indirectly or adding opinions, tools, assumptions, or extra details beyond the request. Keep the response within 3-4 sentences, and conclude by asking for approval or any needed changes. It's strictly prohibited to mention any tools or agents")),
#             __base__=AssistantResponse
#         )
#     else:
#         return AssistantResponse


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

    async def create_plan(self, 
                          conversation_history: List, 
                          user_requirements: Union[dict, str],
                          replan: bool = False, 
                          include_overview: bool = False, 
                          replan_after_execution: bool = False,
                          existing_tasks_ids: List[str] = [],
                          tasks_with_results: List[dict] = [],
                          dependencies_message: str = "",
                          previous_user_requirements: Union[dict, None] = None) -> tuple[List[dict], dict]:
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
        
        join_included = any("join" in tool.name for tool in self.tools)

        tasks_with_results_ids = {task["id"] for task in tasks_with_results}

        tasks_ids_to_exclude = [task_id for task_id in existing_tasks_ids if task_id not in tasks_with_results_ids] if replan_after_execution else existing_tasks_ids


        prompt = PLANNER_PROMPT.format(
            num_tools=len(self.tools),
            tool_descriptions=tool_descriptions,
            examples=self.examples,
            existing_tasks_ids=tasks_ids_to_exclude,
            joiner_instructions=JOINER_INSTRUCTIONS if join_included else ""
        )

        print('previous_user_requirements', previous_user_requirements)

            # The previous plan was executed based on the following requirements:
            # {json.dumps(previous_user_requirements, indent=4)}

            # Here is the previous plan with results:
            # {json.dumps(tasks_with_results, indent=4)}

        if replan_after_execution:
            replan_context = f"""
            The user wants to make changes to the plan. Your task is to update the previous plan according to the new user requirements. 
            - You can add, remove, or modify elements in the plan with new arguments based on the user's updated needs.
            - Any elements that do not require changes **MUST keep their original ID**.
            - If an element needs to be modified, **you MUST assign it a new ID**.
            - You must change the IDs of the tasks that depend on the modified tasks.
            - Ensure to provide requested adjustments in tool's arguments instead the whole task. Remember that it's modification and not a complete reset.
            """

            prompt += f"\n\n{replan_context}"

        print("\033[33mPlanner Prompt:\033[0m", prompt)

        response_schema = create_dynamic_response_model(include_overview, replan_after_execution)
        message = ""

        if dependencies_message:
            message += f"\n{dependencies_message}\nIt is mandatory to provide this as a context to corresponding tool arguments\n"

        message += "Re-plan based on new requirements:" if replan else "Generate a plan based on user requirements:"
        message += f"\n{str(user_requirements)}"

        # if replan_after_execution:
        #     message += "\nIf the user requests additions, modifications, or deletions include only the specific requirement in the corresponding tool's arguments, without passing the full task. This maintains the history, so the new plan reflects changes rather than a complete reset."

        print("\033[33mMessage:\033[0m", message)

        assistant_response = await self.openai_service.get_response(conversation_history=conversation_history, system_prompt=prompt, message=message, response_schema=response_schema)

        print('tasks', json.dumps([task.dict() for task in assistant_response.tasks], indent=4, ensure_ascii=False))
        if isinstance(assistant_response, BaseModel):
            plan_response_dict = assistant_response.model_dump()
        else:
            plan_response_dict = assistant_response
        return conversation_history, plan_response_dict
