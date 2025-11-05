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
【中文说明】Binance订单簿模块
【功能描述】提供Binance交易所订单簿数据的获取和处理功能
【使用场景】用于获取订单簿快照、轮询更新和WebSocket实时数据
【核心功能】
- Entry：订单簿条目数据类
- PartialOrderBook：部分订单簿数据模型
- PartialOrderBookEvent：订单簿更新事件
- PollOrderBook：轮询订单簿事件源
- WebSocketEventSource：WebSocket订单簿事件源
【注意事项】支持轮询和WebSocket两种方式获取订单簿数据
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Awaitable, Callable, List, Optional
import asyncio
import datetime
import logging

import aiohttp

from . import client, helpers
from basana.core import dt, event, logs, token_bucket, websockets as core_ws
from basana.core.pair import Pair


logger = logging.getLogger(__name__)


@dataclass
class Entry:
    """
    【中文说明】订单簿条目数据类
    【功能描述】表示订单簿中的一个价格-数量条目
    【使用场景】用于存储买单或卖单的价格和数量信息
    """
    price: Decimal  # 【中文说明】价格
    volume: Decimal  # 【中文说明】数量


class PartialOrderBook:
    """
    【中文说明】部分订单簿类
    【功能描述】封装Binance订单簿的部分数据，包含买单和卖单列表
    【使用场景】用于处理订单簿快照和增量更新数据
    """
    def __init__(self, pair: Pair, json: dict):
        """
        【中文说明】初始化部分订单簿
        【功能描述】从JSON数据创建订单簿对象
        【参数说明】
        - pair: 交易对对象
        - json: Binance订单簿JSON数据
        """
        self.pair: Pair = pair  # 【中文说明】交易对
        self.json: dict = json  # 【中文说明】原始JSON数据

    @property
    def last_update_id(self) -> int:
        """
        【中文说明】最后更新ID
        【功能描述】获取订单簿的最后更新标识符
        【返回说明】整数类型的最后更新ID
        """
        return self.json["lastUpdateId"]

    @property
    def bids(self) -> List[Entry]:
        """
        【中文说明】买单列表
        【功能描述】获取订单簿的买单（出价）条目列表
        【返回说明】Entry对象列表，按价格从高到低排序
        """
        return [
            Entry(price=Decimal(entry[0]), volume=Decimal(entry[1])) for entry in self.json["bids"]
        ]

    @property
    def asks(self) -> List[Entry]:
        """
        【中文说明】卖单列表
        【功能描述】获取订单簿的卖单（要价）条目列表
        【返回说明】Entry对象列表，按价格从低到高排序
        """
        return [
            Entry(price=Decimal(entry[0]), volume=Decimal(entry[1])) for entry in self.json["asks"]
        ]


class PartialOrderBookEvent(event.Event):
    """
    【中文说明】部分订单簿事件类
    【功能描述】封装订单簿更新事件，包含时间戳和订单簿数据
    【使用场景】用于处理订单簿的实时更新事件
    """
    def __init__(self, when: datetime.datetime, order_book: PartialOrderBook):
        """
        【中文说明】初始化订单簿事件
        【功能描述】创建订单簿更新事件对象
        【参数说明】
        - when: 事件发生时间，必须包含时区信息
        - order_book: 更新的订单簿对象
        """
        super().__init__(when)
        self.order_book: PartialOrderBook = order_book  # 【中文说明】订单簿对象


class PollOrderBook(event.FifoQueueEventSource, event.Producer):
    """
    【中文说明】轮询订单簿事件源类
    【功能描述】通过轮询API定期获取订单簿数据并生成事件
    【使用场景】用于需要定期获取订单簿快照的场景
    【继承关系】继承自event.FifoQueueEventSource和event.Producer
    """
    def __init__(
            self, pair: Pair, interval: float, limit: Optional[int] = None,
            session: Optional[aiohttp.ClientSession] = None, tb: Optional[token_bucket.TokenBucketLimiter] = None,
            config_overrides: dict = {}
    ):
        """
        【中文说明】初始化轮询订单簿
        【功能描述】创建轮询订单簿事件源实例
        【参数说明】
        - pair: 交易对对象
        - interval: 轮询间隔（秒）
        - limit: 订单簿深度限制，可选
        - session: HTTP会话，可选
        - tb: 令牌桶限流器，可选
        - config_overrides: 配置覆盖字典，可选
        """
        assert interval > 0, "Invalid interval"
        super().__init__(producer=self)
        self.pair = pair
        self._interval = interval
        self._limit = limit
        self._client = client.APIClient(session=session, tb=tb, config_overrides=config_overrides)

    async def _fetch_and_push(self, order_book_symbol: str):
        """
        【中文说明】获取并推送订单簿
        【功能描述】调用API获取订单簿数据并生成事件
        【参数说明】
        - order_book_symbol: 交易对符号
        """
        order_book_json = await self._client.get_order_book(order_book_symbol, limit=self._limit)
        self.push(PartialOrderBookEvent(
            dt.utc_now(monotonic=True),  # 【中文说明】订单簿不包含时间戳，使用当前UTC时间
            PartialOrderBook(self.pair, order_book_json)
        ))

    async def on_error(self, error: Any):
        """
        【中文说明】错误处理
        【功能描述】处理轮询过程中发生的错误
        【参数说明】
        - error: 错误对象
        """
        logger.error(logs.StructuredMessage("Error polling order book", channel=self.pair, error=error))

    async def main(self):
        """
        【中文说明】主循环
        【功能描述】轮询订单簿的主循环，定期获取数据并生成事件
        """
        order_book_symbol = helpers.pair_to_symbol(self.pair)
        while True:
            try:
                await self._fetch_and_push(order_book_symbol)
            except Exception as e:
                await self.on_error(e)
            await asyncio.sleep(self._interval)


class WebSocketEventSource(core_ws.ChannelEventSource):
    """
    【中文说明】WebSocket订单簿事件源类
    【功能描述】通过WebSocket实时接收订单簿更新并生成事件
    【使用场景】用于需要实时订单簿数据的场景
    【继承关系】继承自core_ws.ChannelEventSource
    """
    def __init__(self, pair: Pair, producer: event.Producer):
        """
        【中文说明】初始化WebSocket事件源
        【功能描述】创建WebSocket订单簿事件源实例
        【参数说明】
        - pair: 交易对对象
        - producer: 事件生产者
        """
        super().__init__(producer=producer)
        self._pair = pair

    async def push_from_message(self, message: dict):
        """
        【中文说明】处理WebSocket消息
        【功能描述】从WebSocket消息中提取订单簿数据并生成事件
        【参数说明】
        - message: WebSocket消息字典
        """
        event = message["data"]
        self.push(PartialOrderBookEvent(
            dt.utc_now(monotonic=True),  # 【中文说明】事件不包含时间戳，使用当前UTC时间
            PartialOrderBook(self._pair, event)
        ))


def get_channel(pair: Pair, depth: int, interval: int) -> str:
    """
    【中文说明】获取WebSocket通道名称
    【功能描述】生成订单簿WebSocket数据流的通道名称
    【参数说明】
    - pair: 交易对对象
    - depth: 订单簿深度（5、10、20）
    - interval: 更新间隔（100、1000毫秒）
    【返回说明】WebSocket通道名称字符串
    【示例】"btcusdt@depth20@100ms"
    """
    assert depth in [5, 10, 20], "Invalid depth"
    assert interval in [100, 1000], "Invalid interval"
    return "{}@depth{}@{}ms".format(helpers.pair_to_symbol(pair).lower(), depth, interval)


PartialOrderBookEventHandler = Callable[[PartialOrderBookEvent], Awaitable[Any]]
