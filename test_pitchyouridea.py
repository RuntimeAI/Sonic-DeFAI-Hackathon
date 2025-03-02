#!/usr/bin/env python3
"""
Test script for interacting with the PitchYourIdea agent via the ZerePy server.

Usage:
  1. Test with remote server (default): python test_pitchyouridea.py
  2. Test with local server: python test_pitchyouridea.py --url http://localhost:8000
  3. Test with custom pitch: python test_pitchyouridea.py --pitch "Your pitch text here"
  4. Post to Farcaster: python test_pitchyouridea.py --post
  5. Reply to a cast: python test_pitchyouridea.py --post --reply-to CAST_ID
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
    
    # Example pitch
    default_pitch = "I'm developing a decentralized marketplace for carbon credits using blockchain technology. Our platform will connect carbon offset projects directly with businesses looking to reduce their carbon footprint. We're seeking $500K to build our MVP and onboard initial partners."
    
    # Use provided pitch or default
    pitch = args.pitch if args.pitch else default_pitch
    
    print_section("PITCH EVALUATION")
    print(f"Pitch: {pitch}")
    print("\nEvaluating pitch...")
    
    try:
        # Use the agent's evaluate_pitch action
        evaluation_result = client.perform_action(
            agent="pitchyouridea",
            action="evaluate_pitch",
            params={"pitch_text": pitch}
        )
        
        if not evaluation_result.get("success", False):
            print_colorized(f"Error evaluating pitch: {evaluation_result.get('error', 'Unknown error')}", 31)
            return
            
        evaluation = evaluation_result["evaluation"]
        
        # Print the evaluation
        print("\nEvaluation:")
        print(json.dumps(evaluation, indent=2))
        
        # Highlight the decision
        decision = evaluation.get("decision", "unknown").upper()
        decision_color = 32 if decision == "INVEST" else 31  # Green for invest, red for pass
        print_colorized(f"\nDECISION: {decision}", decision_color)
        
        # Generate response
        print_section("RESPONSE GENERATION")
        
        response_result = client.perform_action(
            agent="pitchyouridea",
            action="generate_response",
            params={
                "pitch_text": pitch,
                "evaluation": evaluation
            }
        )
        
        if not response_result.get("success", False):
            print_colorized(f"Error generating response: {response_result.get('error', 'Unknown error')}", 31)
            return
            
        response_text = response_result["response"]
        
        print_colorized("\nResponse (for Farcaster):", 36)
        print(f"@pitchyouridea: {response_text}")
        
        # Character count
        char_count = response_result.get("character_count", len(response_text))
        color = 32 if char_count <= 300 else 31
        print_colorized(f"\nCharacter count: {char_count}/300", color)
        
        # After generating the response, check if we should post to Farcaster
        if args.post:
            print_section("POSTING TO FARCASTER")
            
            post_result = client.perform_action(
                agent="pitchyouridea",
                action="post_to_farcaster",
                params={
                    "response_text": response_text,
                    "reply_to_cast_id": args.reply_to
                }
            )
            
            if post_result.get("success", False):
                print_colorized("Successfully posted to Farcaster!", 32)
                cast_hash = post_result.get("cast_hash", "unknown")
                print(f"Cast hash: {cast_hash}")
            else:
                print_colorized(f"Failed to post to Farcaster: {post_result.get('error', 'Unknown error')}", 31)
        
    except Exception as e:
        print_colorized(f"Error: {e}", 31)
    
    print_colorized("\nTest completed!", 32)

if __name__ == "__main__":
    main() 