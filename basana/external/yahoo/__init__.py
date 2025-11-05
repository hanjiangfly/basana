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
Yahoo金融数据集成模块

此模块提供了从Yahoo Finance获取股票历史数据的集成功能，包括：
- 股票K线数据下载
- 历史价格数据获取
- 多种时间周期的数据支持

主要功能：
- bars: Yahoo Finance K线数据源
- 支持日线、周线、月线等不同时间周期
- 自动处理数据格式转换和时区问题

使用场景：
- 股票市场回测
- 历史数据分析
- 投资策略研究
"""
