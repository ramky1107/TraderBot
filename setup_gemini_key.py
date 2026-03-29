#!/usr/bin/env python3
"""
=============================================================================
setup_gemini_key.py
=============================================================================
Interactive script to help set up your Gemini API key.

This script will:
1. Check if you have a valid API key
2. Guide you to get a new key if needed
3. Update your .env file with the correct key
4. Test the key to make sure it works
=============================================================================
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def check_current_key():
    """Check if there's a current API key and if it's valid."""
    load_dotenv()
    current_key = os.getenv('GEMINI_API_KEY', '')

    if not current_key:
        print("❌ No GEMINI_API_KEY found in .env file")
        return False, current_key

    # Check if it's the old hardcoded key (known to be exhausted)
    if current_key == 'AIzaSyBpBKyDln1NAkPusuAb1wsScxNwPd65nnQ':
        print("⚠️  You have the old hardcoded API key - this key's quota is exhausted!")
        print("   This key has been used up and won't work anymore.")
        return False, current_key

    print(f"✅ Found API key: {current_key[:20]}...")
    return True, current_key

def test_api_key(api_key):
    """Test if the API key works by making a simple call."""
    try:
        import google.genai as genai
        client = genai.Client(api_key=api_key)

        # Try a simple test call
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents='Say "Hello" in one word.'
        )

        if response.text and response.text.strip():
            print("✅ API key is working correctly!")
            return True
        else:
            print("⚠️  API responded but with empty output")
            return False

    except Exception as e:
        error_str = str(e).lower()
        if 'quota' in error_str or 'exceeded' in error_str or '429' in error_str:
            print("❌ API key quota exceeded - this key has been used up!")
            print("   You need to get a fresh API key from Google AI Studio.")
            return False
        elif 'invalid' in error_str or 'unauthorized' in error_str or '403' in error_str:
            print("❌ API key is invalid or unauthorized")
            return False
        else:
            print(f"❌ API key test failed: {e}")
            return False

def update_env_file(api_key):
    """Guide the user to manually update the .env file with the new API key."""
    env_path = Path('.env')

    if not env_path.exists():
        print("❌ .env file not found!")
        print("   Please create a .env file and add:")
        print(f"   GEMINI_API_KEY={api_key}")
        return False

    print("✅ Please manually update your .env file with the new API key:")
    print(f"   Add or update this line in .env:")
    print(f"   GEMINI_API_KEY={api_key}")
    return True

def main():
    print("=" * 70)
    print("🔑 GEMINI API KEY SETUP HELPER")
    print("=" * 70)
    print()

    # Check current status
    print("📋 Checking current API key status...")
    has_key, current_key = check_current_key()
    print()

    if has_key and test_api_key(current_key):
        print("🎉 Your API key is already working! No changes needed.")
        print()
        print("If you're still having issues, try restarting your server:")
        print("  python main.py")
        return

    # Guide user to get new key
    print("🔑 To get a new Gemini API key:")
    print("1. Go to: https://aistudio.google.com/app/apikey")
    print("2. Sign in with your Google account")
    print("3. Click 'Create API Key'")
    print("4. Copy the API key (it starts with 'AIzaSy...')")
    print()

    # Get new key from user
    while True:
        new_key = input("📝 Paste your new API key here: ").strip()

        if not new_key:
            print("❌ No key entered. Please try again.")
            continue

        if not new_key.startswith('AIzaSy'):
            print("⚠️  API key should start with 'AIzaSy'. Please check and try again.")
            continue

        print(f"\n🔍 Testing API key: {new_key[:20]}...")
        if test_api_key(new_key):
            print("\n✅ API key is valid!")

            # Update .env file
            if update_env_file(new_key):
                print("\n🎉 Setup complete! Your API key has been saved to .env")
                print("\n🚀 Next steps:")
                print("1. Restart your server: python main.py")
                print("2. Test the chatbot: POST to /api/chatbot")
                print("3. Test news processing: GET /api/gemini-news?company=Apple")
                break
            else:
                print("\n❌ Failed to save key to .env file")
                print("You can manually add it to your .env file:")
                print(f"GEMINI_API_KEY={new_key}")
                break
        else:
            print("\n❌ API key is invalid. Please check and try again.")
            print("Make sure you copied the entire key from Google AI Studio.")

if __name__ == '__main__':
    main()
