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

import calendar
import datetime
import time

from dateutil import tz


# 全局参考点：用于单调时间计算
# 记录程序启动时的UTC时间和单调时间，用于实现单调时间功能
_start_utc = datetime.datetime.now(tz=datetime.timezone.utc)
_start_monotonic = time.monotonic()


def is_naive(dt: datetime.datetime) -> bool:
    """
    【中文说明】检查时间是否为朴素时间（无时区信息）
    
    【功能描述】
    判断给定的datetime对象是否为朴素时间（naive datetime），即不包含时区信息。
    
    【参数说明】
    - dt: datetime.datetime - 要检查的时间对象
    
    【返回值】
    - bool: 如果时间不包含时区信息则返回True，否则返回False
    
    【使用场景】
    - 在事件系统中验证事件时间是否包含时区信息
    - 时间序列处理中确保时间戳的时区一致性
    - 防止时区混淆导致的逻辑错误
    
    【注意事项】
    - 朴素时间可能导致时区相关的bug，建议始终使用时区感知时间
    - 在分布式系统中，朴素时间可能引起跨时区的时间计算错误
    
    Returns True if datetime is naive.
    """
    return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None


def utc_now(monotonic: bool = False) -> datetime.datetime:
    """
    【中文说明】获取当前UTC时间
    
    【功能描述】
    返回当前UTC时区的时间。支持单调时间模式，避免系统时钟调整的影响。
    
    【参数说明】
    - monotonic: bool - 是否使用单调时间模式
      - True: 使用单调时间，忽略系统时钟调整，适合需要稳定时间间隔的场景
      - False: 使用系统时钟，反映真实的系统时间
    
    【返回值】
    - datetime.datetime: 当前UTC时间，包含时区信息
    
    【算法原理】
    - 单调时间模式：基于程序启动时的参考点和单调时钟计算时间
    - 系统时间模式：直接获取系统当前的UTC时间
    
    【使用场景】
    - 单调时间：性能测试、定时任务、需要稳定时间间隔的场景
    - 系统时间：日志记录、事件时间戳、需要真实时间的场景
    
    【注意事项】
    - 单调时间不会受系统时钟调整（如NTP同步）影响
    - 系统时间可能因时钟调整而跳跃

    Returns the current datetime in UTC timezone.

    :param monotonic: True for monotonic behaviour (ignoring system clock updates).
    """
    if monotonic:
        # 计算从程序启动到现在的单调时间差
        delta = time.monotonic() - _start_monotonic
        # 基于启动时的UTC时间加上时间差，实现单调时间
        return _start_utc + datetime.timedelta(seconds=delta)
    else:
        # 直接获取系统当前的UTC时间
        return datetime.datetime.now(tz=datetime.timezone.utc)


def local_datetime(*args, **kwargs) -> datetime.datetime:
    """
    【中文说明】创建本地时区时间对象
    
    【功能描述】
    创建datetime对象并自动设置本地时区信息。
    这是datetime.datetime构造函数的包装，确保创建的时间对象包含本地时区。
    
    【参数说明】
    - *args: 传递给datetime.datetime构造函数的参数
    - **kwargs: 传递给datetime.datetime构造函数的命名参数
    
    【返回值】
    - datetime.datetime: 包含本地时区信息的时间对象
    
    【使用场景】
    - 创建包含本地时区的固定时间点
    - 确保时间对象始终有时区信息
    - 简化本地时区时间的创建过程
    
    【注意事项】
    - 自动使用系统本地时区
    - 参数格式与标准datetime.datetime构造函数相同
    - 返回的时间对象始终包含时区信息
    
    Returns a datetime object with local timezone information.
    """
    # 创建datetime对象后设置本地时区信息
    return datetime.datetime(*args, **kwargs).replace(tzinfo=tz.tzlocal())


def local_now() -> datetime.datetime:
    """
    【中文说明】获取当前本地时间
    
    【功能描述】
    返回当前系统本地时区的时间。
    
    【返回值】
    - datetime.datetime: 当前本地时间，包含本地时区信息
    
    【使用场景】
    - 需要显示用户本地时间的场景
    - 本地化日志记录
    - 与用户交互时显示本地时间
    
    【注意事项】
    - 返回的时间包含系统本地时区信息
    - 与utc_now()返回的时间可能有时区差异
    - 适合面向用户的场景使用

    Returns the current datetime in local timezone.
    """
    # 获取当前系统时间并设置本地时区
    return datetime.datetime.now().replace(tzinfo=tz.tzlocal())


def to_utc_timestamp(dt: datetime.datetime) -> int:
    """
    【中文说明】将datetime转换为UTC时间戳
    
    【功能描述】
    将包含时区信息的datetime对象转换为UTC时间戳（Unix时间戳）。
    
    【参数说明】
    - dt: datetime.datetime - 要转换的时间对象，必须包含时区信息
    
    【返回值】
    - int: UTC时间戳，表示从1970-01-01 00:00:00 UTC到指定时间的秒数
    
    【算法原理】
    - 使用calendar.timegm()函数计算UTC时间戳
    - 基于datetime.utctimetuple()方法获取UTC时间元组
    
    【使用场景】
    - 与外部系统（如数据库、API）交互时需要时间戳格式
    - 时间序列数据的存储和比较
    - 跨平台时间表示
    
    【注意事项】
    - 输入时间必须包含时区信息
    - 返回的是整数秒级时间戳，不包含毫秒
    - 与time.time()返回的时间戳格式相同

    Converts datetime to UTC timestamp.
    """
    # 使用calendar.timegm计算UTC时间戳
    # 替代方案：(dt - datetime.datetime(1970, 1, 1).replace(tzinfo=datetime.timezone.utc)).total_seconds()
    return calendar.timegm(dt.utctimetuple())
