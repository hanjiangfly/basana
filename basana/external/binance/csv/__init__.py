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
【中文说明】Binance CSV数据模块初始化文件
【功能描述】提供Binance交易所CSV格式K线数据的导入和处理功能
【使用场景】用于从CSV文件加载Binance历史K线数据，支持回测和数据分析
【注意事项】包含K线数据源的定义和导入接口
"""

# ruff: noqa

from .bars import (
    BarSource,
)
