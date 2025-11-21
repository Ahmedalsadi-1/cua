"""
Configuration for the Cua Agent SDK.
"""

import os
from agent import ComputerAgent
from computer import Computer

def get_agent(model_name: str, computer: Computer) -> ComputerAgent:
    """
    Initializes and returns a ComputerAgent with the specified model.
    """
    # Fallback to a local model if the specified model is not available
    available_models = [
        "openai/computer-use-preview",
        "anthropic/claude-sonnet-4-5",
    ]
    if model_name not in available_models:
        print(f"Model '{model_name}' not found. Falling back to local model.")
        model_name = "huggingface-local/GTA1-7B"

    return ComputerAgent(
        model=model_name,
        tools=[computer],
        verbosity=1,
    )

async def main():
    """
    Example of how to use the get_agent function to initialize a ComputerAgent.
    """
    # Note: This requires a running computer environment.
    # This is just an example of how to initialize the agent.
    # To run this, you would need to set up a computer instance first.
    # computer = Computer(...)
    # await computer.run()
    # agent = get_agent("openai/computer-use-preview", computer)
    # print(f"Agent initialized with model: {agent.model}")
    pass

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
