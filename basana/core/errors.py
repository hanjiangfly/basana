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
【中文说明】错误定义模块

【功能描述】
定义Basana框架的异常基类，为所有自定义异常提供统一的基类。
遵循Python异常继承体系，便于错误处理和调试。

【设计原则】
- 统一异常基类：所有自定义异常都继承自Error类
- 清晰的异常层次：便于分类和处理不同类型的错误
- 标准异常接口：遵循Python异常标准

【使用场景】
- 框架内部错误处理
- 自定义异常定义
- 错误分类和捕获
- 调试和错误追踪

【注意事项】
- 所有自定义异常都应继承自Error类
- 遵循Python异常命名规范
- 提供清晰的错误信息
"""


class Error(Exception):
    """
    【中文说明】异常基类
    
    【功能描述】
    Basana框架所有自定义异常的基类。
    继承自Python标准Exception类，提供统一的异常处理接口。
    
    【继承关系】
    - Exception (Python标准异常基类)
      - Error (Basana异常基类)
        - 所有自定义异常类
    
    【使用场景】
    - 定义新的自定义异常
    - 捕获所有Basana相关异常
    - 异常分类和处理
    
    【注意事项】
    - 这是一个抽象基类，不应直接实例化
    - 所有自定义异常都应继承此类
    - 遵循异常链和错误信息最佳实践

    Base class for exceptions.
    """
    pass
