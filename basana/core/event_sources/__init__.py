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
事件源模块 (event_sources)

此模块提供了多种事件源的实现，用于从不同数据源生成和处理事件。
事件源是Basana框架中的核心组件，负责将外部数据转换为内部事件流。

模块包含以下主要组件：

1. CSV事件源 (csv.py)
   - 从CSV文件读取和解析事件
   - 支持多种编码格式自动检测
   - 提供可扩展的行解析器接口

2. 交易信号事件源 (trading_signal.py)
   - 处理交易信号事件（多头、空头、中性持仓）
   - 提供交易信号的分发和订阅机制
   - 支持向后兼容的订单操作到持仓枚举的转换

设计原则：
- 事件驱动架构：所有事件源都遵循生产者-消费者模式
- 模块化设计：每个事件源可以独立使用和扩展
- 异步友好：支持异步事件处理和分发
- 向后兼容：确保现有代码的平滑迁移

使用场景：
- 回测系统：从CSV文件加载历史数据进行策略回测
- 实时交易：处理实时交易信号并执行相应的交易操作
- 数据导入：从外部数据源导入并标准化事件数据

注意：此模块中的CSV事件源不使用异步I/O，因为asyncio不支持异步文件系统操作。
在回测场景中，这通常不是问题，因为不会有其他I/O操作同时进行。
"""
