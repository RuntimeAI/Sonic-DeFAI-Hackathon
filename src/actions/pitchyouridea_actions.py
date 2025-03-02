import logging
import time
from src.action_handler import register_action
from src.helpers import print_h_bar

logger = logging.getLogger("actions.pitchyouridea_actions")

@register_action("check-farcaster-mentions")
def check_farcaster_mentions(agent, **kwargs):
    """Check for mentions of the agent on Farcaster and process them"""
    agent.logger.info("\n👀 CHECKING FARCASTER MENTIONS")
    print_h_bar()
    
    # Get the agent's Farcaster ID
    try:
        me_info = agent.connection_manager.perform_action(
            connection_name="farcaster",
            action_name="get-me"
        )
        
        if not me_info or 'fid' not in me_info:
            agent.logger.error("Could not retrieve Farcaster ID")
            return False
            
        my_fid = me_info['fid']
        agent.logger.info(f"Found Farcaster ID: {my_fid}")
        
        # Store mentions in agent state if not already there
        if "processed_mentions" not in agent.state:
            agent.state["processed_mentions"] = set()
            
        # Get mentions from timeline
        timeline = agent.connection_manager.perform_action(
            connection_name="farcaster",
            action_name="read-timeline",
            params=[]
        )
        
        if not timeline:
            agent.logger.info("No timeline data available")
            return False
            
        # Filter for mentions
        mentions = []
        for cast in timeline:
            # Check if this is a mention of our agent
            if cast.get('text', '').lower().find('@pitchyouridea') >= 0:
                # Check if we've already processed this mention
                if cast.get('hash') not in agent.state["processed_mentions"]:
                    mentions.append(cast)
        
        agent.logger.info(f"Found {len(mentions)} new mentions")
        
        # Store mentions for processing
        agent.state["pending_mentions"] = mentions
        return len(mentions) > 0
        
    except Exception as e:
        agent.logger.error(f"Error checking mentions: {str(e)}")
        return False

@register_action("evaluate-pitch")
def evaluate_pitch(agent, **kwargs):
    """Evaluate investment pitches from mentions"""
    if "pending_mentions" not in agent.state or not agent.state["pending_mentions"]:
        agent.logger.info("No pending mentions to evaluate")
        return False
        
    agent.logger.info("\n🔍 EVALUATING INVESTMENT PITCH")
    print_h_bar()
    
    # Get the next mention to evaluate
    mention = agent.state["pending_mentions"].pop(0)
    
    # Store the current mention being evaluated
    agent.state["current_evaluation"] = mention
    
    # Extract pitch details
    pitch_text = mention.get('text', '')
    author_fid = mention.get('author', {}).get('fid')
    cast_hash = mention.get('hash')
    
    agent.logger.info(f"Evaluating pitch from FID {author_fid}: {pitch_text[:100]}...")
    
    # Create evaluation prompt
    evaluation_prompt = f"""
You are PitchYourIdea, a professional fund manager with 10M tokens to invest.

PITCH TO EVALUATE:
{pitch_text}

Analyze this pitch based on the following criteria:
1. Societal Value: How beneficial is this to society? (Low/Medium/High)
2. Practicality: How feasible is implementation? (Low/Medium/High)
3. Profitability: What's the profit potential? (Low/Medium/High)
4. Equity Potential: What percentage of equity would be appropriate for investment?

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

    # Get evaluation from LLM
    try:
        evaluation_result = agent.prompt_llm(evaluation_prompt)
        agent.logger.info("Evaluation completed")
        
        # Store evaluation result
        agent.state["current_evaluation_result"] = evaluation_result
        return True
        
    except Exception as e:
        agent.logger.error(f"Error evaluating pitch: {str(e)}")
        return False

@register_action("respond-to-pitch")
def respond_to_pitch(agent, **kwargs):
    """Respond to the pitch with investment decision"""
    if "current_evaluation" not in agent.state or "current_evaluation_result" not in agent.state:
        agent.logger.info("No evaluation to respond to")
        return False
        
    agent.logger.info("\n💬 RESPONDING TO PITCH")
    print_h_bar()
    
    mention = agent.state["current_evaluation"]
    evaluation_result = agent.state["current_evaluation_result"]
    
    # Extract necessary information for reply
    parent_fid = mention.get('author', {}).get('fid')
    parent_hash = mention.get('hash')
    
    if not parent_fid or not parent_hash:
        agent.logger.error("Missing parent information for reply")
        return False
    
    # Create response prompt
    response_prompt = f"""
You are PitchYourIdea, a professional fund manager responding to an investment pitch on Farcaster.

ORIGINAL PITCH:
{mention.get('text', '')}

YOUR EVALUATION:
{evaluation_result}

Create a concise, professional response (max 300 characters) that:
1. Acknowledges the pitch
2. Provides your investment decision
3. If investing, states the valuation, amount, and equity percentage
4. If passing, gives a brief reason why

The response should be conversational and direct, without hashtags or emojis.
"""

    try:
        # Generate response text
        response_text = agent.prompt_llm(response_prompt)
        
        # Trim if necessary
        if len(response_text) > 300:
            response_text = response_text[:297] + "..."
            
        agent.logger.info(f"Responding with: {response_text}")
        
        # Post the response as a reply
        result = agent.connection_manager.perform_action(
            connection_name="farcaster",
            action_name="reply-to-cast",
            params={
                "parent_fid": parent_fid,
                "parent_hash": parent_hash,
                "text": response_text
            }
        )
        
        # Mark this mention as processed
        if "processed_mentions" not in agent.state:
            agent.state["processed_mentions"] = set()
        agent.state["processed_mentions"].add(parent_hash)
        
        # Clean up state
        agent.state.pop("current_evaluation", None)
        agent.state.pop("current_evaluation_result", None)
        
        agent.logger.info("Response posted successfully")
        return True
        
    except Exception as e:
        agent.logger.error(f"Error responding to pitch: {str(e)}")
        return False 