# !/usr/bin/env python3
# -*- coding:utf-8 -*-

""""
读取ini文件工具类,自动将指定的section items信息生成dict,并保留options大小写
"""
import configparser


class NewConfigParser(configparser.ConfigParser):
    """
    自定义ConfigParser, 处理options返回小写的问题
    参考:https://www.cnblogs.com/wozijisun/p/6371084.html
    要求先通过 initPath(...) 设置参数文件路径
    然后通过 getSectionItems(...)
    """

    def initPath(self, configPath: str):
        """
        :param configPath: ini文件路径
        """
        self.read(configPath, encoding='utf-8')
        return self

    def optionxform(self, optionstr):
        return optionstr

    def getSectionItems(self, sectionName: str) -> dict:
        """
        从指定的ini文件中读取sections信息,并生成dict
        :param sectionName: ini中section名称
        :return: dict
        """
        items = self.items(sectionName)
        resultDict = {}
        for item in items:
            resultDict[item[0]] = item[1]
        return resultDict
