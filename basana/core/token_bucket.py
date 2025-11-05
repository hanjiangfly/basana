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

import asyncio
import time


class TokenBucketLimiter:
    """
    【中文说明】令牌桶限流器
    
    【功能描述】
    实现令牌桶算法，用于限制请求速率，防止系统过载。
    令牌桶算法是一种常用的流量整形和速率限制算法。
    
    【算法原理】
    1. 令牌以固定速率添加到桶中（令牌生成）
    2. 每个请求需要消耗一个令牌才能执行
    3. 如果桶中有足够的令牌，请求立即执行
    4. 如果令牌不足，请求需要等待直到有足够的令牌
    
    【参数说明】
    - tokens_per_period: float - 每个周期内生成的最大令牌数量
    - period_duration: int - 周期时长（秒）
    - initial_tokens: int - 初始令牌数量，默认为0
    
    【使用场景】
    - API调用速率限制
    - 网络请求流量控制
    - 数据库查询频率限制
    - 防止DDoS攻击和系统过载
    
    【注意事项】
    - 令牌数量不能超过tokens_per_period设置的最大值
    - 支持异步等待，适合高并发场景
    - 时间精度依赖于系统时钟

    This class implements a token bucket algorithm, useful for throttling requests.

    :param tokens_per_period: The maximum amount of tokens per perdiod.
    :param period_duration: The period duration in seconds.
    :param initial_tokens: The initial amount of tokens.
    """

    def __init__(self, tokens_per_period: float, period_duration: int, initial_tokens=0):
        """
        【中文说明】初始化令牌桶限流器
        
        【功能描述】
        创建令牌桶限流器实例，设置令牌生成速率和初始状态。
        
        【参数说明】
        - tokens_per_period: float - 每个周期内生成的最大令牌数量，必须大于0
        - period_duration: int - 周期时长（秒），必须大于0
        - initial_tokens: int - 初始令牌数量，必须大于等于0
        
        【验证检查】
        - 确保令牌生成速率和周期时长都是正数
        - 确保初始令牌数量非负
        
        【内部状态】
        - _tokens_per_period: 每个周期的最大令牌数
        - _period_duration: 周期时长（秒）
        - _tokens: 当前令牌数量
        - _last: 上次令牌补充的时间戳
        """
        # 验证令牌生成速率必须大于0
        assert tokens_per_period > 0
        # 验证周期时长必须大于0
        assert period_duration > 0
        # 验证初始令牌数量必须大于等于0
        assert initial_tokens >= 0

        # 每个周期内生成的最大令牌数量
        self._tokens_per_period = tokens_per_period
        # 周期时长（秒）
        self._period_duration = period_duration
        # 当前令牌数量
        self._tokens = initial_tokens
        # 上次令牌补充的时间戳
        self._last = time.time()

    @property
    def tokens(self) -> int:
        """
        【中文说明】获取当前可用令牌数量
        
        【功能描述】
        返回当前桶中可用的令牌数量，确保返回值为非负整数。
        
        【返回值】
        - int: 当前可用的令牌数量
        
        【使用场景】
        - 监控令牌桶状态
        - 调试和性能分析
        - 动态调整限流策略
        
        【注意事项】
        - 返回的是整数令牌数量
        - 内部使用浮点数计算，但对外暴露整数
        """
        return max(int(self._tokens), 0)

    @property
    def tokens_per_period(self) -> float:
        """
        【中文说明】获取每个周期的最大令牌数量
        
        【返回值】
        - float: 每个周期内生成的最大令牌数量
        """
        return self._tokens_per_period

    @property
    def period_duration(self) -> int:
        """
        【中文说明】获取周期时长
        
        【返回值】
        - int: 周期时长（秒）
        """
        return self._period_duration

    def consume(self) -> float:
        """
        【中文说明】消费一个令牌
        
        【功能描述】
        尝试消费一个令牌，如果令牌不足则返回需要等待的时间。
        该方法会自动补充令牌（基于时间流逝）。
        
        【返回值】
        - float: 需要等待的时间（秒），如果不需要等待则返回0.0
        
        【算法步骤】
        1. 计算自上次调用以来的时间流逝
        2. 根据时间流逝补充相应数量的令牌
        3. 确保令牌数量不超过最大值
        4. 尝试消费一个令牌
        5. 如果令牌不足，计算需要等待的时间
        
        【使用场景】
        - 在发送请求前检查是否被限流
        - 实现精确的速率控制
        
        【注意事项】
        - 该方法会修改内部令牌状态
        - 返回的等待时间基于当前令牌缺口计算
        """
        # 补充令牌池：基于时间流逝计算应该补充的令牌数量
        now = time.time()
        # 计算自上次调用以来的时间流逝
        lapse = now - self._last
        self._last = now
        # 根据时间流逝补充令牌：流逝时间 / 周期时长 * 每周期令牌数
        self._tokens += lapse / self._period_duration * self._tokens_per_period
        # 确保令牌数量不超过最大值
        if self._tokens > self._tokens_per_period:
            self._tokens = self._tokens_per_period

        # 消费一个令牌
        self._tokens -= 1

        # 如果令牌数量足够，不需要等待
        if self._tokens >= 0:
            return 0.0
        else:
            # 计算需要等待的时间：令牌缺口 / 每周期令牌数 * 周期时长
            return -self._tokens / self._tokens_per_period * self._period_duration

    async def wait(self):
        """
        【中文说明】异步等待直到可以消费令牌
        
        【功能描述】
        异步等待所需的时间，直到可以安全地消费一个令牌。
        
        【内部操作】
        - 调用consume()方法获取需要等待的时间
        - 如果需要等待，执行异步睡眠
        - 如果不需要等待，立即返回
        
        【使用场景】
        - 在异步代码中实现速率限制
        - 控制并发请求的频率
        
        【注意事项】
        - 这是一个异步方法，需要在异步环境中调用
        - 等待时间基于令牌桶的当前状态
        """
        # 等待所需的时间，直到可以消费令牌
        await asyncio.sleep(self.consume())
