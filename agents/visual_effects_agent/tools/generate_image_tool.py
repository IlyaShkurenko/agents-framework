# tools/caption_tool.py

import os
from core.base_component import BaseComponent
from pydantic import BaseModel, Field
from runware import Runware, IImageInference

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

    def __init__(self, mediator, tools=None):
        super().__init__(mediator, tools)
        self.runware = Runware(api_key=os.getenv('RUNWARE_API_KEY'))
        self.openai_service = OpenAIService(agent_name='generate_image_tool')

    @property
    def name(self):
        return "generate_image_tool"

    @property
    def description(self):
        return "Tool for generating an image based on a prompt."

    async def execute(self, state: dict):
        """
        Generates an image based on the provided prompt and returns the image URL.
        """
        await self.runware.connect()

        image_requirements = state.get('image_requirements', "")
        message = f"Generate a prompt for an image generation model based on the following requirements: {image_requirements}"
        
        assistant_response = await self.openai_service.get_response(
            conversation_history=[], 
            system_prompt=INIT_PROMPT, 
            message=message, 
            response_schema=AssistantResponse
        )
        
        request_image = IImageInference(
            positivePrompt=assistant_response.prompt,
            model="runware:100@1",
            numberResults=1,
            height=512,
            width=512,
            useCache=False
        )

        images = await self.runware.imageInference(requestImage=request_image)

        if images:
            return {"image_url": images[0].imageURL}
        else:
            raise ValueError("No images generated.")
