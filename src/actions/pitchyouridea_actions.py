import logging
import json
from typing import Dict, Any, List, Optional
from src.agent.base_agent import BaseAgent

logger = logging.getLogger("pitchyouridea_actions")

def monitor_farcaster(agent: BaseAgent, **kwargs) -> Dict[str, Any]:
    """
    Monitor Farcaster for mentions and potential investment pitches.
    
    Args:
        agent: The PitchYourIdea agent instance
        
    Returns:
        Dict containing the monitoring results
    """
    logger.info("Monitoring Farcaster for mentions and pitches")
    
    # Get mentions from Farcaster
    mentions_result = agent.perform_action(
        connection="farcaster",
        action="mentioned-casts",
        params=["25"]  # Get up to 25 mentions
    )
    
    # Get latest casts from Farcaster
    latest_result = agent.perform_action(
        connection="farcaster",
        action="get-latest-casts",
        params=["20"]  # Get 20 latest casts
    )
    
    # Combine and deduplicate casts
    all_casts = {}
    
    if "mentions" in mentions_result:
        for cast in mentions_result["mentions"]:
            cast_id = cast.get("hash")
            if cast_id and cast_id not in all_casts:
                all_casts[cast_id] = cast
    
    if "casts" in latest_result:
        for cast in latest_result["casts"]:
            cast_id = cast.get("hash")
            if cast_id and cast_id not in all_casts:
                all_casts[cast_id] = cast
    
    return {
        "success": True,
        "casts": list(all_casts.values()),
        "mention_count": len(mentions_result.get("mentions", [])),
        "latest_count": len(latest_result.get("casts", []))
    }

def evaluate_pitch(agent: BaseAgent, pitch_text: str, **kwargs) -> Dict[str, Any]:
    """
    Evaluate an investment pitch using the configured LLM provider.
    
    Args:
        agent: The PitchYourIdea agent instance
        pitch_text: The text of the pitch to evaluate
        
    Returns:
        Dict containing the evaluation results
    """
    logger.info(f"Evaluating pitch: {pitch_text[:50]}...")
    
    # Find an available LLM provider
    connections = agent.list_connections()
    llm_providers = [name for name, info in connections.items() 
                    if info.get("is_llm_provider", True) and info.get("configured", False)]
    
    if not llm_providers:
        return {
            "success": False,
            "error": "No configured LLM providers found"
        }
    
    llm_provider = llm_providers[0]
    logger.info(f"Using LLM provider: {llm_provider}")
    
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
    result = agent.perform_action(
        connection=llm_provider,
        action="generate-text",
        params=[evaluation_prompt, system_prompt]
    )
    
    evaluation_text = result.get("result", "")
    
    # Try to parse as JSON
    try:
        evaluation = json.loads(evaluation_text)
        return {
            "success": True,
            "evaluation": evaluation
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Failed to parse evaluation as JSON",
            "raw_result": evaluation_text
        }

def generate_response(agent: BaseAgent, pitch_text: str, evaluation: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    Generate a response to a pitch based on the evaluation.
    
    Args:
        agent: The PitchYourIdea agent instance
        pitch_text: The original pitch text
        evaluation: The evaluation results
        
    Returns:
        Dict containing the response
    """
    logger.info("Generating response to pitch")
    
    # Find an available LLM provider
    connections = agent.list_connections()
    llm_providers = [name for name, info in connections.items() 
                    if info.get("is_llm_provider", True) and info.get("configured", False)]
    
    if not llm_providers:
        return {
            "success": False,
            "error": "No configured LLM providers found"
        }
    
    llm_provider = llm_providers[0]
    
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
    response_result = agent.perform_action(
        connection=llm_provider,
        action="generate-text",
        params=[response_prompt, system_prompt]
    )
    
    response_text = response_result.get("result", "")
    
    # Trim if necessary
    if len(response_text) > 300:
        response_text = response_text[:297] + "..."
    
    return {
        "success": True,
        "response": response_text,
        "character_count": len(response_text)
    }

def post_to_farcaster(agent: BaseAgent, response_text: str, reply_to_cast_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Post a response to Farcaster, optionally as a reply to a specific cast.
    
    Args:
        agent: The PitchYourIdea agent instance
        response_text: The text to post
        reply_to_cast_id: Optional cast ID to reply to
        
    Returns:
        Dict containing the result of the post
    """
    logger.info(f"Posting to Farcaster{' as reply' if reply_to_cast_id else ''}")
    
    # Prepare action parameters
    params = [response_text]
    if reply_to_cast_id:
        action = "reply-to-cast"
        params.append(reply_to_cast_id)
    else:
        action = "post-cast"
    
    # Execute the action
    result = agent.perform_action(
        connection="farcaster",
        action=action,
        params=params
    )
    
    if result.get("success", False):
        return {
            "success": True,
            "cast_hash": result.get("cast_hash", "unknown")
        }
    else:
        return {
            "success": False,
            "error": result.get("error", "Unknown error")
        }

def process_pitch(agent: BaseAgent, pitch_text: str, cast_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Process a pitch from start to finish: evaluate, generate response, and post to Farcaster.
    
    Args:
        agent: The PitchYourIdea agent instance
        pitch_text: The text of the pitch to process
        cast_id: Optional cast ID to reply to
        
    Returns:
        Dict containing the results of the process
    """
    logger.info(f"Processing pitch: {pitch_text[:50]}...")
    
    # Step 1: Evaluate the pitch
    evaluation_result = evaluate_pitch(agent, pitch_text)
    if not evaluation_result.get("success", False):
        return {
            "success": False,
            "stage": "evaluation",
            "error": evaluation_result.get("error", "Unknown error")
        }
    
    evaluation = evaluation_result["evaluation"]
    
    # Step 2: Generate a response
    response_result = generate_response(agent, pitch_text, evaluation)
    if not response_result.get("success", False):
        return {
            "success": False,
            "stage": "response_generation",
            "error": response_result.get("error", "Unknown error")
        }
    
    response_text = response_result["response"]
    
    # Step 3: Post to Farcaster
    post_result = post_to_farcaster(agent, response_text, cast_id)
    if not post_result.get("success", False):
        return {
            "success": False,
            "stage": "posting",
            "error": post_result.get("error", "Unknown error"),
            "evaluation": evaluation,
            "response": response_text
        }
    
    return {
        "success": True,
        "evaluation": evaluation,
        "response": response_text,
        "cast_hash": post_result.get("cast_hash", "unknown")
    }

def is_valid_pitch(text: str) -> bool:
    """
    Determine if a cast is a valid investment pitch.
    
    Args:
        text: The text to check
        
    Returns:
        True if the text appears to be a pitch, False otherwise
    """
    # Convert to lowercase for case-insensitive matching
    text = text.lower()
    
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

def process_new_casts(agent: BaseAgent, processed_casts: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
    """
    Process new casts from Farcaster and respond to pitches.
    
    Args:
        agent: The PitchYourIdea agent instance
        processed_casts: Dictionary of previously processed casts
        
    Returns:
        Dict containing the results of the processing
    """
    logger.info("Processing new casts from Farcaster")
    
    if processed_casts is None:
        processed_casts = {}
    
    # Get casts from Farcaster
    monitor_result = monitor_farcaster(agent)
    if not monitor_result.get("success", False):
        return {
            "success": False,
            "error": "Failed to monitor Farcaster"
        }
    
    all_casts = monitor_result["casts"]
    logger.info(f"Found {len(all_casts)} casts to process")
    
    # Process each cast
    new_processed = {}
    processed_count = 0
    
    for cast in all_casts:
        cast_id = cast.get("hash")
        
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
            
            # Process the pitch
            result = process_pitch(agent, text, cast_id)
            if result.get("success", False):
                logger.info(f"Successfully processed pitch from @{author}")
            else:
                logger.error(f"Failed to process pitch from @{author}: {result.get('error', 'Unknown error')}")
        else:
            logger.info(f"Not a valid pitch from @{author}")
        
        # Mark as processed
        new_processed[cast_id] = {
            "processed_at": kwargs.get("timestamp", ""),
            "author": author,
            "is_pitch": is_valid_pitch(text)
        }
        
        processed_count += 1
    
    return {
        "success": True,
        "processed_count": processed_count,
        "new_processed": new_processed
    } 