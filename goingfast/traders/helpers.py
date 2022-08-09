from os import environ
from typing import List

import binance
from binance.enums import HistoricalKlinesType
from functional import seq
from talib import ATR
import numpy as np

API_KEY = environ.get('API_KEY')
API_SECRET = environ.get('API_SECRET')
IS_TESTNET = True if environ.get('IS_TESTNET') == '1' else False


def get_binance_client(
    api_key: str = API_KEY, api_secret: str = API_SECRET, is_testnet: bool = IS_TESTNET
) -> binance.AsyncClient:
    """
    Get a Binance client
    """
    client = binance.AsyncClient(api_key=api_key, api_secret=api_secret, testnet=is_testnet)
    return client


async def get_aggregated_data(client: binance.AsyncClient, symbol: str) -> List[str | float]:
    """
    Get aggregated data for a list of symbols
    """

    trades = await client.futures_aggregate_trades(symbol=symbol, start_str='60 minutes ago UTC')
    volume_table = {}
    for trade in trades:
        price = float(trade.get('p'))
        quantity = float(trade.get('q'))
        volume = price * quantity

        prev = 0.0 if not volume_table.get(price) else volume_table.get(price)
        volume_table[price] = prev + volume

    sorted_volume = (
        seq(volume_table.items()).map(lambda x: [x[0], x[1]]).sorted(key=lambda x: x[1], reverse=True).to_list()
    )

    return [symbol, *sorted_volume[0]]


async def get_candles(client: binance.AsyncClient, symbol: str, timeframe: str) -> List:
    start_str = '2 days ago utc'
    klines = await client.get_historical_klines(
        symbol=symbol, interval=timeframe, start_str=start_str, klines_type=HistoricalKlinesType.FUTURES
    )
    ohlcv = seq(klines).map(lambda x: [float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])])
    hl2 = seq(ohlcv).map(lambda x: (x[1] + x[2]) / 2).to_list()
    return [ohlcv, hl2]


def atr(highs: np.array, lows: np.array, closes: np.array, period: int = 14) -> np.ndarray:
    return ATR(high=highs, low=lows, close=closes, timeperiod=period)
