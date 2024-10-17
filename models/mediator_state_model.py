from services.mongo_service import MongoService

class MediatorStateModel:
    def __init__(self, client_id: str, chat_id: str, default_agent: str):
        self.client_id = client_id
        self.chat_id = chat_id
        self.default_agent = default_agent
        self.mongo_service = MongoService()

    async def get_current_agent(self) -> str:
        self.state = await self.mongo_service.get_mediator_state(self.client_id, self.chat_id)
        current_agent = self.state.get('current_agent')
        if not current_agent:
            current_agent = self.default_agent
            await self.set_current_agent(current_agent)
        return current_agent

    async def set_current_agent(self, agent_name: str):
        self.state['current_agent'] = agent_name
        await self.mongo_service.update_mediator_state(self.client_id, self.chat_id, self.state)
