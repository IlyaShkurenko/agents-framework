# services/neo4j_service.py

import asyncio
from neo4j import AsyncGraphDatabase
from typing import List
import json

class Neo4jService:
    def __init__(self, uri, user, password):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))	
        asyncio.create_task(self.initialize())
        

    async def initialize(self):
        # await self.clear_nodes_with_connections()
        await self._initialize_constraints_and_indexes()

    async def close(self):
        await self.driver.close()

    async def create_or_update_agent(self, agent_name: str, description: str, plan_summary: str, task_id: str):
        async with self.driver.session() as session:
            await session.write_transaction(self._create_or_update_agent, agent_name, description, plan_summary, task_id)
            
    async def _initialize_constraints_and_indexes(self):
        async with self.driver.session() as session:
            try:
                # Create a uniqueness constraint on the name property of AGENT nodes
                await session.run("CREATE CONSTRAINT agent_task_id_unique IF NOT EXISTS FOR (n:AGENT) REQUIRE n.task_id IS UNIQUE")
                print("Unique constraint on AGENT(task_id) created successfully.")
            except Exception as e:
                print(f"Constraint creation failed: {e}")				

    @staticmethod
    async def _create_or_update_agent(tx, agent_name, description, plan_summary, task_id):
        print("\033[1;33mCreate or update agent:\033[0m", agent_name, plan_summary)
        await tx.run("""
            MERGE (a:AGENT {name: $agent_name, task_id: $task_id})
            SET a.description = $description,
                a.plan_summary = $plan_summary,
                a.name = $agent_name
        """, agent_name=agent_name, description=description, plan_summary=plan_summary, task_id=task_id)

    async def create_or_update_client_chat(self, client_id: str, chat_id: str):
        async with self.driver.session() as session:
            await session.write_transaction(self._create_or_update_client_chat, client_id, chat_id)
            
    @staticmethod
    async def _create_or_update_client_chat(tx, client_id: str, chat_id: str):
        await tx.run("""
            MERGE (c:CLIENT {id: $client_id})
            MERGE (ch:CHAT {id: $chat_id})
            MERGE (c)-[:HAS_CHAT]->(ch)
            SET c.id = $client_id,
                ch.id = $chat_id
        """, client_id=client_id, chat_id=chat_id)

    async def create_or_update_tool(self, tool_name: str, description: str, task_id: str):
        async with self.driver.session() as session:
            await session.write_transaction(self._create_or_update_tool, tool_name, description, task_id)

    @staticmethod
    async def _create_or_update_tool(tx, tool_name, description, task_id):
        await tx.run("""
            MERGE (t:TOOL {task_id: $task_id})
            SET t.description = $description,
                t.name = $tool_name
        """, tool_name=tool_name, description=description, task_id=task_id)

    # async def create_action(self, action_id: str, description: str, arguments: List[dict]):
    #     async with self.driver.session() as session:
    #         await session.write_transaction(self._create_action, action_id, description, arguments)

    # @staticmethod
    # async def _create_action(tx, action_id, description, arguments):
    #     arguments_json = json.dumps(arguments)
    #     await tx.run("""
    #         MERGE (act:ACTION {id: $action_id})
    #         SET act.description = $description,
    #             act.arguments = $arguments
    #     """, action_id=action_id, description=description, arguments=arguments_json)

    # async def create_relationships(self, agent_name: str, tool_name: str, action_id: str, dependencies: List[str]):
    #     async with self.driver.session() as session:
    #         await session.write_transaction(self._create_relationships, agent_name, tool_name, action_id, dependencies)

    # @staticmethod
    # async def _create_relationships(tx, agent_name, tool_name, action_id, dependencies):
    #     await tx.run("""
    #         MATCH (a:AGENT {name: $agent_name})
    #         MATCH (t:TOOL {name: $tool_name})
    #         MATCH (act:ACTION {id: $action_id})
    #         MERGE (a)-[:USES]->(t)
    #         MERGE (a)-[:PERFORMS]->(act)
    #         MERGE (t)-[:PERFORMS]->(act)
    #     """, agent_name=agent_name, tool_name=tool_name, action_id=action_id)

    #     for dep_action_id in dependencies:
    #         await tx.run("""
    #             MATCH (act1:ACTION {id: $action_id})
    #             MATCH (act2:ACTION {id: $dep_action_id})
    #             MERGE (act1)-[:DEPENDS_ON]->(act2)
    #         """, action_id=action_id, dep_action_id=dep_action_id)


            
    async def create_tool_to_agent_relationships(self, from_id: str, to_id: str, relationship_type: str):
        async with self.driver.session() as session:
            await session.write_transaction(self._create_tool_to_agent_relationships, from_id, to_id, relationship_type)

    @staticmethod
    async def _create_tool_to_agent_relationships(tx, from_id: str, to_id: str, relationship_type: str):
        await tx.run(f"""
						MATCH (a {{task_id: $from_id}})
						MATCH (b {{task_id: $to_id}})
						MERGE (a)-[:{relationship_type}]->(b)
				""", from_id=from_id, to_id=to_id)
        
    async def create_chat_to_agent_relationships(self, chat_id: str, agent_id: str):
        async with self.driver.session() as session:
            await session.write_transaction(self._create_chat_to_agent_relationships, chat_id, agent_id)

    @staticmethod
    async def _create_chat_to_agent_relationships(tx, from_id: str, to_id: str):
        await tx.run(f"""
						MATCH (a: CHAT {{id: $from_id}})
						MATCH (b {{task_id: $to_id}})
						MERGE (a)-[:USES]->(b)
				""", from_id=from_id, to_id=to_id)
        
    async def get_all_nodes_and_relationships(self):
        query = """
            MATCH (n)-[r]->(m)
            RETURN 
                n AS StartNode, 
                head(labels(n)) AS StartNodeLabel,
                type(r) AS RelationshipType, 
                m AS EndNode, 
                head(labels(m)) AS EndNodeLabel
        """
        async with self.driver.session() as session:
            result = await session.run(query)
            
            nodes_and_relationships = []
            async for record in result:
                nodes_and_relationships.append(record.data())
        
        return nodes_and_relationships


    # async def delete_agent_actions(self, agent_name: str):
    #     async with self.driver.session() as session:
    #         await session.write_transaction(self._delete_agent_actions, agent_name)

    # @staticmethod
    # async def _delete_agent_actions(tx, agent_name):
    #     await tx.run("""
    #         MATCH (a:AGENT {name: $agent_name})-[:PERFORMS]->(act:ACTION)
    #         DETACH DELETE act
    #     """, agent_name=agent_name)

    async def delete_agent_or_tool_node(self, tool_name: str, task_id: str):
        async with self.driver.session() as session:
            await session.write_transaction(self._delete_agent_or_tool_node, tool_name, task_id)

    @staticmethod
    async def _delete_agent_or_tool_node(tx, tool_name: str, task_id: str):
        await tx.run("""
            MATCH (n {task_id: $task_id, name: $tool_name})
            DETACH DELETE n
        """, task_id=task_id, tool_name=tool_name)

    async def delete_client_chat(self, chat_id: str):
        async with self.driver.session() as session:
            await session.write_transaction(self._delete_client_chat, chat_id)

    @staticmethod
    async def _delete_client_chat(tx, chat_id: str):
        await tx.run("""
            MATCH (ch:CHAT {id: $chat_id})
            DETACH DELETE ch
        """, chat_id=chat_id)
        
    async def clear_nodes_with_connections(self):
        async with self.driver.session() as session:
            try:
                constraints = await session.run("SHOW CONSTRAINTS YIELD name RETURN name")
                async for record in constraints:
                    await session.run("DROP CONSTRAINT $name IF EXISTS", name=record["name"])
                    print(f"Constraint {record['name']} deleted.")
                    
                await session.run("MATCH (n) DETACH DELETE n")
                print("All nodes and relationships deleted.")

            except Exception as e:
                print(f"Failed to clear database: {e}")