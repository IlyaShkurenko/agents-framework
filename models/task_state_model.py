import copy
from pprint import pprint
from typing import Optional, List, Dict, Union
from services.mongo_service import MongoService

class TasksStateModel:
    def __init__(self, client_id: str, chat_id: str):
        self.client_id = client_id
        self.chat_id = chat_id
        self.mongo_service = MongoService()
        self.state = None  # Cache for the state

    async def load_state(self):
        state = await self.mongo_service.get_tasks_state(self.client_id, self.chat_id)
        if not state:
            self.state = {
                "client_id": self.client_id,
                "chat_id": self.chat_id,
                "tasks": []
            }
            await self._update_state()
        else:
            self.state = state
        return copy.deepcopy(self.state)

    async def save_task_result(self, task_id: int, result: Union[dict, str, list[dict]]):
        state = await self.load_state()
        # print('state results save')
        # pprint(state['tasks'])
        for task in state["tasks"]:
            if task["id"] == task_id:
                task["result"] = result
                break
        else:
            state["tasks"].append({"id": task_id, "result": result})
        self.state = state
        await self._update_state()

    async def get_task_result(self, task_id: int) -> Optional[dict]:
        state = await self.load_state()

        for task in state["tasks"]:
            if task["id"] == task_id:
                return task.get("result")

        return None

    # async def task_exists(self, task_id: int) -> bool:
    #     state = await self.get_or_load_state()
    #     return any(task["id"] == task_id for task in state["tasks"])

    async def get_or_load_state(self) -> dict:
        if self.state is None:
            await self.load_state()
        return copy.deepcopy(self.state)

    async def update_tasks_state(self):
        await self.mongo_service.update_tasks_state(
            self.client_id, self.chat_id, self.state
        )
        
    async def _update_state(self):
        if self.state is not None:
            await self.mongo_service.update_tasks_state(
                self.client_id, self.chat_id, self.state
            )
