# core/executor.py

import threading
import time
from typing import List, Dict
from .planner.output_parser import Task
from core.joiner import Joiner

class Executor:
    """
    The Executor executes tasks based on their dependencies.
    """

    def __init__(self, mediator, state):
        self.mediator = mediator
        self.client_id = state['client_id']
        self.chat_id = state['chat_id']
        self.state = state
        self.observations = {}  # Store results of task executions
        self.tasks = state.get('plan', [])
        self.task_lookup = {task.idx: task for task in self.tasks}

    def execute_plan(self):
        """
        Executes the plan stored in the state.
        """
        threads = []
        for task in self.tasks:
            t = threading.Thread(target=self.execute_task, args=(task,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # After all tasks are completed, call the joiner
        joiner = Joiner(self.observations)
        final_response = joiner.join()
        return final_response

    def execute_task(self, task: Task):
        """
        Executes a single task when its dependencies are met.
        """
        # Wait for dependencies
        while not all(dep in self.observations for dep in task.dependencies):
            time.sleep(0.1)

        # Execute the task
        if task.action == 'join':
            # join() will be handled after all tasks are completed
            return

        if task.action in self.mediator.agents:
            # It's an agent
            agent = self.mediator.agents[task.action]
            # Resolve arguments
            args = self.resolve_args(task.args)
            response = agent.handle_message(self.client_id, "", "", self.state, **args)
            self.observations[task.idx] = response
        elif task.action in self.mediator.tools:
            # It's a tool
            tool = self.mediator.tools[task.action]
            args = self.resolve_args(task.args)
            response = tool.run(args)
            self.observations[task.idx] = response
        else:
            # Unknown action
            self.observations[task.idx] = f"Error: Unknown action {task.action}"

    def resolve_args(self, args: Dict) -> Dict:
        """
        Resolves arguments, replacing any placeholders with actual values.
        """
        resolved_args = {}
        for key, value in args.items():
            if isinstance(value, str) and value.startswith('$'):
                # It's a reference to a previous task
                idx = int(value[1:])
                resolved_args[key] = self.observations.get(idx, "")
            else:
                resolved_args[key] = value
        return resolved_args
