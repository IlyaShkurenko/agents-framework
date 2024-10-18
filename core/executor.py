import time
from concurrent.futures import ThreadPoolExecutor, wait
from typing import List, Dict, Any
import asyncio
import json
import pprint
class Executor:
    def __init__(self, agent, tools):
        """
        Initialize the Executor with the parent agent, tools, and tasks state model.

        Args:
            agent: Reference to the parent agent.
            tools (List[BaseTool]): List of tools available for execution.
            tasks_state_model: Model to interact with task states in the database.
        """
        self.agent = agent
        self.tasks_state_model = None
        self.tools = {tool.name: tool for tool in tools}
        self.called_agents = set()
        self.tasks = []  # Store tasks for potential re-entry
        self.observations = {}  # Store results of completed tasks
        self.retry_after = 0.2  # Time to wait before retrying dependent tasks

    def set_tasks_state_model(self, tasks_state_model):
        self.tasks_state_model = tasks_state_model

    async def execute_plan(self, tasks: List[Dict[str, Any]]):
        """
        Execute a plan consisting of multiple tasks.

        Args:
            tasks (List[Dict[str, Any]]): The list of tasks to execute.

        Returns:
            str: Final execution status.
        """
        print("\033[31mTasks:\033[0m", tasks)
        self.tasks = tasks

        # Launch tool tasks in parallel
        tool_tasks = [task for task in tasks if "tool" in task["tool"].lower()]
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(None, self._process_tool_task, task)
            for task in tool_tasks
        ]
        print("\033[31mTool tasks:\033[0m")
        pprint(tool_tasks)

        # Process agent tasks sequentially
        for task in tasks:
            if "tool" not in task["tool"].lower():
                print("\033[32mAgent task:\033[0m")
                pprint(task)
                result = await self.tasks_state_model.get_task_result(task["id"])
                if result:
                    print(f"Result for agent {task['tool']} found in DB.")
                    self.observations[task["id"]] = result
                    continue  # Skip if the agent result is already available

                # If agent hasn't been called and no dependencies, call it
                if not task["dependencies"]:
                    print("\033[32mNo dependencies for agent task\033[0m",task["tool"], task["id"])
                    await self._process_agent_task(task)
                    return

                # If dependencies exist, process them
                if all(dep in self.observations for dep in task["dependencies"]):
                    if task["tool"] in self.called_agents:
                        print("\033[32mAgent was called before:\033[0m")
                        # Agent already called, collect results
                        dependencies_results = [
                            self.observations[dep] for dep in task["dependencies"]
                            if self._is_tool_dependency(dep)
                        ]
                        print("\033[32mDependencies results:\033[0m", task["tool"], task["id"])
                        pprint(dependencies_results)
                        #Result of agent task is a list of tools on which it depends. If it depends on agent then it's used as an argument for it
                        self.observations[task["id"]] = dependencies_results
                        # self.agent.on_agent_execute(task["tool"])
                        await self.tasks_state_model.save_task_result(task["id"], dependencies_results)
                        return dependencies_results
                    else:
                        # Agent not called yet, call with dependencies
                        dependencies_results = self._collect_dependencies_results(task)
                        print("\033[33mDependencies results for first called agent:\033[0m", task["id"])
                        pprint(dependencies_results)
                        await self._process_agent_task(task, dependencies_results)
                        return  # Exit after calling the agent

        # Wait for all tool tasks to complete
        await asyncio.gather(*futures)
        return "Execution completed successfully."

    async def _process_agent_task(self, task: Dict[str, Any], dependencies_results_as_arguments: Dict[str, Any] = None):
        """
        Process an agent task and store its result in the state.

        Args:
            task (Dict[str, Any]): The agent task to process.
            dependencies_results_as_arguments (Dict[str, Any], optional): 
                The results of the dependent tasks to be passed as arguments.
        """
        print("\033[34mInvoking agent:\033[0m", task["tool"], task["id"])
        self.called_agents.add(task["tool"])

        arguments_string = f"Use these arguments as context: {task['arguments']}"

        if dependencies_results_as_arguments:
            formatted_results = "\n".join(
                f"{description}: {result}" 
                for description, result in dependencies_results_as_arguments.items()
            )
            arguments_string = (
                f"{arguments_string}\nHere are the results of the tasks that you depend on:\n{formatted_results}"
            )

        print("\033[34mArguments:\033[0m", arguments_string)

        await self.agent.process_agent_task(
            task["id"], task["tool"], arguments_string
        )

    def add_agent_task_to_dependencies(self, agent_name: str, task_id: int):
        """
        Add a new task ID to the dependencies of the given agent.
        """
        agent_task = next(
            (task for task in self.tasks if task["tool"] == agent_name), None
        )
        if agent_task:
            agent_task["dependencies"].append(task_id)
            print("\033[1;33mAdded agent task to dependencies:\033[0m", task_id)
            pprint(self.tasks)

    def get_tasks_with_results(self) -> List[Dict[str, Any]]:
        """
        Return a list of tasks with their results included.
        If a task has a result in observations, it is added to the task.
        
        Returns:
            List[Dict[str, Any]]: List of tasks with 'result' field added where available.
        """
        tasks_with_results = []

        for task in self.tasks:
            task_with_result = task.copy()

            if task["id"] in self.observations:
                task_with_result["result"] = self.observations[task["id"]]
            else:
                task_with_result["result"] = None

            tasks_with_results.append(task_with_result)

        return tasks_with_results
    
    async def _process_tool_task(self, task: Dict[str, Any]):
        """
        Process a tool task and store the result.

        Args:
            task (Dict[str, Any]): The tool task to process.
        """
        task_id = task["id"]
        tool_dependencies = self._get_tool_dependencies(task["dependencies"])

        # Check if tool dependencies are resolved
        if not self._check_dependencies(tool_dependencies):
            print(f"Tool dependencies for task {task_id} not satisfied.")
            await self._schedule_pending_task(task)
            return

        # Check agent dependencies separately
        agent_dependencies = self._get_agent_dependencies(task["dependencies"])
        if not self._check_dependencies(agent_dependencies):
            print(f"Agent dependencies for tool task {task_id} not satisfied.")
            return

        # Execute the tool and store the result
        try:
            tool_name = task["tool"]
            tool = self.tools[tool_name]
            args = task.get("arguments", [])

            dependencies_results = self._collect_dependencies_results(task)
            formatted_dependencies = "\n".join(
                f"{description}: {result}"
                for description, result in dependencies_results.items()
            )

            # Construct the arguments string with dependencies
            arguments_string = f"Use these arguments as context: {json.dumps(args)}"
            if formatted_dependencies:
                arguments_string += f"\nHere are the results of the tasks that you depend on:\n{formatted_dependencies}"
            print("\033[34mExecuting tool:\033[0m", tool_name, task_id)
            print("\033[33mArguments:\033[0m", arguments_string)
            result = await tool.execute(arguments_string)
            print(f"Executed tool {tool_name} with result: {result}")

            # Store result in observations and state model
            self.observations[task_id] = result
            await self.tasks_state_model.save_task_result(task_id, result)
        except Exception as e:
            print(f"Error executing tool {tool_name}: {str(e)}")

    def _collect_dependencies_results(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect results of all dependencies for a given task, 
        returning a dictionary with task descriptions as keys 
        and their results as values.
        """
        dependencies_results = {}

        for dep_id in task["dependencies"]:
            dep_task = next((t for t in self.tasks if t["id"] == dep_id), None)
            if dep_task and dep_id in self.observations:
                description = dep_task["description"]
                dependencies_results[description] = self.observations[dep_id]

        return dependencies_results


    async def _schedule_pending_task(self, task: Dict[str, Any]):
        """
        Schedule a pending task by checking tool dependencies with a delay.

        Args:
            task (Dict[str, Any]): The task to process.
        """
        while True:
            tool_dependencies = self._get_tool_dependencies(task["dependencies"])
            if all(dep in self.observations for dep in tool_dependencies):
                await self._process_tool_task(task)  # Use await here
                break
            await asyncio.sleep(self.retry_after)

    def _get_tool_dependencies(self, dependencies: List[int]) -> List[int]:
        """
        Extract only tool dependencies from a list of dependencies.

        Args:
            dependencies (List[int]): List of all dependencies.

        Returns:
            List[int]: Filtered list of tool dependencies.
        """
        return [dep for dep in dependencies if self._is_tool_dependency(dep)]

    def _get_agent_dependencies(self, dependencies: List[int]) -> List[int]:
        """
        Extract only agent dependencies from a list of dependencies.

        Args:
            dependencies (List[int]): List of all dependencies.

        Returns:
            List[int]: Filtered list of agent dependencies.
        """
        return [dep for dep in dependencies if not self._is_tool_dependency(dep)]

    def _is_tool_dependency(self, dep: int) -> bool:
        """
        Check if a dependency ID corresponds to a tool.

        Args:
            dep (int): Dependency ID.

        Returns:
            bool: True if the dependency is a tool, otherwise False.
        """
        task = next((task for task in self.tasks if task["id"] == dep), None)
        return task and "tool" in task["tool"].lower()

    def _check_dependencies(self, dependencies: List[int]) -> bool:
        """
        Check if all dependencies are satisfied.

        Args:
            dependencies (List[int]): List of task IDs that must be completed.

        Returns:
            bool: True if all dependencies are satisfied, otherwise False.
        """
        return all(dep in self.observations for dep in dependencies)

    async def resume_execution(self):
        """
        Resume the execution of tasks. If no tasks are currently loaded, 
        restore tasks and observations from the database.
        """
        print("Resuming task execution...")

        if not self.tasks:
            state = await self.tasks_state_model._load_state()

            self.tasks = state.get("tasks", [])
            if not self.tasks:
                print("No tasks found to resume.")
                return

            self.observations.update({
                task_id: result for task_id, result in state.items() if task_id != "tasks"
            })

        await self.execute_plan(self.tasks)