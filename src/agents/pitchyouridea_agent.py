import logging
from typing import Dict, Any, List
from src.agent.base_agent import BaseAgent
from src.actions.pitchyouridea_actions import (
    monitor_farcaster,
    evaluate_pitch,
    generate_response,
    post_to_farcaster,
    process_pitch,
    process_new_casts
)

logger = logging.getLogger("pitchyouridea_agent")

class PitchYourIdeaAgent(BaseAgent):
    """Agent for evaluating investment pitches and responding on Farcaster"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "PitchYourIdea"
        self.description = "An agent that evaluates investment pitches and responds on Farcaster"
        
    def register_actions(self):
        """Register the agent's actions"""
        self.actions = {
            "monitor_farcaster": monitor_farcaster,
            "evaluate_pitch": evaluate_pitch,
            "generate_response": generate_response,
            "post_to_farcaster": post_to_farcaster,
            "process_pitch": process_pitch,
            "process_new_casts": process_new_casts
        }
        
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the agent configuration"""
        # No specific configuration needed for this agent
        return config 