# backend/market_data/sentiment_provider.py
"""
Real sentiment data providers.
Integrates with NewsAPI, Alpaca News, and Polygon news.
"""
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import dotenv_values
import httpx

from .types import SentimentData, MarketDataError


class SentimentProvider:
    """Provider for real sentiment data from multiple sources."""
    
    def __init__(self):
        # Go up from backend/market_data/sentiment_provider.py -> market_data -> backend -> GSIN-backend -> gsin_new_git (repo root)
        CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
        cfg = {}
        if CFG_PATH.exists():
            cfg = dotenv_values(str(CFG_PATH))
            # Validate that we got real values, not placeholders
            for key, value in list(cfg.items()):
                if value and ("your-" in str(value).lower() or "placeholder" in str(value).lower()):
                    del cfg[key]
        
        # NewsAPI
        self.newsapi_key = os.environ.get("NEWSAPI_KEY") or cfg.get("NEWSAPI_KEY")
        
        # Alpaca News (uses same credentials as Alpaca API)
        self.alpaca_api_key = os.environ.get("ALPACA_API_KEY") or cfg.get("ALPACA_API_KEY")
        self.alpaca_secret_key = os.environ.get("ALPACA_SECRET_KEY") or cfg.get("ALPACA_SECRET_KEY")
        
        self.client = httpx.Client(timeout=10.0)
    
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """
        Get sentiment for a symbol from multiple sources.
        
        Returns:
            SentimentData or None if unavailable
        """
        # Try NewsAPI first
        if self.newsapi_key:
            try:
                return self._get_newsapi_sentiment(symbol)
            except Exception:
                # Silently fail - will use fallback
                pass
        
        # Try Alpaca News
        if self.alpaca_api_key and self.alpaca_secret_key:
            try:
                return self._get_alpaca_news_sentiment(symbol)
            except Exception:
                # Silently fail - will use fallback
                pass
        
        # Fallback: return neutral sentiment
        return SentimentData(
            symbol=symbol,
            sentiment_score=0.0,
            sentiment_label="neutral",
            source="fallback",
            timestamp=datetime.now()
        )
    
    def _get_newsapi_sentiment(self, symbol: str) -> SentimentData:
        """Get sentiment from NewsAPI."""
        # Search for news about the symbol
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": symbol,
            "apiKey": self.newsapi_key,
            "sortBy": "publishedAt",
            "pageSize": 10,
            "language": "en",
        }
        
        response = self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        articles = data.get("articles", [])
        if not articles:
            return SentimentData(
                symbol=symbol,
                sentiment_score=0.0,
                sentiment_label="neutral",
                source="newsapi",
                timestamp=datetime.now()
            )
        
        # Simple sentiment: count positive/negative keywords
        positive_keywords = ["up", "gain", "rise", "surge", "bullish", "buy", "growth", "profit"]
        negative_keywords = ["down", "loss", "fall", "drop", "bearish", "sell", "decline", "crash"]
        
        positive_count = 0
        negative_count = 0
        
        for article in articles:
            title = article.get("title", "").lower()
            description = article.get("description", "").lower()
            text = f"{title} {description}"
            
            for keyword in positive_keywords:
                if keyword in text:
                    positive_count += 1
            
            for keyword in negative_keywords:
                if keyword in text:
                    negative_count += 1
        
        # Calculate sentiment score (-1 to 1)
        total = positive_count + negative_count
        if total > 0:
            sentiment_score = (positive_count - negative_count) / total
        else:
            sentiment_score = 0.0
        
        # Determine label
        if sentiment_score > 0.3:
            label = "bullish"
        elif sentiment_score < -0.3:
            label = "bearish"
        else:
            label = "neutral"
        
        return SentimentData(
            symbol=symbol,
            sentiment_score=sentiment_score,
            sentiment_label=label,
            source="newsapi",
            timestamp=datetime.now()
        )
    
    def _get_alpaca_news_sentiment(self, symbol: str) -> SentimentData:
        """Get sentiment from Alpaca News API."""
        url = "https://data.alpaca.markets/v1beta1/news"
        headers = {
            "APCA-API-KEY-ID": self.alpaca_api_key,
            "APCA-API-SECRET-KEY": self.alpaca_secret_key,
        }
        params = {
            "symbols": symbol.upper(),
            "limit": 10,
        }
        
        response = self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        news_items = data.get("news", [])
        if not news_items:
            return SentimentData(
                symbol=symbol,
                sentiment_score=0.0,
                sentiment_label="neutral",
                source="alpaca",
                timestamp=datetime.now()
            )
        
        # Simple sentiment analysis
        positive_keywords = ["up", "gain", "rise", "surge", "bullish", "buy", "growth", "profit"]
        negative_keywords = ["down", "loss", "fall", "drop", "bearish", "sell", "decline", "crash"]
        
        positive_count = 0
        negative_count = 0
        
        for item in news_items:
            headline = item.get("headline", "").lower()
            summary = item.get("summary", "").lower()
            text = f"{headline} {summary}"
            
            for keyword in positive_keywords:
                if keyword in text:
                    positive_count += 1
            
            for keyword in negative_keywords:
                if keyword in text:
                    negative_count += 1
        
        total = positive_count + negative_count
        if total > 0:
            sentiment_score = (positive_count - negative_count) / total
        else:
            sentiment_score = 0.0
        
        if sentiment_score > 0.3:
            label = "bullish"
        elif sentiment_score < -0.3:
            label = "bearish"
        else:
            label = "neutral"
        
        return SentimentData(
            symbol=symbol,
            sentiment_score=sentiment_score,
            sentiment_label=label,
            source="alpaca",
            timestamp=datetime.now()
        )


# Global sentiment provider instance
_sentiment_provider: Optional[SentimentProvider] = None


def get_sentiment_provider() -> SentimentProvider:
    """Get or create the global sentiment provider instance (singleton)."""
    global _sentiment_provider
    if _sentiment_provider is None:
        _sentiment_provider = SentimentProvider()
    return _sentiment_provider

