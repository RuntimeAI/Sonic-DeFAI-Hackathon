import argparse
import sys
import json
import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def print_colorized(text: str, color_code: int) -> None:
    """Print text with ANSI color codes"""
    print(f"\033[{color_code}m{text}\033[0m")

def print_evaluation_summary(evaluation):
    """Print a colorized summary of the evaluation"""
    try:
        # Try to parse the evaluation if it's a string
        if isinstance(evaluation, str):
            evaluation = json.loads(evaluation)
        
        print("\n" + "=" * 60)
        print_colorized("PITCH EVALUATION SUMMARY", 1)
        print("=" * 60)
        
        # Analysis section
        print_colorized("\nANALYSIS:", 1)
        analysis = evaluation.get("analysis", {})
        
        # Colorize values based on High/Medium/Low
        for key, value in analysis.items():
            if key != "equity_notes":
                color = 32 if value == "High" else 33 if value == "Medium" else 31  # Green/Yellow/Red
                print(f"  {key.replace('_', ' ').title()}: ", end="")
                print_colorized(value, color)
            else:
                print(f"  {key.replace('_', ' ').title()}: {value}")
        
        # Decision section
        print_colorized("\nDECISION:", 1)
        decision = evaluation.get("decision", "unknown")
        decision_color = 32 if decision == "invest" else 31  # Green/Red
        print(f"  Decision: ", end="")
        print_colorized(decision.upper(), decision_color)
        
        if decision == "invest":
            print(f"  Valuation: ${evaluation.get('valuation', 0):,}")
            print(f"  Investment Amount: ${evaluation.get('investment_amount', 0):,}")
            print(f"  Equity Percentage: {evaluation.get('equity_percentage', 0)}%")
            print(f"  Terms: {evaluation.get('terms', 'N/A')}")
        
        print(f"  Explanation: {evaluation.get('explanation', 'No explanation provided')}")
        print("=" * 60 + "\n")
    except Exception as e:
        print_colorized(f"Error displaying evaluation: {str(e)}", 31)
        print(f"Raw evaluation: {evaluation}")

class SimpleClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print_colorized("Warning: No OpenAI API key provided. Using mock responses.", 33)
        
    def evaluate_pitch(self, pitch_text):
        """Evaluate a pitch using OpenAI API"""
        if not self.api_key:
            # Return mock evaluation if no API key
            return self._get_mock_evaluation(pitch_text)
            
        try:
            # Direct OpenAI API call
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are an AI investment analyst that evaluates startup pitches. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": f"""Evaluate this investment pitch:
                        
{pitch_text}

Analyze this pitch based on:
1. Societal Value: How beneficial is this to society? (Low/Medium/High)
2. Practicality: How feasible is implementation? (Low/Medium/High)
3. Profitability: What's the profit potential? (Low/Medium/High)
4. Equity Potential: What percentage of equity would be appropriate for investment?

Then make an investment decision:
- If you decide to invest: Specify valuation, investment amount, and equity percentage
- If you decline: Explain your reasoning briefly

FORMAT YOUR RESPONSE AS JSON:
{
  "analysis": {
    "societal_value": "High/Medium/Low",
    "practicality": "High/Medium/Low",
    "profitability": "High/Medium/Low",
    "equity_notes": "Brief notes on equity structure"
  },
  "decision": "invest/pass",
  "valuation": 0,
  "investment_amount": 0,
  "equity_percentage": 0,
  "terms": "Additional terms or conditions",
  "explanation": "Brief explanation of decision"
}"""
                    }
                ]
            }
            
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            
            # Extract the content from the response
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                
                # Try to extract JSON
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    return json.loads(json_str)
            
            raise ValueError("Could not extract valid JSON from response")
            
        except Exception as e:
            print_colorized(f"Error evaluating pitch: {str(e)}", 31)
            return self._get_mock_evaluation(pitch_text)
    
    def _get_mock_evaluation(self, pitch_text):
        """Generate a mock evaluation based on keywords in the pitch"""
        # Simple keyword-based scoring
        societal_value = "Medium"
        if any(word in pitch_text.lower() for word in ["society", "community", "people", "help", "social", "impact"]):
            societal_value = "High"
        
        practicality = "Medium"
        if any(word in pitch_text.lower() for word in ["blockchain", "technology", "ai", "decentralized"]):
            practicality = "Medium"  # Tech projects are moderately practical
        
        profitability = "Medium"
        if any(word in pitch_text.lower() for word in ["earn", "profit", "revenue", "monetize", "business"]):
            profitability = "High"
        
        # Simple decision logic
        if societal_value == "High" and (practicality != "Low" or profitability != "Low"):
            decision = "invest"
            valuation = 500000  # Default valuation
            investment_amount = 50000
            equity_percentage = 10
            
            # Adjust based on requested amount if present
            if "raise" in pitch_text.lower() and "k" in pitch_text.lower():
                try:
                    # Try to extract the amount
                    text_parts = pitch_text.lower().split("raise")
                    amount_text = text_parts[1].split("k")[0].strip()
                    amount_text = ''.join(c for c in amount_text if c.isdigit())
                    if amount_text:
                        requested_amount = int(amount_text) * 1000
                        investment_amount = min(requested_amount, 100000)  # Cap at 100K
                        valuation = investment_amount * 10  # Simple 10x valuation
                        equity_percentage = round((investment_amount / valuation) * 100)
                except:
                    pass
        else:
            decision = "pass"
            valuation = 0
            investment_amount = 0
            equity_percentage = 0
        
        # Create evaluation result
        return {
            "analysis": {
                "societal_value": societal_value,
                "practicality": practicality,
                "profitability": profitability,
                "equity_notes": "Standard equity terms with vesting schedule"
            },
            "decision": decision,
            "valuation": valuation,
            "investment_amount": investment_amount,
            "equity_percentage": equity_percentage,
            "terms": "Standard terms with 4-year vesting, 1-year cliff",
            "explanation": f"Decision based on {societal_value} societal value, {practicality} practicality, and {profitability} profitability."
        }

    def generate_response(self, pitch_text, evaluation):
        """Generate a response based on the evaluation"""
        if not self.api_key:
            # Return mock response if no API key
            return self._get_mock_response(evaluation)
            
        try:
            # Direct OpenAI API call
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a professional fund manager responding to investment pitches."
                    },
                    {
                        "role": "user",
                        "content": f"""
Original pitch:
{pitch_text}

Your evaluation:
{json.dumps(evaluation, indent=2)}

Create a concise, professional response (max 300 characters) that:
1. Acknowledges the pitch
2. Provides your investment decision
3. If investing, states the valuation, amount, and equity percentage
4. If passing, gives a brief reason why

The response should be conversational and direct, without hashtags or emojis.
"""
                    }
                ]
            }
            
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            
            # Extract the content from the response
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                
                # Trim if necessary
                if len(content) > 300:
                    content = content[:297] + "..."
                    
                return content
            
            raise ValueError("Could not extract response from API result")
            
        except Exception as e:
            print_colorized(f"Error generating response: {str(e)}", 31)
            return self._get_mock_response(evaluation)
    
    def _get_mock_response(self, evaluation):
        """Generate a mock response based on the evaluation"""
        if evaluation.get("decision") == "invest":
            return f"Thanks for your pitch! I'm interested in investing ${evaluation.get('investment_amount', 0):,} for {evaluation.get('equity_percentage', 0)}% equity at a ${evaluation.get('valuation', 0):,} valuation. Let's discuss terms."
        else:
            return "Thank you for sharing your pitch. While I appreciate the concept, I'll have to pass on investing at this time. The practicality and profitability don't meet our current investment criteria."

def main():
    parser = argparse.ArgumentParser(description="PitchYourIdea Client")
    parser.add_argument("--pitch", type=str, help="Investment pitch to evaluate")
    parser.add_argument("--file", type=str, help="File containing the pitch text")
    parser.add_argument("--api-key", type=str, help="OpenAI API key (can also be set via OPENAI_API_KEY environment variable)")
    
    args = parser.parse_args()
    
    # Get pitch text from arguments or prompt user
    pitch_text = ""
    if args.pitch:
        pitch_text = args.pitch
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                pitch_text = f.read()
        except Exception as e:
            print_colorized(f"Error reading file: {str(e)}", 31)
            sys.exit(1)
    else:
        # Default pitch
        pitch_text = "My pitch is to create a social dapp empowered by blockchain technology and AI, which allows users to work for a decentralized DAO remotely, and earn working credits. This decentralized DAO will allow people in minor area to contribute to some valuable work without any herdle of physical geological distance. And I'd like to raise 10K USD for the angle investment."
        print_colorized(f"Using default pitch: {pitch_text}", 36)
    
    if not pitch_text:
        print_colorized("No pitch provided", 31)
        sys.exit(1)
    
    # Initialize client with API key from args or environment
    client = SimpleClient(args.api_key)
    
    # Process the pitch
    print_colorized("\n🚀 PROCESSING PITCH...", 36)
    evaluation = client.evaluate_pitch(pitch_text)
    print_evaluation_summary(evaluation)
    
    # Generate response
    print_colorized("\n💬 GENERATING RESPONSE...", 36)
    response = client.generate_response(pitch_text, evaluation)
    
    print_colorized("\n💬 FARCASTER RESPONSE:", 36)
    print(f"@pitchyouridea: {response}")

if __name__ == "__main__":
    main() 