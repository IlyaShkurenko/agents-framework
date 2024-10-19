# core/joiner.py
from services.openai_service import OpenAIService


class Joiner:
    """
    The Joiner collects and combines results from prior actions.
    """

    def __init__(self):
        self.openai_service = OpenAIService(agent_name="joiner")

    async def join(self, initial_message, final_response):
        """
        Joins the observations to form the final response.
        """
        message = f"Your task is to create a friendly response to the user request: {initial_message}. Request finished with results: {final_response}. You should ask if user liked the results or wants to change something."
        print("\033[33mJoiner Prompt:\033[0m", message)
        assistant_response = await self.openai_service.get_response(conversation_history=[], system_prompt="", message=message)
        return assistant_response
