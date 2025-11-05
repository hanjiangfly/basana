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
【中文说明】回测模块初始化文件

【功能描述】
basana/backtesting模块的包初始化文件，定义回测系统的公共接口。
该模块提供完整的量化交易策略回测功能，模拟真实交易环境。

【模块组成】
- 交易所模拟：Exchange类，模拟真实交易所行为
- 账户管理：账户余额、持仓、借贷管理
- 订单系统：订单创建、执行、状态跟踪
- 费用计算：交易手续费、资金费率等
- 流动性管理：订单簿深度和滑点模拟
- 价格管理：历史价格数据和实时价格更新
- 图表工具：回测结果可视化和分析

【核心特性】
- 事件驱动架构：基于时间序列的事件处理
- 高精度模拟：支持滑点、费用、借贷等真实交易因素
- 异步处理：支持异步订单执行和事件处理
- 可扩展设计：支持自定义费用策略、流动性模型等

【使用场景】
- 量化策略开发和验证
- 历史数据回测分析
- 风险管理和资金曲线分析
- 策略参数优化和性能评估

【注意事项】
- 回测结果仅供参考，实际交易可能存在差异
- 需要确保历史数据的质量和完整性
- 遵循Apache 2.0开源协议
"""
