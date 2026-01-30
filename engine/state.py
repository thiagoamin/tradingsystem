from datetime import datetime
from typing import Dict, Tuple, Any, Optional

class MarketState:
    """
    Sole input to the signal engine and provides a
    stable contract between data ingestion and decision logic.

    A MarketState contains *only derived features and current values*.
    It does not own raw history. All temporal aggregation (returns,
    moving averages, volatility, regimes, etc.) is performed upstream
    in the data/feature layer.
    """
    def __init__(self, 
                 prices: Dict[str,float], 
                 indicators: Dict[Tuple[str,str], float], 
                 timestamp: datetime,
                 meta: Dict[str, Any] | None = None):
        """Construct a MarketState snapshot.

        Args:
            prices: Mapping from ticker symbol to its current price.
                Example: {"AAPL": 183.4, "SPY": 471.2}.
            indicators: Mapping from (ticker, indicator_name) to a computed feature value. 
                Example: ("AAPL", "ma_20") -> 182.3.
            timestamp: Time at which this snapshot is valid.
            meta: Optional auxiliary metadata (e.g., data source, regime labels). 
                Not used by the signal engine directly.
        """
        self.prices = prices
        self.indicators = indicators
        self.timestamp = timestamp
        self.meta = meta or {}
    
    def price(self, ticker: str) -> float:
        "Returns price for a ticker."
        return self.prices[ticker]
    
    def indicator(self, ticker: str, name: str) -> float:
        "Returns indicator value for a given ticker and indicator name."
        return self.indicators[(ticker, name)]