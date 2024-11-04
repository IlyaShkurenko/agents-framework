import json
import re

from services.mongo_service import MongoService

async def get_history_use_case(mongo_service: MongoService, websocket, client_id, chat_id):
			"""
			Retrieves the conversation history for a given client and chat.

			Args:
					client_id (str): The unique client identifier.
					chat_id (str): The unique chat identifier.

			Returns:
					list: The conversation history.
			"""
			conversation_history = await mongo_service.get_history(client_id, chat_id)

			filtered_history = []
			for message in conversation_history:
					if message['role'] == 'system':
							continue

					content = message['content']

					try:
							parsed_content = json.loads(content)
							if isinstance(parsed_content, dict) and 'message' in parsed_content and not parsed_content['message']:
									continue
					except (json.JSONDecodeError, TypeError):
							parsed_content = content

					if isinstance(parsed_content, str) and re.search(r'\[\s*{.*?}\s*\]', parsed_content):
							continue 

					if "Here are the results of the tasks that you depend" in parsed_content:
							continue

					filtered_history.append({
							'sender': 'ai' if message['role'] == 'assistant' else 'user',
							'content': parsed_content,
							'agent': message['agent']
					})

			await websocket.send_text(json.dumps({"type": "history", "content": filtered_history}))
