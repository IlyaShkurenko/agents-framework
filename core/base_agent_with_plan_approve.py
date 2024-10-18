# agents/init_agent.py

from core.base_agent import BaseAgent
from core.planner.main import Planner

class BaseAgentWithPlanApprove(BaseAgent):
    """
    The InitAgent handles the initial interaction with the user.
    """

    @property
    def name(self):
        return "init_agent"

    @property
    def description(self):
        return "Agent responsible for initial interaction with the user. Collects user requirements and creates a plan for creation a social media content."
    
    async def handle_message(self, message: str):
        if not self.initial_message:
            self.initial_message = message
        print(f"\033[34mMessage in {self.name}:\033[0m", message)
        assistant_response = await self.run_questionnaire(message)
        print('assistant_response', assistant_response)

        if assistant_response.result_accepted:
            self.state_model.save_agent_status('completed')
            self.mediator.on_agents_done(self.name)
            return assistant_response.message

        if assistant_response.user_requirements:

            if assistant_response.message:
                self.mediator.emit_message('message', assistant_response.message)

            need_replan = self.state_model.is_requirements_changed(assistant_response.user_requirements.dict())

            result_accepted = getattr(assistant_response, 'result_accepted', False)
            previous_user_requirements = self.state_model.get_user_requirements();

            self.state_model.save_user_requirements(assistant_response.user_requirements.dict())
            print('plan approved', getattr(assistant_response, 'plan_approved', False))
            print('need_replan', need_replan)
            print('result accepted', result_accepted)
            print('message', assistant_response.message)
            plan_approved = getattr(assistant_response, 'plan_approved', False)
            if not plan_approved or need_replan:
                # Create a plan or replan based on the user requirements
                self.mediator.emit_message('planning_started')
                planner = Planner(tools=self.tools,examples=self.planner_example)

                user_requirements = self.state_model.get_user_requirements()
                planner_conversation_history = self.state_model.get_agent_planner_conversation_history()

                self.state_model.save_agent_status("planning")
                planner_conversation_history, planner_response = await planner.create_plan(conversation_history=planner_conversation_history, user_requirements=user_requirements, include_overview=True, replan=need_replan, replan_after_execution=not result_accepted, tasks_with_results=self.executor.get_tasks_with_results(), executed_user_requirements=previous_user_requirements)
                
                # Update planner conversation history which includes overview and tasks
                self.state_model.save_agent_planner_history(planner_conversation_history)
                plan_response_dict = planner_response.dict()
    
                # Update agent conversation history which includes only overview
                self.state_model.add_message_to_conversation_history(plan_response_dict['overview'])

                self.state_model.save_agent_plan(plan_response_dict)
                self.tasks = plan_response_dict['tasks']

                self.mediator.emit_plan(plan=plan_response_dict, summary=user_requirements['summary'], agent_name=self.name)

                return plan_response_dict['overview']

            # return 'Start execution'
            # Execute the plan
            self.executor.set_tasks_state_model(self.mediator.mediator_tasks_state_model)
            self.state_model.save_agent_status("execution")
            self.mediator.emit_message('execution_started')
            final_response = await self.executor.execute_plan()

            if self.has_joiner:
                final_response = await self.joiner.join(initial_message=self.initial_message, final_response=final_response)
                
            self.state_model.add_message_to_conversation_history(final_response)
            
            self.state_model.save_agent_status('waiting_for_approval')

            return final_response
        else:
            # Return the assistant's message to the user
            return assistant_response.message or 'Sorry, I did not understand your request.'

    async def run_questionnaire(self, message: str):
        """
        Runs the questionnaire to collect user requirements.

        Args:
            message (str): The message from the user.

        Returns:
            dict: The assistant's response.
        """
        self.state_model.save_agent_status("questionnaire")
        history = self.state_model.get_conversation_history()
        print("\033[34mIs plan exists:\033[0m", self.state_model.is_plan_exists())

        response_model = self.get_response_model()
        print('response_model',response_model)
        assistant_response = await self.openai_service.get_response(conversation_history=history, system_prompt=self.questionnaire_prompt, message=message, response_schema=response_model)

        return assistant_response
    
    def get_response_model(self):
        print("\033[34mIs plan exists:\033[0m", self.state_model.is_plan_exists())

        is_waiting_for_approval = self.state_model.get_agent_status() is 'waiting_for_approval'
        print("\033[34mIs waiting for approval:\033[0m", is_waiting_for_approval)
        
        return self.create_dynamic_response_model(include_plan_action=self.state_model.is_plan_exists(), include_result_accepted=is_waiting_for_approval)  
  