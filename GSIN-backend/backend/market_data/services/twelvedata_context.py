# backend/market_data/services/twelvedata_context.py
"""
Twelve Data market context service.
Provides news, sentiment, and fundamentals data for Brain integration.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from ..providers.twelvedata_provider import get_twelvedata_provider


class TwelveDataContextService:
    """Service for accessing Twelve Data news, sentiment, and fundamentals."""
    
    def __init__(self):
        self.provider = None
        try:
            self.provider = get_twelvedata_provider()
        except Exception as e:
            # Provider not available - service will return None/empty for all methods
            print(f"⚠️  Twelve Data provider not available: {e}")
    
    def get_symbol_news(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get news articles for a symbol.
        
        Returns:
            List of news articles (empty list if unavailable)
        """
        if not self.provider:
            return []
        
        try:
            return self.provider.get_symbol_news(symbol, limit)
        except Exception:
            return []
    
    def get_symbol_sentiment(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get sentiment data for a symbol.
        
        Returns:
            Dictionary with sentiment score and confidence, or None if unavailable
        """
        if not self.provider:
            return None
        
        try:
            sentiment_data = self.provider.get_sentiment(symbol)
            if sentiment_data:
                return {
                    "symbol": sentiment_data.symbol,
                    "sentiment_score": sentiment_data.sentiment_score,
                    "confidence": sentiment_data.confidence,
                    "timestamp": sentiment_data.timestamp,
                    "source": sentiment_data.source
                }
        except Exception:
            pass
        
        return None
    
    def get_symbol_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get fundamental data for a symbol.
        
        Returns:
            Dictionary with fundamental metrics, or None if unavailable
        """
        if not self.provider:
            return None
        
        try:
            return self.provider.get_symbol_fundamentals(symbol)
        except Exception:
            return None
    
    def get_market_context(
        self,
        symbol: str,
        include_news: bool = True,
        include_sentiment: bool = True,
        include_fundamentals: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive market context for a symbol.
        
        Returns:
            Dictionary with news, sentiment, and fundamentals (missing fields are None/empty)
        """
        context = {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc),
            "news": [],
            "sentiment": None,
            "fundamentals": None,
            "news_count": 0,
            "risk_regime": "neutral"  # risk-on, risk-off, neutral, news-heavy
        }
        
        if include_news:
            news = self.get_symbol_news(symbol, limit=10)
            context["news"] = news
            context["news_count"] = len(news)
            
            # Determine risk regime based on news count
            if len(news) > 5:
                context["risk_regime"] = "news-heavy"
        
        if include_sentiment:
            sentiment = self.get_symbol_sentiment(symbol)
            context["sentiment"] = sentiment
            
            # Update risk regime based on sentiment
            if sentiment:
                score = sentiment.get("sentiment_score", 0.0)
                if score > 0.3:
                    context["risk_regime"] = "risk-on"
                elif score < -0.3:
                    context["risk_regime"] = "risk-off"
        
        if include_fundamentals:
            fundamentals = self.get_symbol_fundamentals(symbol)
            context["fundamentals"] = fundamentals
        
        return context


# Singleton instance
_twelvedata_context_service: Optional[TwelveDataContextService] = None


def get_twelvedata_context_service() -> TwelveDataContextService:
    """Get or create Twelve Data context service instance."""
    global _twelvedata_context_service
    if _twelvedata_context_service is None:
        _twelvedata_context_service = TwelveDataContextService()
    return _twelvedata_context_service

