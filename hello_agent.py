"""Step 1: Minimal Strands agent with Amazon Nova 2 Lite on Bedrock.

Prerequisites:
  - AWS credentials configured (~/.aws/credentials or env vars)
  - Nova 2 Lite model access enabled in Bedrock console (us-east-1)
  - pip install strands-agents strands-agents-tools boto3

Usage:
  python hello_agent.py
"""

from strands import Agent
from strands.models import BedrockModel

model = BedrockModel(
    model_id="us.amazon.nova-2-lite-v1:0",
    region_name="us-east-1",
    streaming=True,
)

agent = Agent(model=model)

response = agent("You are a UPSC study planning assistant. Say hello and briefly explain what UPSC CSE is in 2-3 sentences.")
print(response)
