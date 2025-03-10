import logging
import json
import random
import os
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from src.action_handler import register_action

logger = logging.getLogger("actions.persuade_actions")

@register_action("post-persuade-challenge")
def post_persuade_challenge(agent, **kwargs):
    """Post a new 'Persuade Me' challenge on Farcaster.
    
    This function selects a random topic from the persuasion_challenge_settings
    and creates a cast challenging users to persuade the agent on that topic.
    
    Returns:
        str: The result of the post operation or error message
    """
    try:
        # Get challenge settings from agent configuration
        if not hasattr(agent, 'config') or 'persuasion_challenge_settings' not in agent.config:
            logger.error("Agent missing persuasion_challenge_settings configuration")
            return "Error: Missing persuasion challenge settings"
        
        settings = agent.config['persuasion_challenge_settings']
        topics = settings.get('topics', [])
        reward_amount = settings.get('reward_amount', "2")
        
        if not topics:
            logger.error("No topics found in persuasion_challenge_settings")
            return "Error: No topics configured for challenges"
        
        # Select a random topic
        selected_topic = random.choice(topics)
        
        # Create the challenge message
        challenge_text = f"🎯 PERSUADE ME CHALLENGE: Convince me that {selected_topic}. Reply with your most persuasive argument for a chance to win {reward_amount} $S! #PersuadeMe"
        
        # Store the current challenge in agent state for later reference
        if not hasattr(agent, 'state'):
            agent.state = {}
        
        agent.state['current_challenge'] = {
            'topic': selected_topic,
            'timestamp': datetime.now().isoformat(),
            'reward_amount': reward_amount,
            'responses': []
        }
        
        # Post to Farcaster
        result = agent.connection_manager.perform_action(
            connection_name="farcaster",
            action_name="post-cast",
            params=[challenge_text]
        )
        
        logger.info(f"Post result type: {type(result)}")
        logger.info(f"Post result: {result}")
        
        # Store the cast hash for tracking replies
        if result and isinstance(result, dict) and 'hash' in result:
            agent.state['current_challenge']['cast_hash'] = result['hash']
            logger.info(f"Challenge posted with hash from dict: {result['hash']}")
        elif result and isinstance(result, str):
            # Try to parse the result as JSON if it's a string
            try:
                import json
                result_json = json.loads(result)
                if isinstance(result_json, dict) and 'hash' in result_json:
                    agent.state['current_challenge']['cast_hash'] = result_json['hash']
                    logger.info(f"Challenge posted with hash from JSON: {result_json['hash']}")
            except:
                # If we can't parse as JSON, check if it looks like a hash
                if result.startswith('0x') and len(result) > 10:
                    agent.state['current_challenge']['cast_hash'] = result
                    logger.info(f"Challenge posted with hash from string: {result}")
                # Try to extract hash from ApiCast string representation
                elif 'hash=' in result:
                    import re
                    hash_match = re.search(r"hash='([^']+)'", str(result))
                    if hash_match:
                        hash_value = hash_match.group(1)
                        agent.state['current_challenge']['cast_hash'] = hash_value
                        logger.info(f"Challenge posted with hash extracted from ApiCast string: {hash_value}")
        # Handle ApiCast object directly
        elif hasattr(result, 'hash'):
            agent.state['current_challenge']['cast_hash'] = result.hash
            logger.info(f"Challenge posted with hash from ApiCast object: {result.hash}")
        # Try to extract hash from string representation of any object
        elif result is not None:
            try:
                result_str = str(result)
                if 'hash=' in result_str:
                    import re
                    hash_match = re.search(r"hash=['\"]?([^'\"]+)['\"]?", result_str)
                    if hash_match:
                        hash_value = hash_match.group(1)
                        agent.state['current_challenge']['cast_hash'] = hash_value
                        logger.info(f"Challenge posted with hash extracted from object string: {hash_value}")
                elif 'hash' in result_str and '0x' in result_str:
                    import re
                    hash_match = re.search(r"0x[a-fA-F0-9]{40}", result_str)
                    if hash_match:
                        hash_value = hash_match.group(0)
                        agent.state['current_challenge']['cast_hash'] = hash_value
                        logger.info(f"Challenge posted with hash extracted from hex pattern: {hash_value}")
            except:
                logger.warning("Failed to extract hash from result string representation")
        
        # For debugging, print the current state
        logger.info(f"Current challenge state: {agent.state.get('current_challenge')}")
        
        # Save challenge to file for persistence
        _save_challenge_to_file(agent)
        
        return result
    
    except Exception as e:
        logger.error(f"Failed to post persuade challenge: {str(e)}")
        return f"Error: {str(e)}"

@register_action("evaluate-persuasion-reply")
def evaluate_persuasion_reply(agent, **kwargs):
    """Evaluate a user's reply to a persuasion challenge.
    
    This function uses the LLM to determine if the user's argument is persuasive enough.
    
    Args:
        reply_text (str): The text of the user's reply
        username (str): The username of the replier
        user_address (str): The wallet address of the replier (for rewards)
        reply_hash (str): The hash of the reply cast
        
    Returns:
        dict: Evaluation results including score and whether it passed the threshold
    """
    try:
        reply_text = kwargs.get('reply_text')
        username = kwargs.get('username')
        user_address = kwargs.get('user_address')
        reply_hash = kwargs.get('reply_hash')
        
        logger.info(f"Evaluating reply from {username} with hash {reply_hash}")
        logger.info(f"Reply text: {reply_text}")
        
        if not all([reply_text, username, reply_hash]):
            logger.error("Missing required parameters for evaluation")
            return "Error: Missing required parameters"
        
        # Get challenge settings
        if not hasattr(agent, 'config') or 'persuasion_challenge_settings' not in agent.config:
            logger.error("Agent missing persuasion_challenge_settings configuration")
            return "Error: Missing persuasion challenge settings"
        
        settings = agent.config['persuasion_challenge_settings']
        threshold = settings.get('persuasion_threshold', 7)  # Default threshold of 7/10
        
        # Get current challenge
        if not hasattr(agent, 'state') or 'current_challenge' not in agent.state:
            logger.error("No active challenge found")
            return "Error: No active challenge found"
        
        challenge = agent.state['current_challenge']
        topic = challenge.get('topic')
        
        logger.info(f"Evaluating reply for challenge topic: {topic}")
        
        # Prepare prompt for LLM evaluation
        system_prompt = f"""You are evaluating the persuasiveness of an argument on the topic: "{topic}".
        Score the argument from 1 to 10, where 1 is the weakest and 10 is the strongest.
        Consider these factors:
        - Logic and reasoning
        - Evidence and examples
        - Creativity and originality
        - Emotional appeal
        - Addressing counterarguments
        
        Provide your evaluation in JSON format with these fields:
        - score: (number between 1-10)
        - reasoning: (brief explanation of your score)
        - passed: (boolean, true if score >= {threshold})
        """
        
        user_prompt = f"Evaluate this argument from user {username}:\n\n{reply_text}"
        
        # Get LLM provider from agent configuration
        llm_provider = None
        for config in agent.config.get('config', []):
            if config.get('name') in ['openai', 'anthropic', 'together']:
                llm_provider = config.get('name')
                break
        
        if not llm_provider:
            logger.error("No LLM provider configured")
            return "Error: No LLM provider configured"
        
        logger.info(f"Using LLM provider: {llm_provider}")
        
        # Call LLM for evaluation
        try:
            llm_response = agent.connection_manager.perform_action(
                connection_name=llm_provider,
                action_name="generate-text",
                params=[user_prompt, system_prompt]
            )
            
            logger.info(f"LLM response: {llm_response}")
            
            # Parse LLM response to extract JSON
            try:
                # Find JSON in the response
                import re
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    evaluation = json.loads(json_match.group(0))
                    logger.info(f"Extracted evaluation JSON: {evaluation}")
                else:
                    # If no JSON found, try to parse the whole response
                    evaluation = json.loads(llm_response)
                    logger.info(f"Parsed whole response as JSON: {evaluation}")
            except json.JSONDecodeError as e:
                # If JSON parsing fails, create a basic evaluation
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                logger.warning(f"LLM response: {llm_response}")
                evaluation = {
                    "score": 5,  # Default medium score
                    "reasoning": "Failed to parse evaluation, assigning default score",
                    "passed": False
                }
            
            # Ensure evaluation result contains all necessary fields
            if 'score' not in evaluation:
                evaluation['score'] = 5
                logger.warning("Evaluation missing 'score' field, using default value 5")
            
            if 'reasoning' not in evaluation:
                evaluation['reasoning'] = "No reasoning provided"
                logger.warning("Evaluation missing 'reasoning' field, using default value")
            
            if 'passed' not in evaluation:
                evaluation['passed'] = evaluation.get('score', 0) >= threshold
                logger.warning(f"Evaluation missing 'passed' field, calculated based on score: {evaluation['passed']}")
            
            # Add evaluation to challenge responses
            response_data = {
                "username": username,
                "user_address": user_address,
                "reply_hash": reply_hash,
                "reply_text": reply_text,
                "evaluation": evaluation,
                "timestamp": datetime.now().isoformat()
            }
            
            if 'responses' not in agent.state['current_challenge']:
                agent.state['current_challenge']['responses'] = []
            
            agent.state['current_challenge']['responses'].append(response_data)
            _save_challenge_to_file(agent)
            
            # If passed threshold and auto-stop is enabled, mark challenge as completed
            if evaluation.get('passed', False) and settings.get('auto_stop_on_winner', True):
                agent.state['current_challenge']['completed'] = True
                agent.state['current_challenge']['winner'] = username
                _save_challenge_to_file(agent)
                logger.info(f"Challenge completed! Winner: {username}")
            
            return evaluation
        except Exception as e:
            logger.error(f"Error calling LLM for evaluation: {e}")
            return f"Error calling LLM: {str(e)}"
        
    except Exception as e:
        logger.error(f"Failed to evaluate persuasion reply: {str(e)}")
        return f"Error: {str(e)}"

@register_action("reward-successful-persuasion")
def reward_successful_persuasion(agent, **kwargs):
    """Send Sonic tokens to a user who successfully persuaded the agent.
    
    Args:
        username (str, optional): The username to reward. If not provided, 
                                 will use the winner from the current challenge.
        
    Returns:
        str: Transaction result or error message
    """
    try:
        username = kwargs.get('username')
        
        # Get challenge settings
        if not hasattr(agent, 'config') or 'persuasion_challenge_settings' not in agent.config:
            logger.error("Agent missing persuasion_challenge_settings configuration")
            return "Error: Missing persuasion challenge settings"
        
        settings = agent.config['persuasion_challenge_settings']
        reward_amount = float(settings.get('reward_amount', 2))
        
        # Get current challenge
        if not hasattr(agent, 'state') or 'current_challenge' not in agent.state:
            logger.error("No active challenge found")
            return "Error: No active challenge found"
        
        challenge = agent.state['current_challenge']
        
        # Find the winner to reward
        winner_data = None
        
        if username:
            # Find specific user in responses
            for response in challenge.get('responses', []):
                if response.get('username') == username and response.get('evaluation', {}).get('passed', False):
                    winner_data = response
                    break
        else:
            # Use the first passing response
            for response in challenge.get('responses', []):
                if response.get('evaluation', {}).get('passed', False):
                    winner_data = response
                    break
        
        if not winner_data:
            logger.error("No winning response found")
            return "Error: No winning response found"
        
        # 获取获奖者的用户名，确保我们使用的是获奖者的FID
        winner_username = winner_data.get('username')
        display_name = winner_data.get('display_name')  # 获取显示名称
        reply_hash = winner_data.get('reply_hash')  # 获取回复的哈希值
        logger.info(f"Found winner: {winner_username}, display_name: {display_name}, reply_hash: {reply_hash}")
        
        # 重新获取获奖者的钱包地址，确保使用的是获奖者的FID
        user_address = _get_user_wallet_address(agent, winner_username)
        
        if not user_address:
            logger.error(f"No wallet address found for user {winner_username}")
            return f"Error: No wallet address for {winner_username}"
        
        logger.info(f"Sending reward to address: {user_address}")
        
        # Send reward using Sonic connection
        result = agent.connection_manager.perform_action(
            connection_name="sonic",
            action_name="transfer",
            params=[user_address, str(reward_amount)]
        )
        
        # Record the reward in the challenge data
        winner_data['rewarded'] = True
        winner_data['reward_amount'] = reward_amount
        winner_data['reward_tx'] = result
        winner_data['reward_timestamp'] = datetime.now().isoformat()
        
        # Update winner file
        _update_winner_file(agent, winner_data)
        
        # Save updated challenge data
        _save_challenge_to_file(agent)
        
        # Send reward transaction record as a reply to the winner
        try:
            # Use display_name if available, otherwise use username
            mention_name = display_name if display_name else winner_username
            
            # Build reward transaction message in English
            reward_message = f"🎉 Congratulations @{mention_name}!\n\nYou have successfully persuaded me and won {reward_amount} $S reward!\n\n⛓️ Transfer transaction sent: {result}"
            
            # Reply to the winner's cast
            if reply_hash:
                logger.info(f"Sending reward transaction notification to winner's cast: {reply_hash}")
                feedback_result = agent.connection_manager.perform_action(
                    connection_name="farcaster",
                    action_name="reply-to-cast",
                    params=[reply_hash, reward_message]
                )
                logger.info(f"Successfully sent reward transaction notification: {feedback_result}")
            else:
                logger.warning(f"Cannot send reward transaction notification: no reply_hash found for winner {winner_username}")
                
                # Try to reply to the original challenge
                challenge_hash = challenge.get('cast_hash')
                if challenge_hash:
                    logger.info(f"Attempting to send reward transaction notification to original challenge: {challenge_hash}")
                    feedback_result = agent.connection_manager.perform_action(
                        connection_name="farcaster",
                        action_name="reply-to-cast",
                        params=[challenge_hash, reward_message]
                    )
                    logger.info(f"Successfully sent reward transaction notification to original challenge: {feedback_result}")
        except Exception as e:
            logger.error(f"Failed to send reward transaction notification: {e}")
        
        return result
    
    except Exception as e:
        logger.error(f"Failed to reward successful persuasion: {str(e)}")
        return f"Error: {str(e)}"

@register_action("check-challenge-replies")
def check_challenge_replies(agent, **kwargs):
    """Check for new replies to the current persuasion challenge.
    
    This action fetches replies to the current challenge cast and evaluates them.
    
    Returns:
        str: Summary of replies checked and evaluations
    """
    try:
        # Get current challenge
        if not hasattr(agent, 'state') or 'current_challenge' not in agent.state:
            logger.error("No active challenge found")
            return "No active challenge found"
        
        challenge = agent.state['current_challenge']
        
        # For debugging, print the current state
        logger.info(f"Current challenge state: {challenge}")
        
        # If challenge is marked as completed, don't check for more replies
        if challenge.get('completed', False):
            return f"Challenge already completed. Winner: {challenge.get('winner')}"
        
        cast_hash = challenge.get('cast_hash')
        if not cast_hash:
            logger.error("No cast hash found for current challenge")
            
            # Try to load from file as a fallback
            try:
                import os
                import json
                from pathlib import Path
                
                # Find the most recent challenge file
                challenges_dir = Path('challenges')
                if challenges_dir.exists():
                    challenge_files = list(challenges_dir.glob('challenge_*.json'))
                    if challenge_files:
                        # Sort by modification time, newest first
                        challenge_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                        with open(challenge_files[0], 'r') as f:
                            loaded_challenge = json.load(f)
                            if 'cast_hash' in loaded_challenge:
                                cast_hash = loaded_challenge['cast_hash']
                                # Update the agent state
                                agent.state['current_challenge'] = loaded_challenge
                                logger.info(f"Loaded challenge with hash: {cast_hash}")
            except Exception as e:
                logger.error(f"Failed to load challenge from file: {e}")
            
            if not cast_hash:
                return "Error: No cast hash for current challenge"
        
        # Try to get replies using the Neynar API first
        try:
            # Get replies using the Neynar API
            replies = agent.connection_manager.perform_action(
                connection_name="farcaster",
                action_name="get-cast-replies",
                params=[cast_hash]
            )
            
            logger.info(f"Replies type: {type(replies)}")
            logger.info(f"Replies: {replies}")
            
            # Check if we got any replies
            if replies:
                # Handle Neynar API response format (list of messages)
                if isinstance(replies, list):
                    replies_count = len(replies)
                    
                    if replies_count > 0:
                        # Process the replies
                        processed_count = 0
                        for reply in replies:
                            # Extract reply data
                            try:
                                # Check if we've already processed this reply
                                reply_hash = None
                                if isinstance(reply, dict) and 'hash' in reply:
                                    reply_hash = reply['hash']
                                elif hasattr(reply, 'hash'):
                                    reply_hash = reply.hash
                                
                                if not reply_hash:
                                    logger.warning(f"Could not extract hash from reply: {reply}")
                                    continue
                                
                                # Check if we've already processed this reply
                                already_processed = False
                                for response in challenge.get('responses', []):
                                    if response.get('reply_hash') == reply_hash:
                                        already_processed = True
                                        break
                                
                                if already_processed:
                                    logger.info(f"Reply {reply_hash} already processed, skipping")
                                    continue
                                
                                # Extract reply text and author info
                                reply_text = None
                                username = None
                                display_name = None  # Add a new variable to store display name
                                
                                if isinstance(reply, dict):
                                    if 'text' in reply:
                                        reply_text = reply['text']
                                    elif 'content' in reply and 'text' in reply['content']:
                                        reply_text = reply['content']['text']
                                    
                                    if 'author' in reply:
                                        if isinstance(reply['author'], dict):
                                            # Store display name
                                            if 'displayName' in reply['author']:
                                                display_name = reply['author']['displayName']
                                            
                                            # Store username (for internal identification)
                                            if 'username' in reply['author']:
                                                username = reply['author']['username']
                                            elif 'displayName' in reply['author']:
                                                username = reply['author']['displayName']
                                            elif 'fname' in reply['author']:
                                                username = reply['author']['fname']
                                            # If no username, use FID as username
                                            elif 'fid' in reply['author']:
                                                username = f"user_{reply['author']['fid']}"
                                elif hasattr(reply, 'text'):
                                    reply_text = reply.text
                                elif hasattr(reply, 'content') and hasattr(reply.content, 'text'):
                                    reply_text = reply.content.text
                                
                                if hasattr(reply, 'author'):
                                    # Store display name
                                    if hasattr(reply.author, 'displayName'):
                                        display_name = reply.author.displayName
                                    
                                    # Store username (for internal identification)
                                    if hasattr(reply.author, 'username'):
                                        username = reply.author.username
                                    elif hasattr(reply.author, 'displayName'):
                                        username = reply.author.displayName
                                    elif hasattr(reply.author, 'fname'):
                                        username = reply.author.fname
                                    # If no username, use FID as username
                                    elif hasattr(reply.author, 'fid'):
                                        username = f"user_{reply.author.fid}"
                                
                                # If still no username but has FID, use FID as username
                                if not username and isinstance(reply, dict) and 'author' in reply and isinstance(reply['author'], dict) and 'fid' in reply['author']:
                                    username = f"user_{reply['author']['fid']}"
                                
                                # Ensure we have reply text
                                if not reply_text and isinstance(reply, dict) and 'text' in reply:
                                    reply_text = reply['text']
                                
                                if not reply_text or not username:
                                    logger.warning(f"Could not extract text or username from reply: {reply}")
                                    continue
                                
                                # Get user wallet address
                                user_address = _get_user_wallet_address(agent, username)
                                
                                # Evaluate the reply
                                evaluation_result = evaluate_persuasion_reply(
                                    agent,
                                    reply_text=reply_text,
                                    username=username,
                                    user_address=user_address,
                                    reply_hash=reply_hash
                                )
                                
                                processed_count += 1
                                logger.info(f"Processed reply from {username}: {evaluation_result}")
                                
                                # Add reply to challenge responses
                                if 'responses' not in challenge:
                                    challenge['responses'] = []
                                
                                response_data = {
                                    'username': username,
                                    'display_name': display_name,  # Add display_name field
                                    'user_address': user_address,
                                    'reply_hash': reply_hash,
                                    'reply_text': reply_text,
                                    'evaluation': evaluation_result,
                                    'timestamp': datetime.now().isoformat()
                                }
                                
                                challenge['responses'].append(response_data)
                                
                                # If reply passed the challenge, mark challenge as completed
                                if isinstance(evaluation_result, dict) and evaluation_result.get('passed', False):
                                    challenge['completed'] = True
                                    challenge['winner'] = display_name if display_name else username  # Use display_name as winner
                                    logger.info(f"Challenge completed! Winner: {challenge['winner']}")
                                
                                # Save challenge responses
                                _save_challenge_to_file(agent)
                                
                                # Send evaluation result feedback
                                try:
                                    # Build feedback message
                                    if isinstance(evaluation_result, dict):
                                        score = evaluation_result.get('score', 0)
                                        reasoning = evaluation_result.get('reasoning', 'No evaluation reason')
                                        passed = evaluation_result.get('passed', False)
                                        
                                        # Use display_name if available, otherwise use username
                                        mention_name = display_name if display_name else username
                                        
                                        if passed:
                                            feedback = f"🎉 Congratulations @{mention_name}! Your argument was very persuasive, score: {score}/10.\n\nEvaluation: {reasoning}\n\nYou have successfully persuaded me and won the challenge! 🏆"
                                        else:
                                            feedback = f"Thank you @{mention_name} for participating in the challenge! Your argument scored: {score}/10.\n\nEvaluation: {reasoning}\n\nKeep up the good work, looking forward to more of your brilliant perspectives! 💪"
                                        
                                        # Send feedback
                                        try:
                                            logger.info(f"Attempting to send feedback to user {username}, reply hash: {reply_hash}")
                                            feedback_result = agent.connection_manager.perform_action(
                                                connection_name="farcaster",
                                                action_name="reply-to-cast",
                                                params=[reply_hash, feedback]
                                            )
                                            logger.info(f"Successfully sent feedback to {username}: {feedback_result}")
                                        except Exception as e:
                                            logger.error(f"Error sending feedback to user {username}: {e}")
                                            
                                            # Try to reply to original challenge
                                            try:
                                                challenge_hash = challenge.get('cast_hash')
                                                if challenge_hash:
                                                    logger.info(f"Attempting to send feedback to original challenge, challenge hash: {challenge_hash}")
                                                    feedback_with_mention = f"@{mention_name} {feedback}"
                                                    feedback_result = agent.connection_manager.perform_action(
                                                        connection_name="farcaster",
                                                        action_name="reply-to-cast",
                                                        params=[challenge_hash, feedback_with_mention]
                                                    )
                                                    logger.info(f"Successfully sent feedback to original challenge for {username}: {feedback_result}")
                                            except Exception as e2:
                                                logger.error(f"Error sending feedback to original challenge for {username}: {e2}")
                                    else:
                                        logger.warning(f"Cannot send feedback: evaluation result is not in dictionary format: {evaluation_result}")
                                except Exception as e:
                                    logger.error(f"Error sending feedback: {e}")
                                
                            except Exception as e:
                                logger.error(f"Error processing reply: {e}")
                        
                        return f"Processed {processed_count} new replies out of {replies_count} total replies."
                    else:
                        return f"No replies found for this challenge yet. Challenge topic: {challenge.get('topic')}"
                else:
                    # Try to handle other formats
                    replies_count = 0
                    if hasattr(replies, '__len__'):
                        replies_count = len(replies)
                    
                    return f"Found {replies_count} replies to challenge, but could not process them due to unexpected format."
            else:
                return f"No replies found for this challenge yet. Challenge topic: {challenge.get('topic')}"
            
        except Exception as e:
            logger.error(f"Failed to get replies using Neynar API: {e}")
            
            # Fallback to the old method
            try:
                # First try to get the cast details to check if it has replies
                cast_details = agent.connection_manager.perform_action(
                    connection_name="farcaster",
                    action_name="get-cast",
                    params=[cast_hash]
                )
                
                logger.info(f"Cast details type: {type(cast_details)}")
                logger.info(f"Cast details: {cast_details}")
                
                # Check if the cast has replies based on cast details
                has_replies = False
                replies_count = 0
                
                if hasattr(cast_details, 'replies') and hasattr(cast_details.replies, 'count'):
                    replies_count = cast_details.replies.count
                    has_replies = replies_count > 0
                elif isinstance(cast_details, dict) and 'replies' in cast_details:
                    if isinstance(cast_details['replies'], dict) and 'count' in cast_details['replies']:
                        replies_count = cast_details['replies']['count']
                        has_replies = replies_count > 0
                    elif isinstance(cast_details['replies'], int):
                        replies_count = cast_details['replies']
                        has_replies = replies_count > 0
                
                if not has_replies:
                    return f"No replies found for this challenge yet. Challenge topic: {challenge.get('topic')}"
                
                return f"Found {replies_count} replies to challenge, but could not process them. Please try again later."
            except Exception as e2:
                logger.error(f"Failed to check if cast has replies (fallback method): {e2}")
                return f"Error checking replies: {str(e)} and fallback error: {str(e2)}"
        
    except Exception as e:
        logger.error(f"Failed to check challenge replies: {str(e)}")
        return f"Error: {str(e)}"

# Helper functions

def _save_challenge_to_file(agent):
    """Save the current challenge data to a file for persistence"""
    try:
        if not hasattr(agent, 'state') or 'current_challenge' not in agent.state:
            logger.warning("No current challenge to save")
            return
        
        challenge_data = agent.state['current_challenge']
        
        # Create a challenges directory if it doesn't exist
        os.makedirs('challenges', exist_ok=True)
        
        # Generate filename based on timestamp
        timestamp = challenge_data.get('timestamp', datetime.now().isoformat())
        safe_timestamp = timestamp.replace(':', '-').replace('.', '-')
        filename = f"challenges/challenge_{safe_timestamp}.json"
        
        logger.info(f"Saving challenge to file: {filename}")
        logger.info(f"Challenge data: {challenge_data}")
        
        with open(filename, 'w') as f:
            json.dump(challenge_data, f, indent=2)
            
        logger.info(f"Challenge saved to {filename}")
            
    except Exception as e:
        logger.error(f"Failed to save challenge to file: {str(e)}")

def _update_winner_file(agent, winner_data):
    """Update the winner file with new winner information"""
    try:
        if not hasattr(agent, 'config') or 'persuasion_challenge_settings' not in agent.config:
            return
        
        settings = agent.config['persuasion_challenge_settings']
        winner_file = settings.get('winner_file', 'winner_info.json')
        
        # Load existing winners
        winners = []
        if os.path.exists(winner_file):
            try:
                with open(winner_file, 'r') as f:
                    winners = json.load(f)
                    if not isinstance(winners, list):
                        winners = []
            except json.JSONDecodeError:
                winners = []
        
        # Add new winner
        winners.append({
            "username": winner_data.get('username'),
            "address": winner_data.get('user_address'),
            "topic": agent.state['current_challenge'].get('topic'),
            "score": winner_data.get('evaluation', {}).get('score'),
            "reward_amount": winner_data.get('reward_amount'),
            "reward_tx": winner_data.get('reward_tx'),
            "timestamp": winner_data.get('reward_timestamp', datetime.now().isoformat())
        })
        
        # Save updated winners
        with open(winner_file, 'w') as f:
            json.dump(winners, f, indent=2)
            
    except Exception as e:
        logger.error(f"Failed to update winner file: {str(e)}")

def _get_user_wallet_address(agent, username):
    """Get a user's wallet address based on their username or FID
    
    This function uses the Neynar API to fetch user information and extract
    their verified Ethereum addresses.
    
    Args:
        agent: The agent instance
        username: The username or FID of the user
    
    Returns:
        str: The user's Ethereum wallet address or None if not found
    """
    logger.info(f"Getting wallet address for user: {username}")
    
    # Check if username is in the format "user_<fid>"
    fid = None
    if username and username.startswith("user_") and username[5:].isdigit():
        fid = username[5:]
        logger.info(f"Extracted FID from username: {fid}")
    else:
        logger.warning(f"Username '{username}' is not in the format 'user_<fid>', cannot extract FID")
    
    if not fid:
        logger.warning(f"Could not extract FID from username: {username}")
        # For backward compatibility, return the test address
        logger.warning(f"Using fallback test address for user {username}")
        return "0xe28D37E094AC43Fc264bAb5263b3694b985B39df"
    
    try:
        # Use requests to call Neynar API directly
        import requests
        import os
        
        api_key = os.getenv('NEYNAR_API_KEY', 'NEYNAR_API_DOCS')
        url = f"https://api.neynar.com/v2/farcaster/user/bulk?fids={fid}"
        
        headers = {
            "accept": "application/json",
            "api_key": api_key
        }
        
        logger.info(f"Calling Neynar API to get user info for FID: {fid}")
        logger.debug(f"Neynar API URL: {url}")
        logger.debug(f"Neynar API Key: {api_key[:4]}...{api_key[-4:]}")
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Neynar API response: {data}")
            
            if "users" in data and len(data["users"]) > 0:
                user = data["users"][0]
                logger.info(f"Found user data for FID {fid}: username={user.get('username')}, display_name={user.get('display_name')}")
                
                # Check for verified Ethereum addresses
                if "verified_addresses" in user and "eth_addresses" in user["verified_addresses"] and len(user["verified_addresses"]["eth_addresses"]) > 0:
                    # Use the first verified Ethereum address
                    eth_address = user["verified_addresses"]["eth_addresses"][0]
                    logger.info(f"Found verified Ethereum address for user {username} (FID {fid}): {eth_address}")
                    return eth_address
                else:
                    logger.warning(f"No verified Ethereum addresses found for user {username} (FID {fid})")
                
                # If no verified addresses, check custody address
                if "custody_address" in user and user["custody_address"]:
                    logger.info(f"Using custody address for user {username} (FID {fid}): {user['custody_address']}")
                    return user["custody_address"]
                else:
                    logger.warning(f"No custody address found for user {username} (FID {fid})")
            else:
                logger.warning(f"No user data found for FID {fid} in Neynar API response")
                if "users" not in data:
                    logger.warning(f"'users' field missing in Neynar API response: {data}")
                elif len(data["users"]) == 0:
                    logger.warning(f"Empty 'users' array in Neynar API response: {data}")
            
            logger.warning(f"No wallet address found for user {username} (FID {fid}) in Neynar API response")
        else:
            logger.error(f"Failed to get user info from Neynar API: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Error getting wallet address for user {username} (FID {fid}): {e}")
    
    # Fallback to test address if no address found
    logger.warning(f"Using fallback test address for user {username} (FID {fid})")
    return "0xe28D37E094AC43Fc264bAb5263b3694b985B39df" 