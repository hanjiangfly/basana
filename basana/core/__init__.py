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
【中文说明】Basana核心模块初始化文件

【功能描述】
basana/core模块的包初始化文件，定义核心模块的公共接口。
该模块包含Basana框架的核心组件，为交易系统提供基础架构支持。

【模块组成】
- 事件系统：事件生产、分发和处理机制
- 时间处理：时间戳和时区管理工具
- 数据模型：交易对、K线数据等核心数据结构
- 配置管理：统一的配置获取和覆盖机制
- 异步工具：任务管理和异步编程辅助工具
- 日志系统：结构化日志和回测日志模式
- 错误处理：统一的异常基类定义

【使用场景】
- 构建自定义交易策略
- 开发回测系统
- 实现实时交易执行
- 集成外部交易所API

【注意事项】
- 这是一个包初始化文件，不包含具体实现
- 具体功能通过导入子模块使用
- 遵循Apache 2.0开源协议
"""
