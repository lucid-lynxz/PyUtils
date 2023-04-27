# !/usr/bin/env python3
# -*- coding:utf-8 -*-

""""
读取ini文件工具类,自动将指定的section items信息生成dict,并保留options大小写
"""
import configparser


class NewConfigParser(configparser.RawConfigParser):
    """
    自定义ConfigParser, 处理options返回小写的问题
    参考:https://www.cnblogs.com/wozijisun/p/6371084.html
    要求先通过 initPath(...) 设置参数文件路径
    然后通过 getSectionItems(...)
    变更为: RawConfigParser, 忽略config文件中的 % 等特殊字符
    """

    def initPath(self, configPath: str):
        """
        :param configPath: ini文件路径
        """
        self.read(configPath, encoding='utf-8')

        # 缓存config文件内容, key-sectionName value-dict 存储该section中所有k v数据
        self._cache: dict = {}
        for sectionName in self.sections():
            self._cache[sectionName] = self.getSectionItems(sectionName)
        return self

    def optionxform(self, optionstr):
        return optionstr

    def getSectionItems(self, sectionName: str) -> dict:
        """
        从指定的ini文件中读取sections信息,并生成dict
        :param sectionName: ini中section名称
        :return: dict
        """

        if sectionName in self._cache:
            return self._cache[sectionName]

        if not self.has_section(sectionName):
            return {}

        items = self.items(sectionName)
        resultDict = {}
        for item in items:
            resultDict[item[0]] = item[1]
        return resultDict

    def getSectionKeyList(self, sectionName: str) -> list:
        """获取指定section中的所有key列表"""
        result = list()
        map = self.getSectionItems(sectionName)
        if map is not None:
            for key in map:
                result.append(key)  # 保持原始的key,包括前后的空格
        return result

    def updateSectonItem(self, sectionName: str, key: str, value: str):
        """
        更新section属性值
        :param sectionName: section名称, 若不存在,则会新增
        :param key: 属性名
        :param value: 属性值
        """
        if sectionName not in self:
            self.add_section(sectionName)
        self.set(sectionName, key, value)
        sectionDict = self._cache.get(sectionName, dict())
        sectionDict[key] = value
