import requests
import json
import logging
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("server.client")

class ZerePyClientError(Exception):
    """Base exception for ZerePy client errors"""
    pass

class ZerePyClient:
    """Client for interacting with ZerePy server"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the client with server URL"""
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to the server"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            if method.lower() == 'get':
                response = self.session.get(url)
            elif method.lower() == 'post':
                response = self.session.post(url, json=data)
            else:
                raise ZerePyClientError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', str(e))
                    error_msg = f"Server error: {error_detail}"
                except:
                    error_msg = f"Server error: {e.response.text}"
            
            logger.error(error_msg)
            raise ZerePyClientError(error_msg) from e
    
    def get_status(self) -> Dict[str, Any]:
        """Get server status"""
        return self._make_request('get', '/')
    
    def list_agents(self) -> List[str]:
        """List available agents"""
        response = self._make_request('get', '/agents')
        return response.get('agents', [])
    
    def load_agent(self, name: str) -> Dict[str, Any]:
        """Load a specific agent"""
        return self._make_request('post', f'/agents/{name}/load')
    
    def list_connections(self) -> Dict[str, Dict[str, Any]]:
        """List available connections"""
        response = self._make_request('get', '/connections')
        return response.get('connections', {})
    
    def get_connection_status(self, connection_name: str) -> Dict[str, Any]:
        """Get status of a specific connection"""
        return self._make_request('get', f'/connections/{connection_name}/status')
    
    def configure_connection(self, connection_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Configure a specific connection"""
        data = {
            "connection": connection_name,
            "params": params
        }
        return self._make_request('post', f'/connections/{connection_name}/configure', data)
    
    def perform_action(self, connection: str, action: str, params: Union[List[Any], Dict[str, Any]]) -> Dict[str, Any]:
        """Execute an action on the server"""
        data = {
            "connection": connection,
            "action": action,
            "params": params
        }
        return self._make_request('post', '/agent/action', data)
    
    def start_agent(self) -> Dict[str, Any]:
        """Start the agent loop"""
        return self._make_request('post', '/agent/start')
    
    def stop_agent(self) -> Dict[str, Any]:
        """Stop the agent loop"""
        return self._make_request('post', '/agent/stop')