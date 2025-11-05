# Basana
#
# Copyright 2022 Gabriel Martin Becedillas Ruiz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
【中文说明】Binance交易所客户端模块
【功能描述】提供Binance加密货币交易所的完整客户端接口，支持现货、保证金交易和实时数据订阅
【使用场景】用于连接Binance交易所进行实时交易、数据获取和事件处理
【模块特性】
- 支持现货、全仓保证金、逐仓保证金账户操作
- 提供WebSocket实时数据订阅（K线、订单簿、交易等）
- 支持REST API查询（余额、订单、交易对信息等）
- 集成事件分发器，支持异步事件处理
【注意事项】需要配置API密钥和密钥，遵守Binance API使用限制
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union
import dataclasses

import aiohttp

from . import client, helpers, order_book, order_book_diff, trades, spot, cross_margin, isolated_margin, \
    websocket_mgr
from basana.core import bar, dispatcher, enums, token_bucket
from basana.core.pair import Pair, PairInfo


BarEventHandler = bar.BarEventHandler
Error = client.Error
OrderBookDiff = order_book_diff.OrderBookDiff
OrderBookDiffEvent = order_book_diff.OrderBookDiffEvent
OrderBookDiffEventHandler = order_book_diff.OrderBookDiffEventHandler
OrderOperation = enums.OrderOperation
PartialOrderBook = order_book.PartialOrderBook
PartialOrderBookEvent = order_book.PartialOrderBookEvent
PartialOrderBookEventHandler = order_book.PartialOrderBookEventHandler
TradeEvent = trades.TradeEvent
TradeEventHandler = trades.TradeEventHandler

# For backwards compatibility.
OrderBookEvent = order_book.PartialOrderBookEvent
OrderBookEventHandler = order_book.PartialOrderBookEventHandler


@dataclasses.dataclass(frozen=True)
class PairInfoEx(PairInfo):
    """
    【中文说明】扩展交易对信息类
    【功能描述】在基础PairInfo基础上增加权限信息，提供完整的Binance交易对信息
    【使用场景】用于获取交易对的精度信息和账户权限
    【继承关系】继承自PairInfo，增加permissions字段
    【注意事项】数据类，不可变对象
    """

    #: 【中文说明】账户和交易对权限列表
    #: 【功能描述】包含该交易对支持的操作权限，如现货交易、保证金交易等
    #: 【权限示例】["SPOT", "MARGIN", "TRD_GRP_003"]等
    permissions: List[str]


class Exchange:
    """
    【中文说明】Binance交易所客户端类
    【功能描述】提供Binance加密货币交易所的完整客户端功能，支持REST API和WebSocket连接
    【使用场景】用于连接Binance交易所进行交易、数据订阅和账户管理
    【核心功能】
    - 实时数据订阅：K线、订单簿、交易数据等
    - 账户管理：现货、全仓保证金、逐仓保证金账户
    - 交易对信息：精度、权限、符号转换等
    - 订单簿查询：买卖价、深度信息等
    【注意事项】需要配置API密钥和密钥，遵守Binance API使用限制
    """

    def __init__(
            self, dispatcher: dispatcher.EventDispatcher, api_key: Optional[str] = None,
            api_secret: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None,
            tb: Optional[token_bucket.TokenBucketLimiter] = None, config_overrides: dict = {}
    ):
        """
        【中文说明】初始化Binance交易所客户端
        【功能描述】创建Binance交易所客户端实例，配置API认证和连接参数
        【参数说明】
        - dispatcher: 事件分发器，用于处理异步事件
        - api_key: API密钥，可选，未设置时只能使用公共接口
        - api_secret: API密钥，可选，未设置时只能使用公共接口
        - session: HTTP客户端会话，可选，用于复用连接
        - tb: 令牌桶限流器，可选，用于控制请求频率
        - config_overrides: 配置覆盖字典，可选，用于自定义配置参数
        """
        self._dispatcher = dispatcher
        self._cli = client.APIClient(
            api_key=api_key, api_secret=api_secret, session=session, tb=tb, config_overrides=config_overrides
        )
        self._session = session
        self._tb = tb
        self._config_overrides = config_overrides
        self._symbol_info: Dict[str, PairInfoEx] = {}  # 【中文说明】符号到交易对信息的映射缓存
        self._symbol_to_pair: Dict[str, Pair] = {}  # 【中文说明】符号到Pair对象的映射缓存
        self._ws_mgr = websocket_mgr.WebsocketManager(
            dispatcher, self._cli, session=session, config_overrides=config_overrides
        )

    def subscribe_to_bar_events(
            self, pair: Pair, bar_duration: Union[int, str], event_handler: BarEventHandler,
            skip_first_bar: bool = True, flush_delay: float = 1
    ):
        """
        Registers an async callable that will be called when a new bar is available.

        Works as defined in https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-streams but only closed
        klines are reported.

        :param pair: The trading pair.
        :param bar_duration: The bar duration. One of 1s, 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M.
        :type bar_duration: str
        :param event_handler: An async callable that receives a BarEvent.
        :param skip_first_bar: Ignored. It will be removed in a future version.
        :param flush_delay: Ignored. It will be removed in a future version.
        """
        # TODO: Deprecate support for bar_duration as int.
        # TODO: Remove skip_first_bar and flush_delay.
        interval = {
            # Supporting interval as int for backwards compatibility reasons.
            1: "1s",
            60: "1m",
            3 * 60: "3m",
            5 * 60: "5m",
            15 * 60: "15m",
            30 * 60: "30m",
            3600: "1h",
            2 * 3600: "2h",
            4 * 3600: "4h",
            6 * 3600: "6h",
            8 * 3600: "8h",
            12 * 3600: "12h",
            86400: "1d",
            3 * 86400: "3d",
            7 * 86400: "1w",
            31 * 86400: "1M",
            # Once support for interval as int is removed, this should be simplified.
            "1s": "1s",
            "1m": "1m",
            "3m": "3m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "2h": "2h",
            "4h": "4h",
            "6h": "6h",
            "8h": "8h",
            "12h": "12h",
            "1d": "1d",
            "3d": "3d",
            "1w": "1w",
            "1M": "1M",
        }.get(bar_duration)
        assert interval, "Invalid bar_duration"

        self._ws_mgr.subscribe_to_bar_events(pair, interval, event_handler)

    def subscribe_to_order_book_events(
            self, pair: Pair, event_handler: PartialOrderBookEventHandler, depth: int = 10, interval: int = 1000
    ):
        """
        Registers an async callable that will be called with the top bids/asks of the order book.

        Works as defined in
        https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams#partial-book-depth-streams

        :param pair: The trading pair.
        :param event_handler: An async callable that receives a PartialOrderBookEvent.
        :param depth: The order book depth. Valid values are: 5, 10, 20.
        :param interval: The update interval in milliseconds. Valid values are: 1000 (1s), 100 (100ms).
        """

        self._ws_mgr.subscribe_to_order_book_events(pair, event_handler, depth=depth, interval=interval)

    def subscribe_to_order_book_diff_events(
            self, pair: Pair, event_handler: OrderBookDiffEventHandler, interval: int = 1000
    ):
        """
        Registers an async callable that will be called with depth updates.

        Works as defined in
        https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams#diff-depth-stream

        :param pair: The trading pair.
        :param event_handler: An async callable that receives an OrderBookDiffEvent.
        :param interval: The update interval in milliseconds. Valid values are: 1000 (1s), 100 (100ms).
        """

        self._ws_mgr.subscribe_to_order_book_diff_events(pair, event_handler, interval=interval)

    def subscribe_to_trade_events(self, pair: Pair, event_handler: TradeEventHandler):
        """
        Registers an async callable that will be called for every new trade.

        Works as defined in https://binance-docs.github.io/apidocs/spot/en/#trade-streams.

        :param pair: The trading pair.
        :param event_handler: An async callable that receives a TradeEvent.
        """

        self._ws_mgr.subscribe_to_trade_events(pair, event_handler)

    async def get_pair_info(self, pair: Pair) -> PairInfoEx:
        """
        Returns information about a trading pair.

        :param pair: The trading pair.
        """

        return await self._get_pair_info(helpers.pair_to_symbol(pair))

    async def symbol_to_pair(self, symbol: str) -> Pair:
        """
        Returns the pair for a given symbol.

        :param symbol: The symbol.
        """
        ret = self._symbol_to_pair.get(symbol)
        if ret is None:
            await self._get_pair_info(symbol)
            ret = self._symbol_to_pair[symbol]
        return ret

    async def get_bid_ask(self, pair: Pair) -> Tuple[Decimal, Decimal]:
        """
        Returns the current best bid and ask prices.

        :param pair: The trading pair.
        """
        order_book = await self.get_order_book(pair, limit=1)
        return Decimal(order_book.bids[0].price), Decimal(order_book.asks[0].price)

    async def get_order_book(self, pair: Pair, limit: Optional[int] = None) -> order_book.PartialOrderBook:
        """
        Returns the order book for a given trading pair.

        :param pair: The trading pair.
        :param limit: The maximum number of levels to return.
        """
        return order_book.PartialOrderBook(
            pair,
            await self._cli.get_order_book(helpers.pair_to_symbol(pair), limit=limit)
        )

    @property
    def spot_account(self) -> spot.Account:
        """Returns the spot account."""
        return spot.Account(self._cli.spot_account, self._ws_mgr)

    @property
    def cross_margin_account(self) -> cross_margin.Account:
        """Returns the cross margin account."""
        return cross_margin.Account(self._cli.cross_margin_account, self._ws_mgr)

    @property
    def isolated_margin_account(self) -> isolated_margin.Account:
        """Returns the isolated margin account."""
        return isolated_margin.Account(self._cli.isolated_margin_account, self._ws_mgr)

    async def _get_pair_info(self, symbol: str) -> PairInfoEx:
        ret = self._symbol_info.get(symbol)
        if ret is None:
            exchange_info = await self._cli.get_exchange_info(symbol)
            symbols = exchange_info["symbols"]
            assert len(symbols) == 1, "More than 1 symbol found"
            symbol_info = symbols[0]
            price_filter = get_filter_from_symbol_info(symbol_info, "PRICE_FILTER")
            assert price_filter, f"PRICE_FILTER not found for {symbol}"
            lot_size = get_filter_from_symbol_info(symbol_info, "LOT_SIZE")
            assert lot_size, f"LOT_SIZE not found for {symbol}"
            ret = PairInfoEx(
                base_precision=get_precision_from_step_size(lot_size["stepSize"]),
                quote_precision=get_precision_from_step_size(price_filter["tickSize"]),
                permissions=symbol_info.get("permissions")
            )
            self._symbol_info[symbol] = ret
            self._symbol_to_pair[symbol_info["symbol"]] = Pair(symbol_info["baseAsset"], symbol_info["quoteAsset"])
        return ret


def get_filter_from_symbol_info(symbol_info: dict, filter_type: str) -> Optional[dict]:
    filters = symbol_info["filters"]
    price_filters = [filter for filter in filters if filter["filterType"] == filter_type]
    return None if not price_filters else price_filters[0]


def get_precision_from_step_size(step_size: str) -> int:
    return int(-Decimal(step_size).log10() / Decimal(10).log10())
