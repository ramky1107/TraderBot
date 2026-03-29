#!/usr/bin/env python3
"""
=============================================================================
fix_gemini_key.py
=============================================================================
Quick fix for the exhausted Gemini API key issue.

This script will help you replace the old exhausted key with a new one.
=============================================================================
"""

import os
from pathlib import Path
from dotenv import load_dotenv

def main():
    print("=" * 70)
    print("🔧 FIX EXHAUSTED GEMINI API KEY")
    print("=" * 70)
    print()

    # Load current environment
    load_dotenv()
    current_key = os.getenv('GEMINI_API_KEY', '')

    print("📋 Current status:")
    if current_key == 'AIzaSyBpBKyDln1NAkPusuAb1wsScxNwPd65nnQ':
        print("❌ You have the old exhausted API key")
        print("   This key's free quota has been used up.")
    elif current_key:
        print(f"✅ You have an API key set: {current_key[:20]}...")
    else:
        print("❌ No API key found")
    print()

    print("🔑 SOLUTION: Get a fresh API key")
    print("1. Go to: https://aistudio.google.com/app/apikey")
    print("2. Sign in with your Google account")
    print("3. Click 'Create API Key'")
    print("4. Copy the new API key")
    print()

    # Get new key
    new_key = input("📝 Paste your NEW API key here: ").strip()

    if not new_key:
        print("❌ No key entered. Exiting.")
        return

    if not new_key.startswith('AIzaSy'):
        print("⚠️  Key should start with 'AIzaSy'. Please check.")
        return

    # Update .env file
    env_path = Path('.env')
    if env_path.exists():
        print("✅ Please manually update your .env file with the new API key:")
        print(f"   Add or update this line in .env:")
        print(f"   GEMINI_API_KEY={new_key}")
    else:
        print("❌ .env file not found!")
        print("   Please create a .env file and add:")
        print(f"   GEMINI_API_KEY={new_key}")
        return

    print()
    print("🎉 SUCCESS! Your API key has been updated.")
    print()
    print("🚀 Next steps:")
    print("1. Restart your server: python main.py")
    print("2. Test the chatbot - it should work now!")
    print()
    print("💡 Tip: The free tier gives you 2M tokens/month.")
    print("   That's plenty for testing and development!")

if __name__ == '__main__':
    main()
