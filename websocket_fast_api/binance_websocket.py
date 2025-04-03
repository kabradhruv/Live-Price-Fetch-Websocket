import asyncio
import json
import logging
import websockets
from datetime import datetime

# Configure logging for debugging output.
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RECONNECT_DELAY = 5  # seconds before attempting to reconnect

# Global dictionary to store ticker data per symbol.
ticker_data = {}

def build_combined_url(pairs):
    """
    Given a list of crypto pairs (e.g., ["BTCUSDT", "ETHUSDT"]),
    build the combined stream URL for Binance's bookTicker streams.
    The URL format is:
    wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker
    """
    # Binance expects lower-case symbols in the URL.
    streams = "/".join(f"{pair.lower()}@bookTicker" for pair in pairs)
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    return url

async def stream_tickers(pairs):
    """
    Connects to Binance's combined stream endpoint for bookTicker updates
    for the provided pairs. It will update the global ticker_data dictionary.
    """
    url = build_combined_url(pairs)
    while True:
        try:
            logger.info(f"Connecting to Binance stream: {url}")
            async with websockets.connect(url) as ws:
                while True:
                    # Wait for a message with a timeout.
                    response = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(response)
                    
                    # Combined stream messages include a "stream" and "data" field.
                    stream_data = data.get("data", {})
                    symbol = stream_data.get("s")
                    if not symbol:
                        logger.debug("Message without symbol received.")
                        continue
                    
                    # Update ticker_data with bid and ask prices.
                    try:
                        bid = float(stream_data.get("b", 0))
                        ask = float(stream_data.get("a", 0))
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

async def display_tickers(pairs, interval=2):
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
        crypto_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

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
