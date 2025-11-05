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
通用CSV K线数据源模块

此模块提供了跨交易所通用的CSV格式K线数据解析功能，支持标准化的CSV格式：
- 时间戳格式：YYYY-MM-DD HH:MM:SS
- 包含开盘价、最高价、最低价、收盘价、成交量
- 自动跳过成交量为0的K线

主要类：
- RowParser: CSV行解析器，继承自csv.RowParser
"""

from decimal import Decimal
from typing import Sequence
import datetime

from basana.core import pair, event, bar
from basana.core.event_sources import csv


class RowParser(csv.RowParser):
    """通用CSV行解析器
    
    继承自csv.RowParser，用于解析标准化的CSV格式K线数据。
    """
    
    def __init__(
            self, pair: pair.Pair, tzinfo: datetime.tzinfo, timedelta: datetime.timedelta
    ):
        """初始化行解析器
        
        :param pair: 交易对
        :param tzinfo: 时区信息
        :param timedelta: 时间增量，用于调整事件时间
        """
        self.pair = pair
        self.tzinfo = tzinfo
        self.timedelta = timedelta

    def parse_row(self, row_dict: dict) -> Sequence[event.Event]:
        """解析CSV行数据
        
        解析标准CSV格式的K线数据行，格式为：
        datetime,open,high,low,close,volume
        2015-01-01 00:00:00,321,321,321,321,1.73697242
        
        :param row_dict: CSV行数据字典
        :return: K线事件序列，如果成交量为0则返回空列表
        """
        volume = Decimal(row_dict["volume"])
        # 跳过成交量为0的K线
        if volume == 0:
            return []

        dt = datetime.datetime.strptime(row_dict["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=self.tzinfo)
        return [
            bar.BarEvent(
                dt + self.timedelta,
                bar.Bar(
                    dt, self.pair, Decimal(row_dict["open"]), Decimal(row_dict["high"]), Decimal(row_dict["low"]),
                    Decimal(row_dict["close"]), volume
                )
            )
        ]
