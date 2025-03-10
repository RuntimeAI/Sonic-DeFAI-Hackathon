import os
import logging
from typing import Dict, Any, List, Optional
from dotenv import set_key, load_dotenv
from farcaster import Warpcast
from farcaster.models import CastContent, CastHash, IterableCastsResult, Parent, ReactionsPutResult
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.farcaster_connection")

class FarcasterConnectionError(Exception):
    """Base exception for Farcaster connection errors"""
    pass

class FarcasterConfigurationError(FarcasterConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class FarcasterAPIError(FarcasterConnectionError):
    """Raised when Farcaster API requests fail"""
    pass

class FarcasterConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Farcaster connection...")
        super().__init__(config)
        self._client: Warpcast = None
        
        # Try to initialize Warpcast client
        try:
            credentials = self._get_credentials()
            self._client = Warpcast(mnemonic=credentials['FARCASTER_MNEMONIC'])
            # Test connection
            self._client.get_me()
            logger.debug("Warpcast client initialized successfully")
        except Exception as e:
            logger.warning(f"Warpcast client initialization failed: {e}")
            self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Farcaster configuration from JSON"""
        required_fields = ["timeline_read_count", "cast_interval"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
        if not isinstance(config["timeline_read_count"], int) or config["timeline_read_count"] <= 0:
            raise ValueError("timeline_read_count must be a positive integer")

        if not isinstance(config["cast_interval"], int) or config["cast_interval"] <= 0:
            raise ValueError("cast_interval must be a positive integer")
            
        return config

    def register_actions(self) -> None:
        """Register available Farcaster actions"""
        self.actions = {
            "get-latest-casts": Action(
                name="get-latest-casts",
                parameters=[
                    ActionParameter("fid", True, int, "Farcaster ID of the user"),
                    ActionParameter("cursor", False, int, "Cursor, defaults to None"),
                    ActionParameter("limit", False, int, "Number of casts to read, defaults to 25, otherwise min(limit, 100)")
                ],
                description="Get the latest casts from a user"
            ),
            "post-cast": Action(
                name="post-cast",
                parameters=[
                    ActionParameter("text", True, str, "Text content of the cast"),
                    ActionParameter("embeds", False, List[str], "List of embeds, defaults to None"),
                    ActionParameter("channel_key", False, str, "Channel key, defaults to None"),
                ],
                description="Post a new cast"
            ),
            "read-timeline": Action(
                name="read-timeline",
                parameters=[
                    ActionParameter("cursor", False, int, "Cursor, defaults to None"),
                    ActionParameter("limit", False, int, "Number of casts to read from timeline, defaults to 100")
                ],
                description="Read all recent casts"
            ),
            "like-cast": Action(
                name="like-cast",
                parameters=[
                    ActionParameter("cast_hash", True, str, "Hash of the cast to like")
                ],
                description="Like a specific cast"
            ),
            "requote-cast": Action(
                name="requote-cast",
                parameters=[
                    ActionParameter("cast_hash", True, str, "Hash of the cast to requote")
                ],
                description="Requote a cast (recast)"
            ),
            "reply-to-cast": Action(
                name="reply-to-cast",
                parameters=[
                    ActionParameter("parent_hash", True, str, "Hash of the parent cast to reply to"),
                    ActionParameter("text", True, str, "Text content of the cast"),
                    ActionParameter("embeds", False, List[str], "List of embeds, defaults to None"),
                    ActionParameter("channel_key", False, str, "Channel of the cast, defaults to None"),
                ],
                description="Reply to a cast"
            ),
            "get-cast": Action(
                name="get-cast",
                parameters=[
                    ActionParameter("cast_hash", True, str, "Hash of the cast to get")
                ],
                description="Get a cast by hash"
            ),
            "get-cast-replies": Action(
                name="get-cast-replies", # get_all_casts_in_thread
                parameters=[
                    ActionParameter("thread_hash", True, str, "Hash of the thread to query for replies")
                ],
                description="Fetch cast replies (thread)"
            ),
            # Persuade Me Agent actions
            "post-persuade-challenge": Action(
                name="post-persuade-challenge",
                parameters=[],
                description="Post a new 'Persuade Me' challenge on Farcaster"
            ),
            "evaluate-persuasion-reply": Action(
                name="evaluate-persuasion-reply",
                parameters=[
                    ActionParameter("reply_text", True, str, "The text of the user's reply"),
                    ActionParameter("username", True, str, "The username of the replier"),
                    ActionParameter("user_address", True, str, "The wallet address of the replier"),
                    ActionParameter("reply_hash", True, str, "The hash of the reply cast")
                ],
                description="Evaluate a user's reply to a persuasion challenge"
            ),
            "check-challenge-replies": Action(
                name="check-challenge-replies",
                parameters=[],
                description="Check for new replies to the current persuasion challenge"
            )
        }
    
    def _get_credentials(self) -> Dict[str, str]:
        """Get Farcaster credentials from environment with validation"""
        logger.debug("Retrieving Farcaster credentials")
        load_dotenv()

        required_vars = {
            'FARCASTER_MNEMONIC': 'recovery phrase',
        }

        credentials = {}
        missing = []

        for env_var, description in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing.append(description)
            credentials[env_var] = value

        if missing:
            error_msg = f"Missing Farcaster credentials: {', '.join(missing)}"
            raise FarcasterConfigurationError(error_msg)

        logger.debug("All required credentials found")
        return credentials

    def configure(self) -> bool:
        """Sets up Farcaster bot authentication"""
        logger.info("\nStarting Farcaster authentication setup")

        if self.is_configured():
            logger.info("Farcaster is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Farcaster (Warpcast) recovery phrase (for connection):")
        logger.info("1. Open the Warpcast mobile app")
        logger.info("2. Navigate to Settings page (click profile picture on top left, then the gear icon on top right)")
        logger.info("3. Click 'Advanced' then 'Reveal recovery phrase'")
        logger.info("4. Copy your recovery phrase")

        recovery_phrase = input("\nEnter your Farcaster (Warpcast) recovery phrase: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            logger.info("Saving recovery phrase to .env file...")
            set_key('.env', 'FARCASTER_MNEMONIC', recovery_phrase)

            # Simple validation of token format
            if not recovery_phrase.strip():
                logger.error("❌ Invalid recovery phrase format")
                return False

            logger.info("✅ Farcaster (Warpcast) configuration successfully saved!")
            return True

        except Exception as e:
            logger.error(f"❌ Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
        """Check if Farcaster credentials are configured and valid"""
        logger.debug("Checking Farcaster configuration status")
        try:
            credentials = self._get_credentials()

            self._client = Warpcast(mnemonic=credentials['FARCASTER_MNEMONIC'])

            self._client.get_me()
            logger.debug("Farcaster configuration is valid")
            return True

        except Exception as e:
            if verbose:
                error_msg = str(e)
                if isinstance(e, FarcasterConfigurationError):
                    error_msg = f"Configuration error: {error_msg}"
                elif isinstance(e, FarcasterAPIError):
                    error_msg = f"API validation error: {error_msg}"
                logger.error(f"Configuration validation failed: {error_msg}")
            return False
    
    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Farcaster action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Add config parameters if not provided
        if action_name == "read-timeline" and "count" not in kwargs:
            kwargs["count"] = self.config["timeline_read_count"]

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
    
    def get_latest_casts(self, fid: int, cursor: Optional[int] = None, limit: Optional[int] = 25) -> IterableCastsResult:
        """Get the latest casts from a user"""
        logger.debug(f"Getting latest casts for {fid}, cursor: {cursor}, limit: {limit}")

        casts = self._client.get_casts(fid, cursor, limit)
        logger.debug(f"Retrieved {len(casts)} casts")
        return casts

    def post_cast(self, text: str, embeds: Optional[List[str]] = None, channel_key: Optional[str] = None) -> CastContent:
        """Post a new cast"""
        logger.debug(f"Posting cast: {text}, embeds: {embeds}")
        result = self._client.post_cast(text, embeds, None, channel_key)
        
        # Convert result to a dictionary with hash
        if hasattr(result, 'hash'):
            logger.debug(f"Cast posted with hash: {result.hash}")
            return {'hash': result.hash, 'text': text}
        
        # If result doesn't have hash attribute, try to extract it
        if isinstance(result, dict) and 'hash' in result:
            logger.debug(f"Cast posted with hash from dict: {result['hash']}")
            return result
            
        # If result is a string representation of an object, try to extract hash
        if isinstance(result, str) and 'hash=' in result:
            import re
            hash_match = re.search(r"hash='([^']+)'", result)
            if hash_match:
                hash_value = hash_match.group(1)
                logger.debug(f"Cast posted with hash from string: {hash_value}")
                return {'hash': hash_value, 'text': text}
        
        # If we can't extract hash, return the result as is
        logger.debug(f"Returning raw result: {result}")
        return result

    def read_timeline(self, cursor: Optional[int] = None, limit: Optional[int] = 100) -> IterableCastsResult:
        """Read all recent casts"""
        logger.debug(f"Reading timeline, cursor: {cursor}, limit: {limit}")
        return self._client.get_recent_casts(cursor, limit)

    def like_cast(self, cast_hash: str) -> ReactionsPutResult:
        """Like a specific cast"""
        logger.debug(f"Liking cast: {cast_hash}")
        return self._client.like_cast(cast_hash)
    
    def requote_cast(self, cast_hash: str) -> CastHash:
        """Requote a cast (recast)"""
        logger.debug(f"Requoting cast: {cast_hash}")
        return self._client.recast(cast_hash)

    def reply_to_cast(self, parent_hash: str, text: str, embeds: Optional[List[str]] = None, channel_key: Optional[str] = None) -> CastContent:
        """Reply to an existing cast"""
        logger.debug(f"Replying to cast: {parent_hash}, text: {text}")
        
        if not self._client:
            raise FarcasterConfigurationError("Warpcast client not initialized. Please check your credentials.")
        
        try:
            # Get parent cast FID (using Neynar API)
            cast_details = self.get_cast(parent_hash)
            if not cast_details or not hasattr(cast_details, 'author') or not hasattr(cast_details.author, 'fid'):
                raise FarcasterAPIError(f"Could not get details for cast: {parent_hash}")
                
            parent_fid = cast_details.author.fid
            
            # Send reply using Warpcast API
            parent = Parent(fid=parent_fid, hash=parent_hash)
            return self._client.post_cast(text, embeds, parent, channel_key)
        except Exception as e:
            logger.error(f"Error replying to cast: {e}")
            raise FarcasterAPIError(f"Failed to reply to cast: {e}")
    
    def get_cast_replies(self, thread_hash: str) -> IterableCastsResult:
        """Fetch cast replies (thread)"""
        logger.debug(f"Fetching replies for thread: {thread_hash}")
        
        try:
            # Get parent cast FID (using Neynar API)
            cast_details = self.get_cast(thread_hash)
            if not cast_details or not hasattr(cast_details, 'author') or not hasattr(cast_details.author, 'fid'):
                logger.warning(f"Could not get details for cast: {thread_hash}")
                return []
                
            # Use Neynar API's castsByParent endpoint to get replies
            fid = cast_details.author.fid
            
            import requests
            import os
            from dotenv import load_dotenv
            
            # Load environment variables
            load_dotenv()
            api_key = os.getenv('NEYNAR_API_KEY', 'NEYNAR_API_DOCS')
            
            # Neynar API endpoint for replies - using v1 castsByParent endpoint
            url = "https://hub-api.neynar.com/v1/castsByParent"
            
            # Parameters
            params = {
                "fid": fid,
                "hash": thread_hash
            }
            
            # Headers with API key
            headers = {
                "accept": "application/json",
                "api_key": api_key
            }
            
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()  # Raise exception for 4XX/5XX responses
                
                data = response.json()
                logger.debug(f"Neynar API response structure: {list(data.keys())}")
                
                # Extract messages from response
                if "messages" in data:
                    messages = data["messages"]
                    logger.debug(f"Found {len(messages)} replies")
                    
                    # Transform messages to a more usable format
                    formatted_replies = []
                    for message in messages:
                        try:
                            reply = {}
                            
                            # Extract hash
                            if 'hash' in message:
                                reply['hash'] = message['hash']
                            
                            # Extract text
                            if 'data' in message and 'castAddBody' in message['data'] and 'text' in message['data']['castAddBody']:
                                reply['text'] = message['data']['castAddBody']['text']
                            
                            # Extract author info
                            if 'data' in message and 'fid' in message['data']:
                                reply['author'] = {'fid': message['data']['fid']}
                                
                                # If there's a username, add it too
                                if 'username' in message.get('meta', {}).get('displayName', {}):
                                    reply['author']['username'] = message['meta']['displayName']['username']
                            
                            # Extract timestamp
                            if 'data' in message and 'timestamp' in message['data']:
                                reply['timestamp'] = message['data']['timestamp']
                            
                            formatted_replies.append(reply)
                        except Exception as e:
                            logger.warning(f"Error formatting reply: {e}")
                    
                    return formatted_replies
                
                return []
                
            except Exception as e:
                logger.error(f"Error fetching replies with Neynar API: {e}")
                
                # If Neynar API fails, try using Warpcast API
                if self._client:
                    try:
                        # Try using new API endpoint
                        if hasattr(self._client, 'get_cast_replies'):
                            return self._client.get_cast_replies(thread_hash)
                        elif hasattr(self._client, 'get_replies'):
                            return self._client.get_replies(thread_hash)
                        
                        # If no replies or method not available, try using old method
                        return self._client.get_all_casts_in_thread(thread_hash)
                    except Exception as e2:
                        logger.warning(f"Error fetching replies with Warpcast API: {e2}")
                
                return []
        except Exception as e:
            logger.error(f"Error fetching replies: {e}")
            return []
    
    # Persuade Me Agent methods
    def post_persuade_challenge(self) -> Dict[str, Any]:
        """Post a new 'Persuade Me' challenge on Farcaster.
        
        This function is implemented in src/actions/persuade_actions.py
        and will be called through the action_handler.
        """
        from src.action_handler import execute_action
        import src.actions.persuade_actions  # Ensure actions are registered
        
        # Use the current agent from CLI
        from src.cli import ZerePyCLI
        agent = ZerePyCLI().agent
        
        if not agent:
            raise FarcasterAPIError("No agent currently loaded")
        
        # Execute the action through the action handler
        return execute_action(agent, "post-persuade-challenge")
    
    def evaluate_persuasion_reply(self, reply_text: str, username: str, user_address: str, reply_hash: str) -> Dict[str, Any]:
        """Evaluate a user's reply to a persuasion challenge.
        
        This function is implemented in src/actions/persuade_actions.py
        and will be called through the action_handler.
        """
        from src.action_handler import execute_action
        import src.actions.persuade_actions  # Ensure actions are registered
        
        # Use the current agent from CLI
        from src.cli import ZerePyCLI
        agent = ZerePyCLI().agent
        
        if not agent:
            raise FarcasterAPIError("No agent currently loaded")
        
        # Execute the action through the action handler
        return execute_action(
            agent, 
            "evaluate-persuasion-reply",
            reply_text=reply_text,
            username=username,
            user_address=user_address,
            reply_hash=reply_hash
        )
    
    def check_challenge_replies(self) -> str:
        """Check for new replies to the current persuasion challenge.
        
        This function is implemented in src/actions/persuade_actions.py
        and will be called through the action_handler.
        """
        from src.action_handler import execute_action
        import src.actions.persuade_actions  # Ensure actions are registered
        
        # Use the current agent from CLI
        from src.cli import ZerePyCLI
        agent = ZerePyCLI().agent
        
        if not agent:
            raise FarcasterAPIError("No agent currently loaded")
        
        # Execute the action through the action handler
        return execute_action(agent, "check-challenge-replies")

    def get_cast(self, cast_hash: str) -> Any:
        """Get a cast by hash"""
        logger.debug(f"Getting cast: {cast_hash}")
        
        try:
            # Use Neynar API to get cast information
            import requests
            import os
            from dotenv import load_dotenv
            from types import SimpleNamespace
            
            # Load environment variables
            load_dotenv()
            api_key = os.getenv('NEYNAR_API_KEY', 'NEYNAR_API_DOCS')
            
            # Neynar API v2 endpoint for cast
            url = "https://api.neynar.com/v2/farcaster/cast"
            
            # Query parameters
            params = {
                "identifier": cast_hash,
                "type": "hash"
            }
            
            # Headers with API key
            headers = {
                "accept": "application/json",
                "x-api-key": api_key
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            data = response.json()
            logger.debug(f"Neynar API response structure: {list(data.keys())}")
            
            if "cast" in data:
                cast_data = data["cast"]
                
                # Create an object similar to what Warpcast client returns
                cast = SimpleNamespace()
                
                # Set basic properties
                cast.hash = cast_data.get("hash")
                cast.text = cast_data.get("text", "")
                
                # Set author information
                author = SimpleNamespace()
                if "author" in cast_data:
                    author.fid = cast_data["author"].get("fid")
                    author.username = cast_data["author"].get("username", "")
                cast.author = author
                
                return cast
            else:
                logger.warning(f"No cast found in Neynar API response for hash {cast_hash}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching cast: {e}")
            return None
