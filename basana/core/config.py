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
# distributed under the License is distributed on "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
【中文说明】配置管理模块

【功能描述】
提供统一的配置值获取机制，支持嵌套字典路径访问和配置覆盖。
使用点分隔的路径语法访问嵌套配置值，支持默认值和覆盖配置。

【核心特性】
- 路径式配置访问：使用点分隔符访问嵌套字典
- 配置覆盖机制：支持运行时配置覆盖
- 类型安全：验证路径有效性和数据类型
- 默认值支持：为缺失配置提供默认值

【使用场景】
- 应用程序配置管理
- 运行时配置动态更新
- 多环境配置支持
- 配置值验证和类型检查

【注意事项】
- 配置路径必须使用点分隔符
- 中间路径必须指向字典类型
- 配置覆盖优先级高于基础配置
"""


class Missing:
    """
    【中文说明】缺失值标记类
    
    【功能描述】
    用于标记配置值缺失的特殊类，作为内部实现使用。
    用于区分"配置值为None"和"配置值不存在"两种情况。
    
    【使用场景】
    - 内部配置获取实现
    - 区分默认值和实际配置值
    
    【注意事项】
    - 这是一个内部实现类，不应直接使用
    - 用于实现配置覆盖机制
    """
    pass


def _get_config_value_impl(config: dict, path: str, default=None):
    """
    【中文说明】配置值获取实现函数
    
    【功能描述】
    内部实现函数，根据点分隔路径从配置字典中获取值。
    支持嵌套字典访问和默认值返回。
    
    【参数说明】
    - config: dict - 配置字典
    - path: str - 点分隔的配置路径
    - default: Any - 默认值，当配置不存在时返回
    
    【返回值】
    - Any: 配置值或默认值
    
    【验证检查】
    - 路径不能为空
    - 中间路径必须指向字典类型
    
    【异常情况】
    - 路径为空时抛出AssertionError
    - 中间路径不是字典时抛出AssertionError
    
    【注意事项】
    - 这是一个内部函数，不应直接调用
    - 使用get_config_value函数获取配置值
    """
    ret = default
    current_dict = config
    # 分割配置路径为键列表
    keys = path.split(".")
    for i, key in enumerate(keys):
        # 验证路径键不为空
        assert key, "Invalid path {}".format(path)
        # 如果是最后一个键，获取值
        if i == len(keys) - 1:
            ret = current_dict.get(key, default)
        else:
            # 获取中间字典，如果不存在则使用空字典
            current_dict = current_dict.get(key, {})
            # 验证中间路径指向字典类型
            assert isinstance(current_dict, dict), f"Element at {key} is not a dictionary"
    return ret


def get_config_value(config: dict, path: str, default=None, overrides: dict = {}):
    """
    【中文说明】获取配置值
    
    【功能描述】
    从配置字典中获取指定路径的值，支持配置覆盖机制。
    首先检查覆盖配置，如果不存在则检查基础配置。
    
    【参数说明】
    - config: dict - 基础配置字典
    - path: str - 点分隔的配置路径
    - default: Any - 默认值，当配置不存在时返回
    - overrides: dict - 覆盖配置字典，优先级高于基础配置
    
    【返回值】
    - Any: 配置值，按以下优先级返回：
        1. 覆盖配置中的值
        2. 基础配置中的值
        3. 默认值
    
    【算法流程】
    1. 首先在覆盖配置中查找值
    2. 如果覆盖配置中不存在，在基础配置中查找
    3. 如果都不存在，返回默认值
    
    【使用场景】
    - 应用程序配置管理
    - 环境特定配置覆盖
    - 运行时配置动态更新
    
    【注意事项】
    - 配置路径使用点分隔符
    - 覆盖配置优先级最高
    - 支持嵌套字典访问
    """
    # 使用Missing标记来区分"值不存在"和"值为None"
    missing = Missing()
    # 首先在覆盖配置中查找
    ret = _get_config_value_impl(overrides, path, default=missing)
    # 如果在覆盖配置中未找到，在基础配置中查找
    if ret == missing:
        ret = _get_config_value_impl(config, path, default=default)
    return ret
