from typing import Optional
from services.mongo_service import MongoService

class TasksStateModel:
    def __init__(self, client_id: str, chat_id: str):
        """
        Initialize the TasksStateModel with client and chat identifiers.

        Args:
            client_id (str): Unique identifier for the client.
            chat_id (str): Unique identifier for the chat session.
        """
        self.client_id = client_id
        self.chat_id = chat_id
        self.mongo_service = MongoService()
        self.state = None 

    async def save_task_result(self, task_id: int, result: dict):
        """
        Save the result of a task by its ID.

        Args:
            task_id (int): The ID of the task.
            result (dict): The result of the task.
        """
        state = await self._load_state()
        state[task_id] = result
        await self._update_state()

    async def get_task_result(self, task_id: int) -> Optional[dict]:
        """
        Retrieve the result of a task by its ID.

        Args:
            task_id (int): The ID of the task.

        Returns:
            Optional[dict]: The result of the task if found, otherwise None.
        """
        state = await self._load_state()
        return state.get(task_id)

    async def task_exists(self, task_id: int) -> bool:
        """
        Check if a task with the given ID exists in the state.

        Args:
            task_id (int): The ID of the task.

        Returns:
            bool: True if the task exists, otherwise False.
        """
        state = await self._load_state()
        return task_id in state

    async def _load_state(self) -> dict:
        """
        Load the current state from the database if not already cached.

        Returns:
            dict: The current state of tasks.
        """
        if self.state is None:
            self.state = await self.mongo_service.get_tasks_state(self.client_id, self.chat_id) or {}
        return self.state

    async def _update_state(self):
        """
        Update the state in the database using the local cache.
        """
        if self.state is not None:
            await self.mongo_service.update_tasks_state(self.client_id, self.chat_id, self.state)
