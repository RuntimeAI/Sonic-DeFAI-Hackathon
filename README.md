# Persuade Me! - AI Farcaster Debate Game based on Soinic

<div align="center">
  <img width="554" alt="2970" src="https://github.com/user-attachments/assets/4cd8fa58-bd14-42f5-8ddd-dedff7d93c05" />
  <br>
  <em>Sonic ZerePy Farcaster</em>
</div>

## 🌟 Overview

**Persuade Me** is an engaging AI-powered debate game built on Farcaster using Sonic blockchain for rewards. The game leverages ZerePy's AI architecture to create an interactive and educational experience around Web3 topics.

The concept is simple: the [@typox-ai](https://warpcast.com/typox-ai/) account posts Web3-related challenges, and players respond with their most persuasive arguments. If you successfully convince the AI, you'll be rewarded with $S tokens directly on Sonic.

This project combines education, social engagement, and blockchain rewards in a seamless experience that makes learning about Web3 concepts fun and rewarding.

## 🎮 How It Works

1. **Challenge**: The AI agent posts a "Persuade Me" challenge on Farcaster about a Web3-related topic
2. **Debate**: Users reply with their most persuasive arguments
3. **Evaluation**: The AI evaluates each response based on persuasiveness
4. **Reward**: Successful persuaders receive $S tokens as rewards

## 🛠️ Technical Features

### Enhanced Farcaster Integration
- Reimplemented Farcaster Connection using the more stable Neynar API
- Improved error handling and fallback mechanisms
- Enhanced user interaction through automated feedback

### Custom ZerePy Actions
- `post-persuade-challenge`: Posts a new challenge on Farcaster
- `check-challenge-replies`: Evaluates participant responses and scores them
- `reward-successful-persuasion`: Sends $S rewards to winners

### Sonic Blockchain Integration
- Fast and efficient reward distribution
- Leverages Sonic's speed advantages for seamless user experience
- Direct integration with Farcaster social layer

## 🚀 Future Development

1. **Server Deployment**: Transform the ZerePy persuade_me_agent into a persistent server
2. **Expanded Challenges**: Introduce more diverse challenge topics and formats
3. **Deep Sonic & Farcaster Integration**: Develop Sonic-based Farcaster frames for enhanced social gaming experiences

## 🔧 Installation & Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/persuade-me.git
cd persuade-me

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and configuration

# Run the agent
poetry run python3 main.py

#Load agent
load-agent persuade_me_agent
#Post a challenge
agent-action farcaster post-persuade-challenge
#Check the replies
agent-action farcaster check-challenge-replies
#Send reward
agent-action sonic reward-successful-persuasion


```

## 🔑 Environment Variables

Create a `.env` file with the following variables:

```
NEYNAR_API_KEY=your_neynar_api_key
FARCASTER_FID=your_farcaster_id
FARCASTER_MNEMONIC=your_farcaster_mnmonic
OPENAI_API_KEY=your_openai_api_key
SONIC_PRIVATE_KEY=your_sonic_private_key
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- [ZerePy](https://github.com/blorm-network/ZerePy) - The AI agent framework powering this project
- [Farcaster](https://www.farcaster.xyz/) - The decentralized social network platform
- [Sonic](https://www.soniclabs.com/) - The Fastest EVM Layer-1 Blockchain
- [Neynar](https://neynar.com/) - For their reliable Farcaster API

---

<div align="center">
  <p>Built with ❤️ for the Sonic Eco</p>
  <p>Created during an Sonic-DeFAI hackathon</p>
</div>
