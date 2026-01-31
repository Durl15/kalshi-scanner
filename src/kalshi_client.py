"""
Kalshi API Client (PATCHED - Conservative Rate Limiting)
========================================================
Core client for interacting with the Kalshi prediction market API.
Handles authentication, rate limiting, and common operations.
"""

import time
import hashlib
import base64
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, ed25519
from cryptography.hazmat.backends import default_backend

from .config import Config


@dataclass
class Market:
    """Represents a Kalshi market."""
    ticker: str
    title: str
    subtitle: str
    status: str
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    volume: int
    volume_24h: int
    open_interest: int
    close_time: Optional[datetime]
    event_ticker: str
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.yes_ask - self.yes_bid
    
    @property
    def midpoint(self) -> float:
        """Calculate midpoint price."""
        return (self.yes_bid + self.yes_ask) / 2
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Market":
        """Create Market from API response data."""
        return cls(
            ticker=data.get("ticker", ""),
            title=data.get("title", ""),
            subtitle=data.get("subtitle", ""),
            status=data.get("status", ""),
            yes_bid=data.get("yes_bid", 0) / 100,  # Convert cents to dollars
            yes_ask=data.get("yes_ask", 0) / 100,
            no_bid=data.get("no_bid", 0) / 100,
            no_ask=data.get("no_ask", 0) / 100,
            volume=data.get("volume", 0),
            volume_24h=data.get("volume_24h", 0),
            open_interest=data.get("open_interest", 0),
            close_time=datetime.fromisoformat(data["close_time"].replace("Z", "+00:00")) 
                       if data.get("close_time") else None,
            event_ticker=data.get("event_ticker", ""),
        )


@dataclass
class Position:
    """Represents a user's position in a market."""
    ticker: str
    market_exposure: int  # in cents
    position: int  # number of contracts
    realized_pnl: int
    resting_orders_count: int
    total_traded: int


class RateLimiter:
    """Conservative rate limiter for Kalshi API."""
    
    def __init__(self, requests_per_minute: int = 10, min_interval: float = 2.0):
        self.requests_per_minute = requests_per_minute
        self.min_interval = min_interval  # Minimum seconds between requests
        self.requests: List[float] = []
        self.last_request: float = 0
    
    def wait_if_needed(self):
        """Block if we've exceeded rate limits, using two conservative rules."""
        now = time.time()
        
        # Rule 1: Always wait for a minimum interval between subsequent requests.
        time_since_last = now - self.last_request
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            print(f"   [Rate limit: waiting {sleep_time:.1f}s (minimum interval)]")
            time.sleep(sleep_time)
            now = time.time()  # Update current time after sleeping
        
        # Rule 2: Enforce a rolling window for requests per minute.
        # Remove requests from our tracking list that are older than 60 seconds.
        self.requests = [r for r in self.requests if now - r < 60]
        
        # If the number of requests in the last minute still exceeds the limit,
        # wait until the oldest request expires from the 60-second window.
        if len(self.requests) >= self.requests_per_minute:
            # The time to wait is until the first request in the list is 60s old.
            sleep_time = 60 - (now - self.requests[0]) + 1  # +1 for a buffer
            if sleep_time > 0:
                print(f"   [Rate limit: waiting {sleep_time:.1f}s (per-minute limit)]")
                time.sleep(sleep_time)
        
        # Record the timestamp of the current request.
        self.requests.append(time.time())
        self.last_request = time.time()


class KalshiClient:
    """
    Client for the Kalshi prediction market API.
    
    Usage:
        config = Config.from_env()
        client = KalshiClient(config)
        
        # Get markets
        markets = client.get_markets(status="open")
        
        # Get balance
        balance = client.get_balance()
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.api_base_url
        self.session = requests.Session()
        # PATCHED: More conservative rate limiting
        self.rate_limiter = RateLimiter(requests_per_minute=10, min_interval=2.0)
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        
        # Load private key
        self._load_private_key()
    
    def _load_private_key(self):
        """Load the RSA private key for signing requests."""
        key_content = self.config.private_key
        self._private_key = serialization.load_pem_private_key(
            key_content.encode(),
            password=None,
            backend=default_backend()
        )
    
    def _sign_request(self, method: str, path: str, timestamp: str) -> str:
        """Sign a request using the private key."""
        message = f"{timestamp}{method}{path}"
        
        # Sign based on key type
        if isinstance(self._private_key, ed25519.Ed25519PrivateKey):
            signature = self._private_key.sign(message.encode())
        else:
            # RSA signing
            signature = self._private_key.sign(
                message.encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        
        return base64.b64encode(signature).decode()
    
    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate authenticated headers for a request."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        signature = self._sign_request(method, path, timestamp)
        
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.config.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        retry_count: int = 4,
        base_wait_sec: int = 5
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the API with rate limiting and retry logic.
        Implements exponential backoff with jitter for handling 429 rate limit errors.
        """
        self.rate_limiter.wait_if_needed()
        
        url = f"{self.base_url}{endpoint}"
        path = f"/trade-api/v2{endpoint}"
        headers = self._get_headers(method, path)
        
        for attempt in range(retry_count):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout=15  # Add a timeout
                )
                
                if response.status_code == 401:
                    raise AuthenticationError(
                        "Authentication failed (401). Please check your "
                        "KALSHI_API_KEY_ID and private key configuration in your "
                        ".env file or environment variables."
                    )
                
                if response.status_code == 429:
                    # This is a rate limit error, trigger a retry
                    raise RateLimitError(f"Rate limited (429) on attempt {attempt + 1}")

                # Raise an exception for other bad status codes (4xx or 5xx)
                response.raise_for_status()
                
                return response.json()

            except requests.exceptions.RequestException as e:
                # Handle network errors (e.g., DNS failure, refused connection)
                if attempt < retry_count - 1:
                    print(f"   [Network error: {e}. Retrying...]")
                    time.sleep(1) # Simple wait for network issues
                    continue
                raise APIError(f"A network error occurred: {e}") from e

            except RateLimitError as e:
                # Handle rate limit errors with exponential backoff
                if attempt < retry_count - 1:
                    # Calculate wait time: base * (2^attempt) + random_jitter
                    backoff_time = base_wait_sec * (2 ** attempt) + random.uniform(0, 1)
                    print(f"   [{e} - waiting {backoff_time:.1f}s before retry {attempt+2}/{retry_count}]")
                    time.sleep(backoff_time)
                    continue
                
                # If all retries fail, re-raise the final exception
                raise RateLimitError(f"Rate limit exceeded after {retry_count} retries.") from e

            except APIError as e:
                # Re-raise other API errors immediately
                raise e

        # This part should not be reachable if logic is correct, but as a fallback:
        raise APIError(f"Request failed after {retry_count} retries.")
    
    # ========== Account Methods ==========
    
    def get_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        return self._request("GET", "/portfolio/balance")
    
    def get_positions(self) -> List[Position]:
        """Get all current positions."""
        data = self._request("GET", "/portfolio/positions")
        return [Position(**p) for p in data.get("market_positions", [])]
    
    # ========== Market Methods ==========
    
    def get_markets(
        self,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None,
        event_ticker: Optional[str] = None,
        series_ticker: Optional[str] = None,
        min_close_ts: Optional[int] = None,
        max_close_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get markets with optional filters.
        
        Args:
            status: Market status filter (open, closed, settled)
            limit: Max results per page (1-200)
            cursor: Pagination cursor
            event_ticker: Filter by event
            series_ticker: Filter by series
            min_close_ts: Minimum close timestamp
            max_close_ts: Maximum close timestamp
            
        Returns:
            Dict with 'markets' list and 'cursor' for pagination
        """
        params = {
            "status": status,
            "limit": min(limit, 200),
        }
        
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if min_close_ts:
            params["min_close_ts"] = min_close_ts
        if max_close_ts:
            params["max_close_ts"] = max_close_ts
        
        return self._request("GET", "/markets", params=params)
    
    def get_all_markets(self, max_pages: int = 5, **kwargs) -> List[Market]:
        """
        Get markets with automatic pagination.
        PATCHED: Limited to max_pages to avoid rate limits.
        
        Returns:
            List of Market objects
        """
        all_markets = []
        cursor = None
        page = 0
        
        while page < max_pages:
            print(f"   Fetching page {page + 1}...")
            response = self.get_markets(cursor=cursor, **kwargs)
            markets = response.get("markets", [])
            all_markets.extend([Market.from_api(m) for m in markets])
            
            cursor = response.get("cursor")
            if not cursor or not markets:
                break
            
            page += 1
        
        if page >= max_pages:
            print(f"   [Stopped at {max_pages} pages to respect rate limits]")
        
        return all_markets
    
    def get_market(self, ticker: str) -> Market:
        """Get a specific market by ticker."""
        data = self._request("GET", f"/markets/{ticker}")
        return Market.from_api(data.get("market", {}))
    
    def get_events(
        self,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get events (groups of related markets)."""
        params = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/events", params=params)
    
    # ========== Trading Methods ==========
    
    def place_order(
        self,
        ticker: str,
        side: str,  # "yes" or "no"
        action: str,  # "buy" or "sell"
        count: int,
        type: str = "limit",  # "limit" or "market"
        yes_price: Optional[int] = None,  # Price in cents (1-99)
        no_price: Optional[int] = None,
        expiration_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Place an order on a market.
        
        Args:
            ticker: Market ticker
            side: "yes" or "no"
            action: "buy" or "sell"
            count: Number of contracts
            type: Order type ("limit" or "market")
            yes_price: Limit price for yes contracts (cents)
            no_price: Limit price for no contracts (cents)
            expiration_ts: Order expiration timestamp
            
        Returns:
            Order response with order_id
        """
        order = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": type,
        }
        
        if yes_price is not None:
            order["yes_price"] = yes_price
        if no_price is not None:
            order["no_price"] = no_price
        if expiration_ts:
            order["expiration_ts"] = expiration_ts
        
        return self._request("POST", "/portfolio/orders", json=order)
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel a pending order."""
        return self._request("DELETE", f"/portfolio/orders/{order_id}")
    
    def get_orders(
        self,
        ticker: Optional[str] = None,
        status: str = "resting",
    ) -> List[Dict[str, Any]]:
        """Get orders with optional filters."""
        params = {"status": status}
        if ticker:
            params["ticker"] = ticker
        data = self._request("GET", "/portfolio/orders", params=params)
        return data.get("orders", [])
    
    # ========== Exchange Info ==========
    
    def get_exchange_status(self) -> Dict[str, Any]:
        """Get exchange status (trading hours, maintenance)."""
        return self._request("GET", "/exchange/status")


# ========== Exceptions ==========

class KalshiError(Exception):
    """Base exception for Kalshi client errors."""
    pass

class AuthenticationError(KalshiError):
    """Raised when API authentication fails (401)."""
    pass

class RateLimitError(KalshiError):
    """Raised when rate limits are exceeded (429)."""
    pass

class APIError(KalshiError):
    """Raised for other client-side or server-side API errors (4xx, 5xx)."""
    pass
