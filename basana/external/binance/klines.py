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
【中文说明】Binance K线数据模块
【功能描述】提供Binance交易所K线数据的处理和WebSocket事件源功能
【使用场景】用于处理Binance WebSocket K线数据流，生成K线事件
【核心功能】
- Bar类：Binance特定K线数据封装
- WebSocketEventSource类：K线WebSocket事件源
- 通道管理：K线数据流通道名称生成
【注意事项】只处理已完成的K线（x=True），忽略中间更新
"""

from decimal import Decimal
import logging

from . import helpers
from basana.core import bar, event, websockets as core_ws
from basana.core.pair import Pair


logger = logging.getLogger(__name__)


class Bar(bar.Bar):
    """
    【中文说明】Binance K线数据类
    【功能描述】继承基础Bar类，封装Binance特定的K线数据
    【使用场景】用于解析Binance WebSocket返回的K线JSON数据
    【继承关系】继承自bar.Bar，增加pair和json属性
    【数据字段】
    - t: 开盘时间戳（毫秒）
    - o: 开盘价
    - h: 最高价
    - l: 最低价
    - c: 收盘价
    - v: 成交量
    """
    def __init__(self, pair: Pair, json: dict):
        """
        【中文说明】初始化Binance K线对象
        【功能描述】从Binance WebSocket JSON数据创建K线对象
        【参数说明】
        - pair: 交易对对象
        - json: Binance K线JSON数据
        """
        super().__init__(
            helpers.timestamp_to_datetime(int(json["t"])), pair, Decimal(json["o"]), Decimal(json["h"]),
            Decimal(json["l"]), Decimal(json["c"]), Decimal(json["v"])
        )
        self.pair: Pair = pair  # 【中文说明】交易对信息
        self.json: dict = json  # 【中文说明】原始JSON数据


class WebSocketEventSource(core_ws.ChannelEventSource):
    """
    【中文说明】K线WebSocket事件源类
    【功能描述】从Binance WebSocket K线数据流生成K线事件
    【使用场景】用于订阅和处理Binance K线实时数据
    【继承关系】继承自core_ws.ChannelEventSource
    【处理逻辑】只处理已完成的K线（x=True），忽略中间更新
    """
    def __init__(self, pair: Pair, producer: event.Producer):
        """
        【中文说明】初始化K线事件源
        【功能描述】创建K线WebSocket事件源实例
        【参数说明】
        - pair: 交易对对象
        - producer: 事件生产者
        """
        super().__init__(producer=producer)
        self._pair: Pair = pair

    async def push_from_message(self, message: dict):
        """
        【中文说明】处理WebSocket消息
        【功能描述】从WebSocket消息中提取K线数据并生成事件
        【参数说明】
        - message: WebSocket消息字典
        【处理流程】
        1. 提取K线事件数据
        2. 检查K线是否已完成（x=True）
        3. 如果已完成，创建BarEvent并推送到事件流
        """
        kline_event = message["data"]
        kline = kline_event["k"]
        # 【中文说明】等待K线的最后更新（即K线完成）
        if kline["x"] is False:
            return
        self.push(bar.BarEvent(
            helpers.timestamp_to_datetime(int(kline_event["E"])),  # 【中文说明】事件时间
            Bar(self._pair, kline)
        ))


def get_channel(pair: Pair, interval: str) -> str:
    """
    【中文说明】获取K线WebSocket通道名称
    【功能描述】生成Binance K线数据流的WebSocket通道名称
    【参数说明】
    - pair: 交易对对象
    - interval: K线时间间隔（如"1m", "1h", "1d"等）
    【返回说明】WebSocket通道名称字符串
    【示例】"btcusdt@kline_1m"
    """
    return "{}@kline_{}".format(helpers.pair_to_symbol(pair).lower(), interval)
