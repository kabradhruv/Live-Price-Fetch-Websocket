import asyncio
import json
import logging
import websockets
from datetime import datetime

# Configure logging: DEBUG for maximum verbosity.
# logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logging.basicConfig(level=logging.WARNING)  # Suppress DEBUG logs
logger = logging.getLogger(__name__)

KRAKEN_WS_URL = "wss://ws.kraken.com"
RECONNECT_DELAY = 5  # seconds

# Global dictionary to store ticker data for each pair.
ticker_data = {}

async def subscribe(ws, pairs):
    """
    Sends a subscription message to Kraken for order book data.
    """
    sub_request = {
        "event": "subscribe",
        "pair": pairs,
        "subscription": {
            "name": "book"
        }
    }
    await ws.send(json.dumps(sub_request))
    logger.debug(f"Sent subscription request: {sub_request}")

async def stream_tickers(pairs):
    """
    Connects to Kraken's WebSocket, subscribes to the order book feed,
    and processes incoming messages.
    """
    while True:
        try:
            logger.info(f"Connecting to Kraken WebSocket at {KRAKEN_WS_URL}")
            async with websockets.connect(KRAKEN_WS_URL) as ws:
                await subscribe(ws, pairs)
                async for message in ws:
                    logger.debug(f"Raw message received: {message}")
                    process_message(message)
        except Exception as e:
            logger.error(f"Error in Kraken stream: {e}. Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

def process_message(message):
    """
    Processes incoming messages from Kraken.
    Kraken sends event messages (dicts) and data messages (lists).
    Data messages have the format: [channelID, data, pair, ...].
    """
    try:
        parsed = json.loads(message)
    except Exception as e:
        logger.error(f"Failed to parse message: {message} | Error: {e}")
        return

    # Process event messages.
    if isinstance(parsed, dict):
        event = parsed.get("event")
        if event:
            logger.debug(f"Event message: {parsed}")
        return

    # Process data messages.
    if isinstance(parsed, list) and len(parsed) >= 3:
        logger.debug(f"Data message received: {parsed}")
        try:
            pair = parsed[-1]
            data = parsed[1]
            if not isinstance(data, dict):
                logger.debug(f"Unexpected data structure: {data}")
                return

            # Initialize ticker_data if not already present.
            if pair not in ticker_data:
                ticker_data[pair] = {"bid": None, "ask": None}

            # For snapshots, keys "as" (asks) and "bs" (bids) are provided.
            if "as" in data:
                ask_snapshot = data["as"]
                if ask_snapshot and isinstance(ask_snapshot, list):
                    ticker_data[pair]["ask"] = float(ask_snapshot[0][0])
            if "bs" in data:
                bid_snapshot = data["bs"]
                if bid_snapshot and isinstance(bid_snapshot, list):
                    ticker_data[pair]["bid"] = float(bid_snapshot[0][0])

            # For incremental updates, keys "a" (ask updates) and "b" (bid updates).
            if "a" in data:
                ask_update = data["a"]
                if ask_update and isinstance(ask_update, list):
                    ticker_data[pair]["ask"] = float(ask_update[0][0])
            if "b" in data:
                bid_update = data["b"]
                if bid_update and isinstance(bid_update, list):
                    ticker_data[pair]["bid"] = float(bid_update[0][0])

            logger.debug(f"Updated {pair}: {ticker_data[pair]}")
        except Exception as e:
            logger.error(f"Error processing data message: {parsed} | Error: {e}")
    else:
        logger.debug(f"Ignored unexpected message format: {parsed}")

def format_ticker_output(pair):
    """
    Returns a formatted string for the given pair's ticker data.
    """
    data = ticker_data.get(pair)
    if data and data["bid"] is not None and data["ask"] is not None:
        return f"{pair:10} | {data['bid']:>12,.2f} | {data['ask']:>12,.2f}"
    else:
        return f"{pair:10} | {'--':>12} | {'--':>12}"

async def display_tickers(pairs, interval=1):
    """
    Periodically prints the ticker data for each provided Kraken pair in a formatted table.
    """
    header = f"{'Pair':10} | {'Bid':>12} | {'Ask':>12}"
    separator = "-" * (len(header) + 2)
    while True:
        print("\n" + separator)
        print(f"Ticker Data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(separator)
        print(header)
        print(separator)
        for pair in pairs:
            print(format_ticker_output(pair))
        print(separator)
        await asyncio.sleep(interval)

async def main(kraken_pairs=None):
    """
    Starts the Kraken stream and ticker display concurrently.
    Provide Kraken pair names, e.g., ["XBT/USD", "ETH/USD"].
    """
    if kraken_pairs is None:
        kraken_pairs = ["XBT/USD", "ETH/USD"]

    await asyncio.gather(
        stream_tickers(kraken_pairs),
        display_tickers(kraken_pairs)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Kraken WebSocket client stopped.")
