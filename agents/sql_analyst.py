import os 
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.llm_pick import llm_pick
from Models.schema import AgentState,judgeSchema
from langchain_core.messages import AIMessage, HumanMessage
from utils.database import DatabaseUtil
from langgraph.graph  import StateGraph, START, END

# llm_obj = llm_pick("medium")  # Example usage of the llm_pick function
# print(llm_obj.invoke("What is the capital of France?"))  # This will print the instance of the selected LLM model


#----------------------------- AI Agent Code------------#
def curate_question(state: AgentState)-> AgentState:
    user_question = state.user_question # Bcz this is a Pydantic model object
    llm = llm_pick("low")

    response = llm.invoke(f"Curate the following question: {user_question}").content

    state.curated_que = response
    state.messages = state.messages + [HumanMessage(content=f"{response}")]
    return state


def prompt_context_query(state: AgentState)->AgentState:
    curated_question = state.curated_que

    conn_details = {
        "host": os.environ['host'],
        "port": int(os.environ['port']),
        "user": os.environ['user'],
        "password": os.environ['password'],
        "dbname": os.environ['database'],
    }

    obj = DatabaseUtil(conn_details)

    schema_info = obj.schema_details("public")

    # Constructing the prompt query for the agent to generate the SQL query.
    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language 
    query into Postgres SQL query that can be executed on the database. You are provided 
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that 
    you can understand the structure of the database and generate an accurate SQL query.
    Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications.  
    
    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}
    """

    state.prompt_context_query = prompt

    return state

# Generate SQL Query Node
def generate_sql(state: AgentState)->AgentState:
    prompt = state.prompt_context_query

    llm = llm_pick("medium")

    generated_sql_query = llm.invoke(prompt).content

    state.generated_sql_query = generated_sql_query
    return state

# Use AI as a judge(Allow  read only queries) to check if the generated SQL query is safe to execute on the database or not.
def is_safe_sql(state: AgentState)->AgentState:
    sql_query  =  state.generated_sql_query

    llm = llm_pick("medium")  # Example usage of the llm_pick function
    llm_judge = llm.with_structured_output(judgeSchema)

    prompt = f"""
    You are an SQL Judge for data security. Your task is to determine whether the SQL query is 
        safe or not. The SQL query should only be used for data retrieval and should not modify the 
        database in any way. Neither the SQL query nor the prompt should contain any SQL commands that can modify the
        database, such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change
        the structure or content of the database. If the SQL query is safe, respond with 'Yes' otherwise respond with 
        'No'. Additionally, provide comments explaining your decision
        Here is the SQL query to evaluate: {sql_query}
    """

    response = llm_judge.invoke(prompt).model_dump()
    state.is_safe = response['answer']
    state.comments = response['comments']

    return state


def cancel_query(state: AgentState)->AgentState:
    comments = state.comments 
    state.final_answer = f"The generated SQL query is not safe to execute on the database. It contains commands that can modify the database, which is not allowed. Please review the query and ensure it only retrieves data without altering the database structure or content."
    return state

def execute_sql(state: AgentState)->AgentState:
    sql_query = state.generated_sql_query

    conn_details = {
    "host": os.environ['host'],
    "port": int(os.environ['port']),
    "user": os.environ['user'],
    "password": os.environ['password'],
    "dbname": os.environ['database'],
    }

    obj = DatabaseUtil(conn_details)

    result = obj.execute_query(sql_query)

    state.sql_query_execution_result = result

    return state


def represent_final_answer(state: AgentState)->AgentState:
    execution_result = state.sql_query_execution_result
    curated_question = state.curated_que

    llm = llm_pick("medium")

    prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {execution_result} \n
    Here is the user's original question: {curated_question}
    """

    llm_response = llm.invoke(prompt).content
    state.final_answer = llm_response
    state.messages = state.messages + [AIMessage(content=f"{llm_response}")]
    return state

#-------------------Graph Building---------------
sql_agent_graph = StateGraph(AgentState)

#Nodes
sql_agent_graph.add_node("curate_question", curate_question)
sql_agent_graph.add_node("prompt_context_query", prompt_context_query)  
sql_agent_graph.add_node("generate_sql", generate_sql)
sql_agent_graph.add_node("is_safe_sql", is_safe_sql)
sql_agent_graph.add_node("cancel_query", cancel_query)
sql_agent_graph.add_node("execute_sql", execute_sql)
sql_agent_graph.add_node("represent_final_answer", represent_final_answer)

#Edges
sql_agent_graph.add_edge(START, "curate_question")
sql_agent_graph.add_edge("curate_question", "prompt_context_query")
sql_agent_graph.add_edge("prompt_context_query", "generate_sql")
sql_agent_graph.add_edge("generate_sql", "is_safe_sql")


def is_safe_sql_edge(state: AgentState)->str:
    is_safe = state.is_safe

    if is_safe.lower() == "yes":
        return "execute_sql"
    else:
        return "cancel_query"

sql_agent_graph.add_conditional_edges("is_safe_sql", is_safe_sql_edge,{
    "execute_sql": "execute_sql",
    "cancel_query": "cancel_query"
})

# sql_agent_graph.add_edge("is_safe_sql", "execute_sql")
# sql_agent_graph.add_edge("is_safe_sql", "cancel_query")

sql_agent_graph.add_edge("cancel_query", END)
sql_agent_graph.add_edge("execute_sql", "represent_final_answer")
sql_agent_graph.add_edge("represent_final_answer", END)

if __name__ == "__main__":

    #Compile the graph
    sql_analyst = sql_agent_graph.compile()

    from IPython.display import display, Image
    img = Image(sql_analyst.get_graph().draw_mermaid_png())
    with open("sql_analyst_graph.png", "wb") as f:
        f.write(img.data)

    input_schema = {
        "messages": [],
        "user_question": "What are the different types of Payment Methods we have in our database",
        "curated_que": "",
        "prompt_context_query": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }

    # Execute the Graph
    sql_analyst_response = sql_analyst.invoke(input_schema)
    print(sql_analyst_response['messages'])  # Print the final output of the graph execution
    print("********************************")

    print(sql_analyst_response['generated_sql_query'])  # Print the generated SQL query

    print("********************************")

    print(sql_analyst_response['sql_query_execution_result'])  # Print the result of executing the SQL query

    print("********************************")

    print(sql_analyst_response['prompt_context_query'])  # Print the prompt query context







    