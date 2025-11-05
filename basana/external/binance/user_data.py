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
Binance用户数据模块

此模块提供了Binance用户数据的处理功能，包括：
- 订单更新数据模型
- 用户数据事件处理
- WebSocket用户数据流处理

主要类：
- OrderUpdate: 订单更新数据类
- Event: 用户数据事件基类
- OrderEvent: 订单事件类
- WebSocketEventSource: WebSocket事件源类
"""

from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, Optional
import datetime

from . import helpers
from basana.core import event, websockets as core_ws
from basana.core.enums import OrderOperation


class OrderUpdate:
    """订单更新数据类
    
    表示订单执行报告中的更新信息。
    """
    
    def __init__(self, json: dict):
        """初始化订单更新数据
        
        :param json: JSON格式的订单更新数据
        :raises AssertionError: 如果JSON数据不是执行报告类型
        """
        assert json["e"] == "executionReport"

        #: JSON表示形式
        self.json: dict = json

    @property
    def id(self) -> str:
        """获取订单ID
        
        :return: 订单ID字符串
        """
        return str(self.json["i"])

    @property
    def symbol(self) -> str:
        """获取交易对符号
        
        :return: 交易对符号字符串
        """
        return str(self.json["s"])

    @property
    def client_order_id(self) -> str:
        """获取客户端订单ID
        
        :return: 客户端订单ID字符串
        """
        return self.json["c"]

    @property
    def operation(self) -> OrderOperation:
        """获取订单操作类型
        
        :return: 订单操作类型枚举
        """
        return helpers.side_to_order_operation(self.json["S"])

    @property
    def type(self) -> str:
        """
        获取订单类型

        参考 **Order types** 在
        https://developers.binance.com/docs/binance-spot-api-docs/enums#order-types-ordertypes-type。
        
        :return: 订单类型字符串
        """
        return self.json["o"]

    @property
    def time_in_force(self) -> Optional[str]:
        """
        获取订单有效时间

        参考 **Time in force** 在
        https://developers.binance.com/docs/binance-spot-api-docs/enums#time-in-force-timeinforce。
        
        :return: 订单有效时间字符串，如果没有则为None
        """
        return self.json.get("f")

    @property
    def amount(self) -> Decimal:
        """获取订单数量
        
        :return: 订单数量
        """
        return Decimal(self.json["q"])

    @property
    def quote_amount(self) -> Optional[Decimal]:
        """获取报价货币数量
        
        :return: 以报价货币计价的订单数量，如果没有则为None
        """
        return helpers.get_optional_decimal(self.json, "Q", True)

    @property
    def limit_price(self) -> Optional[Decimal]:
        """获取限价价格
        
        :return: 限价价格，如果没有则为None
        """
        return helpers.get_optional_decimal(self.json, "p", True)

    @property
    def stop_price(self) -> Optional[Decimal]:
        """获取止损价格
        
        :return: 止损价格，如果没有则为None
        """
        return helpers.get_optional_decimal(self.json, "P", True)

    @property
    def order_list_id(self) -> Optional[str]:
        """获取订单列表ID
        
        :return: 订单列表ID，如果没有则为None
        """
        ret = self.json.get("g")
        ret = None if ret in [None, -1] else str(ret)
        return ret

    @property
    def status(self) -> str:
        """
        获取订单状态

        参考 **Order status** 在 https://developers.binance.com/docs/binance-spot-api-docs/enums#order-status-status。
        
        :return: 订单状态字符串
        """
        return self.json["X"]

    @property
    def is_open(self) -> bool:
        """检查订单是否处于开放状态
        
        :return: 如果订单处于开放状态则为True，否则为False
        """
        return helpers.order_status_is_open(self.status)

    @property
    def amount_filled(self) -> Decimal:
        """获取已成交数量
        
        :return: 累计已成交数量
        """
        return Decimal(self.json["z"])

    @property
    def quote_amount_filled(self) -> Decimal:
        """获取已成交报价货币数量
        
        :return: 累计已成交的报价货币数量
        """
        return Decimal(self.json["Z"])

    @property
    def fees(self) -> Dict[str, Decimal]:
        """获取手续费
        
        :return: 手续费字典，键为资产符号，值为手续费金额
        """
        ret = {}
        if commision_asset := self.json.get("N"):
            ret[commision_asset] = Decimal(self.json["n"])
        return ret

    @property
    def fill_price(self) -> Optional[Decimal]:
        """获取成交价格
        
        :return: 成交价格，如果没有成交则为None
        """
        ret = None
        if self.amount_filled:
            ret = self.quote_amount_filled / self.amount_filled
        return ret


class Event(event.Event):
    """用户数据事件基类，继承自event.Event
    
    表示用户数据流中的事件。
    """
    
    def __init__(self, when: datetime.datetime, json: dict):
        """初始化用户数据事件
        
        :param when: 事件发生时间
        :param json: JSON格式的事件数据
        """
        super().__init__(when)
        #: JSON表示形式
        self.json: dict = json


class OrderEvent(Event):
    """
    订单事件类，继承自Event
    
    表示订单更新事件。

    :param when: 事件发生的时间，必须设置时区信息。
    :param order_update: 订单更新数据。
    """

    def __init__(self, when: datetime.datetime, json: dict):
        """初始化订单事件
        
        :param when: 事件发生时间
        :param json: JSON格式的订单事件数据
        """
        super().__init__(when, json)

        #: 订单更新数据
        self.order_update: OrderUpdate = OrderUpdate(json)


class WebSocketEventSource(core_ws.ChannelEventSource):
    """WebSocket事件源类，继承自core_ws.ChannelEventSource
    
    从WebSocket消息生成用户数据事件。
    """
    
    def __init__(self, producer: event.Producer):
        """初始化WebSocket事件源
        
        :param producer: 事件生产者
        """
        super().__init__(producer=producer)

    async def push_from_message(self, message: dict):
        """从WebSocket消息推送事件
        
        :param message: WebSocket消息字典
        """
        json = message["data"]
        # 推送事件
        event_cls = {
            "executionReport": OrderEvent,
        }.get(json["e"], Event)
        event = event_cls(
            helpers.timestamp_to_datetime(int(json["E"])),  # 事件时间
            json
        )
        self.push(event)


OrderEventHandler = Callable[[OrderEvent], Awaitable[Any]]
"""订单事件处理器类型

表示处理OrderEvent的异步回调函数类型。
"""

UserDataEventHandler = Callable[[Event], Awaitable[Any]]
"""用户数据事件处理器类型

表示处理Event的异步回调函数类型。
"""
