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
Binance交易数据模块

此模块提供了Binance交易数据的处理功能，包括：
- 交易数据模型定义
- 交易事件处理
- WebSocket交易数据流处理

主要类：
- Trade: 交易数据类
- TradeEvent: 交易事件类
- WebSocketEventSource: WebSocket事件源类
"""

from decimal import Decimal
from typing import Any, Awaitable, Callable
import datetime
import logging

from . import helpers
from basana.core import event, websockets as core_ws
from basana.core.pair import Pair


logger = logging.getLogger(__name__)


class Trade:
    """交易数据类
    
    表示单个交易记录，包含交易相关的详细信息。
    """
    
    def __init__(self, pair: Pair, json: dict):
        """初始化交易数据
        
        :param pair: 交易对
        :param json: JSON格式的交易数据
        :raises AssertionError: 如果JSON数据不是交易类型
        """
        assert json["e"] == "trade"

        #: 交易对
        self.pair: Pair = pair
        #: JSON表示形式
        self.json: dict = json

    @property
    def id(self) -> str:
        """获取交易ID
        
        :return: 交易ID字符串
        """
        return str(self.json["t"])

    @property
    def datetime(self) -> datetime.datetime:
        """获取交易时间
        
        :return: 交易时间戳
        """
        return helpers.timestamp_to_datetime(int(self.json["T"]))

    @property
    def price(self) -> Decimal:
        """获取交易价格
        
        :return: 交易价格
        """
        return Decimal(self.json["p"])

    @property
    def amount(self) -> Decimal:
        """获取交易数量
        
        :return: 交易数量
        """
        return Decimal(self.json["q"])

    @property
    def buy_order_id(self) -> str:
        """获取买方订单ID
        
        :return: 买方订单ID字符串
        """
        return str(self.json["b"])

    @property
    def sell_order_id(self) -> str:
        """获取卖方订单ID
        
        :return: 卖方订单ID字符串
        """
        return str(self.json["a"])


class TradeEvent(event.Event):
    """交易事件类，继承自event.Event
    
    表示新的交易事件。

    :param when: 事件发生的时间，必须设置时区信息。
    :param trade: 交易数据。
    """

    def __init__(self, when: datetime.datetime, trade: Trade):
        """初始化交易事件
        
        :param when: 事件发生时间
        :param trade: 交易数据
        """
        super().__init__(when)
        #: 交易数据
        self.trade: Trade = trade


class WebSocketEventSource(core_ws.ChannelEventSource):
    """WebSocket事件源类，继承自core_ws.ChannelEventSource
    
    从WebSocket消息生成TradeEvent事件。
    """
    
    def __init__(self, pair: Pair, producer: event.Producer):
        """初始化WebSocket事件源
        
        :param pair: 交易对
        :param producer: 事件生产者
        """
        super().__init__(producer=producer)
        self._pair: Pair = pair

    async def push_from_message(self, message: dict):
        """从WebSocket消息推送事件
        
        :param message: WebSocket消息字典
        """
        event = message["data"]
        self.push(TradeEvent(
            helpers.timestamp_to_datetime(int(event["E"])),  # 事件时间
            Trade(self._pair, event)
        ))


def get_channel(pair: Pair) -> str:
    """获取交易通道名称
    
    :param pair: 交易对
    :return: 交易通道名称字符串
    """
    return "{}@trade".format(helpers.pair_to_symbol(pair).lower())


TradeEventHandler = Callable[[TradeEvent], Awaitable[Any]]
"""交易事件处理器类型

表示处理TradeEvent的异步回调函数类型。
"""
