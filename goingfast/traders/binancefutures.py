from logging import Logger
from os import environ

import numpy as np
import pyfiglet
from binance.enums import (
    KLINE_INTERVAL_5MINUTE,
    SIDE_BUY,
    SIDE_SELL,
    FUTURE_ORDER_TYPE_MARKET,
    ORDER_RESP_TYPE_RESULT,
    FUTURE_ORDER_TYPE_STOP_MARKET,
    FUTURE_ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC,
)
from binance.exceptions import BinanceAPIException
from functional import seq

from goingfast import BaseTrader, Actions
from goingfast.traders.helpers import get_candles, get_binance_client, atr

MINIMUM_ATR_VALUE = environ.get('MINIMUM_ATR_VALUE')
MINIMUM_ATR_IN_PERCENT = environ.get('MINIMUM_ATR_IN_PERCENT')
SYMBOL = environ.get('SYMBOL', 'BTCUSDT')
PRICE_PRECISION = int(environ.get('PRICE_PRECISION', '1'))
QTY_PRECISION = int(environ.get('QTY_PRECISION', '3'))
LEVERAGE = int(environ.get('LEVERAGE', '100'))


class BinanceFutures(BaseTrader):
    __name__ = 'binance-futures'

    def __init__(
        self,
        action: Actions,
        quantity: int,
        logger: Logger,
        metadata: dict = None,
        symbol: str = SYMBOL,
        price_precision: int = PRICE_PRECISION,
        qty_precision: int = QTY_PRECISION,
        leverage: int = LEVERAGE,
    ):
        super().__init__(action, quantity, logger, metadata)

        self.last_price = None
        self.atr = None
        self.hl2 = None
        self.ohlcv = None
        self.symbol = symbol
        self.price_precision = price_precision
        self.qty_precision = qty_precision
        self.leverage = leverage
        self.binance_client = get_binance_client()

        # Misc
        self.stop_order = None

    @property
    def quantity_in_asset(self) -> str:
        q = float(self.quantity) / float(self.last_price)
        return self.format_number(q, precision=self.qty_precision)

    @property
    def minimum_atr_value(self) -> float:
        if MINIMUM_ATR_VALUE:
            return float(MINIMUM_ATR_VALUE)

        if not MINIMUM_ATR_IN_PERCENT:
            raise ValueError('MINIMUM_ATR_IN_PERCENT is not set')

        atr_in_percent = float(MINIMUM_ATR_IN_PERCENT) / 100
        return float(self.last_price) * atr_in_percent

    @property
    def stop_price(self) -> str | None:
        if self.action == Actions.LONG:
            return self.format_number(number=self.last_price - self.minimum_atr_value, precision=self.price_precision)
        elif self.action == Actions.SHORT:
            return self.format_number(number=self.last_price + self.minimum_atr_value, precision=self.price_precision)
        return None

    @property
    def tp_price(self) -> str | None:
        if self.action == Actions.LONG:
            return self.format_number(number=self.last_price + self.minimum_atr_value, precision=self.price_precision)
        elif self.action == Actions.SHORT:
            return self.format_number(number=self.last_price - self.minimum_atr_value, precision=self.price_precision)
        return None

    @property
    def entry_order_id(self) -> str | None:
        if not self.entry_order:
            return None
        return self.entry_order.get('orderId')

    @property
    def entry_executed_qty(self) -> float | None:
        if not self.entry_order:
            return None
        return float(self.entry_order.get('executedQty'))

    @property
    def stop_order_id(self) -> str | None:
        if not self.stop_order:
            return None
        return self.stop_order.get('orderId')

    @property
    def exit_order_id(self) -> str | None:
        if not self.exit_order:
            return None
        return self.exit_order.get('orderId')

    async def pre_entry(self):
        title = pyfiglet.figlet_format(f'{self.__name__.title()}')
        print(title)

        # Get Candles
        self.ohlcv, self.hl2 = await get_candles(
            client=self.binance_client, symbol=self.symbol, timeframe=KLINE_INTERVAL_5MINUTE
        )

        # ATR
        highs = np.array(seq(self.ohlcv).map(lambda x: x[1]).to_list())
        lows = np.array(seq(self.ohlcv).map(lambda x: x[2]).to_list())
        closes = np.array(seq(self.ohlcv).map(lambda x: x[3]).to_list())
        self.atr = atr(highs=highs, lows=lows, closes=closes, period=14)

        # Last Price
        self.last_price = closes[-1]

        self.logger.info(f'{self.__name__} - {self.action} - Initializing..')
        self.logger.info(f'{self.__name__} - {self.action} - Symbol: {self.symbol}')
        self.logger.info(f'{self.__name__} - {self.action} - Quantity: {self.quantity}')
        self.logger.info(f'{self.__name__} - {self.action} - Quantity (Asset): {self.quantity_in_asset}')
        self.logger.info(f'{self.__name__} - {self.action} - Last Price: {self.last_price}')
        self.logger.info(f'{self.__name__} - {self.action} - Stop Price: {self.stop_price}')
        self.logger.info(f'{self.__name__} - {self.action} - TP Price: {self.tp_price}')
        self.logger.info(f'{self.__name__} - {self.action} - ATR: {self.atr[-1]}')
        self.logger.info(f'{self.__name__} - {self.action} - Minimum ATR Value: {self.minimum_atr_value}')

        # Check if there's an open position
        orders = await self.binance_client.futures_get_open_orders(symbol=self.symbol)
        print(orders)

        try:
            assert len(orders) == 0, f'{self.__name__} - {self.action} - There is an open position, bailed out..'
            assert self.atr[-1] > self.minimum_atr_value, f'{self.__name__} - {self.action} - ATR is too small'
        except AssertionError as exc:
            await self.binance_client.close_connection()
            raise exc

        # Set Leverage
        try:
            await self.binance_client.futures_change_margin_type(symbol=self.symbol, marginType='CROSSED')
            await self.binance_client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
        except BinanceAPIException:
            self.logger.info(
                f'{self.__name__} - {self.action} - Margin is already CROSSED and leverage is {self.leverage}'
            )

        self.logger.info(f'{self.__name__} - {self.action} - Pre-entry passed, ready to trade')

    async def long_entry(self):
        await self.pre_entry()

        # Create Entry Order
        self.entry_order = await self.binance_client.futures_create_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=FUTURE_ORDER_TYPE_MARKET,
            quantity=self.quantity_in_asset,
            newOrderRespType=ORDER_RESP_TYPE_RESULT,
        )
        self.logger.info(f'{self.__name__} - {self.action} - Entry Order ID: {self.entry_order_id}')
        self.logger.info(f'{self.__name__} - {self.action} - Executed Qty: {self.entry_executed_qty}')

        await self.long_exit()

    async def long_exit(self):
        # Create Stop Order
        self.stop_order = await self.binance_client.futures_create_order(
            symbol=self.symbol,
            side=SIDE_SELL,
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            quantity=self.format_number(self.entry_executed_qty, precision=self.qty_precision),
            stopPrice=self.stop_price,
            newOrderRespType=ORDER_RESP_TYPE_RESULT,
        )
        self.logger.info(f'{self.__name__} - {self.action} - Stop Order ID: {self.stop_order_id}')

        # Create TP Order
        self.exit_order = await self.binance_client.futures_create_order(
            symbol=self.symbol,
            side=SIDE_SELL,
            type=FUTURE_ORDER_TYPE_LIMIT,
            quantity=self.format_number(self.entry_executed_qty, precision=self.qty_precision),
            price=self.tp_price,
            newOrderRespType=ORDER_RESP_TYPE_RESULT,
            timeInForce=TIME_IN_FORCE_GTC,
        )
        self.logger.info(f'{self.__name__} - {self.action} - Exit Order ID: {self.exit_order_id}')

        await self.binance_client.close_connection()

    async def short_entry(self):
        await self.pre_entry()

        # Create Entry Order
        self.entry_order = await self.binance_client.futures_create_order(
            symbol=self.symbol,
            side=SIDE_SELL,
            type=FUTURE_ORDER_TYPE_MARKET,
            quantity=self.format_number(self.quantity, precision=self.qty_precision),
            newOrderRespType=ORDER_RESP_TYPE_RESULT,
        )
        self.logger.info(f'{self.__name__} - {self.action} - Entry Order ID: {self.entry_order_id}')
        self.logger.info(f'{self.__name__} - {self.action} - Executed Qty: {self.entry_executed_qty}')

        await self.short_exit()

    async def short_exit(self):
        # Create Stop Order
        self.stop_order = await self.binance_client.futures_create_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            quantity=self.format_number(self.entry_executed_qty, precision=self.qty_precision),
            stopPrice=self.stop_price,
            newOrderRespType=ORDER_RESP_TYPE_RESULT,
        )
        self.logger.info(f'{self.__name__} - {self.action} - Stop Order ID: {self.stop_order_id}')

        # Create TP Order
        self.exit_order = await self.binance_client.futures_create_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=FUTURE_ORDER_TYPE_LIMIT,
            quantity=self.format_number(self.entry_executed_qty, precision=self.qty_precision),
            price=self.tp_price,
            newOrderRespType=ORDER_RESP_TYPE_RESULT,
        )
        self.logger.info(f'{self.__name__} - {self.action} - Exit Order ID: {self.exit_order_id}')

        await self.binance_client.close_connection()
