# tools/caption_tool.py

from datetime import datetime
import json
import os
from core.base_component import BaseComponent
from pydantic import BaseModel, Field
from runware import Runware, IImageInference

from core.utils.parse_message import parse_message
from services.openai_service import OpenAIService

class AssistantResponse(BaseModel):
    prompt: str = Field(..., description="Prompt for the image generation model.")

init_prompt_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'generate_image_prompt.txt')
with open(init_prompt_file_path, 'r') as file:
    INIT_PROMPT = file.read()

class GenerateImageTool(BaseComponent):
    """
    Tool that generates an image based on a prompt.
    """

    def __init__(self):
        print(os.getenv('RUNWARE_API_KEY'))
        self.runware = Runware(api_key=os.getenv('RUNWARE_API_KEY'))
        self.openai_service = OpenAIService(agent_name=self.name)

    @property
    def name(self):
        return "generate_image_tool"

    @property
    def description(self):
        return "Tool for generating an image based on a prompt."

    async def execute(self, message: str, conversation_history: list):
        """
        Generates an image based on the provided prompt and returns the image URL.
        """
        await self.runware.connect()
        print('message in generate image tool', message)

        seed_image, prompt = parse_message(message)

        print('seed_image', seed_image)
        print('prompt', prompt)

        assistant_response = await self.openai_service.get_response(
            conversation_history=conversation_history, 
            system_prompt=INIT_PROMPT, 
            message=prompt, 
            response_schema=AssistantResponse
        )

        print('prompt', assistant_response.prompt)
        
        inference_params = {
            "positivePrompt": assistant_response.prompt,
            "model": "runware:100@1",
            "numberResults": 1,
            "height": 512,
            "width": 512,
        }

        if seed_image is not None:
            inference_params["seedImage"] = seed_image
            inference_params["positivePrompt"] = prompt
            inference_params["strength"] = 0.7

        request_image = IImageInference(**inference_params)

        print(request_image)

        images = await self.runware.imageInference(requestImage=request_image)

        print('images', images)

        if images:
            response = { "image_url": images[0].imageURL }

            self.openai_service.add_assistant_message_to_conversation_history(conversation_history=conversation_history, content=json.dumps(response, indent=4))

            return response, conversation_history
        else:
            raise ValueError("No images generated.")
