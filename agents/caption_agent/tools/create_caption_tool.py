# tools/caption_tool.py

import openai

from core.base_component import BaseComponent

class CreateCaptionTool(BaseComponent):
    """
    Tool that generates captions based on the current state.
    """

    @property
    def name(self):
        return "CreateCaptionTool"

    @property
    def description(self):
        return "Tool for generating captions based on user input."

    async def execute(self, state: dict):
        """
        Generates a caption based on the state provided.
        """
        caption_style = state.get('caption_style', 'informative')
        visual_description = state.get('visual_description', 'an image')

        prompt = f"Generate a {caption_style} caption for {visual_description}."

        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=60,
            temperature=0.7,
        )
        caption = response.choices[0].text.strip()
        return caption
