from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import os
import requests
import json
from neo4j import GraphDatabase
from google import genai
from google.genai import types


load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file!")

#neo4j configuration

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4jneo4j"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))  #Creates a Neo4j driver instance to run queries

def create_role(tx, role_name, role_type):   #Transaction object used to run queries
    tx.run("MERGE (r:Role {name: $role_name, type: $role_type})",
           role_name=role_name, role_type=role_type)  #create node with the role and type

def create_skill(tx, role_name, skill_name):  
    """Creates a relationship (:Role)-[:REQUIRES]->(:Skill) This models the “Role requires these Skills” relationship in Neo4j"""
    tx.run("""
        MERGE (s:Skill {name: $skill_name})
        MERGE (r:Role {name: $role_name})
        MERGE (r)-[:REQUIRES]->(s)
    """, role_name=role_name, skill_name=skill_name)

def create_tool(tx, role_name, tool_name):
    """Make sure the role exists, make sure the tool exists, and connect them with USES"""
    tx.run("""
        MERGE (t:Tool {name: $tool_name})
        MERGE (r:Role {name: $role_name})
        MERGE (r)-[:USES]->(t)
    """, role_name=role_name, tool_name=tool_name)




client = genai.Client()  # Reads GEMINI_API_KEY automatically

def gemini_predict(prompt: str) -> str:
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)  # optional
            ),
        )
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return ""



# Define system steps as nodes

def process_input(state):
    """Process user input into a structured task using Gemini"""
    user_text = state["user_text"]
    prompt = (
        f"Rewrite the query into a task form. "
        f"Example: 'I want to be a data engineer' -> 'What it takes to be a Data Engineer'\n"
        f"User: {user_text}"
    )
    state["processed_text"] = gemini_predict(prompt)
    return state




def extract_entities(state):
    """Extract career-related entities, skip non-career queries"""
    text = state["processed_text"]
    prompt = f"Extract main career entities from: {text}. Return JSON with keys: role, type."
    response = gemini_predict(prompt)
    
    try:
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response.replace("```json", "").replace("```", "").strip()
        entities = json.loads(cleaned_response)
    except json.JSONDecodeError:
        entities = {"role": None, "type": None}

    # If no valid career role, skip workflow
    if not entities.get("role") or not entities.get("type") or entities.get("role").lower() in ["unknown", "career"]:
        state["skip_workflow"] = True
        state["entities"] = {}
        state["message"] = "Sorry, this assistant only provides career guidance."
    else:
        state["skip_workflow"] = False
        state["entities"] = entities

    return state





def map_to_graph(state):
    """Map extracted entities into Neo4j graph database"""
    if state.get("skip_workflow"):
        print(state.get("message"))
        state["graph_mapped"] = False
        return state

    entities = state["entities"]
    print("Mapping entities into Neo4j:", entities)
    with driver.session() as session:
        session.write_transaction(create_role, entities["role"], entities["type"])
    state["graph_mapped"] = True
    return state




def expand_graph(state):
    """Expand the graph only if a valid career role exists"""
    if state.get("skip_workflow"):
        print(state.get("message"))
        state["expanded"] = {"skills": [], "tools": []}
        return state

    role = state["entities"]["role"]
    prompt = (
        f"List 5 key skills and 3 tools required for the role: {role}. "
        "Return valid JSON with keys 'skills' and 'tools'."
    )
    response = gemini_predict(prompt)

    try:
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response.replace("```json", "").replace("```", "").strip()
        skills_tools = json.loads(cleaned_response)
    except json.JSONDecodeError:
        skills_tools = {"skills": [], "tools": []}

    # Store in Neo4j
    with driver.session() as session:
        for skill in skills_tools.get("skills", []):
            session.write_transaction(create_skill, role, skill)
        for tool in skills_tools.get("tools", []):
            session.write_transaction(create_tool, role, tool)

    state["expanded"] = skills_tools
    return state



def query_graph(state):
    """Convert follow-up question into Cypher query and execute it"""
    q = state["followup_question"]
    print(f"Converting question to Cypher: {q}")
    state["cypher"] = "MATCH (n) RETURN n"  # placeholder
    return state


# Build workflow graph

workflow = StateGraph(dict)
workflow.add_node("process_input", process_input)
workflow.add_node("extract_entities", extract_entities)
workflow.add_node("map_to_graph", map_to_graph)
workflow.add_node("expand_graph", expand_graph)
workflow.add_node("query_graph", query_graph)

workflow.set_entry_point("process_input")
workflow.add_edge("process_input", "extract_entities")
workflow.add_edge("extract_entities", "map_to_graph")
workflow.add_edge("map_to_graph", "expand_graph")
workflow.add_edge("expand_graph", "query_graph")
workflow.add_edge("query_graph", END)


app = workflow.compile()




# if __name__ == "__main__":
#     user_text = input("Enter your career query (e.g., 'I want to be a data engineer'): ")
#     followup_question = input("Enter a follow-up question (e.g., 'What skills are required?'): ")

#     inputs = {
#         "user_text": user_text,
#         "followup_question": followup_question
#     }

#     try:
#         final_state = app.invoke(inputs)
#         print("Final state:", final_state)
#     except Exception as e:
#         print(f"Error running workflow: {e}")


if __name__ == "__main__":
    print("Career Workflow Assistant (type 'exit' to quit)\n")

    while True:
        user_text = input("Enter your career query: ")
        if user_text.lower() in ["exit", "quit"]:
            print("Exiting workflow. Goodbye!")
            break

        followup_question = input("Enter a follow-up question: ")
        if followup_question.lower() in ["exit", "quit"]:
            print("Exiting workflow. Goodbye!")
            break

        inputs = {
            "user_text": user_text,
            "followup_question": followup_question
        }

        try:
            final_state = app.invoke(inputs)
            # Display results nicely
            print("\n=== Query Result ===")
            print(f"Processed Text: {final_state.get('processed_text')}")
            print(f"Entities: {final_state.get('entities')}")
            print(f"Expanded Skills: {final_state.get('expanded', {}).get('skills', [])}")
            print(f"Expanded Tools: {final_state.get('expanded', {}).get('tools', [])}")
            print("===================\n")
        except Exception as e:
            print(f"Error running workflow: {e}")


