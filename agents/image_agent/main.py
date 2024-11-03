from agents.image_agent.tools.generate_image_tool import GenerateImageTool
from agents.image_agent.tools.joiner import Joiner
from core.base_agent import BaseAgent
from core.base_component import BaseComponent
from core.executor import Executor
from core.planner.main import Planner
from services.openai_service import OpenAIService
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Literal, Type, Union
import os

# Load the prompt
file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'image_agent_prompt.txt')
planner_example_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'planner_example.txt')

with open(planner_example_file_path, 'r') as file:
    PLANNER_EXAMPLE = file.read()
with open(file_path, 'r') as file:
    IMAGE_PROMPT = file.read()
    
# class UserRequirements(BaseModel):
#     theme: Optional[str] = Field(
#         None, 
#         description="Theme or concept the user wants in the image (e.g., 'space', 'nature', 'cityscape', 'medieval fantasy')"
#     )
#     colors: Optional[List[str]] = Field(
#         default_factory=list, 
#         description="Specific colors the user wants in the image (e.g., 'red', 'blue', 'gold', 'pastel tones')"
#     )
#     lighting: Optional[Literal['natural', 'studio', 'dramatic', 'soft', 'backlit']] = Field(
#         None, 
#         description="Preferred type of lighting in the image"
#     )
#     mood: Optional[Literal['dark', 'bright', 'mysterious', 'cheerful', 'calm', 'epic']] = Field(
#         None, 
#         description="Desired mood or emotional tone of the image"
#     )
#     subject: Optional[str] = Field(
#         None, 
#         description="Main subject of the image (e.g., 'a warrior', 'a futuristic car', 'a serene lake')"
#     )
#     background: Optional[str] = Field(
#         None, 
#         description="Type of background (e.g., 'forest', 'space nebula', 'empty white background')"
#     )
#     summary: str = Field(..., description="Brief Summary of the user's requirements. This info will be used by next agent to create a plan. If user mentioned sequence of actions then include it in summary so plan can be correct. Change it only if new requirements are provided otherwise leave it as is. Start with 'User decided to'")

class ImageAgent(BaseAgent):
    """
    The ImageAgent handles image generation and editing.
    """

    @property
    def name(self):
        return "image_agent"

    @property
    def description(self):
        return "An agent that handles image generation and editing."
    
    # @property
    # def user_requirements_schema(self) -> Type[BaseModel]:
    #     return UserRequirements
    
    @property
    def questionnaire_prompt(self) -> str:
        return IMAGE_PROMPT
    
    def __init__(self, mediator, tools: Optional[List[Union[BaseComponent, BaseAgent]]] = None):
        generate_image_tool = GenerateImageTool()
        joiner = Joiner()
        agent_tools = [generate_image_tool, joiner]

        super().__init__(mediator, agent_tools + (tools or []))
        self.executor = Executor(tools=agent_tools, agent=self)
        self.planner = Planner(tools=self.tools, examples=PLANNER_EXAMPLE)
        
    def get_questionnaire_response_model(self) -> Type[BaseModel]:

        user_requirements_fields = {
            "theme": (Optional[str], Field(
                None, 
                description="Theme or concept the user wants in the image (e.g., 'space', 'nature', 'cityscape', 'medieval fantasy')"
            )),
            "colors": (Optional[List[str]], Field(
                default_factory=list, 
                description="Specific colors the user wants in the image (e.g., 'red', 'blue', 'gold', 'pastel tones')"
            )),
            "lighting": (Optional[Literal['natural', 'studio', 'dramatic', 'soft', 'backlit']], Field(
                None, 
                description="Preferred type of lighting in the image"
            )),
            "mood": (Optional[Literal['dark', 'bright', 'mysterious', 'cheerful', 'calm', 'epic']], Field(
                None, 
                description="Desired mood or emotional tone of the image"
            )),
            "subject": (Optional[str], Field(
                None, 
                description="Main subject of the image (e.g., 'a warrior', 'a futuristic car', 'a serene lake')"
            )),
            "background": (Optional[str], Field(
                None, 
                description="Type of background (e.g., 'forest', 'space nebula', 'empty white background')"
            ))
        }

        return self._create_dynamic_response_model(extra_fields={}, user_requirements_fields=user_requirements_fields)
