"""
=============================================================================
sentiment_engine.py
=============================================================================
Orchestrates sentiment analysis using Ollama with the gemma3:1b model.
Classifies text as 'Positive', 'Negative', or 'Neutral'.
=============================================================================
"""

import os
import logging
from typing import List, Dict
import ollama
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:1b')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

class SentimentEngine:
    """Uses Ollama to determine sentiment of news or tweets."""

    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model
        try:
            # We assume Ollama is running on the local machine as per user's request.
            # No need for explicit host if default is used, but we keep it flexible.
            pass
        except Exception as e:
            logger.error(f"[Ollama] Connection error: {e}")

    def analyze_sentiment(self, text: str) -> str:
        """Classifies a single text as positive, negative, or neutral.
        
        Args:
            text: The headline or tweet to analyze.
            
        Returns:
            A string label (Positive/Negative/Neutral).
        """
        prompt = f"""
        You are a financial sentiment analyzer. 
        Classify the sentiment of the following financial text as either 'Positive', 'Negative', or 'Neutral'.
        Only respond with the word itself.

        Text: "{text}"
        Sentiment:"""

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                stream=False
            )
            sentiment = response.get('response', '').strip().capitalize()
            # Basic validation
            if 'Positive' in sentiment: return 'Positive'
            if 'Negative' in sentiment: return 'Negative'
            return 'Neutral'
        except Exception as e:
            logger.error(f"[Ollama] Analysis error: {e}")
            return 'Neutral'

    def batch_analyze(self, texts: List[str]) -> List[Dict]:
        """Analyzes a list of texts and returns detailed results.
        
        Args:
            texts: List of strings (headlines/tweets).
            
        Returns:
            List of dicts with 'text' and 'sentiment'.
        """
        results = []
        for text in texts:
            sentiment = self.analyze_sentiment(text)
            results.append({
                'text': text,
                'sentiment': sentiment
            })
        return results

    def get_aggregate_score(self, analyzed_items: List[Dict]) -> float:
        """Calculates a score from -100 to +100 based on results."""
        if not analyzed_items:
            return 0.0
        
        weights = {'Positive': 1, 'Negative': -1, 'Neutral': 0}
        total_score = sum(weights.get(item['sentiment'], 0) for item in analyzed_items)
        
        # Normalize to -100 to 100
        normalized = (total_score / len(analyzed_items)) * 100
        return round(normalized, 2)
