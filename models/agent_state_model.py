# state_model.py

from datetime import datetime
from services.mongo_service import MongoService


class AgentStateModel:
    def __init__(self, client_id: str, chat_id: str, agent_name: str):
        self.client_id = client_id
        self.chat_id = chat_id
        self.agent_name = agent_name
        self.mongo_service = MongoService()
        self.state = {}

    async def load_state(self):
        state = await self.mongo_service.get_agent_state(self.client_id, self.chat_id, self.agent_name)
        if not state:
            self.state = {
                "name": self.agent_name,
                "client_id": self.client_id,
                "chat_id": self.chat_id,
                "conversation_history": [],
                "planner_conversation_history": []
        }
            await self.save_state()
        else:
            self.state = state

    async def save_state(self):
        await self.mongo_service.update_agent_state(self.client_id, self.chat_id, self.state)

    def save_user_requirements(self, user_requirements: dict):
        self.state['user_requirements'] = user_requirements
        
    def add_message_to_conversation_history(self, message: dict):
        message_data = {"role": "assistant", "content": message, "agent": self.agent_name, "datetime": datetime.now()}
        self.state['conversation_history'].append(message_data)

    def save_agent_history(self, history: list):
        self.state['conversation_history'] = history
        
    def save_agent_planner_history(self, history: list):
        self.state['planner_conversation_history'] = history

    def save_agent_status(self, status: str):
        self.state['status'] = status  
        
    def get_agent_status(self):
        return self.state.get('status')
        
    def save_agent_plan(self, plan: dict):
        if 'plan' not in self.state:
            self.state['plan'] = [plan]
        else:
            self.state['plan'].append(plan)

    def get_user_requirements(self):
        return self.state.get('user_requirements')

    def get_conversation_history(self):
        return self.state.get('conversation_history', [])
    
    def get_agent_planner_conversation_history(self):
        return self.state.get('planner_conversation_history', [])
    
    def is_plan_exists(self):
        return 'plan' in self.state

    def add_to_conversation_history(self, messages: list[dict]):
        self.state['conversation_history'].extend(messages)
        
    def is_requirements_changed(self, new_requirements: dict) -> bool:
        
        existing_requirements = self.get_user_requirements()

        if not existing_requirements:
            return False

        for field, new_value in new_requirements.items():
            old_value = existing_requirements.get(field)
            if old_value != new_value:
                return True

        return False 