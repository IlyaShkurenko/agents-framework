import time
from concurrent.futures import ThreadPoolExecutor, wait
from typing import List, Dict, Any, Union
import asyncio
import json
from pprint import pprint
class Executor:
    def __init__(self, agent, tools, last_tool_name: str = 'join'):
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
        self.last_tool_name = last_tool_name
        self.called_agents = set()
        self.tasks = []  # Store tasks for potential re-entry
        self.observations = {}  # Store results of completed tasks
        self.retry_after = 0.2  # Time to wait before retrying dependent tasks
        self.agents_tasks_dependencies = []

    def set_tasks_state_model(self, tasks_state_model):
        self.tasks_state_model = tasks_state_model

    def set_tasks(self, tasks: List[Dict[str, Any]]):
        self.tasks = tasks

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
        tool_tasks = [
            task for task in tasks 
            if "tool" in task["tool"].lower() or task["tool"].lower() == self.last_tool_name.lower()
        ]
        print("\033[31mTool tasks:\033[0m", tool_tasks)
        if len(tool_tasks) > 0:
            futures = [self._process_tool_task(task) for task in tool_tasks]
            print("\033[31mTool tasks:\033[0m")
            pprint(tool_tasks)
            # Wait for all tool tasks to complete
            tools_results = await asyncio.gather(*futures)
            print('tools results', tools_results)

            filtered_tools_results = [result for result in tools_results if result is not None]
            all_tools_done = any(tool_result['tool'] == self.last_tool_name for tool_result in filtered_tools_results)

            if all_tools_done:
                # self.agent.on_agent_execute('join')
                return self.get_execution_result(tools_results) #needs to check here if that's a last agent or tool

        # Process agent tasks sequentially
        for task in tasks:
            if "agent" in task["tool"].lower():
                print("\033[32mAgent task:\033[0m")
                pprint(task)
                # result = await self.tasks_state_model.get_task_result(task["id"])
                # if result:
                #     print(f"Result for agent {task['tool']} found in DB.")
                #     self.observations[task["id"]] = result
                #     continue  # Skip if the agent result is already available

                # If agent hasn't been called and no dependencies, call it
                # if not task["dependencies"]:
                #     print("\033[32mNo dependencies for agent task\033[0m",task["tool"], task["id"])
                #     await self._process_agent_task(task)
                #     return

                # If dependencies exist, process them
                if all(dep in self.observations for dep in task["dependencies"]):
                    if self.observations.get(task["id"]):
                        continue 
                    print('task id', task["id"])
                    print('observations', self.observations)
                    print('concrete result',self.observations.get(task["id"]))
                    print('called agents', self.called_agents)
                    if task["tool"] in self.called_agents and not self.observations.get(task["id"]):
                        try:
                            print("\033[32mAgent was called before:\033[0m", task["tool"], task["id"])
                            # if self.observations[task["id"]]:
                            #     print(f"Result for agent {task['tool']} found in DB.")
                            #     self.observations[task["id"]] = result
                            #     continue  # Skip if the agent result is already available
                            # Agent already called, collect results
                            dependencies_results = [
                                self.observations[dep] for dep in task["dependencies"]
                                if self._is_tool_dependency(dep)
                            ]
                            print("\033[32mDependencies results:\033[0m", task["tool"], task["id"])
                            pprint(dependencies_results)
                            #Result of agent task is a list of tools on which it depends. If it depends on agent then it's used as an argument for it
                            result = None
                            if len(dependencies_results) == 1:
                                result = self.observations[task["dependencies"][0]]
                            else:
                                result = dependencies_results
                            self.observations[task["id"]] = result
                            # self.agent.on_agent_execute(task["tool"])
                            await self.tasks_state_model.save_task_result(task["id"], result)
                            print('before tool which depends on agent')
                            tool_which_depends_on_agent = next((t for t in self.tasks if t["dependencies"] == [task["id"]]), None)
                            print('tool which depends on agent', tool_which_depends_on_agent)

                            if tool_which_depends_on_agent and tool_which_depends_on_agent["tool"] == self.last_tool_name:
                                tool_result= await self._process_tool_task(tool_which_depends_on_agent)
                                return tool_result['result']
                            
                            return result
                        except KeyError as e:
                            print(f"\033[31mKeyError:\033[0m Dependency '{e}' not found in observations.")
                        except Exception as e:
                            print(f"\033[31mError:\033[0m {e}")
                    else:
                        # Agent not called yet, call with dependencies
                        dependencies_results = self._collect_dependencies_results(task)
                        print("\033[33mDependencies results as arguments for first called agent:\033[0m", task["id"])
                        pprint(dependencies_results)
                        await self._process_agent_task(task, dependencies_results)
                        return  # Exit after calling the agent

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

        tool_context = ""

        if dependencies_results_as_arguments:
            formatted_results = "\n".join(
                f"{description}: {result}" 
                for description, result in dependencies_results_as_arguments.items()
            )
            tool_context = (
                f"{tool_context}\nHere are the results of the tasks that you depend on:\n{formatted_results}"
            )
        tool_context += f"\nUse these arguments to process your task: {task['arguments']}"

        print("\033[34mArguments:\033[0m", tool_context)

        await self.agent.process_agent_task(
            task["id"], task["tool"], tool_context
        )

    def add_agent_task_to_dependencies(self, agent_name: str, task_id: int, task_name: str):
        """
        Add a new task ID to the dependencies of the given agent.
        """
        print(f'in executor add agent task to dependencies {agent_name}')
        pprint(self.tasks)
        agent_task = next(
            (task for task in self.tasks if task["tool"] == agent_name), None
        )
        print('agent name', agent_name)
        if agent_task:
            agent_task["dependencies"].append(task_id)
            self.agents_tasks_dependencies.append({
                "id": task_id,
                "tool": task_name,
                "dependencies": []
            })
            print("\033[1;33mAdded agent task to dependencies:\033[0m", task_id)
            print('After adding')
            pprint(self.tasks)
        return self.tasks

    def set_previous_agent_result(self, previous_agent_result):
        print("\033[1;33mSet previous agent result:\033[0m", previous_agent_result)
        pprint(self.tasks)
        agent_task = next(
            (task for task in self.tasks if task["tool"] == previous_agent_result["agent"]), None
        )
        print('agent task', agent_task)
        if agent_task:
            self.observations[agent_task["id"]] = previous_agent_result["result"]
            asyncio.create_task(self.tasks_state_model.save_task_result(agent_task["id"], previous_agent_result["result"]))
            

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
        print("\033[34mProcessing tool task:\033[0m", task)
        task_id = task["id"]
        tool_dependencies = self._get_tool_dependencies(task["dependencies"])

        # Check if tool dependencies are resolved
        if not self._check_dependencies(tool_dependencies):
            print(f"Tool dependencies for task {task_id} not satisfied.")
            return await self._schedule_pending_task(task)

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

            tool_context = ""
            if len(args) > 0:
                tool_context += f"Use these arguments as context: {json.dumps(args)}"
            if formatted_dependencies:
                tool_context += f"\nHere are the results of the tasks that you depend on:\n{formatted_dependencies}"

            print("\033[34mExecuting tool:\033[0m", tool_name, task_id)
            print("\033[33mArguments:\033[0m", tool_context)

            result = None

            if tool_name != 'join':
                result = await tool.execute(tool_context)
            else:
                result = await tool.execute(message=tool_context, plan=self.tasks)

            print(f"Executed tool {tool_name} with result: {result}")

            # Store result in observations and state model
            self.observations[task_id] = result
            await self.tasks_state_model.save_task_result(task_id, result)
            return { "id": task_id, "tool": tool_name, "description": task["description"], "result": result }
        except Exception as e:
            print(e)
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
                return await self._process_tool_task(task)  # Use await here
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
        all_dependencies = self.tasks + self.agents_tasks_dependencies
        task = next((task for task in all_dependencies if task["id"] == dep), None)
        return task and ("tool" in task["tool"].lower() or task["tool"].lower() == 'join')

    def _check_dependencies(self, dependencies: List[int]) -> bool:
        """
        Check if all dependencies are satisfied.

        Args:
            dependencies (List[int]): List of task IDs that must be completed.

        Returns:
            bool: True if all dependencies are satisfied, otherwise False.
        """
        return all(dep in self.observations for dep in dependencies)

    async def resume_execution(self, tasks: List[Dict[str, Any]] = None):
        """
        Resume the execution of tasks. If no tasks are currently loaded, 
        restore tasks and observations from the database.
        """
        print("Resuming task execution...")
        print('tasks', tasks)
        if not tasks:
            print("No tasks found to resume.")
            return
        self.tasks = tasks

        state = await self.tasks_state_model.get_or_load_state()
        # print('state', state)
        tasks_results = state.get('tasks', [])
        print('tasks results', tasks_results)
        self.observations.update({task['id']: task['result'] for task in tasks_results})

        print('observations', self.observations)

        return await self.execute_plan(self.tasks)

    def get_execution_result(self, tools_results: List[Dict[str, Any]]) -> str:
        """
        Processes the results from tools and returns a response.

        Args:
            tools_results (List[Dict[str, Any]]): List of tool results, where each result 
                is a dictionary with 'id', 'tool', 'description', and 'result'.

        Returns:
            str: The final result, based on the logic described.
        """

        for tool_result in tools_results:
            if self.last_tool_name == tool_result['tool']:
                print(f"Last tool '{self.last_tool_name}' found, returning its result:", tool_result['result'])
                return tool_result['result']

        # If neither 'joiner' nor the last tool is found, aggregate all results
        aggregated_results = "\n".join(
            f"{res['description']}: {self._format_result(res['result'])}" for res in tools_results
        )
        final_result = f"Here are results of tools:\n{aggregated_results}"
        
        print('Aggregated results:', final_result)
        return final_result
    
    def _format_result(self, result: Any) -> str:
        """
        Formats the result, handling both strings and JSON-like objects.

        Args:
            result (Any): The result to format.

        Returns:
            str: A string representation of the result.
        """
        if isinstance(result, str):
            return result  # If it's already a string, return as is
        try:
            return json.dumps(result, indent=2)
        except (TypeError, ValueError):
            return str(result)


#No, i mean let's have only hashtags without caption or visual