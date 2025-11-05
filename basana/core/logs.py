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
【中文说明】日志管理模块

【功能描述】
提供回测日志模式和结构化日志消息支持。
包含时间戳调整和结构化日志格式化的工具。

【核心功能】
- 回测日志模式：调整日志时间戳以匹配回测时间
- 结构化消息：支持JSON格式的结构化日志记录
- 时间戳管理：正确处理回测环境下的时间戳

【使用场景】
- 回测系统中的日志记录
- 结构化日志输出
- 时间敏感的日志分析

【注意事项】
- 回测日志模式会影响全局日志记录
- 结构化消息支持任意JSON可序列化数据
- 遵循Python日志记录最佳实践
"""

import contextlib
import json
import logging

from . import dt


@contextlib.contextmanager
def backtesting_log_mode(dispatcher):
    """
    【中文说明】回测日志模式上下文管理器
    
    【功能描述】
    临时修改日志记录工厂，使日志时间戳与回测时间对齐。
    在回测环境中，日志时间应该反映模拟时间而非真实时间。
    
    【参数说明】
    - dispatcher: 事件分发器，提供当前回测时间
    
    【操作流程】
    1. 保存原有的日志记录工厂
    2. 设置新的日志记录工厂，使用回测时间
    3. 在上下文管理器退出时恢复原有工厂
    
    【使用场景】
    - 回测系统中的日志记录
    - 时间对齐的日志分析
    - 回测结果的可重现性
    
    【注意事项】
    - 这是一个上下文管理器，使用with语句
    - 会影响全局日志记录时间戳
    - 退出时会自动恢复原有设置
    """
    # 保存原有的日志记录工厂
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        """
        【中文说明】回测日志记录工厂
        
        【功能描述】
        自定义日志记录工厂，使用回测时间而非系统时间。
        
        【参数说明】
        - *args: 位置参数，传递给原有工厂
        - **kwargs: 关键字参数，传递给原有工厂
        
        【返回值】
        - logging.LogRecord: 修改时间戳后的日志记录
        
        【操作流程】
        1. 从分发器获取当前回测时间
        2. 调用原有工厂创建日志记录
        3. 修改日志记录的时间戳和毫秒字段
        4. 返回修改后的日志记录
        
        【注意事项】
        - 使用分发器的now()方法获取回测时间
        - 时间戳转换为UTC时间戳
        - 毫秒字段从微秒计算得到
        """
        # 从分发器获取当前回测时间
        record_dt = dispatcher.now()
        # 调用原有工厂创建日志记录
        record = old_factory(*args, **kwargs)
        # 修改时间戳为回测时间的UTC时间戳
        record.created = dt.to_utc_timestamp(record_dt)
        # 计算毫秒字段
        record.msecs = int(record_dt.microsecond / 1000)
        return record

    try:
        # 设置新的日志记录工厂
        logging.setLogRecordFactory(record_factory)
        yield
    finally:
        # 恢复原有的日志记录工厂
        logging.setLogRecordFactory(old_factory)


# https://docs.python.org/3/howto/logging-cookbook.html#implementing-structured-logging
class StructuredMessage:
    """
    【中文说明】结构化日志消息类
    
    【功能描述】
    实现结构化日志记录，将消息和结构化数据组合。
    支持JSON格式输出，便于日志分析和处理。
    
    【设计参考】
    基于Python官方文档中的结构化日志记录实现：
    https://docs.python.org/3/howto/logging-cookbook.html#implementing-structured-logging
    
    【核心特性】
    - 结构化数据：支持任意关键字参数作为结构化数据
    - JSON格式化：输出为JSON格式便于解析
    - 消息组合：将消息和结构化数据组合为单一字符串
    
    【使用场景】
    - 结构化日志记录
    - 日志分析和监控
    - 机器可读的日志输出
    
    【注意事项】
    - 使用位置参数作为消息
    - 关键字参数作为结构化数据
    - 支持任意JSON可序列化数据类型
    """

    def __init__(self, message, /, **kwargs):
        """
        【中文说明】初始化结构化消息
        
        【功能描述】
        创建结构化消息实例，设置消息内容和结构化数据。
        
        【参数说明】
        - message: str - 日志消息（位置参数）
        - **kwargs: 结构化数据，作为关键字参数
        
        【内部状态】
        - message: 日志消息
        - kwargs: 结构化数据字典
        
        【注意事项】
        - 使用位置参数语法（/）强制message为位置参数
        - 关键字参数作为结构化数据存储
        """
        # 日志消息
        self.message = message
        # 结构化数据
        self.kwargs = kwargs

    def __str__(self):
        """
        【中文说明】字符串表示
        
        【功能描述】
        将结构化消息转换为字符串格式，用于日志输出。
        格式为：消息内容 + JSON格式的结构化数据。
        
        【返回值】
        - str: 格式化的日志字符串
        
        【格式化规则】
        - 消息内容原样输出
        - 结构化数据转换为JSON字符串
        - 使用空格分隔消息和JSON数据
        
        【注意事项】
        - 使用json.dumps序列化结构化数据
        - 支持default=str处理非JSON可序列化对象
        - 输出格式便于日志解析工具处理
        """
        return "{} {}".format(self.message, json.dumps(self.kwargs, default=str))
