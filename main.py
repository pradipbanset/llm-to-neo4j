from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import os
import requests
import json
from neo4j import GraphDatabase


load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file!")

#neo4j configuration

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4jneo4j"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def create_role(tx, role_name, role_type):
    tx.run("MERGE (r:Role {name: $role_name, type: $role_type})",
           role_name=role_name, role_type=role_type)

def create_skill(tx, role_name, skill_name):
    tx.run("""
        MERGE (s:Skill {name: $skill_name})
        MERGE (r:Role {name: $role_name})
        MERGE (r)-[:REQUIRES]->(s)
    """, role_name=role_name, skill_name=skill_name)

def create_tool(tx, role_name, tool_name):
    tx.run("""
        MERGE (t:Tool {name: $tool_name})
        MERGE (r:Role {name: $role_name})
        MERGE (r)-[:USES]->(t)
    """, role_name=role_name, tool_name=tool_name)


# Helper function to call Google Gemini via REST API

def gemini_predict(prompt: str) -> str:
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        if 'candidates' in result and len(result['candidates']) > 0:
            return result['candidates'][0]['content']['parts'][0]['text']
        return ""
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return ""


# Define system steps as nodes

def process_input(state):
    user_text = state["user_text"]
    prompt = (
        f"Rewrite the query into a task form. "
        f"Example: 'I want to be a data engineer' -> 'What it takes to be a Data Engineer'\n"
        f"User: {user_text}"
    )
    state["processed_text"] = gemini_predict(prompt)
    return state

def extract_entities(state):
    text = state["processed_text"]
    prompt = f"Extract main career entities from: {text}. Return JSON with keys: role, type."
    response = gemini_predict(prompt)
    try:
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response.replace("```json", "").replace("```", "").strip()
        state["entities"] = json.loads(cleaned_response)
    except json.JSONDecodeError:
        print(f"JSON decode error. Raw response: {response}")
        state["entities"] = {"role": response.strip(), "type": "Career"}
    return state

def map_to_graph(state):
    entities = state["entities"]
    print("Mapping entities into Neo4j:", entities)
    with driver.session() as session:
        session.write_transaction(create_role, entities["role"], entities["type"])
    state["graph_mapped"] = True
    return state

def expand_graph(state):
    role = state["entities"].get("role", "Unknown")
    prompt = f"List 5 key skills and 3 tools required for the role: {role}. Return JSON with keys 'skills' and 'tools'. Make sure the response is valid JSON format."
    response = gemini_predict(prompt)
    try:
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response.replace("```json", "").replace("```", "").strip()
        skills_tools = json.loads(cleaned_response)
    except json.JSONDecodeError:
        print(f"JSON decode error in expand_graph. Raw response: {response}")
        skills_tools = {"skills": [], "tools": []}

    # Store skills and tools in Neo4j
    with driver.session() as session:
        for skill in skills_tools.get("skills", []):
            session.write_transaction(create_skill, role, skill)
        for tool in skills_tools.get("tools", []):
            session.write_transaction(create_tool, role, tool)

    print(f"Expanding graph for role: {role} with skills/tools: {skills_tools}")
    state["expanded"] = skills_tools
    return state

def query_graph(state):
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




if __name__ == "__main__":
    user_text = input("Enter your career query (e.g., 'I want to be a data engineer'): ")
    followup_question = input("Enter a follow-up question (e.g., 'What skills are required?'): ")

    inputs = {
        "user_text": user_text,
        "followup_question": followup_question
    }

    try:
        final_state = app.invoke(inputs)
        print("Final state:", final_state)
    except Exception as e:
        print(f"Error running workflow: {e}")

