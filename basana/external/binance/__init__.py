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
【中文说明】Binance交易所集成模块初始化文件
【功能描述】提供Binance加密货币交易所的完整集成支持，包括现货交易、保证金交易、WebSocket实时数据等
【使用场景】用于连接Binance交易所进行实时交易、数据获取和回测分析
【模块组成】
- 现货交易：支持市价单、限价单、止损单等订单类型
- 保证金交易：支持全仓保证金和逐仓保证金模式
- 实时数据：通过WebSocket获取订单簿、交易、K线等实时数据
- 历史数据：通过REST API获取历史K线、交易记录等数据
- 账户管理：查询余额、订单状态、交易历史等
【注意事项】需要配置API密钥和密钥，遵守Binance API使用限制
"""
