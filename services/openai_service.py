from datetime import datetime
from pprint import pprint
from typing import Optional, Union
import openai


import json
from pydantic import BaseModel

async def openai_structured_outputs_stream(**kwargs):
    client = openai.AsyncOpenAI()

    async with client.beta.chat.completions.stream(
        **kwargs, stream_options={"include_usage": True}
    ) as stream:
        async for chunk in stream:
            try:
                if chunk.type == 'chunk':
                    latest_snapshot = chunk.to_dict().get('snapshot')
                    if not latest_snapshot:
                        # print("Snapshot is missing in chunk, skipping.")
                        continue

                    choices = latest_snapshot.get('choices', [])
                    if not choices or 'message' not in choices[0]:
                        # print("No valid choices or message in snapshot, skipping.")
                        continue

                    latest_parsed = choices[0]['message'].get('parsed')
                    if latest_parsed:
                        yield latest_parsed
                    # else:
                        # print("Parsed data is empty or not found in chunk")
            except Exception as e:
                print(f"Error processing chunk: {e}")
                continue

class OpenAIService:
    """
    This class handles interactions with the OpenAI API, optionally using a schema to parse the response.
    """

    def __init__(self, agent_name: str):
        """
        Initializes the OpenAI handler with agent name and system prompt.
        
        Args:
            agent_name (str): The name of the agent.
            system_prompt (str): The system prompt to guide the assistant.
        """
        self.agent_name = agent_name
        # self.client = openai.OpenAI()  # Initialize the OpenAI client
        self.client = openai.AsyncOpenAI()  # Initialize the OpenAI client

    async def get_response(self, conversation_history: list, system_prompt: Union[str, None], message: str, response_schema: Optional[BaseModel] = None):
        """
        Sends a request to the OpenAI API and optionally parses the response using a schema.

        Args:
            conversation_history (list): The list of previous conversation messages.
            message (str): The new message from the user.
            response_schema (BaseModel, optional): Pydantic model to validate the OpenAI response.

        Returns:
            dict: Parsed response from OpenAI if schema is provided, otherwise raw response.
        """
        # Add system message at the beginning
        if not any(msg["role"] == "system" for msg in conversation_history):
            # Add system message at the beginning if it's not already there
            if system_prompt:
                conversation_history.insert(0, {"role": "system", "content": system_prompt, "agent": self.agent_name, "datetime": datetime.now()})

        # Append the user's new message
        conversation_history.append({"role": "user", "content": message, "agent": "user", "datetime": datetime.now()})

        # Prepare messages for OpenAI API
        openai_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in conversation_history
            if msg["agent"] == self.agent_name or msg["agent"] == "user"
        ]

        # If response_schema is provided, use the parsing method
        if response_schema:
            completion = await self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",  # Example model
                messages=openai_messages,
                response_format=response_schema
            )
            result = completion.choices[0].message.parsed
            # print('before openai response')
            # result = completion.choices[0].message.parsed
            # async for parsed_completion in openai_structured_outputs_stream(
            #     model="gpt-4o-2024-08-06",
            #     messages=openai_messages,
            #     response_format=response_schema
            # ):
            #     result = parsed_completion
                # print("Current result field:", result)
        else:
            # Use the standard method if no schema is provided
            completion = await self.client.chat.completions.create(
                model="gpt-4o",  # Example model
                messages=openai_messages
            )
            result = completion.choices[0].message.content
            
				#save result to history
        if response_schema:
            # result = response_schema(**result) #to pedantic model
            # content = result.message if hasattr(result, 'message') and result.message else result.model_dump_json()
            content = result.message if hasattr(result, 'message') and result.message else result.model_dump_json()

        else:
            content = result

        if content:
            conversation_history.append({"role": "assistant", "content": content, "agent": self.agent_name, "datetime": datetime.now()})
        print('after openai response')
        return result
    
    def add_assistant_message_to_conversation_history(self, conversation_history: list, content: str):
        conversation_history.append({"role": "assistant", "content": content, "agent": self.agent_name, "datetime": datetime.now()})