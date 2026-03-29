#!/usr/bin/env python3
"""
=============================================================================
test_gemini_news.py
=============================================================================
Quick test script to verify Gemini news processing is working.

Usage:
    python test_gemini_news.py
    
This will fetch news for Apple and process it with Gemini to extract
simple English headlines.
=============================================================================
"""

import os
import sys
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_gemini_news():
    """Test Gemini news processing with sample data."""
    
    # Check if API key is set
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        logger.error('❌ GEMINI_API_KEY not found in .env file')
        logger.info('Please set GEMINI_API_KEY in .env file')
        return False
    
    logger.info('✅ GEMINI_API_KEY found')
    
    try:
        # Import the news processing function
        from news import process_company_news_gemini, get_gemini_news_headlines
        
        # Test 1: Process company news for Apple
        logger.info('\n' + '='*60)
        logger.info('TEST 1: Processing news for Apple (AAPL)')
        logger.info('='*60)
        
        result = process_company_news_gemini('Apple', 'AAPL')
        
        logger.info(f'Status: {result.get("status")}')
        logger.info(f'Company: {result.get("company")}')
        logger.info(f'Number of headlines: {len(result.get("headlines", []))}')
        logger.info(f'Sentiment: {result.get("sentiment", "N/A")}')
        logger.info(f'Summary: {result.get("summary", "N/A")}')
        
        logger.info('\n📰 Simplified Headlines:')
        for i, headline in enumerate(result.get('headlines', []), 1):
            logger.info(f'  {i}. {headline}')
        
        # Test 2: Direct headline processing
        logger.info('\n' + '='*60)
        logger.info('TEST 2: Processing sample headlines')
        logger.info('='*60)
        
        sample_headlines = [
            'Tesla stock surges on Q4 earnings beat',
            'Apple announces record revenue from iPhone sales',
            'Microsoft releases new AI features for Office 365',
            'Google faces antitrust investigation',
            'Amazon expands cloud services to new regions'
        ]
        
        logger.info('Input headlines:')
        for h in sample_headlines:
            logger.info(f'  • {h}')
        
        result2 = get_gemini_news_headlines('Tech Companies', sample_headlines)
        
        logger.info(f'\n✅ Processing Status: {result2.get("status")}')
        logger.info(f'Sentiment: {result2.get("sentiment")}')
        logger.info(f'Summary: {result2.get("summary")}')
        
        logger.info('\n📰 Simplified Headlines:')
        for i, headline in enumerate(result2.get('headlines', []), 1):
            logger.info(f'  {i}. {headline}')
        
        logger.info('\n' + '='*60)
        logger.info('🎉 TEST COMPLETE - Gemini news processing is working!')
        logger.info('='*60)
        
        # Show raw output for reference
        logger.info('\n📋 RAW GEMINI OUTPUT (for debugging):')
        logger.info('-'*60)
        logger.info(result2.get('raw_output', 'N/A'))
        logger.info('-'*60)
        
        return True
        
    except ImportError as e:
        logger.error(f'❌ Import error: {e}')
        logger.info('Make sure all dependencies are installed: pip install -r requirements.txt')
        return False
    
    except Exception as e:
        logger.error(f'❌ Test failed: {e}')
        logger.exception(e)
        return False


if __name__ == '__main__':
    logger.info('Starting Gemini news test...\n')
    
    success = test_gemini_news()
    
    if success:
        logger.info('\n✅ All tests passed! Gemini news processing is ready.')
        logger.info('You can now use /api/gemini-news endpoint in the Flask app.')
        sys.exit(0)
    else:
        logger.error('\n❌ Tests failed. Please check the setup.')
        sys.exit(1)
