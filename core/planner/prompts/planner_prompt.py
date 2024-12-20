# prompts/planner_prompt.py

PLANNER_PROMPT = """
Given a user query, create a plan to solve it with the utmost parallelism. Each plan should comprise an action from the following {num_tools} types:
{tool_descriptions}

{joiner_instructions}

Guidelines:
 - Each action described above contains input/output types and description.
    - You must strictly adhere to the input and output types for each action.
    - The action descriptions contain the guidelines. You MUST strictly follow those guidelines when you use the actions.
 - Each action in the plan should strictly be one of the above types. Follow the Python conventions for each action.
 - Each action MUST have a unique ID, which is strictly increasing.
 - Inputs for actions can either be constants or outputs from preceding actions. In the latter case, use the format $id to denote the ID of the previous action whose output will be the input.
 - Always call join as the last action in the plan.
 - Only use the provided action types. If a query cannot be addressed using these, invoke the join action for the next steps.
  - If 'context_results' is provided, you MUST use these results as context in relevant arguments for the tools.
 - Never introduce new actions other than the ones provided.

An example of how correct answer look like:
{examples}

Do not use the following IDs:
{existing_tasks_ids}
"""

#  - Ensure the plan maximizes parallelism.