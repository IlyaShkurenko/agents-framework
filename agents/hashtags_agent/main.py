# agents/caption_agent.py

import openai
from agents.hashtags_agent.tools.create_hashtags_tool import CreateLLMHashtagsTool
from core.base_agent import BaseAgent
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
import os

from core.base_component import BaseComponent
from services.openai_service import OpenAIService

# Load the prompt
file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'create_hashtags_prompt.txt')

with open(file_path, 'r') as file:
    HASHTAGS_PROMPT = file.read()

class HashtagsPreferences(BaseModel):
    hashtags_style: Literal['informative', 'humorous', 'inspirational', 'other'] = Field(..., description="Style of the hashtags")
    additional_notes: str = Field("", description="Any additional notes from the user")

class AssistantResponse(BaseModel):
    message: str = Field(None, description="Assistant's message to the user")
    hashtags_preferences: HashtagsPreferences = Field(None, description="User's hashtags preferences")

class HashtagsAgent(BaseAgent):
    """
    The HashtagsAgent handles hashtag generation.
    """
    @property
    def name(self):
        return "create_hashtags_agent"

    @property
    def description(self):
        return "An agent that handles hashtag generation."
    
    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        self.create_llm_hashtags_tool = CreateLLMHashtagsTool()
        super().__init__(mediator, [self.create_llm_hashtags_tool] + (tools or []))
        
        self.openai_service = OpenAIService(agent_name=self.name)

    def handle_message(self, client_id: str, chat_id: str, message: str, state: dict):
        # Check if we have enough context to proceed
        if 'hashtags_preferences' not in state:
            # Run the questionnaire to collect hashtags style
            response = self.run_questionnaire(message, state)
            assistant_response = response.get('assistant_response')

            # Update conversation history
            conversation_history = state.get('conversation_history', [])
            conversation_history.append({"role": "assistant", "content": assistant_response.message, "agent": self.name})
            state['conversation_history'] = conversation_history

            if assistant_response.hashtags_preferences:
                state['hashtags_preferences'] = assistant_response.hashtags_preferences.dict()
            else:
                # Return the assistant's message to the user
                return assistant_response.message or 'Sorry, I did not understand your request.'

        # Generate the caption using the tool
        # caption = CaptionTool().execute(state)
        # return caption

    def run_questionnaire(self, message: str, state: dict):
        """
        Runs the questionnaire to collect caption preferences.

        Args:
            message (str): The message from the user.

        Returns:
            dict: The assistant's response.
        """
        messages = state.get('conversation_history', [])
        messages.append({"role": "system", "content": HASHTAGS_PROMPT, "agent": self.name})
        if message:
            messages.append({"role": "user", "content": message, "agent": "user"})

        # Convert messages to OpenAI format
        openai_messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages if msg["agent"] == self.name or msg["agent"] == "user"]

        # Use the OpenAI ChatCompletion with Pydantic parsing
        response = openai.ChatCompletion.create(
            model="gpt-4-0613",
            messages=openai_messages,
            temperature=0.7,
            max_tokens=150,
            response_format=AssistantResponse  # This is the Pydantic model
        )

        assistant_message = response.choices[0].message

        # Parse the assistant's response using the Pydantic model
        assistant_response = assistant_message.parsed

        return {'assistant_response': assistant_response}
