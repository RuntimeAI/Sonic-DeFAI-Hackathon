#!/usr/bin/env python3
"""
Diagnostic script for testing Farcaster connection and posting capabilities.

Usage:
  python diagnose_farcaster.py [--url URL]
"""

import sys
import json
import logging
import argparse
import time
from src.server.client import ZerePyClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("farcaster_diagnostic")

def print_section(title):
    """Print a section title"""
    print("\n" + "=" * 50)
    print(f" {title} ".center(50, "="))
    print("=" * 50)

def print_colorized(text, color_code):
    """Print text with ANSI color codes"""
    print(f"\033[{color_code}m{text}\033[0m")

def check_farcaster_connection(client):
    """Check if Farcaster connection is available and configured"""
    print_section("CHECKING FARCASTER CONNECTION")
    
    try:
        connections = client.list_connections()
        
        if "farcaster" not in connections:
            print_colorized("❌ Farcaster connection not available in the server", 31)
            return False
            
        farcaster_info = connections["farcaster"]
        if not farcaster_info.get("configured", False):
            print_colorized("❌ Farcaster connection not configured", 31)
            print("The connection exists but is not properly configured.")
            return False
        
        print_colorized("✅ Farcaster connection is available and configured", 32)
        
        # Print connection details
        print("\nConnection details:")
        for key, value in farcaster_info.items():
            if key != "params":  # Don't print sensitive params
                print(f"  - {key}: {value}")
        
        return True
        
    except Exception as e:
        print_colorized(f"❌ Error checking Farcaster connection: {e}", 31)
        return False

def test_get_account_info(client):
    """Test getting Farcaster account information"""
    print_section("TESTING FARCASTER ACCOUNT INFO")
    
    try:
        result = client.perform_action(
            connection="farcaster",
            action="get-account-info",
            params=[]
        )
        
        if "account" in result:
            account = result["account"]
            print_colorized("✅ Successfully retrieved account info", 32)
            print(f"\nAccount details:")
            print(f"  - Username: @{account.get('username', 'unknown')}")
            print(f"  - Display name: {account.get('display_name', 'unknown')}")
            print(f"  - FID: {account.get('fid', 'unknown')}")
            print(f"  - Followers: {account.get('follower_count', 0)}")
            print(f"  - Following: {account.get('following_count', 0)}")
            return True
        else:
            print_colorized("❌ Failed to retrieve account info", 31)
            print(f"Response: {result}")
            return False
            
    except Exception as e:
        print_colorized(f"❌ Error getting account info: {e}", 31)
        return False

def test_post_cast(client):
    """Test posting a cast to Farcaster"""
    print_section("TESTING CAST POSTING")
    
    test_message = f"This is a test cast from the PitchYourIdea diagnostic tool. Timestamp: {time.time()}"
    
    print(f"Attempting to post: \"{test_message}\"")
    
    try:
        result = client.perform_action(
            connection="farcaster",
            action="post-cast",
            params=[test_message]
        )
        
        print(f"\nRaw response: {json.dumps(result, indent=2)}")
        
        if result.get("success", False):
            print_colorized("✅ Successfully posted test cast!", 32)
            cast_hash = result.get("cast_hash", "unknown")
            print(f"Cast hash: {cast_hash}")
            
            # Try to verify the cast was posted by getting latest casts
            print("\nVerifying cast was posted by checking latest casts...")
            time.sleep(2)  # Wait a bit for the cast to be indexed
            
            latest_result = client.perform_action(
                connection="farcaster",
                action="get-latest-casts",
                params=["5"]  # Get 5 latest casts
            )
            
            if "casts" in latest_result and latest_result["casts"]:
                found = False
                for cast in latest_result["casts"]:
                    if cast.get("hash") == cast_hash or test_message in cast.get("text", ""):
                        print_colorized("✅ Verified cast appears in latest casts!", 32)
                        found = True
                        break
                
                if not found:
                    print_colorized("⚠️ Cast was posted but doesn't appear in latest casts yet", 33)
                    print("This might be due to indexing delay or API caching.")
            else:
                print_colorized("⚠️ Could not verify cast in latest casts", 33)
                
            return True
        else:
            print_colorized(f"❌ Failed to post cast: {result.get('error', 'Unknown error')}", 31)
            return False
            
    except Exception as e:
        print_colorized(f"❌ Error posting cast: {e}", 31)
        import traceback
        print(traceback.format_exc())
        return False

def check_api_permissions(client):
    """Check if the API key has the necessary permissions"""
    print_section("CHECKING API PERMISSIONS")
    
    # This is a bit of a guess since we don't have direct access to check permissions
    # We'll infer based on the ability to perform certain actions
    
    try:
        # Try to get account info (read permission)
        account_result = client.perform_action(
            connection="farcaster",
            action="get-account-info",
            params=[]
        )
        
        read_access = "account" in account_result
        print(f"Read access: {'✅' if read_access else '❌'}")
        
        # Try to post a cast (write permission)
        write_test_message = f"Permission test {time.time()}"
        post_result = client.perform_action(
            connection="farcaster",
            action="post-cast",
            params=[write_test_message]
        )
        
        write_access = post_result.get("success", False)
        print(f"Write access: {'✅' if write_access else '❌'}")
        
        if read_access and write_access:
            print_colorized("✅ API key appears to have necessary permissions", 32)
            return True
        else:
            print_colorized("❌ API key may be missing required permissions", 31)
            if not read_access:
                print("- Missing read permission (cannot get account info)")
            if not write_access:
                print("- Missing write permission (cannot post casts)")
            return False
            
    except Exception as e:
        print_colorized(f"❌ Error checking API permissions: {e}", 31)
        return False

def suggest_fixes(client):
    """Suggest potential fixes based on diagnostic results"""
    print_section("SUGGESTED FIXES")
    
    try:
        connections = client.list_connections()
        farcaster_info = connections.get("farcaster", {})
        
        if not farcaster_info:
            print("1. The Farcaster connection is not available on the server.")
            print("   - Make sure the Farcaster connection is properly registered in the server.")
            return
            
        if not farcaster_info.get("configured", False):
            print("1. The Farcaster connection is not configured.")
            print("   - Configure the Farcaster connection with valid credentials.")
            print("   - Check your .env file for FARCASTER_* environment variables.")
            return
            
        # If we got here, the connection exists and is configured, but posting might still fail
        print("Potential issues and fixes:")
        print("\n1. API Key Issues:")
        print("   - Your API key might be invalid or expired")
        print("   - The API key might not have write permissions")
        print("   - Try generating a new API key from your Farcaster client")
        
        print("\n2. Rate Limiting:")
        print("   - You might be hitting Farcaster's rate limits")
        print("   - Try posting less frequently")
        
        print("\n3. Content Issues:")
        print("   - Your content might be flagged or filtered")
        print("   - Try posting simpler content without links or special characters")
        
        print("\n4. Network Issues:")
        print("   - There might be connectivity issues between the server and Farcaster")
        print("   - Check if the server can reach Farcaster's API endpoints")
        
        print("\n5. Server Configuration:")
        print("   - The server might need to be restarted to apply new configuration")
        print("   - Try restarting the ZerePy server")
        
    except Exception as e:
        print_colorized(f"❌ Error generating suggestions: {e}", 31)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Diagnose Farcaster connection issues")
    parser.add_argument("--url", type=str, default="https://api.singha.today", 
                        help="ZerePy server URL (default: https://api.singha.today)")
    args = parser.parse_args()
    
    # Initialize the client
    server_url = args.url
    is_remote = "localhost" not in server_url and "127.0.0.1" not in server_url
    env_name = "REMOTE" if is_remote else "LOCAL"
    
    print_colorized(f"Connecting to {env_name} ZerePy server at {server_url}", 36)
    client = ZerePyClient(server_url)
    
    # Check server status
    print_section("SERVER STATUS")
    try:
        status = client.get_status()
        print(f"Status: {json.dumps(status, indent=2)}")
    except Exception as e:
        print_colorized(f"❌ Error getting server status: {e}", 31)
        print("Make sure the server is running and accessible.")
        return
    
    # Run diagnostic tests
    connection_ok = check_farcaster_connection(client)
    
    if connection_ok:
        account_ok = test_get_account_info(client)
        permissions_ok = check_api_permissions(client)
        posting_ok = test_post_cast(client)
        
        # Summary
        print_section("DIAGNOSTIC SUMMARY")
        print(f"Farcaster Connection: {'✅' if connection_ok else '❌'}")
        print(f"Account Information: {'✅' if account_ok else '❌'}")
        print(f"API Permissions: {'✅' if permissions_ok else '❌'}")
        print(f"Test Post: {'✅' if posting_ok else '❌'}")
        
        if not (account_ok and permissions_ok and posting_ok):
            suggest_fixes(client)
    else:
        print_colorized("\nFarcaster connection is not properly configured. Cannot proceed with further tests.", 31)
        suggest_fixes(client)
    
    print_colorized("\nDiagnostic completed!", 32)

if __name__ == "__main__":
    main() 