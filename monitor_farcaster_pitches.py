#!/usr/bin/env python3
"""
Script to monitor Farcaster for investment pitches and respond to them using the PitchYourIdea agent.

Usage:
  python monitor_farcaster_pitches.py [--url URL] [--interval SECONDS]
"""

import sys
import json
import time
import logging
import argparse
from datetime import datetime
from src.server.client import ZerePyClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("farcaster_monitor")

def print_section(title):
    """Print a section title"""
    print("\n" + "=" * 50)
    print(f" {title} ".center(50, "="))
    print("=" * 50)

def print_colorized(text, color_code):
    """Print text with ANSI color codes"""
    print(f"\033[{color_code}m{text}\033[0m")

def is_valid_pitch(cast_text):
    """
    Determine if a cast is a valid investment pitch.
    
    This is a simple heuristic that looks for keywords related to pitches,
    funding, investment, etc.
    """
    # Convert to lowercase for case-insensitive matching
    text = cast_text.lower()
    
    # Keywords that suggest this might be a pitch
    pitch_keywords = [
        'pitch', 'startup', 'idea', 'business', 'venture', 
        'funding', 'investment', 'investor', 'seed', 'angel',
        'raise', 'raising', 'fund', 'capital', 'series',
        'valuation', 'equity', 'stake', 'share', 'round',
        'million', 'billion', 'k', 'm', 'b', '$', 'usd', 'dollar'
    ]
    
    # Check if the text contains any of the keywords
    for keyword in pitch_keywords:
        if keyword in text:
            return True
    
    return False

def evaluate_pitch(client, pitch_text, llm_provider):
    """Evaluate an investment pitch using the PitchYourIdea agent"""
    try:
        # Create evaluation prompt
        evaluation_prompt = f"""
Analyze this investment pitch based on the following criteria:
1. Societal Value: How beneficial is this to society? (Low/Medium/High)
2. Practicality: How feasible is implementation? (Low/Medium/High)
3. Profitability: What's the profit potential? (Low/Medium/High)
4. Equity Potential: What percentage of equity would be appropriate for investment?

PITCH TO EVALUATE:
{pitch_text}

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
        
        # Execute the evaluation
        result = client.perform_action(
            connection=llm_provider,
            action="generate-text",
            params=[evaluation_prompt, system_prompt]
        )
        
        evaluation_text = result.get("result", "")
        
        # Try to parse as JSON
        evaluation = json.loads(evaluation_text)
        return evaluation
        
    except Exception as e:
        logger.error(f"Error evaluating pitch: {e}")
        return None

def generate_response(client, pitch_text, evaluation, llm_provider):
    """Generate a response to the pitch"""
    try:
        response_prompt = f"""
Create a concise, professional response (max 300 characters) to this investment pitch:

ORIGINAL PITCH:
{pitch_text}

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
        
        # Generate response
        response_result = client.perform_action(
            connection=llm_provider,
            action="generate-text",
            params=[response_prompt, system_prompt]
        )
        
        response_text = response_result.get("result", "")
        
        # Trim if necessary
        if len(response_text) > 300:
            response_text = response_text[:297] + "..."
            
        return response_text
        
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return None

def post_to_farcaster(client, response_text, reply_to_cast_id=None):
    """Post a response to Farcaster, optionally as a reply to a specific cast"""
    try:
        # Prepare action parameters
        params = [response_text]
        if reply_to_cast_id:
            action = "reply-to-cast"
            params.append(reply_to_cast_id)
        else:
            action = "post-cast"
        
        # Execute the action
        logger.info(f"Posting to Farcaster using '{action}'...")
        result = client.perform_action(
            connection="farcaster",
            action=action,
            params=params
        )
        
        if result.get("success", False):
            logger.info("Successfully posted to Farcaster!")
            cast_hash = result.get("cast_hash", "unknown")
            logger.info(f"Cast hash: {cast_hash}")
            return cast_hash
        else:
            logger.error(f"Failed to post to Farcaster: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error posting to Farcaster: {e}")
        return False

def get_latest_casts(client, count=10):
    """Get the latest casts from Farcaster"""
    try:
        # Convert count to string for the remote API
        result = client.perform_action(
            connection="farcaster",
            action="get-latest-casts",
            params=[str(count)]  # Convert to string
        )
        
        if "casts" in result:
            return result["casts"]
        else:
            logger.error("No casts found in response")
            return []
            
    except Exception as e:
        logger.error(f"Error getting latest casts: {e}")
        return []

def get_mentions(client):
    """Get mentions of the PitchYourIdea agent on Farcaster"""
    try:
        result = client.perform_action(
            connection="farcaster",
            action="mentioned_casts",
            params=["25"]
        )
        
        if "mentions" in result:
            return result["mentions"]
        else:
            logger.warning("No mentions found in response")
            return []
            
    except Exception as e:
        logger.error(f"Error getting mentions: {e}")
        return []

def process_new_casts(client, processed_casts, llm_provider):
    """Process new casts and respond to pitches"""
    # Get mentions first (higher priority)
    mentions = get_mentions(client)
    logger.info(f"Found {len(mentions)} mentions")
    
    # Then get latest casts
    latest_casts = get_latest_casts(client, 20)
    logger.info(f"Found {len(latest_casts)} latest casts")
    
    # Combine and deduplicate
    all_casts = {}
    for cast in mentions + latest_casts:
        cast_id = cast.get("hash")
        if cast_id and cast_id not in all_casts:
            all_casts[cast_id] = cast
    
    logger.info(f"Total unique casts to process: {len(all_casts)}")
    
    # Process each cast
    new_processed = {}
    for cast_id, cast in all_casts.items():
        # Skip if already processed
        if cast_id in processed_casts:
            continue
            
        # Extract cast details
        author = cast.get("author", {}).get("username", "unknown")
        text = cast.get("text", "")
        
        logger.info(f"Processing cast from @{author}: {text[:50]}...")
        
        # Check if this is a valid pitch
        if is_valid_pitch(text):
            logger.info(f"Valid pitch detected from @{author}")
            
            # Evaluate the pitch
            evaluation = evaluate_pitch(client, text, llm_provider)
            if not evaluation:
                logger.error("Failed to evaluate pitch")
                continue
                
            # Generate response
            response = generate_response(client, text, evaluation, llm_provider)
            if not response:
                logger.error("Failed to generate response")
                continue
                
            # Post response as a reply
            success = post_to_farcaster(client, response, cast_id)
            if success:
                logger.info(f"Successfully replied to @{author}'s pitch")
            else:
                logger.error(f"Failed to reply to @{author}'s pitch")
        else:
            logger.info(f"Not a valid pitch from @{author}")
        
        # Mark as processed
        new_processed[cast_id] = {
            "processed_at": datetime.now().isoformat(),
            "author": author,
            "is_pitch": is_valid_pitch(text)
        }
    
    return new_processed

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Monitor Farcaster for investment pitches")
    parser.add_argument("--url", type=str, default="https://api.singha.today", 
                        help="ZerePy server URL (default: https://api.singha.today)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Polling interval in seconds (default: 60)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode (more verbose logging)")
    args = parser.parse_args()
    
    # Set logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Initialize the client
    server_url = args.url
    is_remote = "localhost" not in server_url and "127.0.0.1" not in server_url
    env_name = "REMOTE" if is_remote else "LOCAL"
    
    logger.info(f"Connecting to {env_name} ZerePy server at {server_url}")
    client = ZerePyClient(server_url)
    
    # Check server status
    try:
        status = client.get_status()
        logger.info(f"Server status: {status}")
    except Exception as e:
        logger.error(f"Error getting server status: {e}")
        if not is_remote:
            logger.error("Make sure the server is running with: python main.py --server --host 0.0.0.0 --port 8000")
        return
    
    # Load the PitchYourIdea agent
    try:
        result = client.load_agent("pitchyouridea")
        logger.info(f"Agent loaded: {result}")
    except Exception as e:
        logger.error(f"Error loading agent: {e}")
        return
    
    # Check connections
    try:
        connections = client.list_connections()
        
        # Check Farcaster connection
        if "farcaster" not in connections:
            logger.error("Farcaster connection not available")
            return
            
        if not connections["farcaster"].get("configured", False):
            logger.error("Farcaster connection not configured")
            return
            
        logger.info("Farcaster connection is configured")
        
        # Find an available LLM provider
        llm_providers = [name for name, info in connections.items() 
                        if info.get("is_llm_provider", False) and info.get("configured", False)]
        
        if not llm_providers:
            logger.error("No configured LLM providers found")
            return
        
        llm_provider = llm_providers[0]
        logger.info(f"Using LLM provider: {llm_provider}")
        
    except Exception as e:
        logger.error(f"Error checking connections: {e}")
        return
    
    # Initialize processed casts dictionary
    processed_casts = {}
    
    # Main monitoring loop
    logger.info(f"Starting monitoring loop with {args.interval} second interval")
    try:
        while True:
            logger.info("Checking for new casts...")
            
            # Process new casts using the agent
            timestamp = datetime.now().isoformat()
            result = client.perform_action(
                agent="pitchyouridea",
                action="process_new_casts",
                params={
                    "processed_casts": processed_casts,
                    "timestamp": timestamp
                }
            )
            
            if result.get("success", False):
                # Update processed casts
                new_processed = result.get("new_processed", {})
                processed_casts.update(new_processed)
                
                # Log stats
                processed_count = result.get("processed_count", 0)
                logger.info(f"Processed {processed_count} new casts, {len(processed_casts)} total")
            else:
                logger.error(f"Error processing casts: {result.get('error', 'Unknown error')}")
            
            # Sleep for the specified interval
            logger.info(f"Sleeping for {args.interval} seconds...")
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    logger.info("Monitoring ended")

if __name__ == "__main__":
    main() 