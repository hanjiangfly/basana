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

from typing import Optional, Sequence
import abc
import codecs
import contextlib
import csv

from basana.core import event

# 本模块不使用异步IO的原因说明：
# asyncio不支持文件系统的异步操作。
# 参考：https://github.com/python/asyncio/wiki/ThirdParty#filesystem
# 可以使用aiofiles，但考虑到：
# * aiofiles将操作委托给单独的线程池
# * 本模块主要用于回测场景，没有其他IO操作发生
# 因此决定最初不支持异步IO。


@contextlib.contextmanager
def open_file_with_detected_encoding(filename, default_encoding='utf-8'):
    """
    自动检测文件编码并打开文件的上下文管理器。
    
    功能描述：
        通过读取文件开头的字节顺序标记（BOM）来自动检测文件的编码格式，
        然后使用正确的编码重新打开文件，并跳过BOM标记。
    
    参数说明：
        filename: str - 要打开的文件路径
        default_encoding: str - 默认编码格式，当无法检测到BOM时使用，默认为'utf-8'
    
    返回值说明：
        返回一个上下文管理器，在上下文中提供已正确打开的文件对象
    
    设计原理解释：
        1. 首先以二进制模式读取文件前4个字节（足够检测所有常见BOM）
        2. 遍历预定义的BOM列表，检查文件开头是否匹配任何BOM
        3. 如果找到匹配的BOM，使用对应的编码并设置偏移量跳过BOM
        4. 使用检测到的编码重新以文本模式打开文件
    
    使用场景说明：
        主要用于处理来自不同来源的CSV文件，这些文件可能使用不同的编码格式，
        如UTF-8、UTF-16、UTF-32等，确保能够正确读取包含非ASCII字符的文件。
    """
    with open(filename, 'rb') as file:
        raw = file.read(4)  # 读取足够的字节来检测BOM

    boms = [
        (codecs.BOM_UTF32_LE, 'utf-32-le'),
        (codecs.BOM_UTF32_BE, 'utf-32-be'),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF8, "utf-8-sig"),
    ]
    encoding = default_encoding
    offset = 0
    for bom, enc in boms:
        if raw.startswith(bom):
            encoding = enc
            offset = len(bom)
            break

    # 使用检测到的编码重新打开文件，并跳过BOM
    f = open(filename, 'r', encoding=encoding)
    if offset:
        f.seek(offset)
    yield f


class RowParser(metaclass=abc.ABCMeta):
    """
    CSV行解析器的抽象基类。
    
    功能描述：
        定义了解析CSV行并将其转换为事件序列的接口。
        这是一个抽象基类，需要子类实现具体的解析逻辑。
    
    设计原理解释：
        使用抽象基类模式，强制子类必须实现parse_row方法。
        这种设计允许不同的CSV格式使用不同的解析器，提高了代码的灵活性和可扩展性。
    
    使用场景说明：
        当需要从CSV文件读取特定格式的数据并转换为事件时，需要创建此类的具体子类。
        例如，可以创建K线数据解析器、交易信号解析器等。
    """
    @abc.abstractmethod
    def parse_row(self, row_dict: dict) -> Sequence[event.Event]:
        """
        解析单行CSV数据并返回事件序列。
        
        参数说明：
            row_dict: dict - 从CSV文件中读取的一行数据，以字典形式表示，
                            键为列名，值为对应的字符串值
        
        返回值说明：
            Sequence[event.Event] - 从该行数据解析出的事件序列
            
        设计原理解释：
            子类需要根据具体的CSV格式，从row_dict中提取相关信息，
            创建相应类型的事件对象并返回。
        
        使用场景说明：
            在CSV事件源处理每一行数据时调用，将原始数据转换为系统内部的事件表示。
        """
        raise NotImplementedError()


def load_sort_and_yield(csv_path: str, row_parser: RowParser, dict_reader_kwargs: dict = {}):
    events = []

    # Load events.
    with open_file_with_detected_encoding(csv_path) as f:
        dict_reader = csv.DictReader(f, **dict_reader_kwargs)
        for row in dict_reader:
            for ev in row_parser.parse_row(row):
                events.append(ev)

    # Sort them for proper delivery.
    events = sorted(events, key=lambda ev: ev.when)

    for ev in events:
        yield ev


def load_and_yield(csv_path: str, row_parser: RowParser, dict_reader_kwargs: dict = {}):

    # Load events.
    with open_file_with_detected_encoding(csv_path) as f:
        dict_reader = csv.DictReader(f, **dict_reader_kwargs)
        for row in dict_reader:
            for ev in row_parser.parse_row(row):
                yield ev


class EventSource(event.EventSource, event.Producer):
    """
    从CSV文件读取事件的事件源类。
    
    功能描述：
        实现了一个事件源，可以从CSV文件中读取事件，并支持按时间排序或按文件顺序交付。
        继承自event.EventSource和event.Producer，既是事件源也是事件生产者。
    
    设计原理解释：
        1. 采用混合继承模式，既是事件源也是生产者
        2. 支持两种事件加载模式：排序模式和非排序模式
        3. 使用异步初始化来准备事件迭代器，但同步提供事件
        4. 设计考虑了回测场景的性能和内存使用
    
    使用场景说明：
        主要用于回测系统中从历史CSV数据加载事件，如K线数据、交易信号等。
        适用于需要从文件系统读取历史数据进行策略测试的场景。
    """
    def __init__(self, csv_path: str, row_parser: RowParser, sort: bool = True, dict_reader_kwargs: dict = {}):
        """
        初始化CSV事件源。
        
        参数说明：
            csv_path: str - CSV文件路径
            row_parser: RowParser - 行解析器实例，用于将CSV行转换为事件
            sort: bool - 是否按事件时间排序，默认为True（排序模式）
            dict_reader_kwargs: dict - 传递给csv.DictReader的额外参数，默认为空字典
        
        设计原理解释：
            在初始化阶段设置所有配置参数，但实际的文件读取和事件生成在initialize方法中进行。
            这种延迟加载设计提高了资源使用效率。
        """
        super().__init__(producer=self)
        self._csv_path = csv_path
        self._row_parser = row_parser
        self._sort = sort
        self._dict_reader_kwargs = dict_reader_kwargs
        self._row_it = None

    async def initialize(self):
        """
        异步初始化事件源。
        
        功能描述：
            根据排序设置创建事件迭代器，准备事件流。
        
        设计原理解释：
            在异步环境中执行文件读取和事件加载，即使文件读取本身是同步的。
            这种设计保持了与异步事件系统的接口一致性。
        
        使用场景说明：
            在事件循环开始前调用，确保事件源已准备好提供事件。
        """
        if self._sort:
            self._row_it = load_sort_and_yield(self._csv_path, self._row_parser, self._dict_reader_kwargs)
        else:
            self._row_it = load_and_yield(self._csv_path, self._row_parser, self._dict_reader_kwargs)

    async def finalize(self):
        """
        异步清理事件源。
        
        功能描述：
            释放事件迭代器资源，清理状态。
        
        设计原理解释：
            提供对称的清理接口，确保资源正确释放。
        
        使用场景说明：
            在事件循环结束后调用，进行资源清理。
        """
        self._row_it = None

    def pop(self) -> Optional[event.Event]:
        """
        从事件源获取下一个事件。
        
        功能描述：
            从事件迭代器中获取下一个事件，如果迭代器耗尽则返回None。
        
        返回值说明：
            Optional[event.Event] - 下一个事件对象，如果没有更多事件则返回None
        
        设计原理解释：
            使用同步的pop方法提供事件，与异步的initialize/finalize方法配合。
            这种混合设计允许在异步环境中使用同步的事件提供机制。
        
        使用场景说明：
            在事件分发循环中重复调用，直到返回None表示事件流结束。
        """
        ret = None
        try:
            if self._row_it:
                ret = next(self._row_it)
        except StopIteration:
            self._row_it = None
        return ret
