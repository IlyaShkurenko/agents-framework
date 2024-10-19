# agents/init_agent.py

from core.base_agent import BaseAgent
from core.planner.main import Planner
import copy
import time
import asyncio
class BaseAgentWithPlanApprove(BaseAgent):
    """
    The InitAgent handles the initial interaction with the user.
    """

    def __init__(self, mediator, tools=None):
        super().__init__(mediator, tools or [])
    
    async def handle_message(self, message: str):
        self.tasks = [{
            "id": 12345677,
            "tool": "create_hashtags_tool",
            "dependencies": [],
            "arguments": [{
                "name": "prompt",
                "value": "Generate a hashtags for Bali retreat"
						}]
				}]
        #todo handle case when bellow
        # await self.mediator.add_agent_to_call_stack(
        #         parent_agent=self.name,
        #         agent_name='create_hashtags_agent',
        #         task_id="32345672",
        #         message=message
        #     )
        # print('add to call stack')
        # asyncio.create_task(
        #     self.mediator.add_agent_to_call_stack(
        #         parent_agent=self.name,
        #         agent_name='create_hashtags_agent',
        #         task_id=1123123,
        #         message=message
        #     )
        # )
        # await asyncio.sleep(0)
        # return
        if self._is_executing() or True:
            print('is exec')
            return await self._execute_plan_and_finalize(self.tasks)

        self._save_initial_message(message)

        print(f"\033[34mMessage in {self.name}:\033[0m", message)
        start_time = time.time()
        assistant_response = await self.run_questionnaire(message)
        print('assistant_response', assistant_response)
        end_time = time.time()
        print(f"\033[34mTime taken to run questionnaire:\033[0m {end_time - start_time} seconds")
        
        need_replan, replan_after_execution, previous_user_requirements = self._parse_assistant_response(assistant_response)
        
				#In case if no user requirements provided or no need to replan. In case of replan we will send message to user as plan overview  
        plan_is_required = need_replan or (not self._is_plan_exists() and assistant_response.user_requirements)
        
        print('plan_is_required', plan_is_required)
        
            # return
        
        print('tasks in handle message agent', self.tasks)
        plan_overview_sent = False
        if assistant_response.user_requirements:
            self._save_user_requirements(assistant_response)
            # plan_approved = getattr(assistant_response, 'plan_approved', False)
            plan_response = {};
            if plan_is_required:
                # Create a plan or replan based on the user requirements
                plan_response = await self._create_and_save_plan(
                    need_replan=need_replan,
                    replan_after_execution=replan_after_execution,
                    tasks_with_results=self.executor.get_tasks_with_results(),
                    executed_user_requirements=previous_user_requirements
                )
                self._add_message_to_conversation_history(plan_response['overview'])
                self._emit_assistant_message(plan_response['overview'])
                plan_overview_sent = True
                return

            if self.tasks:
                final_response = await self._execute_plan_and_finalize(self.tasks)
                return final_response
            else:
                return await self.handle_message(f"{message}, generate user_requirements")
            
        if assistant_response.message and not plan_overview_sent:
            self._emit_assistant_message(assistant_response.message)
    
    def get_response_model(self):
        print("\033[34mIs plan exists:\033[0m", self._is_plan_exists())

        is_waiting_for_approval = self._get_agent_status() == 'waiting_for_approval'
        print("\033[34mIs waiting for approval:\033[0m", is_waiting_for_approval)
        
        return self._create_dynamic_response_model()  
    
# ['init_agent']
# Time taken to get current agent: 0.3455948829650879 seconds
# tasks in load state []
# Time taken to set client data: 0.3660280704498291 seconds
# setting current agent init_agent
# before execute init_agent
# message Bali retreat

# is exec
# in mediator emitMessage
# Tasks: []
# Tool tasks:
# []
# start asyncio.gather
# done execution
# in execute plan and finalize
# final_response Execution completed successfully.
# in mediator emitMessage
# <class 'dict'>
# {'content': None, 'type': 'execution_started'}
# <class 'dict'>
# {'content': 'Execution completed successfully.', 'type': 'message'}
# after execute init_agent
# Time taken to execute agent: 0.04810976982116699 seconds
#it's because status is executing