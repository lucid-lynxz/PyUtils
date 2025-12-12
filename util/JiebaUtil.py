# !/usr/bin/env python3
# -*- coding:utf-8 -*-
from typing import Optional, Union, Set, Dict, List

import jieba
import jieba.posseg as pseg

from util.CommonUtil import CommonUtil


class JiebaUtil:
    """
    jieba库工具类

    常见词性
    flag_en2cn = {
        'a': '形容词', 'ad': '副形词', 'ag': '形语素', 'an': '名形词', 'b': '区别词',
        'c': '连词', 'd': '副词', 'df': '不要', 'dg': '副语素',
        'e': '叹词', 'f': '方位词', 'g': '语素', 'h': '前接成分',
        'i': '成语', 'j': '简称略语', 'k': '后接成分', 'l': '习用语',
        'm': '数词', 'mg': '数语素', 'mq': '数量词',
        'n': '名词', 'ng': '名语素', 'nr': '人名', 'nrfg': '古代人名', 'nrt': '音译人名',
        'ns': '地名', 'nt': '机构团体', 'nz': '其他专名',
        'o': '拟声词', 'p': '介词', 'q': '量词',
        'r': '代词', 'rg': '代语素', 'rr': '代词', 'rz': '代词',
        's': '处所词', 't': '时间词', 'tg': '时间语素',
        'u': '助词', 'ud': '得', 'ug': '过', 'uj': '的', 'ul': '了', 'uv': '地', 'uz': '着',
        'v': '动词', 'vd': '副动词', 'vg': '动语素', 'vi': '动词', 'vn': '名动词', 'vq': '动词',
        'x': '非语素字', 'y': '语气词', 'z': '状态词', 'zg': '状态语素',
    }
    """

    # 常见的动词和名词标记
    verb_flags = {'v', 'vd', 'vi', 'vg', 'vn'}
    noun_flags = {'n', 'f', 's', 't', 'nr', 'ns', 'nt', 'nz', 'nrt', 'nrfg'}

    # 默认的停用词列表,若有传入, 则非对源文本分词后删除对应的词再做后续操作
    default_stop_words: Set[str] = set()

    # 需删除的词性标签（非语素词+语气词），可按需增删
    default_delete_tags: Set[str] = {
        # 核心必删：非语素字,语气词+助词+叹词+拟声词+标点
        'x', 'y', 'u', 'e', 'o', 'w',
        # 可选删除：空泛方位词/副词/数词/量词（根据业务调整）
        # "f", "d", "m", "q"
    }

    # 需要替换的词性标签 (会先删除再做替换), 比如日常可能会将数词词性看成名词,方便判断短语是否是简单名词
    # key-原词性  value-新词性
    default_replace_tags: Dict[str, str] = {}

    # 替换指定次的词性,部分配置通过 load_dict() 可能无效, 此处可以强制替换
    # key-分词, 比如: '镇'   value-词性, 比如: 'n', 则recook() 分词得到 '镇' 时, 会将其词性改为 'n'
    default_replace_word_tag: Dict[str, str] = {}

    @staticmethod
    def init(user_dict: str = None,
             words: Optional[Dict[str, str]] = None,
             stop_words: Optional[Set[str]] = None,
             replace_tags: Optional[Dict[str, str]] = None,
             delete_tags: Optional[Set[str]] = None,
             replace_word_tag: Optional[Dict[str, str]] = None
             ):
        """
        初始化jieba库
        :param user_d
        ict: 自定义词典路径, 若传入, 则会加载自定义词典
        :param words: 自定义词典set, 其 key-词语  value-词性,比如 {'停车场': 'n'}  以便确保专有名词不被拆分, 效果等同于user_dict
        :param stop_words: 默认的停用词列表, 若传入, 则会过滤停用词, 比如: {'的' , '?' }
        :param replace_tags: 需要替换的词性标签, 比如日常可能会将数词词性看成名词,方便判断短语是否是简单名词
        :param delete_tags: 需删除的词性标签（非语素词+语气词） (会先替换再删除)，可按需增删, 比如: {'y', 'u', 'uj', 'uz', 'uv', 'e', 'o', 'w'}
        :param replace_word_tag: 将指定分词改为特定的词性, 比如: '镇' 原本会被识别为动词'v', 传入: {'镇':'n'} 可强行改为名称 'n'
        """
        if user_dict:
            jieba.load_userdict(user_dict)

        if words:
            for word, tag in words.items():
                jieba.add_word(word, None, tag)

        if stop_words:
            JiebaUtil.default_stop_words.update(stop_words)

        if replace_tags:
            JiebaUtil.default_replace_tags.update(replace_tags)

        if delete_tags:
            JiebaUtil.default_delete_tags.update(delete_tags)

        if replace_word_tag:
            JiebaUtil.default_replace_word_tag.update(replace_word_tag)

    @staticmethod
    def recook(text: str, stop_words: Optional[Set[str]] = None,
               replace_tags: Optional[Dict[str, str]] = None,
               replace_word_tag: Optional[Dict[str, str]] = None,
               delete_tags: Optional[Set[str]] = None,
               delete_previous_words: bool = False,
               print_log: bool = False) -> List[pseg.pair]:
        """
        分词并替换和删除指定词性/停止词信息，返回有核心词汇
        :param text: 输入文本
        :param stop_words: 自定义停用词列表, 若传入, 则会过滤停用词, 比如: {'的', '?' }
        :param replace_tags: 需要替换的词性标签, 比如日常可能会将数词词性看成名词,方便判断短语是否是简单名词
        :param replace_word_tag:  将指定分词改为特定的词性, 比如: '镇' 原本会被识别为动词'v', 传入: {'镇':'n'} 可强行改为名称 'n'
        :param delete_tags: 需删除的词性标签（非语素词+语气词） (会先替换再删除)，可按需增删, 比如: {'y', 'u', 'uj', 'uz', 'uv', 'e', 'o', 'w'}
        :param delete_previous_words: 当命中 stop_words或delete_tags 操作时, 是否删除该词之前已缓存的词,默认false
        :param print_log: 是否打印日志
        :return: 过滤后的词性信息数组, 若要获取最终文本: ''.join([pair.word for pair in filtered_words])
        """
        # 步骤1：分词+词性标注
        words_with_tags = pseg.lcut(text)

        t_delete_tags = JiebaUtil.default_delete_tags if delete_tags is None else JiebaUtil.default_delete_tags.union(delete_tags)
        t_stop_words = JiebaUtil.default_stop_words if stop_words is None else JiebaUtil.default_stop_words.union(stop_words)
        t_replace_tags = JiebaUtil.default_replace_tags if replace_tags is None else (JiebaUtil.default_replace_tags | replace_tags)  # python 3.9+
        t_replace_word_tags = JiebaUtil.default_replace_word_tag if replace_word_tag is None else (JiebaUtil.default_replace_word_tag | replace_word_tag)

        # 步骤2：过滤规则
        filtered_words = []
        for pair in words_with_tags:
            word, flag = pair.word, pair.flag

            # 先进行词性替换
            if flag in t_replace_tags:
                flag = t_replace_tags[flag]
                pair.flag = flag

            # 修改分次词性替换
            if len(t_replace_word_tags) > 0:
                if pair.word in t_replace_word_tags:
                    flag = t_replace_word_tags[pair.word]
                    pair.flag = flag

            # 条件1：排除指定词性的词
            if flag in t_delete_tags:
                if delete_previous_words:
                    filtered_words.clear()
                continue
            # 条件2：排除自定义停用词
            if word in t_stop_words:
                if delete_previous_words:
                    filtered_words.clear()
                continue
            # 条件3：排除空字符串/单字无实义词（可选，根据业务调整）
            if len(word) < 1 or word.strip() == "":
                continue
            # 保留有语义的词
            filtered_words.append(pair)

        if print_log:
            f_text = ''.join([pair.word for pair in filtered_words])
            if text == f_text:
                CommonUtil.printLog(f'recook("{text})": {filtered_words}', print_log)
            else:
                CommonUtil.printLog(f'recook("{text})" -> "{f_text}": {filtered_words}, ori words_with_tags:{words_with_tags}', print_log)

        return filtered_words
        # return ''.join([pair.word for pair in filtered_words])

    @staticmethod
    def is_noun_phrase(text: Union[str, List[jieba.posseg.pair]],
                       endswith_noun_only: bool = False,
                       **kwargs) -> bool:
        """
        简单判断一个文本片段是否是名词性短语, 不一定准确
        策略：
        1. 分析分词和词性
        2. 如果所有分次都是名词词性,则肯定是名词性短语
        3. 如果短语以动词结尾，则大概率不是名词性短语
        4. 如果短语以名词结尾，则很可能是名词性短语
        5. 特殊处理一些常见的非名词短语结构，如“动词+名词”

        :param text: 待判断的文本片段 或者已经拆分好的词性列表
        :param endswith_noun_only: 只要以名词结尾的, 都返回True, 默认False
        :param **kwargs: 主要是传入 recook() 方法支持的参数, 包括以下内容:
            stop_words (Optional[Set[str]]): 停用词列表, 若传入, 则会过滤停用词, 比如: {'的' , '?' }
            replace_tags (Optional[Dict[str, str]]): 需要替换的词性标签 , 比如日常可能会将数词词性看成名词,方便判断短语是否是简单名词
            delete_tags (Optional[Set[str]]): 需删除的词性标签（非语素词+语气词）(会先替换再做删除)，可按需增删, 比如: {'y', 'u', 'uj', 'uz', 'uv', 'e', 'o', 'w'}
            replace_word_tag (Optional[Dict[str, str]]):  将指定分词改为特定的词性, 比如: '镇' 原本会被识别为动词'v', 传入: {'镇':'n'} 可强行改为名称 'n'
            print_log (bool): 是否打印日志
        """
        if not text:
            return False

        if isinstance(text, str):
            word_list = JiebaUtil.recook(text, **kwargs)
        else:
            word_list = text

        print_log: bool = kwargs.get('print_log', False)
        if not word_list:
            CommonUtil.printLog(f'is_noun_phrase("{text})" fail, word_list is: {word_list}', print_log)
            return False
        CommonUtil.printLog(f'is_noun_phrase: {text}: {word_list if isinstance(text, str) else ""}', print_log)

        # 获取词性标记
        flags = [word.flag for word in word_list]

        # 若所有词性都是名词, 则直接返回True
        if all(flag.startswith('n') for flag in flags):
            return True

        # 规则1: 如果以动词结尾，则不是名词短语。
        # 这可以处理 "正在跑步", "导航去厦门" (厦门是ns, 但去是v, 整个短语是v-n结构)
        if flags[-1] in JiebaUtil.verb_flags:
            CommonUtil.printLog(f'is_noun_phrase("{text}")=False as flags[-1]={flags[-1]} is verb_flag', print_log)
            return False

        # 有任何动词就不算名词性短语
        # 若有需要忽略指定的动词, 请按需传入: stop_words 参数
        if not endswith_noun_only and any(flag in JiebaUtil.verb_flags for flag in flags):
            return False

        # 非名词结尾的都返回False
        return flags[-1] in JiebaUtil.noun_flags


if __name__ == '__main__':
    import os

    # 名词短语
    noun_text_list = ['呃 , 唔!@@@北京 天安门 广场', '洛阳古墓博物馆', '农业银行', "杭州山姆会员店"]

    current_dir = os.path.dirname(os.path.abspath(__file__))
    user_dict = f'{current_dir}/cache/user_dict.txt'
    _delete_tags = {'uj'}
    _relace_tags = {'m': 'n'}

    JiebaUtil.init(user_dict, delete_tags=_delete_tags, replace_tags=_relace_tags)
    for text in noun_text_list:
        if not JiebaUtil.is_noun_phrase(text, print_log=False):
            print(f'{text} 不是名词性短语, 与预期不符')
            JiebaUtil.recook(text, print_log=True)
