# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from ultralytics import YOLO
from pathlib import Path
from typing import Union

import numpy as np
import torch

"""
yolo v8工具类
"""


class YoloUtil(object):
    def __init__(self, model="yolov8n.pt", **kwargs):
        self.model = YOLO(model, **kwargs)
        self.last_predict_results: list = None

    def train(self, data, epochs: int = 100, batch: int = 8, exist_ok: bool = False, **kwargs) -> str:
        """
        使用指定的模型进行训练
        文档:https://docs.ultralytics.com/zh/modes/train/#key-features-of-train-mode
        :param data: yaml文件路径
        :param epochs: 训练总轮数 每轮会整个数据集进行一次完整的训练。调整该值会影响训练时间和模型性能
        :param batch: 训练的批量大小，表示在更新模型内部参数之前要处理多少张图像。自动批处理 (batch=-1)会根据 GPU 内存可用性动态调整批处理大小
        :param exist_ok: 如果为 True，则允许覆盖现有的项目/名称目录。这对迭代实验非常有用，无需手动清除之前的输出
        :param kwargs: 其他参数, 如epochs/batch/exist_ok等
        :return: str  训练得到的 best.pt 路径
        """
        results = self.model.train(data=data, epochs=epochs, batch=batch, exist_ok=exist_ok, **kwargs)
        save_dir = '/'.join(results.save_dir.parts)
        best_pt_path = save_dir + "/weights/best.pt"
        print('train finished:', best_pt_path)
        return best_pt_path

    def predict(self, source: Union[str, Path, int, list, tuple, np.ndarray, torch.Tensor], classes: list = None,
                conf: float = 0.25, save: bool = True,
                save_conf: bool = True, save_txt: bool = True,
                save_dir: str = 'predict/output', **kwargs):
        """
        预测
        :param source: 图片/视频路径
        :param classes: 要检测的类别序号列表,如: [0,1,2], 默认None表示不做过滤
        :param conf: 最低置信度, 默认0.25
        :param save: 是否将注释的图像或视频保存到文件中。这有助于记录、进一步分析或共享结果
        :param save_conf: 在保存的文本文件中包含置信度分数。增强了后期处理和分析的细节
        :param save_txt: 将检测结果保存在文本文件中，格式如下 [class] [x_center] [y_center] [width] [height] [confidence].有助于与其他分析工具集成
        :param save_dir: 保存路径, 会存储到: `runs/detect/{save_dir}`
        :return:
        """
        results = self.model.predict(source=source, classes=classes, conf=conf,
                                     save=save, save_conf=save_conf, save_txt=save_txt, name=save_dir, **kwargs)
        # for result in results:
        #     print("path:", result.path)  # 源文件路径
        #     print("save_dir:", result.save_dir)  # 结果文件保存目录
        #     for box in result.boxes:
        #         print("Object type:", box.cls)  # 类别序号信息,如: tensor([0.], device='cuda:0')
        #         print("Coordinates:", box.xyxy)  # 方框位置,如: tensor([[751.4216, 539.9158, 853.5619, 659.7280]]')
        #         print("Conf:", box.conf)  # 置信度, 如: tensor([0.9951], device='cuda:0')
        #         print("names:", self.model.names)  # 类别序号和名称信息, 如: {0: 'bubble', 1: 'person', 2: 'car'}
        #
        #         class_index = box.cls.item()
        #         class_name = self.model.names[class_index]
        #         confidence = box.conf.item()
        #         bbox = box.xyxy.squeeze().tolist()
        #         print('cur cls name=%s,confidence=%s,bbox=%s' % (class_name, confidence, bbox))

        self.last_predict_results = results
        return results

    def export(self, fmt: str, **kwargs):
        """
        将pt文件导出为指定格式
        :param fmt: 新格式, 如:'tflite'
        :param kwargs:
        :return: 导出文件的路径
        """
        return self.model.export(format=fmt, **kwargs)

    def get_box(self, cls_name: str, min_conf: float = 0.5, predict_results: list = None,
                model_cls_names: dict = None) -> list:
        """
        获取物体检测结果中指定类别的box列表
        :param cls_name: 要获取的类别名称
        :param min_conf: 最低置信度要求
        :param predict_results:检测结果,若为None,则会自动使用上一次检测的结果
        :param model_cls_names:模型类型dict, key-value 分别是 int 和 str, predict_results非空时有效
        :return: list 的元素是 list, 依次表示左上点的x,y和右下角的x,y坐标,即: [[x1,y1,x2,y2]]
        """
        result_boxes = list()
        results = predict_results
        classes = model_cls_names
        if predict_results is None:
            results = self.last_predict_results
            classes = self.model.names

        for result in results:
            for box in result.boxes:
                class_index = box.cls.item()
                class_name = classes[class_index]
                confidence = box.conf.item()
                if cls_name == class_name and confidence >= min_conf:
                    result_boxes.append(box.xyxy.squeeze().tolist())
        return result_boxes
