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
【中文说明】Binance配置模块
【功能描述】定义Binance交易所API的默认配置参数，包括HTTP和WebSocket连接设置
【使用场景】用于配置Binance API客户端的基础URL、超时时间、心跳间隔等参数
【注意事项】这些配置可以通过config_overrides参数进行覆盖和自定义
"""

DEFAULTS = {
    "api": {
        "http": {
            "base_url": "https://api.binance.com/",  # 【中文说明】HTTP API基础URL
            "timeout": 30,  # 【中文说明】HTTP请求超时时间（秒）
        },
        "websockets": {
            "base_url": "wss://stream.binance.com/",  # 【中文说明】WebSocket基础URL
            "heartbeat": 30,  # 【中文说明】WebSocket心跳间隔（秒）
            "spot": {
                "user_data_stream": {
                    "heartbeat": 15 * 60,  # 【中文说明】现货用户数据流心跳间隔（15分钟）
                },
            },
            "cross_margin": {
                "user_data_stream": {
                    "heartbeat": 15 * 60,  # 【中文说明】全仓保证金用户数据流心跳间隔（15分钟）
                },
            },
            "isolated_margin": {
                "user_data_stream": {
                    "heartbeat": 15 * 60,  # 【中文说明】逐仓保证金用户数据流心跳间隔（15分钟）
                },
            },
        }
    }
}
"""
【中文说明】Binance API默认配置字典
【功能描述】包含Binance交易所API的所有默认配置参数
【配置说明】
- api.http.base_url: HTTP REST API的基础URL
- api.http.timeout: HTTP请求超时时间，单位秒
- api.websockets.base_url: WebSocket流数据的基础URL  
- api.websockets.heartbeat: WebSocket连接心跳间隔，单位秒
- api.websockets.spot.user_data_stream.heartbeat: 现货用户数据流心跳间隔
- api.websockets.cross_margin.user_data_stream.heartbeat: 全仓保证金用户数据流心跳间隔
- api.websockets.isolated_margin.user_data_stream.heartbeat: 逐仓保证金用户数据流心跳间隔
【注意事项】用户数据流心跳间隔设置为15分钟，符合Binance API要求
"""
