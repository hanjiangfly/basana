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
# distributed under the License is distributed on "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
【中文说明】Binance CSV K线数据源模块
【功能描述】提供从CSV文件加载Binance交易所K线数据的功能
【使用场景】用于回测系统从历史CSV数据加载K线，支持多种时间周期
【注意事项】支持时间周期转换和时区处理，确保数据时间戳正确性
"""

import datetime

from basana.core import pair
from basana.core.event_sources import csv
from basana.external.binance.tools.download_bars import period_to_step
from basana.external.common.csv.bars import RowParser


period_to_timedelta = {
    period_str: datetime.timedelta(seconds=period_secs)
    for period_str, period_secs in period_to_step.items()
}
"""
【中文说明】时间周期到时间增量的映射字典
【功能描述】将字符串形式的时间周期转换为datetime.timedelta对象
【使用场景】用于计算K线周期的实际时间跨度
【注意事项】包含从1秒到1个月的各种时间周期
"""


class BarSource(csv.EventSource):
    """
    【中文说明】Binance CSV K线数据源类
    【功能描述】从CSV文件加载Binance交易所的K线数据，并转换为事件流
    【使用场景】用于回测系统加载历史K线数据，支持排序和时区处理
    【注意事项】继承自csv.EventSource，提供Binance特定的数据解析逻辑
    """
    def __init__(
            self, pair: pair.Pair, csv_path: str, period: str,
            sort: bool = False, tzinfo: datetime.tzinfo = datetime.timezone.utc,
            dict_reader_kwargs: dict = {}
    ):
        """
        【中文说明】初始化Binance CSV K线数据源
        【功能描述】创建K线数据源实例，配置交易对、文件路径、时间周期等参数
        【参数说明】
        - pair: 交易对对象，指定要加载的交易对
        - csv_path: CSV文件路径，包含K线历史数据
        - period: 时间周期字符串，如"1m", "1h", "1d"等
        - sort: 是否对事件进行排序，可选，默认为False
        - tzinfo: 时区信息，可选，默认为UTC时区
        - dict_reader_kwargs: CSV字典读取器额外参数，可选
        【注意事项】CSV文件中的时间戳是K线周期的开始时间，但事件会在周期结束时生成
        """
        # 【中文说明】CSV文件中的时间戳是K线周期的开始时间，但我们需要在周期结束时生成事件
        timedelta = period_to_timedelta.get(period)
        assert timedelta is not None, "Invalid period"
        self.row_parser = RowParser(pair, tzinfo=tzinfo, timedelta=timedelta)
        super().__init__(csv_path, self.row_parser, sort=sort, dict_reader_kwargs=dict_reader_kwargs)
