from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from agents.hashtags_agent.main import HashtagsAgent
from agents.image_agent.main import ImageAgent
from agents.visual_effects_agent.main import VisualEffectsAgent
from core.mediator import Mediator
from agents.init_agent.main import InitAgent
from agents.caption_agent.main import CaptionAgent
from rich.traceback import install
from typing import List
import json
import asyncio
import traceback

install()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# from agents.visual_effects_agent.tools.generate_image_tool import GenerateImageTool


# generate_image = GenerateImageTool()

# asyncio.create_task(generate_image.execute({
# 	"image_requirements": "Bali retreat"
# }))

class ConnectionManager:
    def __init__(self):
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

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)

    async def handle_message_response(response):
        try:
            if websocket.application_state == "DISCONNECTED" or websocket.client_state == "DISCONNECTED":
                print("WebSocket is closed, skipping message sending")
                return
            # print(type(response))
            # print(response)
            await manager.send_message(json.dumps({"type": response['type'], "content": response['content']}), websocket)
        except Exception as e:
            print(f"Weird error: {str(e)}")
            # traceback.print_exc()
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
                mediator.set_client_data(client_id, chat_id)

                if message_type == "message":
                    try:
                        await mediator.handle_message(client_id, chat_id, message_content)
                        # await manager.send_message(json.dumps({"type": "message", "content": response}), websocket)
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
# from pprint import pprint
# import random

# class Test:
#     def __init__(self):
#         self.agent_plans = []
#         self.default_agent = "init_agent"

#     def update_agent_plans(self, agent_name: str, plan: list[dict], description: str):
#         # If the agent_name is the default agent and the list is empty, add the default agent entry
#             if agent_name == self.default_agent and not self.agent_plans:
#                 self.agent_plans.extend(plan)

#                 default_agent_entry = {
#                     "tool": self.default_agent,
#                     "description": description,
#                     "id": random.randint(10**7, 10**8 - 1),
#                     "arguments": [],
#                     "dependencies": [plan[-1]['id']]
#                 }
#                 self.agent_plans.append(default_agent_entry)
#                 return

#             # Find the index of the first element where 'tool' matches agent_name
#             print('before')
#             pprint(agent_name)
#             found_index = next((i for i, task in enumerate(self.agent_plans) if task['tool'] == agent_name), None)
#             print('found_index', found_index)
#             dependencies_to_remove = set([])
#             if found_index is not None:
#                 # Update dependencies for the agent
#                 last_task = plan[-1]
            
#                 matching_task = next((task for task in self.agent_plans if task['tool'] == last_task['tool']), None)
#                 # Insert the new plan at the position of the old one
#                 self.agent_plans[found_index:found_index] = plan
#                 if matching_task:
#                     matching_task_id = matching_task['id']
#                     print('matching_task_id', matching_task_id)
#                     dependencies_to_remove = set([matching_task_id])
#                     def collect_dependencies(task_id):
#                         for task in self.agent_plans:
#                             if task['id'] == task_id:
#                                 dependencies_to_remove.update(task.get('dependencies', []))
#                                 for dep_id in task.get('dependencies', []):
#                                     collect_dependencies(dep_id)

#                     collect_dependencies(matching_task_id)

#                     print('dependencies_to_remove', dependencies_to_remove)
#                     dependencies = self.agent_plans[found_index + len(plan)].get('dependencies', [])
#                     if matching_task_id in dependencies:
#                         dependencies.remove(matching_task_id)

#                 self.agent_plans[found_index + len(plan)]['dependencies'].append(last_task['id'])

#             else:
#                 # If the agent doesn't exist, simply append the plan at the end
#                 self.agent_plans.extend(plan)
            
#             if dependencies_to_remove:
#                 self.agent_plans = [task for task in self.agent_plans if task['id'] not in dependencies_to_remove]



# test = Test()

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

# test.update_agent_plans("init_agent", plan, "Create a post")
# pprint(test.agent_plans)

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
# test.update_agent_plans("create_caption_agent", new_plan, "Create a post")
# pprint(test.agent_plans)

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
# test.update_agent_plans("create_hashtags_agent", new_plan, "Create a post")
# pprint(test.agent_plans)

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
# test.update_agent_plans("create_hashtags_agent", new_plan, "Create a post")
# pprint(test.agent_plans)