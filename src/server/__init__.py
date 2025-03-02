try:
    import uvicorn
except ImportError:
    print("Error: uvicorn package not found. Please install it with:")
    print("poetry add uvicorn fastapi")
    print("or")
    print("pip install uvicorn fastapi")
from .app import create_app

def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the ZerePy server"""
    app = create_app()
    uvicorn.run(app, host=host, port=port)