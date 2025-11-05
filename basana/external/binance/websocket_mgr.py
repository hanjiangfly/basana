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
Binance WebSocket管理器模块

此模块提供了Binance WebSocket连接的管理功能，包括：
- WebSocket客户端管理
- 各种数据流的订阅管理
- 事件分发处理

主要类：
- WebsocketManager: WebSocket管理器类
"""

from typing import cast, Callable, Optional

import aiohttp

from . import client, order_book, order_book_diff, trades, user_data, websockets as binance_ws, klines
from basana.core import bar, dispatcher, websockets as core_ws
from basana.core.pair import Pair


class WebsocketManager:
    """WebSocket管理器类
    
    管理Binance WebSocket连接和各种数据流的订阅。
    """
    
    def __init__(
            self, dispatcher: dispatcher.EventDispatcher, api_client: client.APIClient,
            session: Optional[aiohttp.ClientSession] = None, config_overrides: dict = {}
    ):
        """初始化WebSocket管理器
        
        :param dispatcher: 事件分发器
        :param api_client: API客户端
        :param session: aiohttp客户端会话，可选
        :param config_overrides: 配置覆盖字典
        """
        self._dispatcher = dispatcher
        self._cli = api_client
        self._session = session
        self._config_overrides = config_overrides
        self._websocket: Optional[binance_ws.WebSocketClient] = None

    def subscribe_to_bar_events(self, pair: Pair, interval: str, event_handler: bar.BarEventHandler):
        """订阅K线数据事件
        
        :param pair: 交易对
        :param interval: K线时间间隔
        :param event_handler: K线事件处理器
        """
        self._subscribe_to_ws_channel_events(
            binance_ws.PublicChannel(klines.get_channel(pair, interval)),
            lambda ws_cli: klines.WebSocketEventSource(pair, ws_cli),
            cast(dispatcher.EventHandler, event_handler)
        )

    def subscribe_to_order_book_events(
            self, pair: Pair, event_handler: order_book.PartialOrderBookEventHandler, depth: int = 10,
            interval: int = 1000
    ):
        """订阅订单簿事件
        
        :param pair: 交易对
        :param event_handler: 订单簿事件处理器
        :param depth: 订单簿深度，默认为10
        :param interval: 更新间隔，默认为1000毫秒
        """
        self._subscribe_to_ws_channel_events(
            binance_ws.PublicChannel(order_book.get_channel(pair, depth, interval)),
            lambda ws_cli: order_book.WebSocketEventSource(pair, ws_cli),
            cast(dispatcher.EventHandler, event_handler)
        )

    def subscribe_to_order_book_diff_events(
            self, pair: Pair, event_handler: order_book_diff.OrderBookDiffEventHandler, interval: int = 1000
    ):
        """订阅订单簿差异事件
        
        :param pair: 交易对
        :param event_handler: 订单簿差异事件处理器
        :param interval: 更新间隔，默认为1000毫秒
        """
        self._subscribe_to_ws_channel_events(
            binance_ws.PublicChannel(order_book_diff.get_channel(pair, interval)),
            lambda ws_cli: order_book_diff.WebSocketEventSource(pair, ws_cli),
            cast(dispatcher.EventHandler, event_handler)
        )

    def subscribe_to_trade_events(self, pair: Pair, event_handler: trades.TradeEventHandler):
        """订阅交易事件
        
        :param pair: 交易对
        :param event_handler: 交易事件处理器
        """
        self._subscribe_to_ws_channel_events(
            binance_ws.PublicChannel(trades.get_channel(pair)),
            lambda ws_cli: trades.WebSocketEventSource(pair, ws_cli),
            cast(dispatcher.EventHandler, event_handler)
        )

    def subscribe_to_user_data_events(
        self, channel: binance_ws.Channel,
        event_src_factory: Callable[[core_ws.WebSocketClient], core_ws.ChannelEventSource],
        event_handler: user_data.UserDataEventHandler,
    ):
        """订阅用户数据事件
        
        :param channel: WebSocket通道
        :param event_src_factory: 事件源工厂函数
        :param event_handler: 用户数据事件处理器
        """
        self._subscribe_to_ws_channel_events(
            channel, event_src_factory, cast(dispatcher.EventHandler, event_handler)
        )

    def subscribe_to_order_events(
        self, channel: binance_ws.Channel,
        event_src_factory: Callable[[core_ws.WebSocketClient], core_ws.ChannelEventSource],
        event_handler: user_data.OrderEventHandler,
    ):
        """订阅订单事件
        
        :param channel: WebSocket通道
        :param event_src_factory: 事件源工厂函数
        :param event_handler: 订单事件处理器
        """
        async def forward_if_order_event(event: user_data.Event):
            """转发订单事件
            
            :param event: 用户数据事件
            """
            if isinstance(event, user_data.OrderEvent):
                await event_handler(event)

        self._subscribe_to_ws_channel_events(
            channel, event_src_factory, cast(dispatcher.EventHandler, forward_if_order_event)
        )

    def _subscribe_to_ws_channel_events(
            self, channel: binance_ws.Channel,
            event_src_factory: Callable[[core_ws.WebSocketClient], core_ws.ChannelEventSource],
            event_handler: dispatcher.EventHandler
    ):
        """订阅WebSocket通道事件
        
        :param channel: WebSocket通道
        :param event_src_factory: 事件源工厂函数
        :param event_handler: 事件处理器
        """
        # 获取或创建通道的事件源
        ws_cli = self._get_ws_client()
        event_source = ws_cli.get_channel_event_source_ex(channel)
        if not event_source:
            event_source = event_src_factory(ws_cli)
            ws_cli.set_channel_event_source_ex(channel, event_source)

        # 将事件处理器订阅到事件源
        self._dispatcher.subscribe(event_source, event_handler)

    def _get_ws_client(self) -> binance_ws.WebSocketClient:
        """获取WebSocket客户端
        
        :return: WebSocket客户端实例
        """
        if self._websocket is None:
            self._websocket = binance_ws.WebSocketClient(
                self._dispatcher, self._cli, session=self._session, config_overrides=self._config_overrides
            )
        return self._websocket
