import json
import logging
from typing import Dict, Any, List, Optional

from src.connections.base_connection import BaseConnection
from src.types.action import Action, ActionParameter

logger = logging.getLogger("connections.pitchyouridea")

class PitchYourIdeaConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.is_llm_provider = False
        self.name = "pitchyouridea"
        self.register_actions()
    
    def is_configured(self) -> bool:
        """Check if the connection is properly configured"""
        return True  # No external API needed for this connection
    
    def register_actions(self) -> None:
        """Register available PitchYourIdea actions"""
        self.actions = {
            "evaluate-pitch-direct": Action(
                name="evaluate-pitch-direct",
                parameters=[
                    ActionParameter("pitch_text", True, str, "The pitch text to evaluate")
                ],
                description="Directly evaluate a pitch without using Farcaster"
            )
        }
    
    def evaluate_pitch(self, pitch_text: str) -> Dict[str, Any]:
        """
        Evaluate an investment pitch
        
        Args:
            pitch_text: The pitch text to evaluate
            
        Returns:
            Dict containing evaluation results and response
        """
        logger.info("Evaluating pitch")
        
        # Get LLM connection from agent
        llm_connection = self._get_llm_connection()
        
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
        evaluation_result = llm_connection.generate_text(
            prompt=evaluation_prompt,
            system_prompt="You are an AI investment analyst that evaluates startup pitches. Always respond with valid JSON."
        )
        
        # Parse the evaluation result
        try:
            eval_data = json.loads(evaluation_result)
        except json.JSONDecodeError:
            logger.error("Failed to parse evaluation result as JSON")
            # Try to extract JSON from the response
            try:
                json_start = evaluation_result.find('{')
                json_end = evaluation_result.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = evaluation_result[json_start:json_end]
                    eval_data = json.loads(json_str)
                else:
                    raise ValueError("Could not extract JSON from response")
            except:
                logger.error("Could not extract JSON from response")
                eval_data = {
                    "analysis": {
                        "societal_value": "Unknown",
                        "practicality": "Unknown",
                        "profitability": "Unknown",
                        "equity_notes": "Error in evaluation"
                    },
                    "decision": "pass",
                    "valuation": 0,
                    "investment_amount": 0,
                    "equity_percentage": 0,
                    "terms": "N/A",
                    "explanation": "Error in evaluation process"
                }
        
        # Generate response based on evaluation
        response_prompt = f"""
You are PitchYourIdea, a professional fund manager responding to an investment pitch.

ORIGINAL PITCH:
{pitch_text}

YOUR EVALUATION:
{json.dumps(eval_data, indent=2)}

Create a concise, professional response (max 300 characters) that:
1. Acknowledges the pitch
2. Provides your investment decision
3. If investing, states the valuation, amount, and equity percentage
4. If passing, gives a brief reason why

The response should be conversational and direct, without hashtags or emojis.
"""
        
        # Get response from LLM
        response_text = llm_connection.generate_text(
            prompt=response_prompt,
            system_prompt="You are a professional fund manager responding to investment pitches."
        )
        
        # Trim if necessary
        if len(response_text) > 300:
            response_text = response_text[:297] + "..."
        
        return {
            "evaluation": eval_data,
            "response": response_text
        }
    
    def _get_llm_connection(self):
        """Get the LLM connection from the agent's connection manager"""
        # Try to get Anthropic first, then OpenAI, then any LLM provider
        for provider in ["anthropic", "openai", "groq", "together"]:
            if provider in self._agent.connection_manager.connections:
                return self._agent.connection_manager.connections[provider]
        
        # If no specific provider found, get any LLM provider
        for name, conn in self._agent.connection_manager.connections.items():
            if conn.is_llm_provider:
                return conn
        
        raise ValueError("No LLM provider found in connection manager")
    
    def perform_action(self, action_name: str, params: List[Any]) -> Any:
        """Perform the specified action with the given parameters"""
        if action_name == "evaluate-pitch-direct":
            if not params or len(params) < 1:
                raise ValueError("Missing pitch text parameter")
            return self.evaluate_pitch(params[0])
        else:
            raise ValueError(f"Unknown action: {action_name}") 