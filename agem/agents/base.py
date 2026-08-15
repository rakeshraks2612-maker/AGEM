"""Base ADK agent for AGEM."""
from google.adk.agents import Agent

class BaseAGEMAgent:
    """Base class for all AGEM ADK agents."""
    def __init__(self, name, instruction, tools=None):
        self.name = name
        self.agent = Agent(
            name=name,
            model="gemini-3.5-flash",
            description=instruction,
            instruction=instruction,
            tools=tools or [],
        )
