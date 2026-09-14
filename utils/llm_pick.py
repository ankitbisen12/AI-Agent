from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()

def llm_pick(model_level:str):

    """
    Pick a LLM model based on the provided level.

    Args:
        model_level (str): The level of the model to use.

    Returns:
        An instance of the selected LLM model.
    """
    # Example implementation (this would depend on the actual LLM library being used)
    if model_level.lower() == "low":
       llm_instance = ChatOpenAI(model_name="gpt-5.6-luna", temperature=0)
    elif model_level.lower() == "medium":
        llm_instance = ChatOpenAI(model_name="gpt-5.6-terra", temperature=0)
    elif model_level.lower() == "high":
        llm_instance = ChatOpenAI(model_name="gpt-5.6-sol", temperature=0) 
    else:
        raise ValueError(f"Invalid model level: {model_level}. Choose from 'low', 'medium', or 'high'.")

    return llm_instance


if __name__ == "__main__":
    # Example usage
    llm_obj = llm_pick("medium")
    print(llm_obj.invoke("What is the capital of France?"))
