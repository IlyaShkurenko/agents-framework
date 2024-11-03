import copy
from services.mongo_service import MongoService

class MediatorStateModel:
    def __init__(self, client_id: str, chat_id: str, default_agent: str):
        self.client_id = client_id
        self.chat_id = chat_id
        self.default_agent = default_agent
        self.mongo_service = MongoService()

    async def load_state(self):
        state = await self.mongo_service.get_mediator_state(self.client_id, self.chat_id)
        if not state:
            self.state = {
                "client_id": self.client_id,
                "chat_id": self.chat_id,
                "call_stack": [self.default_agent],
                "tasks": []
            }
            await self.save_state()
        else:
            self.state = state
        if not self.state.get('call_stack'):
            self.state['call_stack'] = [self.default_agent]
            await self.save_state()
        return copy.deepcopy(self.state)
    
    async def save_state(self):
        print('mediator state', self.state)
        await self.mongo_service.update_mediator_state(self.client_id, self.chat_id, self.state)

    async def get_call_stack(self):
        return copy.deepcopy(self.state.get('call_stack'))
    
    def set_tasks(self, tasks: list):
        self.state['tasks'] = tasks

    async def add_agent_to_call_stack(self, agent_name: str):
        last_agent = self.state['call_stack'][-1]
        print("\033[33mLast agent\033[0m", last_agent)
        print("\033[33mStack\033[0m", self.state['call_stack'])
        if last_agent != agent_name:
            self.state['call_stack'].append(agent_name)
            print("\033[33mStack updated\033[0m")
            print(self.state)
            await self.save_state()

    async def remove_agent_from_call_stack(self, agent_name: str):
        try:
            if agent_name in self.state['call_stack']:
                self.state['call_stack'].remove(agent_name)
                print(f"\033[33mAgent '{agent_name}' removed from call stack\033[0m")
                await self.save_state()
            else:
                print(f"\033[31mAgent '{agent_name}' not found in call stack\033[0m")
        except Exception as e:
            print(f"\033[31mError removing agent from call stack: {e}\033[0m")