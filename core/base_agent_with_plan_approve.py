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
        # content = {
        #     'caption': "Oops, I Bali'd it again! 🌴🤣 Ready for a getaway? Book your escape to paradise today! 🌺✨ #BaliRetreat #EscapeTheOrdinary",
        #     'hashtags': ['#BaliRetreat', '#TravelGoals', '#IslandLife', '#Wanderlust', '#AdventureAwaits', '#ParadiseFound', '#TravelGram', '#InstaTravel', '#YoungAndFree', '#EscapeToBali'],
        #     'imageUrl': None,
        #     'is_done': True,
        #     'message': "Here is the combined content for your social media post focused on a Bali retreat theme. Let me know if you need any changes!",
        #     'videoUrl': None

        # }
        # return self.mediator.emit_message('message', content)

#         plans = [{'arguments': [{'name': 'prompt',
#                  'value': 'Generate a humorous, short Instagram caption about '
#                           'a Bali retreat that includes storytelling elements '
#                           'and emojis.'}],
#   'dependencies': [],
#   'description': 'Create a humorous, short Instagram caption about a Bali '
#                  'retreat that includes storytelling elements and emojis.',
#   'id': '00000001',
#   'tool': 'create_caption_tool'},
#  {'arguments': [],
#   'dependencies': ['00000001'],
#   'description': 'Join the result of the create_caption_tool task to finalize '
#                  'the caption.',
#   'id': '00000002',
#   'tool': 'join'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Generate a creative and engaging caption for an '
#                           'Instagram post about a Bali retreat'}],
#   'dependencies': ['00000002'],
#   'description': 'Call the create_caption_agent to generate a caption for an '
#                  'Instagram post about a Bali retreat.',
#   'id': '32412460',
#   'tool': 'create_caption_agent'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Refine or leverage the generated caption for a Bali '
#                           'retreat post.'}],
#   'dependencies': ['32412460'],
#   'description': 'Passing the results of caption creation for Bali retreat to '
#                  'join for final check or enhancement.',
#   'id': '32412461',
#   'tool': 'join'}]

#         plans = [{'arguments': [{'name': 'prompt',
#                  'value': 'Generate a formal caption for a Bali retreat post'}],
#   'dependencies': [],
#   'description': 'Generate a formal caption for the Bali retreat post with no '
#                  'dependencies.',
#   'id': '78845012',
#   'tool': 'create_caption_agent'},
#  {'arguments': [{'name': 'prompt',
#                  'value': 'Summarize the generated caption for the Bali '
#                           'retreat post.'}],
#   'dependencies': ['78845012'],
#   'description': 'Use the generated caption for a Bali retreat post to provide '
#                  'a summary.',
#   'id': '78845013',
#   'tool': 'join'}]
        # await self.mediator.emit_plan(
        #     plan=copy.deepcopy(plans),
        #     summary='some summary',
        #     agent_name=self.name
        # )
        # return
#         plans2 = [
#     {
#         "id": "10000001",
#         "tool": "create_caption_tool",
#         "arguments": [
#             {
#                 "name": "prompt",
#                 "value": "Create a short, humorous Instagram caption with emojis for a Bali retreat post. The caption should be engaging and does not require specific keywords."
#             }
#         ],
#         "dependencies": [],
#         "description": "Call the create_caption_tool to generate a humorous caption with emojis for a Bali retreat Instagram post with no dependencies."
#     },
#     {
#         "id": "10000002",
#         "tool": "join",
#         "arguments": [],
#         "dependencies": [
#             "10000001"
#         ],
#         "description": "Join the results to finalize the caption for the user's Instagram post."
#             }
#         ]
#         await self.mediator.emit_plan(
#             plan=copy.deepcopy(plans2),
#             summary='some summary',
#             agent_name='create_caption_agent'
#         )

        # await asyncio.sleep(0)
        # return;
        
        # self.tasks = [{
        #     "id": 12345677,
        #     "tool": "create_hashtags_tool",
        #     "dependencies": [],
        #     "arguments": [{
        #         "name": "prompt",
        #         "value": "Generate a hashtags for Bali retreat"
				# 		}]
				# }]
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
        # if self._is_executing() or True:
        #     print('is exec')
        #     return await self._execute_plan_and_finalize(self.tasks)

        self._save_initial_message(message)
        if self._is_executing():
            print(f"Agent {self.name} is executing")
            return await self._execute_plan_and_finalize(tasks=self.tasks, resume_execution=True)
        start_time = time.time()
        assistant_response = await self.run_questionnaire(message)
        end_time = time.time()
        print(f"\033[34mTime taken to run questionnaire:\033[0m {end_time - start_time} seconds")

        if self.if_result_accepted(assistant_response):
            if assistant_response.message:
                self._emit_assistant_message(assistant_response.message)
            return
        
        need_replan, replan_after_execution, previous_user_requirements = self._parse_assistant_response(assistant_response)
        
        #In case if no user requirements provided or no need to replan. In case of replan we will send message to user as plan overview  
        plan_is_required = need_replan or (not self._is_plan_exists() and assistant_response.user_requirements)
        
        print('plan_is_required', plan_is_required)
        
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
    
    def get_response_model(self):
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