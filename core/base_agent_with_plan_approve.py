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
        # plan = [{'arguments': [{'name': 'prompt',
        #          'value': 'Generate a creative and engaging caption related to '
        #                   "'Bali retreat'"}],
        # 'dependencies': [],
        # 'description': "Generate a caption related to 'Bali retreat'",
        # 'id': '87654321',
        # 'tool': 'create_caption_agent'},
        # {'arguments': [{'name': 'prompt',
        #                 'value': "Generate relevant hashtags for a post about a 'Bali "
        #                         "retreat' using the caption generated as context."}],
        # 'dependencies': ['87654321'],
        # 'description': "Generate hashtags using the generated caption about 'Bali "
        #                 "retreat'",
        # 'id': '87654322',
        # 'tool': 'create_hashtags_agent'},
        # {'arguments': [{'name': 'prompt',
        #                 'value': 'Combine the generated caption and hashtags for the '
        #                         'final post.'}],
        # 'dependencies': ['87654321', '87654322'],
        # 'description': 'Combine the caption and hashtags to create the final post.',
        # 'id': '87654323',
        # 'tool': 'join'}]
        # await self.mediator.emit_plan(
        #     plan=copy.deepcopy(plan),
        #     summary="I will start by creating visual content that captures the essence of a Bali retreat. Simultaneously, I will work on generating a captivating caption and relevant hashtags for the Instagram post. Once the visual content, caption, and hashtags are ready, I'll combine them to create a complete post. Let me know if this plan works for you or if there's anything you'd like to adjust.",
        #     agent_name="init_agent"
        # )
        # existing_tasks_ids = await self.state_model.get_all_tasks_ids()
        # print('existing_tasks_ids', existing_tasks_ids)
        # return

        self._save_initial_message(message)
        if self._is_executing():
            print(f"Agent {self.name} is executing")
            return await self._execute_plan_and_finalize(tasks=self.tasks)
        start_time = time.time()
        assistant_response = await self._run_questionnaire(message)
        end_time = time.time()
        print(f"\033[34mTime taken to run questionnaire:\033[0m {end_time - start_time} seconds")

        if self._if_result_accepted(assistant_response):
            if assistant_response.message:
                self._emit_assistant_message(assistant_response.message)
            return
        
        need_replan, replan_after_execution, user_requirements = self._parse_assistant_response(assistant_response)
        
        #In case if no user requirements provided or no need to replan. In case of replan we will send message to user as plan overview  
        plan_is_required = need_replan or (not self._is_plan_exists() and user_requirements)
        
        print('plan_is_required', plan_is_required)
        
        print('tasks in handle message agent', self.tasks)
        plan_overview_sent = False
        if user_requirements:
            # self._save_user_requirements(assistant_response)
            # plan_approved = getattr(assistant_response, 'plan_approved', False)
            if plan_is_required:
                # Create a plan or replan based on the user requirements
                plan_response = await self._create_and_save_plan(
                    need_replan=need_replan,
                    replan_after_execution=replan_after_execution,
                    user_requirements=user_requirements
                )
                print("\033[31mThis overview response\033[0m", plan_response['overview'])
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
    
    def get_questionnaire_response_model(self):
        # is_waiting_for_approval = self._get_agent_status() == 'waiting_for_approval'
        # print("\033[34mIs waiting for approval:\033[0m", is_waiting_for_approval)
        
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