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
【中文说明】Binance K线数据下载工具模块
【功能描述】提供从Binance交易所下载历史K线数据并保存为CSV格式的功能
【使用场景】用于获取历史K线数据用于回测、分析和研究
【注意事项】支持多种时间周期，包含命令行接口和异步数据获取
"""

from typing import List, Optional
import argparse
import datetime
import sys

import aiohttp
import asyncio

from basana.core import dt, token_bucket
from basana.external.binance import client, helpers


period_to_step = {
    "1s": 1,
    "1m": 60,
    "3m": 3 * 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 3600,
    "2h": 2 * 3600,
    "4h": 4 * 3600,
    "6h": 6 * 3600,
    "8h": 8 * 3600,
    "12h": 12 * 3600,
    "1d": 86400,
    "3d": 3 * 86400,
    "1w": 7 * 86400,
    "1M": 31 * 86400,
}
"""
【中文说明】时间周期到秒数的映射字典
【功能描述】定义Binance支持的各种K线时间周期对应的秒数
【使用场景】用于计算时间间隔和验证周期参数
【注意事项】包含从1秒到1个月的各种时间周期，1个月按31天计算
"""


def parse_date(date: str):
    """
    【中文说明】解析日期字符串
    【功能描述】将YYYY-MM-DD格式的日期字符串转换为UTC时区的datetime对象
    【参数说明】
    - date: 日期字符串，格式为YYYY-MM-DD
    【返回说明】UTC时区的datetime对象
    """
    return datetime.datetime.combine(
        datetime.date.fromisoformat(date), datetime.time()
    ).replace(tzinfo=datetime.timezone.utc)


class Candlestick:
    """
    【中文说明】K线数据类
    【功能描述】封装Binance K线数据的各个字段
    【使用场景】用于解析和存储从API获取的K线数据
    【注意事项】时间戳为毫秒级，价格和数量为字符串格式
    """
    def __init__(self, candlestick: list):
        """
        【中文说明】初始化K线数据
        【功能描述】从API返回的列表数据创建K线对象
        【参数说明】
        - candlestick: K线数据列表，包含7个元素
        【数据格式】
        - [0]: 开盘时间戳（毫秒）
        - [1]: 开盘价
        - [2]: 最高价
        - [3]: 最低价
        - [4]: 收盘价
        - [5]: 成交量
        - [6]: 收盘时间戳（毫秒）
        """
        self.open_timestamp = candlestick[0]
        self.open = candlestick[1]
        self.high = candlestick[2]
        self.low = candlestick[3]
        self.close = candlestick[4]
        self.volume = candlestick[5]
        self.close_timestamp = candlestick[6]


def to_binance_currency_pair(currency_pair: str):
    """
    【中文说明】转换交易对格式
    【功能描述】将斜杠分隔的交易对格式转换为Binance格式
    【参数说明】
    - currency_pair: 交易对字符串，如"BTC/USDT"
    【返回说明】Binance格式的交易对字符串，如"BTCUSDT"
    【示例】"BTC/USDT" -> "BTCUSDT"
    """
    parts = currency_pair.upper().split("/")
    return "".join(parts)


class CSVWriter:
    """
    【中文说明】CSV写入器类
    【功能描述】将K线数据写入CSV文件或标准输出
    【使用场景】用于保存下载的K线数据到CSV格式
    【注意事项】支持文件输出和标准输出两种模式
    """
    def __init__(self, output_file: Optional[str]):
        """
        【中文说明】初始化CSV写入器
        【功能描述】创建CSV写入器实例，配置输出目标
        【参数说明】
        - output_file: 输出文件路径，如果为None则输出到标准输出
        """
        self._header_written = False
        self._output_file = open(output_file, "w") if output_file else sys.stdout

    def write_candlestick(self, candlestick: Candlestick):
        """
        【中文说明】写入K线数据
        【功能描述】将单个K线数据写入CSV文件
        【参数说明】
        - candlestick: K线数据对象
        【注意事项】如果是第一次写入，会自动写入CSV表头
        """
        if not self._header_written:
            print("datetime,open,high,low,close,volume", file=self._output_file)
            self._header_written = True

        dt_col = datetime.datetime.fromtimestamp(candlestick.open_timestamp / 1000, tz=datetime.timezone.utc)
        print(",".join([
            str(dt_col.replace(tzinfo=None)),
            candlestick.open, candlestick.high, candlestick.low, candlestick.close, candlestick.volume
        ]), file=self._output_file)


async def main(params: Optional[List[str]] = None, config_overrides: dict = {}):
    """
    【中文说明】主函数 - 下载Binance K线数据
    【功能描述】从Binance交易所下载指定时间范围和周期的K线数据并保存为CSV格式
    【使用场景】作为命令行工具使用，支持异步数据获取和分页下载
    【参数说明】
    - params: 命令行参数列表，可选
    - config_overrides: 配置覆盖项，可选
    【注意事项】使用令牌桶限流器控制API请求频率，避免被限流
    """
    # 【中文说明】解析命令行参数
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--currency-pair", help="The currency pair.", required=True)
    parser.add_argument(
        "-p", "--period", help="The period for the bars.", choices=period_to_step.keys(), required=True
    )
    parser.add_argument(
        "-s", "--start", help="The starting date YYYY-MM-DD format. Included in the range.", required=True
    )
    parser.add_argument(
        "-e", "--end", help="The ending date YYYY-MM-DD format. Included in the range.", required=True
    )
    parser.add_argument("-o", "--output", help="The output file.", required=False, default=None)
    parser.add_argument("--proxy", help="Proxy URL for HTTP requests (supports HTTP/HTTPS/SOCKS5).", required=False, default=None)
    args = parser.parse_args(args=params)

    # 【中文说明】计算时间参数
    step = period_to_step[args.period]
    start = parse_date(args.start)
    end = parse_date(args.end)
    assert start <= end, "Invalid start/end"
    # 【中文说明】start/end设置为日期，为了超过结束时间，我们需要使用至少1天的时间步长
    past_the_end = end + datetime.timedelta(seconds=max(period_to_step["1d"], step))

    # 【中文说明】转换为时间戳（毫秒）
    start_ts = helpers.datetime_to_timestamp(start)
    past_the_end_ts = helpers.datetime_to_timestamp(past_the_end)
    step = step * 1000  # 转换为毫秒

    # 【中文说明】初始化限流器和写入器
    tb = token_bucket.TokenBucketLimiter(10, 1)  # 10个令牌，每秒补充1个
    now_ts = helpers.datetime_to_timestamp(dt.utc_now())
    writer = CSVWriter(args.output)
    
    # 【中文说明】异步下载数据
    async with aiohttp.ClientSession() as session:
        cli = client.APIClient(session=session, tb=tb, config_overrides=config_overrides, proxy=args.proxy)
        eof = False
        currency_pair = to_binance_currency_pair(args.currency_pair)
        
        # 【中文说明】分页下载循环
        while not eof:
            # 【中文说明】获取K线数据
            response = await cli.get_candlestick_data(
                currency_pair, args.period, start_time=start_ts, end_time=past_the_end_ts, limit=1000
            )
            eof = True
            
            # 【中文说明】处理返回的K线数据
            for candlestick in response:
                eof = False
                candlestick = Candlestick(candlestick)
                start_ts = max(start_ts, candlestick.open_timestamp)
                
                # 【中文说明】跳过超出时间范围或未来的数据
                if candlestick.open_timestamp >= past_the_end_ts or candlestick.close_timestamp >= now_ts:
                    continue
                    
                writer.write_candlestick(candlestick)
                
            # 【中文说明】更新起始时间戳，继续下一页
            if not eof:
                start_ts += step
                eof = start_ts >= past_the_end_ts


if __name__ == "__main__":  # pragma: no cover
    """
    【中文说明】程序入口点
    【功能描述】当脚本直接运行时启动异步主函数
    【使用场景】作为独立的命令行工具使用
    """
    asyncio.run(main())
