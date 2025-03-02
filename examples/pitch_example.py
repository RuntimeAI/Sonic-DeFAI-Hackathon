#!/usr/bin/env python3
"""
Example script for using the PitchYourIdea client.

Usage:
  1. Start the ZerePy server: python main.py --server --host 0.0.0.0 --port 8000
  2. Run this script: python examples/pitch_example.py
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.server.client import ZerePyClient, ZerePyClientError

def main():
    # Initialize the client
    client = ZerePyClient("http://localhost:8000")
    
    try:
        # Check server status
        status = client.get_status()
        print(f"Server status: {status}")
        
        # List available agents
        agents = client.list_agents()
        print(f"Available agents: {agents}")
        
        # Load the PitchYourIdea agent
        if "pitchyouridea" in agents:
            result = client.load_agent("pitchyouridea")
            print(f"Loaded agent: {result}")
        else:
            print("PitchYourIdea agent not found!")
            return
        
        # List available connections
        connections = client.list_connections()
        print(f"Available connections: {list(connections.keys())}")
        
        # Check if we have an LLM provider configured
        llm_provider = None
        for name, info in connections.items():
            if info.get("is_llm_provider", False) and info.get("configured", False):
                llm_provider = name
                break
        
        if not llm_provider:
            print("No configured LLM provider found. Please configure OpenAI or Anthropic.")
            return
        
        # Example pitch
        pitch = "I'm developing a decentralized marketplace for carbon credits using blockchain technology. Our platform will connect carbon offset projects directly with businesses looking to reduce their carbon footprint. We're seeking $500K to build our MVP and onboard initial partners."
        
        # Evaluate the pitch
        print(f"\nEvaluating pitch using {llm_provider}...")
        result = client.perform_action(
            connection=llm_provider,
            action="generate-text",
            params={
                "prompt": f"""
Analyze this investment pitch based on societal value, practicality, profitability, and equity potential:

{pitch}

Format your response as JSON with the following structure:
{{
  "analysis": {{
    "societal_value": "High/Medium/Low",
    "practicality": "High/Medium/Low",
    "profitability": "High/Medium/Low",
    "equity_notes": "Brief notes"
  }},
  "decision": "invest/pass",
  "valuation": 0,
  "investment_amount": 0,
  "equity_percentage": 0,
  "terms": "Additional terms",
  "explanation": "Brief explanation"
}}
""",
                "system_prompt": "You are PitchYourIdea, a professional fund manager evaluating investment pitches."
            }
        )
        
        print("\nEvaluation result:")
        print(result.get("result", "No result"))
        
    except ZerePyClientError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main() 