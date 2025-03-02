import logging
from typing import Dict, Any, Optional
from src.server.client import ZerePyClient, ZerePyClientError

logger = logging.getLogger("clients.pitchyouridea_client")

class PitchYourIdeaClient:
    """Client for interacting with the PitchYourIdea agent via the ZerePy server"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        """Initialize the client with server URL"""
        self.client = ZerePyClient(server_url)
        self.agent_loaded = False
        
    def ensure_agent_loaded(self) -> bool:
        """Ensure the PitchYourIdea agent is loaded"""
        if not self.agent_loaded:
            try:
                status = self.client.get_status()
                if status.get('agent') != "PitchYourIdea":
                    logger.info("Loading PitchYourIdea agent")
                    self.client.load_agent("pitchyouridea")
                self.agent_loaded = True
                return True
            except ZerePyClientError as e:
                logger.error(f"Failed to load agent: {str(e)}")
                return False
        return True
    
    def evaluate_pitch(self, pitch_text: str) -> Dict[str, Any]:
        """Evaluate an investment pitch"""
        if not self.ensure_agent_loaded():
            raise ZerePyClientError("Failed to load PitchYourIdea agent")
        
        # Use Anthropic for evaluation if available
        try:
            connections = self.client.list_connections()
            provider = "anthropic" if "anthropic" in connections and connections["anthropic"]["configured"] else "openai"
            
            result = self.client.perform_action(
                connection=provider,
                action="generate-text",
                params={
                    "prompt": self._create_evaluation_prompt(pitch_text),
                    "system_prompt": "You are PitchYourIdea, a professional fund manager evaluating investment pitches."
                }
            )
            
            # Parse the evaluation result
            evaluation_text = result.get("result", "")
            import json
            try:
                return json.loads(evaluation_text)
            except json.JSONDecodeError:
                logger.error("Failed to parse evaluation result as JSON")
                # Extract JSON from text if possible
                import re
                json_match = re.search(r'({.*})', evaluation_text, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except:
                        pass
                
                # Return a basic structure if parsing fails
                return {
                    "analysis": {
                        "societal_value": "Unknown",
                        "practicality": "Unknown",
                        "profitability": "Unknown",
                        "equity_notes": "Error parsing evaluation"
                    },
                    "decision": "unknown",
                    "explanation": "Error processing evaluation"
                }
            
        except ZerePyClientError as e:
            logger.error(f"Error evaluating pitch: {str(e)}")
            raise
    
    def generate_response(self, pitch_text: str, evaluation: Dict[str, Any]) -> str:
        """Generate a response to the pitch based on evaluation"""
        if not self.ensure_agent_loaded():
            raise ZerePyClientError("Failed to load PitchYourIdea agent")
        
        try:
            connections = self.client.list_connections()
            provider = "openai" if "openai" in connections and connections["openai"]["configured"] else "anthropic"
            
            import json
            evaluation_str = json.dumps(evaluation, indent=2)
            
            result = self.client.perform_action(
                connection=provider,
                action="generate-text",
                params={
                    "prompt": self._create_response_prompt(pitch_text, evaluation_str),
                    "system_prompt": "You are PitchYourIdea, a professional fund manager responding to investment pitches."
                }
            )
            
            response_text = result.get("result", "")
            
            # Trim if necessary
            if len(response_text) > 300:
                response_text = response_text[:297] + "..."
                
            return response_text
            
        except ZerePyClientError as e:
            logger.error(f"Error generating response: {str(e)}")
            raise
    
    def _create_evaluation_prompt(self, pitch_text: str) -> str:
        """Create prompt for pitch evaluation"""
        return f"""
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
    
    def _create_response_prompt(self, pitch_text: str, evaluation_str: str) -> str:
        """Create prompt for generating response"""
        return f"""
Create a concise, professional response (max 300 characters) to this investment pitch:

ORIGINAL PITCH:
{pitch_text}

YOUR EVALUATION:
{evaluation_str}

Your response should:
1. Acknowledge the pitch
2. Provide your investment decision
3. If investing, state the valuation, amount, and equity percentage
4. If passing, give a brief reason why

The response should be conversational and direct, without hashtags or emojis.
""" 