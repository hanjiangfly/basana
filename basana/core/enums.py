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

import enum


# 使用这些值来避免与外部API值产生误解
# 定义内部枚举值，确保与外部系统值的隔离和一致性
@enum.unique
class OrderOperation(enum.Enum):
    """
    【中文说明】订单操作枚举
    
    【功能描述】
    定义订单操作类型的枚举，用于表示买入和卖出操作。
    使用内部定义的值（100, 101）来避免与外部API值混淆。
    
    【枚举值说明】
    - BUY: 买入操作，值为100
    - SELL: 卖出操作，值为101
    
    【设计考虑】
    - 使用@enum.unique装饰器确保枚举值唯一
    - 使用较大的数值（100+）避免与外部系统值冲突
    - 提供字符串表示方法便于日志和显示
    
    【使用场景】
    - 订单创建和执行的类型标识
    - 交易策略中的操作方向判断
    - 订单历史记录的操作类型存储
    
    【注意事项】
    - 枚举值在内部使用，与外部API值隔离
    - 字符串表示使用小写，符合常见API规范

    Enumeration for order operations.
    """

    #: 买入操作
    BUY = 100
    #: 卖出操作
    SELL = 101

    def __str__(self):
        """
        【中文说明】返回订单操作的字符串表示
        
        【功能描述】
        将枚举值转换为对应的字符串表示，便于日志记录和显示。
        
        【返回值】
        - str: 订单操作的字符串表示（"buy" 或 "sell"）
        
        【使用场景】
        - 日志记录时显示操作类型
        - 用户界面显示操作类型
        - API响应中的操作类型表示
        
        【注意事项】
        - 返回小写字符串，符合常见API规范
        - 与外部系统交互时可能需要转换
        """
        return {
            OrderOperation.BUY: "buy",
            OrderOperation.SELL: "sell",
        }[self]


@enum.unique
class Position(enum.Enum):
    """
    【中文说明】持仓方向枚举
    
    【功能描述】
    定义持仓方向的枚举，用于表示多头、空头和中性的持仓状态。
    使用内部定义的值（200, 201, 202）来避免与外部API值混淆。
    
    【枚举值说明】
    - LONG: 多头持仓，值为200
    - SHORT: 空头持仓，值为201  
    - NEUTRAL: 中性持仓（无持仓），值为202
    
    【设计考虑】
    - 使用@enum.unique装饰器确保枚举值唯一
    - 使用较大的数值（200+）避免与外部系统值冲突
    - 提供字符串表示方法便于日志和显示
    
    【使用场景】
    - 持仓管理中的方向标识
    - 交易策略的持仓状态判断
    - 风险管理和头寸监控
    
    【注意事项】
    - 枚举值在内部使用，与外部API值隔离
    - 字符串表示使用小写，符合常见API规范

    Enumeration for positions.
    """

    #: 多头持仓
    LONG = 200
    #: 空头持仓
    SHORT = 201
    #: 中性持仓（无持仓）
    NEUTRAL = 202

    def __str__(self):
        """
        【中文说明】返回持仓方向的字符串表示
        
        【功能描述】
        将枚举值转换为对应的字符串表示，便于日志记录和显示。
        
        【返回值】
        - str: 持仓方向的字符串表示（"long"、"short" 或 "neutral"）
        
        【使用场景】
        - 日志记录时显示持仓方向
        - 用户界面显示持仓状态
        - 风险报告中的持仓方向表示
        
        【注意事项】
        - 返回小写字符串，符合常见API规范
        - 与外部系统交互时可能需要转换
        """
        return {
            Position.LONG: "long",
            Position.SHORT: "short",
            Position.NEUTRAL: "neutral",
        }[self]
