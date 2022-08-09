from abc import abstractmethod
from decimal import Decimal
from os import environ
from logging import Logger
import enum
import ccxt

STOP_DELTA = Decimal(environ.get('STOP_DELTA'))
TP_DELTA = Decimal(environ.get('TP_DELTA'))
API_KEY = environ.get('API_KEY')
API_SECRET = environ.get('API_SECRET')


class Actions(enum.Enum):
    LONG = 'long'
    SHORT = 'short'


class BaseTrader:
    __name__ = 'base'
    symbol = ''
    normalized_symbol = ''

    def __init__(self, action: Actions, quantity: int, logger: Logger, metadata: dict = None):
        self.action = action
        self.quantity = quantity
        self.logger = logger
        self.metadata = metadata

        self.entry_order = dict()
        self.exit_order = dict()
        self.exit_stop_limit_order = dict()
        self.exit_stop_market_order = dict()

        self.leverage = None

    @property
    def tp_using_risk_reward_ratio(self):
        return self.metadata and self.metadata.get('rr') is not None

    @property
    def risk_reward_ratio(self):
        if self.tp_using_risk_reward_ratio:
            return Decimal(self.metadata.get('rr'))

        return None

    @property
    def stop_delta(self):
        if self.metadata and self.metadata.get('stop_delta') is not None:
            return Decimal(self.metadata.get('stop_delta')).__round__(0)

        return STOP_DELTA

    @property
    def tp_delta(self):
        # First Priority
        if self.tp_using_risk_reward_ratio and self.stop_limit_trigger_price != Decimal(0):
            tp_stop_delta = Decimal(abs(self.entry_price - self.stop_limit_trigger_price))
            tp_delta = Decimal(tp_stop_delta * self.risk_reward_ratio)
            if self.action == Actions.LONG:
                return (self.entry_price + tp_delta).__round__(0)
            elif self.action == Actions.SHORT:
                return (self.entry_price - tp_delta).__round__(0)

        # Second Priority
        if self.metadata and self.metadata.get('tp_delta') is not None:
            return Decimal(self.metadata.get('tp_delta')).__round__(0)

        # Last Priority
        return TP_DELTA

    @property
    def entry_price(self) -> Decimal:
        if not self.entry_order:
            return Decimal(0)
        return Decimal(self.entry_order.get('price'))

    @property
    def stop_limit_trigger_price(self) -> Decimal:
        if self.metadata and self.metadata.get('stop_limit_trigger_price') is not None:
            return Decimal(self.metadata.get('stop_limit_trigger_price')).__round__(0)

        if self.action == Actions.LONG:
            return self.entry_price - self.stop_delta
        elif self.action == Actions.SHORT:
            return self.entry_price + self.stop_delta
        else:
            return Decimal(0)

    @property
    def stop_limit_price(self) -> Decimal:
        if self.action == Actions.LONG:
            return self.stop_limit_trigger_price - Decimal(5)
        elif self.action == Actions.SHORT:
            return self.stop_limit_trigger_price + Decimal(5)
        else:
            return Decimal(0)

    @property
    def stop_price(self) -> Decimal | None:
        return None

    @property
    def stop_market_price(self) -> Decimal:
        if self.action == Actions.LONG:
            return self.stop_limit_trigger_price - Decimal(10)
        elif self.action == Actions.SHORT:
            return self.stop_limit_trigger_price + Decimal(10)
        else:
            return Decimal(0)

    @property
    def tp_price(self):
        if self.action == Actions.LONG:
            return self.entry_price + self.tp_delta
        elif self.action == Actions.SHORT:
            return self.entry_price - self.tp_delta
        else:
            return Decimal(0)

    @property
    def client(self):
        exc_class = getattr(ccxt, self.__name__)
        if not exc_class:
            raise NotImplementedError('This exchange is not implemented yet')

        return exc_class({'apiKey': API_KEY, 'secret': API_SECRET, 'timeout': 30000, 'enableRateLimit': True})

    @abstractmethod
    async def long_entry(self):
        raise NotImplementedError()

    @abstractmethod
    async def long_exit(self):
        raise NotImplementedError()

    @abstractmethod
    async def short_entry(self):
        raise NotImplementedError()

    @abstractmethod
    async def short_exit(self):
        raise NotImplementedError()

    async def market_buy_order(self, quantity):
        if not self.client.has['createMarketOrder']:
            raise AttributeError('The selected exchange does not support market orders')
        order = self.client.create_market_buy_order(symbol=self.normalized_symbol, amount=quantity)
        return order

    async def market_sell_order(self, quantity):
        if not self.client.has['createMarketOrder']:
            raise AttributeError('The selected exchange does not support market orders')
        order = self.client.create_market_sell_order(symbol=self.normalized_symbol, amount=quantity)
        return order

    async def limit_buy_order(self, amount, price):
        order = self.client.create_limit_buy_order(self.normalized_symbol, amount, price)
        return order

    async def limit_sell_order(self, amount, price):
        order = self.client.create_limit_sell_order(self.normalized_symbol, amount, price)
        return order

    @staticmethod
    def format_number(number, precision: int = 2) -> str:
        return '{:0.0{}f}'.format(number, precision)
