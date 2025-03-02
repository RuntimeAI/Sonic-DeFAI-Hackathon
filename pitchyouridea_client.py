from src.server.client import ZerePyClient
import argparse
import sys

def print_colorized(text: str, color_code: int) -> None:
    """Print text with ANSI color codes"""
    print(f"\033[{color_code}m{text}\033[0m")

def main():
    parser = argparse.ArgumentParser(description="PitchYourIdea Client")
    parser.add_argument("--pitch", type=str, help="Pitch text to evaluate")
    parser.add_argument("--file", type=str, help="File containing the pitch text")
    parser.add_argument("--url", type=str, default="http://localhost:8000", 
                        help="Server URL (default: http://localhost:8000)")
    
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
        print_colorized("Enter your pitch (type 'END' on a new line when finished):", 36)
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        pitch_text = "\n".join(lines)
    
    if not pitch_text:
        print_colorized("No pitch provided", 31)
        sys.exit(1)
    
    # Initialize client
    client = ZerePyClient(args.url)
    
    # Load the agent
    print_colorized("\n🔄 LOADING AGENT...", 36)
    client.load_agent("pitchyouridea")
    print_colorized("✅ Agent loaded successfully", 32)
    
    # Process the pitch
    print_colorized("\n🚀 PROCESSING PITCH...", 36)
    result = client.perform_action(
        connection="check-farcaster-mentions",
        action="evaluate-pitch",
        params=[pitch_text]
    )
    
    print_colorized("\n📊 EVALUATION RESULTS:", 36)
    print(result)
    
    # Generate response
    response = client.perform_action(
        connection="respond-to-pitch",
        action="generate-response",
        params=[pitch_text, result]
    )
    
    print_colorized("\n💬 FARCASTER RESPONSE:", 36)
    print(f"@pitchyouridea: {response}")

if __name__ == "__main__":
    main() 