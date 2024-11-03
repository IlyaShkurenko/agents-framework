from pprint import pprint
import random
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from agents.hashtags_agent.main import HashtagsAgent
from agents.image_agent.main import ImageAgent
from agents.image_agent.tools.generate_image_tool import GenerateImageTool
from agents.visual_effects_agent.main import VisualEffectsAgent
from core.mediator import Mediator
from agents.init_agent.main import InitAgent
from agents.caption_agent.main import CaptionAgent
from rich.traceback import install
from typing import List
import json
import asyncio
import traceback

from core.utils.parse_message import parse_message
from services.generative_ai_service import GenerativeAIServiceClient

install()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

generative_ai_service_client = GenerativeAIServiceClient("ws://localhost:8001/ws/generative_ai_api")

# Initialize the mediator
mediator = Mediator()

# Register agents
caption_agent = CaptionAgent(mediator)
hashtags_agent = HashtagsAgent(mediator)
image_agent = ImageAgent(mediator)
visual_effects_agent = VisualEffectsAgent(mediator, [image_agent])
init_agent = InitAgent(mediator, [caption_agent, hashtags_agent, visual_effects_agent])

mediator.register_agent(init_agent)
mediator.register_agent(caption_agent)
mediator.register_agent(hashtags_agent)
mediator.register_agent(visual_effects_agent)
mediator.register_agent(image_agent)

message = '''Use these arguments to process your task:
        [
            {
            "name": "prompt",
            "value": "A couple on beach with children, sunset"
            },
            {
            "name": "seed_image",
            "value": "https://im.runware.ai/image/ws/0.5/ii/c6654da2-9570-4ff1-8a55-f2039c672c86.jpg"
            }
        ]'''

# seed_image, prompt = parse_message(message)
# print("seed_image:", seed_image)
# print("prompt:", prompt)

# generate_image = GenerateImageTool()

# asyncio.create_task(generate_image.execute(message, []))

# plan = [{'arguments': [{'name': 'prompt',
#                  'value': 'Generate hashtags for a Bali retreat targeting '
#                           "young travelers with the specific keyword 'bali'. "
#                           "Also, incorporate 'Ubud' and 'girls' in the "
#                           'hashtags. Use instagram hashtags format. Use 10 '
#                           'hashtags or less.'}],
#   'dependencies': [],
#   'description': 'Call the create_hashtags_tool to generate hashtags for a '
#                  'Bali retreat targeting young travelers with the specific '
#                  "keywords 'bali', 'Ubud', and 'girls'.",
#   'id': '00000032',
#   'tool': 'create_hashtags_tool'},
#  {'arguments': [],
#   'dependencies': ['00000032'],
#   'description': 'Passing the results of hashtags creation for Bali retreat '
#                  "with keywords 'bali', 'Ubud', and 'girls' for join analysis.",
#   'id': '00000033',
#   'tool': 'join'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Generate relevant hashtags for a Bali retreat.'}],
#   'dependencies': ['00000033'],
#   'description': 'Call the create_hashtags_agent to generate hashtags for a '
#                  "Bali retreat based on the user's request.",
#   'id': '00000024',
#   'summary': 'User decided to generate hashtags for a Bali retreat targeting '
#              "young travelers with the specific keyword 'bali' and includes "
#              "requests to incorporate 'Ubud' and 'girls' in the hashtags.",
#   'tool': 'create_hashtags_agent'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Present the generated hashtags for the Bali '
#                           'retreat.'}],
#   'dependencies': ['00000024'],
#   'description': 'Pass the generated hashtags to the join action for final '
#                  'presentation.',
#   'id': '00000025',
#   'tool': 'join'},
#  {'arguments': [],
#   'dependencies': ['00000025'],
#   'id': 90170288,
#   'summary': 'User decided to generate hashtags for a Bali retreat without any '
#              'additional content or captions.',
#   'tool': 'init_agent'}]

# def find_parent_agent(agent_name, current_id=None):
#     task = next((task for task in plan if task["tool"] == agent_name), None) if current_id is None else next((task for task in plan if task["id"] == current_id), None)
    
#     if task is None:
#         return None
    
#     parent_task = next((t for t in plan if task["id"] in t["dependencies"]), None)
    
#     if parent_task is None:
#         return None
    
#     if "agent" in parent_task["tool"].lower():
#         return parent_task["tool"]
    
#     return find_parent_agent(agent_name, parent_task["id"])

# parent_agent = find_parent_agent('create_hashtags_agent')
# print('parent agent', parent_agent)
class ConnectionManager:
    def __init__(self):
        self.default_agent = 'init_agent'
        self.chat_tasks = []
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    # def _is_tool_dependency(self, all_dependencies, dep: int) -> bool:
    #     """
    #     Check if a dependency ID corresponds to a tool.

    #     Args:
    #         dep (int): Dependency ID.

    #     Returns:
    #         bool: True if the dependency is a tool, otherwise False.
    #     """
    #     task = next((task for task in all_dependencies if task["id"] == dep), None)
    #     return bool(task and ("tool" in task["tool"].lower() or task["tool"].lower() == 'join'))

    # def update_agent_plans(self, agent_name: str, plan: list[dict], description: str):
    #     chat_tasks = self.chat_tasks.copy()

    #     # print("\033[34mPlans before:\033[0m", chat_tasks)
    #     last_plan_id = plan[-1]['id']
    #     # Keep the initial part as is
    #     if agent_name == self.default_agent and not chat_tasks:
    #         chat_tasks.extend(plan)

    #         default_agent_entry = {
    #             "tool": self.default_agent,
    #             "description": description,
    #             "id": random.randint(10**7, 10**8 - 1),
    #             "arguments": [],
    #             "dependencies": [last_plan_id]
    #         }
    #         chat_tasks.append(default_agent_entry)
    #         self.chat_tasks = chat_tasks
    #         return

    #     # Find the task where 'tool' == agent_name
    #     agent_task = next((task for task in chat_tasks if task['tool'] == agent_name))
    #     dependencies_to_remove = set()

    #     # Function to recursively collect dependencies of tasks where 'tool' == agent_name
    #     def collect_dependencies_to_remove(task_ids):
    #         for dep_id in task_ids:
    #             dep_task = next((t for t in chat_tasks if t['id'] == dep_id), None)
    #             if dep_task and dep_task['id'] not in dependencies_to_remove:
    #                 dependencies_to_remove.add(dep_task['id'])
    #                 collect_dependencies_to_remove(dep_task.get('dependencies', []))

    #     # Start collecting dependencies from the agent_task, only tools
    #     task_dependencies = agent_task.get('dependencies', [])
    #     tool_dependencies = [dep for dep in task_dependencies if self._is_tool_dependency(self.chat_tasks, dep)]
    #     collect_dependencies_to_remove(tool_dependencies)

    #     agent_task['dependencies'] = [dep for dep in task_dependencies if dep not in tool_dependencies]

    #     chat_tasks = [task for task in chat_tasks if task['id'] not in dependencies_to_remove]

    #     agent_task['dependencies'].append(last_plan_id)

    #     agent_task_index = chat_tasks.index(agent_task)

    #     chat_tasks[agent_task_index:agent_task_index] = plan

    #     self.chat_tasks = chat_tasks


    # def update_task_dependencies(self, chat_tasks, agent_name, old_last_task_id, new_last_task_id, description):
    #     for entry in chat_tasks:
    #         for task in entry.get('tasks', []):
    #             if task['tool'] == agent_name:
    #                 if old_last_task_id in task['dependencies']:
    #                     task['dependencies'].remove(old_last_task_id)
    #                 task['dependencies'].append(new_last_task_id)
    #                 task['description'] = description

    # def update_agent_plans(self, agent_name: str, plan: list[dict], description: str):
    #     chat_tasks = self.chat_tasks.copy()
    #     last_task_id = plan[-1]['id']
        
    #     agent_entry = next((entry for entry in chat_tasks if entry['tool'] == agent_name), None)
        
    #     if agent_entry is None:
    #         if agent_name == self.default_agent:
    #             agent_entry = {
    #                 "tool": agent_name,
    #                 "description": description,
    #                 "id": random.randint(10**7, 10**8 - 1),
    #                 "arguments": [],
    #                 "dependencies": [last_task_id],
    #                 "tasks": plan
    #             }
    #             chat_tasks.append(agent_entry)
    #         else:
    #             self.update_task_dependencies(chat_tasks, agent_name, None, last_task_id, description)
    #             chat_tasks.insert(0, {
    #                 "tool": agent_name,
    #                 "tasks": plan
    #             })
    #     else:
    #         old_last_task_id = agent_entry['tasks'][-1]['id'] if agent_entry['tasks'] else None
    #         agent_entry['tasks'] = plan
    #         self.update_task_dependencies(chat_tasks, agent_name, old_last_task_id, last_task_id, description)

    #     self.chat_tasks = chat_tasks
    #     pprint(self.chat_tasks)

manager = ConnectionManager()

# plan = [
#             {
#                 "id": "32412460",
#                 "description": "Call the create_caption_agent with the appropriate prompt to generate a caption for the Instagram post.",
#                 "dependencies": [],
#                 "tool": "create_caption_agent",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "Generate a creative and engaging caption for an Instagram post about a vacation to Bali"
#                 }
#             ]
#         },
#         {
#             "id": "32412461",
#             "description": "Use the create_hashtags_agent to generate relevant hashtags for the Instagram post. Ensure that the hashtags are generated using the caption from the previous step (ID: 32412460) to provide better context and coherence between the caption and hashtags.",
#             "dependencies": [32412460],
#             "tool": "create_hashtags_agent",
#             "arguments": [
# 			    {
#                         "name": "prompt",
#                         "value": "Generate relevant hashtags for an Instagram post about a vacation to Bali."
#                     }
#                 ]
#             },
#             {
#                 "id": "32412462",
#                 "description": "Call the create_post_tool with the caption and hashtags to create the final Instagram post.",
#                 "dependencies": ["32412460", "32412461"],
#                 "tool": "create_post_tool",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "Create an Instagram post using the generated caption and hashtags."
#                     }
#                 ]
#             }
# ]

# manager.update_agent_plans("init_agent", plan, "Create a post")
# pprint(manager.chat_tasks)

# print('New plan')

# new_plan = [
#     {
#                 "id": "11111111",
#                 "description": "Call the create_caption_tool",
#                 "dependencies": [],
#                 "tool": "create_caption_tool",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "somevalue"
#                 }
#         ]
#     },
# ]
# manager.update_agent_plans("create_caption_agent", new_plan, "Create a post")
# pprint(manager.chat_tasks)

# print('New plan hashtags')

# new_plan = [
#     {
#                 "id": "15151515",
#                 "description": "Call the create_hashtags_tool_2",
#                 "dependencies": [],
#                 "tool": "create_hashtags_tool_2",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "somevalue"
#                 }
#         ]
#     },
#     {
#                 "id": "22222222",
#                 "description": "Call the create_hashtags_tool",
#                 "dependencies": ["15151515"],
#                 "tool": "create_hashtags_tool",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "somevalue"
#                 }
#         ]
#     },
# ]
# manager.update_agent_plans("create_hashtags_agent", new_plan, "Create a post")
# pprint(manager.chat_tasks)

# print('New plan hashtags 2')

# new_plan = [
#     {
#                 "id": "33333333",
#                 "description": "Call the create_hashtags_tool",
#                 "dependencies": [],
#                 "tool": "create_hashtags_tool",
#                 "arguments": [
#                     {
#                         "name": "prompt",
#                         "value": "somevalue"
#                 }
#         ]
#     },
# ]
# manager.update_agent_plans("create_hashtags_agent", new_plan, "Create a post")
# pprint(manager.chat_tasks)

# print("\033[34mPlan 1:\033[0m")

# plan1 = [{'arguments': [{'name': 'prompt',
#                  'value': 'Generate a creative and engaging caption for a Bali '
#                           'retreat.'}],
#   'dependencies': [],
#   'description': 'Generate a caption for a Bali retreat.',
#   'id': '00000012',
#   'tool': 'create_caption_agent'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Generate relevant hashtags for an Instagram post '
#                           'about a Bali retreat.'}],
#   'dependencies': [],
#   'description': 'Generate hashtags for a Bali retreat post.',
#   'id': '00000013',
#   'tool': 'create_hashtags_agent'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Create an Instagram post using the generated '
#                           'caption and hashtags for a Bali retreat.'}],
#   'dependencies': ['00000012', '00000013'],
#   'description': 'Combine the generated caption and hashtags for the final '
#                  'Instagram post.',
#   'id': '00000014',
#   'tool': 'join'}]

# manager.update_agent_plans('init_agent', plan1, 'Init agent which calls create_caption_agent, create_hashtags_agent and join')

# print("\033[34mPlan 2:\033[0m")

# plan1 = [{'arguments': [{'name': 'prompt',
#                  'value': 'Generate a creative and engaging caption for a Bali '
#                           'retreat.'}],
#   'dependencies': [],
#   'description': 'Generate a caption for a Bali retreat.',
#   'id': '00000012',
#   'tool': 'create_caption_agent'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Generate relevant hashtags for an Instagram post '
#                           'about a Bali retreat.'}],
#   'dependencies': [],
#   'description': 'Generate hashtags for a Bali retreat post.',
#   'id': '00000013',
#   'tool': 'create_hashtags_agent'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Create an Instagram post using the generated '
#                           'caption and hashtags for a Bali retreat.'}],
#   'dependencies': ['00000012', '00000013'],
#   'description': 'Combine the generated caption and hashtags for the final '
#                  'Instagram post.',
#   'id': '00000015',
#   'tool': 'join'}]


@app.on_event("startup")
async def startup_event():
    """Connect to the WebSocket service on startup."""
    await generative_ai_service_client.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Close the WebSocket connection on shutdown."""
    await generative_ai_service_client.close()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)

    async def handle_message_response(response):
        try:
            if websocket.application_state == "DISCONNECTED" or websocket.client_state == "DISCONNECTED":
                print("WebSocket is closed, skipping message sending")
                return
            await manager.send_message(json.dumps({"type": response['type'], "content": response['content']}), websocket)
            
        except Exception as e:
            print(f"Weird error: {str(e)}")
            try:
                if websocket.application_state != "DISCONNECTED" and websocket.client_state != "DISCONNECTED":
                    await manager.send_message(json.dumps({"type": "error", "content": str(e)}), websocket)
            except Exception as inner_e:
                print(f"Error occurred while sending error message: {str(inner_e)}")

    mediator.event_emitter.on('message-response', handle_message_response)

    try:
        while True:
            try:
                data = await websocket.receive_text()

                parsed_data = json.loads(data)
                message_type = parsed_data.get('type')
                message_content = parsed_data.get('content')
                chat_id = parsed_data.get('chatId')

                if message_type == "init_chat":
                    await mediator.init_chat(client_id, chat_id)
                    await manager.send_message(json.dumps({"type": "chat_initialized", "content": None}), websocket)

                elif message_type == "message":
                    try:
                        await mediator.handle_message(message_content)

                    except ValidationError as ve:
                        print(ve)
                        await manager.send_message(json.dumps({"type": "validation_error", "content": str(ve)}), websocket)
                    except Exception as e:
                        print(e)
                        await manager.send_message(json.dumps({"type": "error", "content": str(e)}), websocket)

                elif message_type == "get_history":
                    response = await mediator.get_conversation_history(client_id, chat_id)
                    await manager.send_message(json.dumps({"type": "history", "content": response}), websocket)

                elif message_type == "delete_message":
                    response = await mediator.delete_message(client_id, chat_id, message_content)
                    await manager.send_message(json.dumps({"type": "message_deleted", "content": None}), websocket)

                else:
                    await manager.send_message(json.dumps({"type": "error", "content": "Unknown message type"}), websocket)

            except json.JSONDecodeError as e:
                await manager.send_message(json.dumps({"type": "error", "content": "Invalid JSON format: " + str(e)}), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)