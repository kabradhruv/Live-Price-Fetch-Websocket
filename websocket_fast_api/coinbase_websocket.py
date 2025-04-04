import asyncio
import json
import logging
import websockets
from datetime import datetime

# Configure logging for debugging output
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RECONNECT_DELAY = 5  # seconds before attempting to reconnect

# Global dictionary to store ticker data per symbol
ticker_data = {}

def build_combined_url(pairs):
    """
    Given a list of crypto pairs (e.g., ["BTC-USD", "ETH-USD"]),
    build the combined stream URL for Coinbase's ticker updates.
    """
    url = 'wss://ws-feed.exchange.coinbase.com'
    return url

async def stream_tickers(pairs):
    """
    Connects to Coinbase's WebSocket stream for ticker updates
    for the provided pairs. It will update the global ticker_data dictionary.
    """
    url = build_combined_url(pairs)
    while True:
        try:
            logger.info(f"Connecting to Coinbase WebSocket stream.")
            async with websockets.connect(url) as ws:
                # Subscribe to each pair
                for pair in pairs:
                    subscribe_message = {
                        "type": "subscribe",
                        "channels": [{"name": "ticker", "product_ids": [pair]}]
                    }
                    await ws.send(json.dumps(subscribe_message))
                    logger.info(f"Subscribed to {pair}")

                while True:
                    # Wait for a message with a timeout
                    response = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(response)
                    
                    # Only process 'ticker' messages
                    if 'type' in data and data['type'] == 'ticker':
                        symbol = data.get('product_id')
                        if not symbol:
                            logger.debug("Message without symbol received.")
                            continue

                        # Extract bid and ask prices
                        try:
                            bid = float(data.get("best_bid", 0))
                            ask = float(data.get("best_ask", 0))
                        except Exception as e:
                            logger.error(f"Error parsing prices for {symbol}: {e}")
                            continue

                        ticker_data[symbol] = {"bid": bid, "ask": ask}
                        logger.debug(f"Updated {symbol}: bid={bid}, ask={ask}")

        except Exception as e:
            logger.error(f"Error in stream: {e}. Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

def format_ticker_output(pair):
    """
    Formats the ticker output for a given pair.
    """
    data = ticker_data.get(pair.upper())
    if data:
        return f"{pair:10} | Bid: {data['bid']:<12} | Ask: {data['ask']:<12}"
    else:
        return f"{pair:10} | Data not available yet."

async def display_tickers(pairs, interval=1):
    """
    Periodically prints ticker data for the specified crypto pairs.
    """
    while True:
        print("\n" + "=" * 50)
        print(f"Ticker Data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        for pair in pairs:
            print(format_ticker_output(pair))
        await asyncio.sleep(interval)

async def main(crypto_pairs=None):
    """
    Main function to start the ticker stream and display tasks concurrently.
    """
    if crypto_pairs is None:
        crypto_pairs = ["BTC-USD", "ETH-USD", "LTC-USD"]  # Default pairs

    # Run both the stream and display tasks concurrently.
    await asyncio.gather(
        stream_tickers(crypto_pairs),
        display_tickers(crypto_pairs)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted. Exiting...")
