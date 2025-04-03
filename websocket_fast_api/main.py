import asyncio
import json
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

# Import streaming functions and global data caches from each exchange module.
from binance_websocket import stream_tickers as stream_binance, ticker_data as binance_ticker
from kraken_websocket import stream_tickers as stream_kraken, ticker_data as kraken_ticker
from coinbase_websocket import stream_tickers as stream_coinbase, ticker_data as coinbase_ticker
from cryptocom_websocket import stream_orderbook as stream_cryptocom, orderbook_data as cryptocom_data

PROFIT_THRESHOLD = 0.05

# Global list of pairs in a common format.
GLOBAL_PAIRS = [
"BTC/USD",
"ETH/USD",
"SOL/USD",
"XRP/USD",
"DOT/USD",
"LINK/USD",
"ADA/USD",
"DOGE/USD",
"SHIB/USD",
"SOL/BTC",
"SOL/ETH",
"ETH/BTC",
"MATIC/BTC",
"POL/BTC",
"POL/ETH",
"AVAX/USD",
"DOT/USD",
"ALGO/USD",
"ATOM/USD"
]

def map_pair(global_pair, exchange):
    """
    Maps a global pair (e.g. "BTC/USD") to the exchange-specific format.
    """
    try:
        base, quote = global_pair.split("/")
    except ValueError:
        return global_pair

    if exchange.lower() == "binance":
        if quote.upper() == "USD":
            quote = "USDT"
        return f"{base.upper()}{quote.upper()}"
    elif exchange.lower() == "kraken":
        if base.upper() == "BTC":
            base = "XBT"
        return f"{base.upper()}/{quote.upper()}"
    elif exchange.lower() == "coinbase":
        return f"{base.upper()}-{quote.upper()}"
    elif exchange.lower() == "cryptocom":
        return f"{base.upper()}{quote.upper()}-PERP"
    else:
        return global_pair

def build_exchange_pairs(global_pairs, exchange):
    """
    Returns a list of exchange-specific pairs for the given global pairs.
    """
    return [map_pair(pair, exchange) for pair in global_pairs]

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the main HTML page."""
    with open("index.html", "r") as f:
        html_content = f.read()
    logging.debug("Served index.html")
    return html_content

def print_arbitrage_table(result):
    """
    Prints the entire prices table and arbitrage table in a formatted way using Rich.
    """
    from rich.console import Console
    from rich.table import Table
    import os

    console = Console()
    # Clear the console for a real-time refresh effect.
    os.system("cls" if os.name == "nt" else "clear")
    
    timestamp = result.get("timestamp", "")
    
    # Prices Table
    prices_table = Table(title=f"Live Prices - {timestamp}", show_header=True, header_style="bold cyan")
    prices_table.add_column("Pair", justify="center", style="bold")
    prices_table.add_column("Binance Bid/Ask", justify="center", style="yellow")
    prices_table.add_column("Kraken Bid/Ask", justify="center", style="yellow")
    prices_table.add_column("Coinbase Bid/Ask", justify="center", style="yellow")
    prices_table.add_column("Crypto.com Bid/Ask", justify="center", style="yellow")
    
    for item in result.get("prices", []):
        pair = item.get("pair", "")
        binance = item.get("binance", {})
        kraken = item.get("kraken", {})
        coinbase = item.get("coinbase", {})
        cryptocom = item.get("cryptocom", {})
        
        binance_bid = binance.get("bid", "N/A")
        binance_ask = binance.get("ask", "N/A")
        kraken_bid = kraken.get("bid", "N/A")
        kraken_ask = kraken.get("ask", "N/A")
        coinbase_bid = coinbase.get("bid", "N/A")
        coinbase_ask = coinbase.get("ask", "N/A")
        cryptocom_bid = cryptocom.get("best_bid", "N/A")
        cryptocom_ask = cryptocom.get("best_ask", "N/A")
        
        prices_table.add_row(
            pair,
            f"{binance_bid} / {binance_ask}",
            f"{kraken_bid} / {kraken_ask}",
            f"{coinbase_bid} / {coinbase_ask}",
            f"{cryptocom_bid} / {cryptocom_ask}"
        )
    
    # Arbitrage Opportunities Table
    arb_table = Table(title="Arbitrage Opportunities", show_header=True, header_style="bold magenta")
    arb_table.add_column("Pair", justify="center", style="bold")
    arb_table.add_column("Buy Exchange", justify="center", style="green")
    arb_table.add_column("Sell Exchange", justify="center", style="red")
    arb_table.add_column("Buy Price", justify="right", style="yellow")
    arb_table.add_column("Sell Price", justify="right", style="yellow")
    arb_table.add_column("Profit (%)", justify="right", style="bold magenta")
    
    for opp in result.get("arbitrage_opportunities", []):
        arb_table.add_row(
            opp.get("pair", ""),
            opp.get("buy_exchange", ""),
            opp.get("sell_exchange", ""),
            f"{opp.get('buy_price', 0):.6f}",
            f"{opp.get('sell_price', 0):.6f}",
            f"{opp.get('profit_pct', 0):.2f}%"
        )
    
    # Print the tables
    console.print(prices_table)
    console.print("\n")  # Blank line between tables
    console.print(arb_table)



@app.get("/stream")
async def stream():
    """
    SSE endpoint that streams the latest ticker data and arbitrage opportunities every second.
    """
    async def event_generator():
        while True:
            # Gather ticker data for each pair from global caches.
            data_list = []
            for pair in GLOBAL_PAIRS:
                binance_sym   = map_pair(pair, "binance")
                kraken_sym    = map_pair(pair, "kraken")
                coinbase_sym  = map_pair(pair, "coinbase")
                cryptocom_sym = map_pair(pair, "cryptocom")
                
                binance_data = binance_ticker.get(binance_sym, {"bid": None, "ask": None})
                kraken_data = kraken_ticker.get(kraken_sym, {"bid": None, "ask": None})
                coinbase_data = coinbase_ticker.get(coinbase_sym, {"bid": None, "ask": None})
                cryptocom_data_item = cryptocom_data.get(cryptocom_sym, {"best_bid": None, "best_ask": None})
                
                pair_info = {
                    "pair": pair,
                    "binance": binance_data,
                    "kraken": kraken_data,
                    "coinbase": coinbase_data,
                    "cryptocom": cryptocom_data_item,
                }
                data_list.append(pair_info)
            
                # Compute arbitrage opportunities for each pair.
                arbitrage_opportunities = []
                for item in data_list:
                    pair = item["pair"]
                    prices = {
                        "binance": item["binance"],
                        "kraken": item["kraken"],
                        "coinbase": item["coinbase"],
                        "cryptocom": item["cryptocom"]
                    }
                    for buy_ex, buy_data in prices.items():
                        for sell_ex, sell_data in prices.items():
                            if buy_ex == sell_ex:
                                continue
                            # Determine buy_price and sell_price. For Crypto.com, use best_ask/best_bid.
                            buy_price = buy_data.get("ask") or buy_data.get("best_ask")
                            sell_price = sell_data.get("bid") or sell_data.get("best_bid")
                            
                            if buy_price is not None and sell_price is not None:
                                try:
                                    # Convert values to float if they are not already.
                                    buy_price_float = float(buy_price)
                                    sell_price_float = float(sell_price)
                                    profit_pct = round(((sell_price_float - buy_price_float) / buy_price_float) * 100, 2)
                                    # print(profit_pct)
                                    
                                    if profit_pct >= PROFIT_THRESHOLD:
                                        arbitrage_opportunities.append({
                                            "pair": pair,
                                            "buy_exchange": buy_ex,
                                            "sell_exchange": sell_ex,
                                            "buy_price": buy_price_float,
                                            "sell_price": sell_price_float,
                                            "profit_pct": profit_pct,
                                        })
                                except ValueError:
                                    # Log conversion error and skip this pair
                                    logging.debug(f"Conversion error for pair {pair} from {buy_ex} or {sell_ex}: buy_price={buy_price}, sell_price={sell_price}")
                                    continue
            
            result = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "prices": data_list,
                "arbitrage_opportunities": arbitrage_opportunities
            }
            print_arbitrage_table(result)
            logging.debug(f"Sending data: {result}")
            yield f"data: {json.dumps(result)}\n\n"
            await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")



@app.on_event("startup")
async def startup_event():
    """
    On startup, launch background tasks to stream data from exchanges.
    """
    logging.debug("Starting background tasks for exchange streams")
    binance_pairs   = build_exchange_pairs(GLOBAL_PAIRS, "binance")
    kraken_pairs    = build_exchange_pairs(GLOBAL_PAIRS, "kraken")
    coinbase_pairs  = build_exchange_pairs(GLOBAL_PAIRS, "coinbase")
    cryptocom_pairs = build_exchange_pairs(GLOBAL_PAIRS, "cryptocom")
    
    loop = asyncio.get_event_loop()
    loop.create_task(stream_binance(binance_pairs))
    loop.create_task(stream_kraken(kraken_pairs))
    loop.create_task(stream_coinbase(coinbase_pairs))
    loop.create_task(stream_cryptocom(cryptocom_pairs))
    logging.debug("Background tasks started.")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

