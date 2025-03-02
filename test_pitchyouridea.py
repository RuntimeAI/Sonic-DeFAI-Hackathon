#!/usr/bin/env python3
"""
Test script for interacting with the PitchYourIdea agent via the ZerePy server.

Usage:
  1. Test with remote server (default): python test_pitchyouridea.py
  2. Test with local server: python test_pitchyouridea.py --url http://localhost:8000
  3. Test with custom pitch: python test_pitchyouridea.py --pitch "Your pitch text here"
"""

import sys
import json
import logging
import argparse
from src.server.client import ZerePyClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("test_client")

def print_section(title):
    """Print a section title"""
    print("\n" + "=" * 50)
    print(f" {title} ".center(50, "="))
    print("=" * 50)

def print_colorized(text, color_code):
    """Print text with ANSI color codes"""
    print(f"\033[{color_code}m{text}\033[0m")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test the PitchYourIdea agent")
    parser.add_argument("--url", type=str, default="https://api.singha.today", 
                        help="ZerePy server URL (default: https://api.singha.today)")
    parser.add_argument("--pitch", type=str, 
                        help="Custom pitch to evaluate (default: uses example pitch)")
    parser.add_argument("--post", action="store_true",
                        help="Post the response to Farcaster")
    parser.add_argument("--reply-to", type=str,
                        help="Cast ID to reply to (requires --post)")
    args = parser.parse_args()
    
    # Initialize the client
    server_url = args.url
    is_remote = "localhost" not in server_url and "127.0.0.1" not in server_url
    env_name = "REMOTE" if is_remote else "LOCAL"
    
    print_colorized(f"Connecting to {env_name} ZerePy server at {server_url}", 36)
    client = ZerePyClient(server_url)
    
    # Check server status
    print_section("SERVER STATUS")
    try:
        status = client.get_status()
        print(f"Status: {json.dumps(status, indent=2)}")
    except Exception as e:
        print_colorized(f"Error getting server status: {e}", 31)
        if not is_remote:
            print("Make sure the server is running with: python main.py --server --host 0.0.0.0 --port 8000")
        return
    
    # List available agents
    print_section("AVAILABLE AGENTS")
    try:
        agents = client.list_agents()
        print(f"Agents: {agents}")
        
        if "pitchyouridea" not in agents:
            print_colorized("PitchYourIdea agent not found! Make sure it's properly configured.", 31)
            return
    except Exception as e:
        print_colorized(f"Error listing agents: {e}", 31)
        return
    
    # Load the PitchYourIdea agent
    print_section("LOADING AGENT")
    try:
        result = client.load_agent("pitchyouridea")
        print(f"Agent loaded: {result}")
    except Exception as e:
        print_colorized(f"Error loading agent: {e}", 31)
        return
    
    # List available connections
    print_section("AVAILABLE CONNECTIONS")
    try:
        connections = client.list_connections()
        print("Connections:")
        for name, info in connections.items():
            status = "✅ Configured" if info.get("configured", False) else "❌ Not configured"
            llm = "🧠 LLM Provider" if info.get("is_llm_provider", False) else ""
            print(f"  - {name}: {status} {llm}")
        
        # Find an available LLM provider
        llm_providers = [name for name, info in connections.items() 
                        if info.get("is_llm_provider", False) and info.get("configured", False)]
        
        if not llm_providers:
            print_colorized("\nNo configured LLM providers found.", 31)
            print("Please configure one of the following:")
            for name, info in connections.items():
                if info.get("is_llm_provider", False) and not info.get("configured", False):
                    print(f"  - {name}")
            return
        
        print_colorized(f"\nUsing LLM provider: {llm_providers[0]}", 32)
        llm_provider = llm_providers[0]
        
    except Exception as e:
        print_colorized(f"Error listing connections: {e}", 31)
        return
    
    # Test pitch evaluation
    print_section("PITCH EVALUATION")
    
    # Example pitch or use custom pitch from args
    if args.pitch:
        pitch = args.pitch
    else:
        pitch = "I'm developing a decentralized marketplace for carbon credits using blockchain technology. Our platform will connect carbon offset projects directly with businesses looking to reduce their carbon footprint. We're seeking $500K to build our MVP and onboard initial partners."
    
    print(f"Pitch: {pitch}")
    print("\nEvaluating pitch...")
    
    try:
        # Create evaluation prompt
        evaluation_prompt = f"""
Analyze this investment pitch based on the following criteria:
1. Societal Value: How beneficial is this to society? (Low/Medium/High)
2. Practicality: How feasible is implementation? (Low/Medium/High)
3. Profitability: What's the profit potential? (Low/Medium/High)
4. Equity Potential: What percentage of equity would be appropriate for investment?

PITCH TO EVALUATE:
{pitch}

Then make an investment decision:
- If you decide to invest: Specify valuation, investment amount, and equity percentage
- If you decline: Explain your reasoning briefly

FORMAT YOUR RESPONSE AS JSON:
{{
  "analysis": {{
    "societal_value": "High/Medium/Low",
    "practicality": "High/Medium/Low",
    "profitability": "High/Medium/Low",
    "equity_notes": "Brief notes on equity structure"
  }},
  "decision": "invest/pass",
  "valuation": 0,
  "investment_amount": 0,
  "equity_percentage": 0,
  "terms": "Additional terms or conditions",
  "explanation": "Brief explanation of decision"
}}
"""
        
        system_prompt = "You are PitchYourIdea, a professional fund manager evaluating investment pitches."
        
        # Execute the evaluation - Using a list for params
        result = client.perform_action(
            connection=llm_provider,
            action="generate-text",
            params=[evaluation_prompt, system_prompt]
        )
        
        evaluation_text = result.get("result", "")
        
        # Try to parse as JSON
        try:
            evaluation = json.loads(evaluation_text)
            print("\nEvaluation result:")
            print(json.dumps(evaluation, indent=2))
            
            # Color-coded decision
            decision = evaluation.get("decision", "unknown")
            decision_color = 32 if decision == "invest" else 31  # Green for invest, red for pass
            print_colorized(f"\nDECISION: {decision.upper()}", decision_color)
            
            # Generate response
            print_section("RESPONSE GENERATION")
            
            response_prompt = f"""
Create a concise, professional response (max 300 characters) to this investment pitch:

ORIGINAL PITCH:
{pitch}

YOUR EVALUATION:
{json.dumps(evaluation, indent=2)}

Your response should:
1. Acknowledge the pitch
2. Provide your investment decision
3. If investing, state the valuation, amount, and equity percentage
4. If passing, give a brief reason why

The response should be conversational and direct, without hashtags or emojis.
"""
            
            system_prompt = "You are PitchYourIdea, a professional fund manager responding to investment pitches."
            
            # Using a list for params
            response_result = client.perform_action(
                connection=llm_provider,
                action="generate-text",
                params=[response_prompt, system_prompt]
            )
            
            response_text = response_result.get("result", "")
            
            # Trim if necessary
            if len(response_text) > 300:
                response_text = response_text[:297] + "..."
            
            print_colorized("\nResponse (for Farcaster):", 36)
            print(f"@pitchyouridea: {response_text}")
            
            # Character count
            char_count = len(response_text)
            color = 32 if char_count <= 300 else 31
            print_colorized(f"\nCharacter count: {char_count}/300", color)
            
            # After generating the response, check if we should post to Farcaster
            if args.post:
                post_to_farcaster(client, response_text, args.reply_to)
            
        except json.JSONDecodeError:
            print_colorized("\nCould not parse evaluation as JSON. Raw result:", 31)
            print(evaluation_text)
        
    except Exception as e:
        print_colorized(f"Error evaluating pitch: {e}", 31)
    
    print_colorized("\nTest completed!", 32)

def post_to_farcaster(client, response_text, reply_to_cast_id=None):
    """Post a response to Farcaster, optionally as a reply to a specific cast"""
    print_section("POSTING TO FARCASTER")
    
    try:
        # Check if Farcaster connection is available and configured
        connections = client.list_connections()
        if "farcaster" not in connections:
            print_colorized("Farcaster connection not available", 31)
            return False
            
        if not connections["farcaster"].get("configured", False):
            print_colorized("Farcaster connection not configured", 31)
            return False
        
        # Prepare action parameters
        params = [response_text]
        if reply_to_cast_id:
            action = "reply-to-cast"
            params.append(reply_to_cast_id)
        else:
            action = "post-cast"
        
        # Execute the action
        print_colorized(f"Posting to Farcaster using '{action}'...", 36)
        result = client.perform_action(
            connection="farcaster",
            action=action,
            params=params
        )
        
        if result.get("success", False):
            print_colorized("Successfully posted to Farcaster!", 32)
            cast_hash = result.get("cast_hash", "unknown")
            print(f"Cast hash: {cast_hash}")
            return cast_hash
        else:
            print_colorized(f"Failed to post to Farcaster: {result.get('error', 'Unknown error')}", 31)
            return False
            
    except Exception as e:
        print_colorized(f"Error posting to Farcaster: {e}", 31)
        return False

if __name__ == "__main__":
    main() 