import asyncio
import json
import logging
import websockets
from datetime import datetime

# Configure logging for debugging output
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RECONNECT_DELAY = 5  # seconds before attempting to reconnect

# Global dictionary to store bid and ask data per symbol
orderbook_data = {}

def build_combined_url():
    """
    Build the WebSocket URL for Crypto.com market data.
    """
    url = 'wss://stream.crypto.com/exchange/v1/market'
    return url

async def stream_orderbook(pairs):
    """
    Connect to Crypto.com's WebSocket stream for order book updates
    and process bid/ask data.
    """
    url = build_combined_url()
    while True:
        try:
            logger.info(f"Connecting to Crypto.com WebSocket stream.")
            async with websockets.connect(url) as ws:
                # Subscribe to each pair
                for pair in pairs:
                    subscribe_message = {
                        "id": 1,
                        "method": "subscribe",
                        "params": {
                            "channels": [f"ticker.{pair.upper()}"]
                        }
                    }
                    await ws.send(json.dumps(subscribe_message))
                    logger.info(f"Subscribed to ticker.{pair.upper()}")

                while True:
                    # Wait for a message with a timeout
                    response = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(response)
                    
                    # Only process 'ticker' messages
                    if 'method' in data and data['method'] == 'subscribe':
                        ticker_info = data.get('result', {}).get('data', [{}])[0]
                        symbol = ticker_info.get("i")  # instrument_name (e.g., BTCUSD-PERP)
                        if not symbol:
                            logger.debug("Message without symbol received.")
                            continue

                        # Extract bid and ask prices
                        try:
                            best_bid = ticker_info.get("b", "N/A")
                            best_ask = ticker_info.get("k", "N/A")
                        except Exception as e:
                            logger.error(f"Error parsing bids/asks for {symbol}: {e}")
                            continue

                        orderbook_data[symbol] = {
                            "best_bid": best_bid, 
                            "best_ask": best_ask
                        }
                        logger.debug(f"Updated {symbol}: Bid={best_bid}, Ask={best_ask}")

        except Exception as e:
            logger.error(f"Error in stream: {e}. Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

def format_orderbook_output(pair):
    """
    Formats the bid and ask output for a given pair.
    """
    data = orderbook_data.get(pair.upper())
    if data:
        return f"{pair:10} | Bid: {data['best_bid']} | Ask: {data['best_ask']}"
    else:
        return f"{pair:10} | Data not available yet."

async def display_orderbook(pairs, interval=1):
    """
    Periodically prints the bid and ask data for the specified crypto pairs.
    """
    while True:
        print("\n" + "=" * 50)
        print(f"Order Book Data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        for pair in pairs:
            print(format_orderbook_output(pair))
        await asyncio.sleep(interval)

async def main(crypto_pairs=None):
    """
    Main function to start the orderbook stream and display tasks concurrently.
    """
    if crypto_pairs is None:
        crypto_pairs = ["BTCUSD-PERP", "ETHUSD-PERP", "LTCUSD-PERP"]  # Default pairs

    # Run both the stream and display tasks concurrently.
    await asyncio.gather(
        stream_orderbook(crypto_pairs),
        display_orderbook(crypto_pairs)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted. Exiting...")
