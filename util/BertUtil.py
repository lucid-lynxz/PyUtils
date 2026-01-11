#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# pip install torch transformers datasets scikit-learn evaluate pandas numpy tokenizers -U

import os
import platform
import re
import warnings
from typing import Optional, List, Dict, Tuple, Set

import numpy as np
import pandas as pd
import torch
from datasets import Dataset, DatasetDict, ClassLabel
from sklearn.utils.class_weight import compute_class_weight
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments, AutoTokenizer, AutoModelForTokenClassification, pipeline

from util.CSVUtil import CSVUtil
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
基于bert-base-chinese库的语义分类工具类, 网址: https://huggingface.co/google-bert/bert-base-chinese/tree/main
相关方法:
训练: train()
预测: predict_single_with_confidence()

基于 uer/roberta-base-finetuned-cluener2020-chinese 进行的命名实体识别(NER),
hg网址:https://huggingface.co/uer/roberta-base-finetuned-cluener2020-chinese
github:https://github.com/CLUEbenchmark/CLUENER2020
相关方法: 
提取实体关键信息: extract_entity()
生成类别信息: update_entity_category()



以上库默认从huggingface加载, 可以手动下载后离线使用,通常需要下载以下文件:
* config.json	            模型结构配置（层数、维度等），是加载模型的 “身份证”
* tokenizer_config.json	    分词器配置（如何切分文本、最大长度等）
* pytorch_model.bin	        模型权重文件（核心参数），PyTorch 框架必须依赖
* vocab.txt	                分词器词汇表（中文模型的汉字、符号映射）
* special_tokens_map.json	特殊 token 映射（如 [CLS]/[SEP] 等，分词器需要）

以下几个可以不用下载, 补充下文件功能说明:
* flax_model.msgpack：Flax/JAX 框架的权重（用 PyTorch 的话不需要）
* tf_model.h5：TensorFlow 框架的权重（同理，不用 TensorFlow 则无需下载）
* added_tokens.json：如果模型没有额外新增 token，这个文件可选（大部分场景用不到）
* .gitattributes/README.md：仓库配置和说明文档（不影响模型加载）
"""

# ===================== 基础配置 & 内存保护 =====================
os.environ["WANDB_DISABLED"] = "true"  # 关闭wandb日志
# os.environ["CUDA_VISIBLE_DEVICES"] = "-1" # 强制使用CPU避免显存错误
# 设置 Hugging Face 镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# os.environ["HF_ENDPOINT"] = "https://hub.yonghong.tech"
# os.environ["HF_ENDPOINT"] = "https://aliendao.cn"
# os.environ["HF_HUB_OFFLINE"] = "0"  # 设为1表示离线模式，0表示在线

# 限制PyTorch内存占用策略
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True
warnings.filterwarnings('ignore')

# ===================== 环境检测 =====================
print("=" * 50)
print("环境检测：")
print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA是否可用: {torch.cuda.is_available()}")
print(f"操作系统: {platform.system()}")
if torch.cuda.is_available():
    print(f"CUDA版本: {torch.version.cuda}")
    print(f"GPU名称: {torch.cuda.get_device_name(0)}")
    print(f"GPU显存: {torch.cuda.get_device_properties(0).total_memory / 1024 / 1024:.0f} MB")
else:
    print("CUDA不可用")
print("=" * 50)


class BertUtil:
    """
    基于bert-base-chinese的语义分类工具类
    核心优化：
    1. 使用更大容量的bert-base模型
    2. 强制CPU运行避免显存问题
    3. 标签索引边界检查，避免内存越界
    4. 更严格的内存管理
    5. macOS 兼容性优化
    """

    _cache = FileUtil.create_cache_dir(None, __file__)

    def __init__(
            self,
            classify_model_path: str = "bert-base-chinese",
            id2label: Optional[Dict[int, str]] = None,
            device: Optional[str] = None,
            ner_model_path: str = "uer/roberta-base-finetuned-cluener2020-chinese",
            model_cache_dir: Optional[str] = None
    ):
        """
        初始化工具类
        :param classify_model_path: 文本分类模型路径, 也支持本地路径, 默认是下载到 HF_HOME 所在的目录,若未设置, 默认位置: 'C:/Users/{用户名}/.cache/huggingface/' 目录
                            bert-base-chinese 模型下载地址:  https://huggingface.co/google-bert/bert-base-chinese/tree/main
                           若训练速度太慢, 且对精度要求不高, 可以使用模型: "prajjwal1/bert-tiny"  下载地址:  https://huggingface.co/prajjwal1/bert-tiny/tree/main
        :param id2label: 标签id到名称的映射, 格式: {0: "测试", 1: "其他"}   key-数字 value-名称
        :param device: 运行设备（自动检测或手动指定）
        :param ner_model_path: 文本关键信息提取模型路径, 也支持本地路径
        :param model_cache_dir: 缓存目录, 用于存储模型和分词器, 默认为 None, 会自动创建缓存目录
        """

        if model_cache_dir is None:
            model_cache_dir = FileUtil.recookPath(f"{BertUtil._cache}/models")
        FileUtil.createFile(f'{model_cache_dir}/', False)

        # 处理分类模型路径
        classify_model_path = classify_model_path if classify_model_path else 'bert-base-chinesebert-base-chinese'
        is_local_path = FileUtil.isFileExist(classify_model_path)
        local_path = classify_model_path if is_local_path else f'{model_cache_dir}/{classify_model_path}/'
        local_path = FileUtil.recookPath(local_path)
        is_local_path = FileUtil.isFileExist(local_path)
        classify_model_path = local_path if is_local_path else classify_model_path
        CommonUtil.printLog(f"加载文本分类模型: {classify_model_path}")

        # 处理NER模型路径
        ner_model_path = ner_model_path if ner_model_path else 'uer/roberta-base-finetuned-cluener2020-chinese'
        is_local_path = FileUtil.isFileExist(ner_model_path)
        local_path = ner_model_path if is_local_path else f'{model_cache_dir}/{ner_model_path}/'
        local_path = FileUtil.recookPath(local_path)
        is_local_path = FileUtil.isFileExist(local_path)
        ner_model_path = local_path if is_local_path else ner_model_path
        CommonUtil.printLog(f"加载文本关键信息提取模型: {ner_model_path}")

        # 基础配置
        self.model_cache_dir = model_cache_dir
        self.model_path = classify_model_path
        self.id2label = id2label if id2label else {0: "测试", 1: "其他"}
        self.num_labels = len(self.id2label)
        self.label2id = {v: k for k, v in self.id2label.items()}

        # 改进设备检测，特别针对 macOS
        if device is None:
            if platform.system() == "Darwin":  # macOS
                # macOS 默认使用 CPU，因为 MPS 支持可能不稳定
                self.device = torch.device('cpu')
                print("检测到 macOS 系统，强制使用 CPU 设备")
            elif torch.cuda.is_available():
                self.device = torch.device('cuda')
            else:
                self.device = torch.device('cpu')
        else:
            # 如果用户明确指定，验证设备可用性
            if device == 'cuda' and not torch.cuda.is_available():
                print("警告：CUDA 不可用，强制使用 CPU")
                self.device = torch.device('cpu')
            else:
                self.device = torch.device(device)

        # 以下是文本分类相关变量, 初始化模型/分词器
        self.tokenizer = None
        self.model = None
        self.trainer = None
        self.training_args = None

        # 标签映射相关
        self.data_label_classes = None
        self.data_label2idx = None
        self.idx2data_label = None

        # train() 后生成的微调模型信息
        self.predict_model_path = None
        self.predict_model = None
        self.predict_tokenizer = None

        # 以下是文本关键信息提取(NER)相关变量初始化tokenizer和模型（中文优化版）
        if ner_model_path is not None:
            local_path = FileUtil.isFileExist(ner_model_path)
            abs_path_ner = ner_model_path
            # if abs_path_ner.endswith('/'):
            #     abs_path_ner = abs_path_ner[:-1]

            CommonUtil.printLog(f"加载文本关键信息提取模型 | 本地路径：{local_path} | 模型路径：{FileUtil.recookPath(abs_path_ner) if local_path else abs_path_ner}")
            self.tokenizer_ner = AutoTokenizer.from_pretrained(abs_path_ner, local_files_only=local_path, cache_dir=self.model_cache_dir, resume_download=True)
            self.model_ner = AutoModelForTokenClassification.from_pretrained(abs_path_ner, local_files_only=local_path)
            self.pipeline_ner = pipeline("token-classification", model=self.model_ner, tokenizer=self.tokenizer_ner, aggregation_strategy="simple")
            self.entity_category: Set[str] = set()  # 实体类别, 用于模型提取无结果时的兜底策略, 通过 update_entity_category() 方法进行设置

            # 打印模型的标签数量和索引（key的范围）
            CommonUtil.printLog("模型的标签数量：", self.model_ner.num_labels)  # 输出7，对应0-6
            CommonUtil.printLog("模型的标签索引范围：0 ~", self.model_ner.num_labels - 1)

            # （进阶）如果模型自带id2label映射，可直接获取
            if hasattr(self.model_ner.config, "id2label"):
                CommonUtil.printLog("模型自带的标签映射：", self.model_ner.config.id2label)

        CommonUtil.printLog(
            f"\n初始化完成 | 设备：{self.device} | 标签数：{self.num_labels} | 分类模型：{classify_model_path} | 缓存路径: {BertUtil._cache} | 文本关键信息提取模型：{ner_model_path}")

    def _init_tokenizer_and_model(self):
        """初始化bert-base-chinese分词器和模型"""
        if self.tokenizer is None:
            self.tokenizer = BertTokenizer.from_pretrained(self.model_path, cache_dir=self.model_cache_dir, resume_download=True)
        if self.model is None:
            # 针对 macOS 的特殊处理
            if platform.system() == "Darwin" and str(self.device) == 'cpu':
                # 对于 macOS CPU，直接加载到 CPU
                self.model = BertForSequenceClassification.from_pretrained(
                    self.model_path,
                    num_labels=self.num_labels,
                    id2label=self.id2label,
                    label2id=self.label2id,
                    # 内存优化参数
                    low_cpu_mem_usage=True,
                    torch_dtype=torch.float32,
                    # 明确指定不使用 CUDA
                    device_map='cpu'  # 添加 device_map 参数
                )
            else:
                # 对于其他情况，使用原始方式
                self.model = BertForSequenceClassification.from_pretrained(
                    self.model_path,
                    num_labels=self.num_labels,
                    id2label=self.id2label,
                    label2id=self.label2id,
                    low_cpu_mem_usage=True,
                    torch_dtype=torch.float32
                )

            # 确保模型在正确的设备上
            self.model = self.model.to(self.device)

    def _convert_to_classlabel(self, dataset: Dataset, label_col: str) -> Dataset:
        """转换标签列为合法ClassLabel类型（添加边界检查）"""
        # 获取数据中的实际标签ID
        self.data_label_classes = sorted(dataset.unique(label_col))
        print(f"\n数据中实际标签ID：{self.data_label_classes}")

        # 创建标签ID到索引的映射（解决标签值超出范围）
        self.data_label2idx = {label_id: idx for idx, label_id in enumerate(self.data_label_classes)}
        self.idx2data_label = {idx: label_id for label_id, idx in self.data_label2idx.items()}

        # 定义ClassLabel特征
        label_names = [self.id2label.get(label_id, f"label_{label_id}") for label_id in self.data_label_classes]
        class_label = ClassLabel(num_classes=len(self.data_label_classes), names=label_names)

        # 转换标签值为合法索引（添加边界检查）
        def map_label_to_idx(example):
            label_val = example[label_col]
            # 边界检查：未知标签映射到0
            example[label_col] = self.data_label2idx.get(label_val, 0)
            return example

        dataset = dataset.map(map_label_to_idx)
        dataset = dataset.cast_column(label_col, class_label)

        print(f"标签映射完成 | {self.data_label2idx} | 标签名称：{label_names}")
        return dataset

    def _preprocess_dataset(
            self,
            df,
            query_col: str,
            label_col: str,
            test_size: float = 0.1,
            max_length: int = 64,  # 增加长度
            batch_size: int = 50  # 减小预处理批次
    ) -> DatasetDict:
        """预处理数据集：分词+格式转换"""
        # 转换为HuggingFace Dataset
        dataset = Dataset.from_pandas(df[[query_col, label_col]])

        # 转换标签列
        dataset = self._convert_to_classlabel(dataset, label_col)

        # 拆分训练/验证集
        dataset_size = len(dataset)
        if dataset_size < 5:
            dataset_split = DatasetDict({"train": dataset, "test": dataset})
        else:
            dataset_split = dataset.train_test_split(
                test_size=test_size,
                seed=42,
                stratify_by_column=label_col
            )

        # 分词函数
        def preprocess_function(examples):
            return self.tokenizer(
                examples[query_col],
                truncation=True,
                padding="max_length",
                max_length=max_length,
                return_attention_mask=True
            )

        # 批量分词
        tokenized_datasets = dataset_split.map(
            preprocess_function,
            batched=True,
            batch_size=batch_size,
            remove_columns=[query_col]
        )

        # 重命名标签列+设置torch格式
        tokenized_datasets = tokenized_datasets.rename_column(label_col, "labels")
        tokenized_datasets.set_format(
            type="torch",
            columns=["input_ids", "attention_mask", "labels"]
        )

        print(f"\n数据集预处理完成：")
        print(f"训练集：{len(tokenized_datasets['train'])}条 | 验证集：{len(tokenized_datasets['test'])}条")
        return tokenized_datasets

    def _get_padded_class_weights(self, df, label_col: str) -> torch.Tensor:
        """计算并填充类别权重"""
        # 转换标签为索引
        labels_idx = []
        for label_id in df[label_col].values:
            labels_idx.append(self.data_label2idx.get(label_id, 0))
        labels_idx = np.array(labels_idx)

        # 计算基础权重
        classes = np.array(list(range(len(self.data_label_classes))))
        base_weights = compute_class_weight(
            class_weight="balanced",
            classes=classes,
            y=labels_idx
        )

        # 填充到模型标签数维度 - 确保在正确的设备上创建tensor
        padded_weights = torch.ones(self.num_labels, dtype=torch.float32)
        for idx, label_id in self.idx2data_label.items():
            if label_id < self.num_labels:
                padded_weights[label_id] = base_weights[idx]

        # 最后转移到目标设备
        padded_weights = padded_weights.to(self.device)

        print(f"\n类别权重：")
        print(f"原始权重（{len(self.data_label_classes)}维）：{base_weights.tolist()}")
        print(f"填充后（{self.num_labels}维）：{padded_weights.tolist()}")
        return padded_weights

    def train(
            self,
            df: pd.DataFrame,
            query_col: str = 'query',
            label_col: str = 'label_id',
            output_dir: str = f"{_cache}/bert_base_output",
            model_save_path: str = f"{_cache}/bert_base_model",
            test_size: float = 0.1,
            max_length: int = 64,  # 增加长度
            per_device_train_batch_size: int = 2,  # macOS 上进一步减小批次
            per_device_eval_batch_size: int = 2,
            num_train_epochs: int = 3,  # 增加训练轮数
            learning_rate: float = 2e-5,  # 调整学习率
            use_class_weight: bool = True
    ):
        """
        训练模型
        :param df: 数据集
        :param query_col: 文本列名, 使用哪一个列数据作为输入文本进行训练
        :param label_col: 标签列名, 该列存储有标签数字信息
        :param output_dir: 训练输出目录
        :param model_save_path: 模型保存路径
        :param test_size: 验证集比例
        :param max_length: 最大长度
        :param per_device_train_batch_size: 训练批次大小
        :param per_device_eval_batch_size: 评估批次大小
        :param num_train_epochs: 训练轮数
        :param learning_rate: 学习率
        :param use_class_weight: 是否使用类别权重
        """
        # 初始化模型
        self._init_tokenizer_and_model()

        # 预处理数据集
        tokenized_datasets = self._preprocess_dataset(
            df=df,
            query_col=query_col,
            label_col=label_col,
            test_size=test_size,
            max_length=max_length
        )

        # 保存映射关系到局部变量
        idx2data_label = self.idx2data_label

        # 纯numpy实现accuracy计算
        def compute_metrics(eval_pred):
            """计算评估指标"""
            logits, labels = eval_pred
            # 将标签索引恢复为原始ID
            labels_original = []
            for idx in labels:
                labels_original.append(idx2data_label.get(idx, 0))
            labels_original = np.array(labels_original)
            # 预测标签
            predictions = np.argmax(logits, axis=-1)
            # 计算准确率
            accuracy = np.mean(predictions == labels_original)
            return {"eval_accuracy": float(accuracy)}

        # 训练参数配置
        self.training_args = TrainingArguments(
            output_dir=output_dir,
            per_device_train_batch_size=per_device_train_batch_size,
            per_device_eval_batch_size=per_device_eval_batch_size,
            num_train_epochs=num_train_epochs,
            learning_rate=learning_rate,
            logging_dir=f"{output_dir}/logs",
            logging_steps=50,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="eval_accuracy",
            greater_is_better=True,
            overwrite_output_dir=True,
            disable_tqdm=True,
            no_cuda=not torch.cuda.is_available() or str(self.device) == 'cpu',
            seed=42,
            fp16=False,
            gradient_accumulation_steps=1,
            report_to="none",
            save_total_limit=1,
            # 内存优化参数
            dataloader_pin_memory=False,
            dataloader_num_workers=0,
            # 避免列被意外移除
            remove_unused_columns=False,
        )

        # 类别权重变量
        class_weights = None

        # 带类别权重的Trainer
        if use_class_weight:
            try:
                class_weights = self._get_padded_class_weights(df, label_col)

                class WeightedTrainer(Trainer):
                    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
                        """自定义损失计算"""
                        labels = inputs.pop("labels")
                        # 恢复原始标签ID
                        labels_original = []
                        for idx in labels:
                            idx_val = idx.item()
                            labels_original.append(idx2data_label.get(idx_val, 0))
                        labels_original = torch.tensor(
                            labels_original,
                            device=labels.device,
                            dtype=torch.long
                        )
                        # 计算损失
                        outputs = model(**inputs)
                        logits = outputs.logits
                        loss_fct = torch.nn.CrossEntropyLoss(weight=class_weights)
                        loss = loss_fct(logits.view(-1, model.config.num_labels), labels_original.view(-1))
                        return (loss, outputs) if return_outputs else loss

                self.trainer = WeightedTrainer(
                    model=self.model,
                    args=self.training_args,
                    train_dataset=tokenized_datasets["train"],
                    eval_dataset=tokenized_datasets["test"],
                    compute_metrics=compute_metrics,
                )
            except Exception as e:
                print(f"⚠️ 类别权重计算失败，禁用类别权重: {e}")
                use_class_weight = False

        # 普通Trainer（无类别权重）
        if not use_class_weight:
            class CustomTrainer(Trainer):
                def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
                    """自定义损失计算"""
                    labels = inputs.pop("labels")
                    # 恢复原始标签ID
                    labels_original = []
                    for idx in labels:
                        idx_val = idx.item()
                        labels_original.append(idx2data_label.get(idx_val, 0))
                    labels_original = torch.tensor(
                        labels_original,
                        device=labels.device,
                        dtype=torch.long
                    )
                    # 计算损失
                    outputs = model(**inputs)
                    logits = outputs.logits
                    loss_fct = torch.nn.CrossEntropyLoss()
                    loss = loss_fct(logits.view(-1, model.config.num_labels), labels_original.view(-1))
                    return (loss, outputs) if return_outputs else loss

            self.trainer = CustomTrainer(
                model=self.model,
                args=self.training_args,
                train_dataset=tokenized_datasets["train"],
                eval_dataset=tokenized_datasets["test"],
                compute_metrics=compute_metrics,
            )

        # 开始训练
        CommonUtil.printLog("开始训练...")
        self.trainer.train()

        # 保存模型
        self.model.save_pretrained(model_save_path)
        self.tokenizer.save_pretrained(model_save_path)
        CommonUtil.printLog(f"模型训练完成，保存路径：{model_save_path}")

    def init_predict_model(self, model_path: str = None):
        """
        初始化预测模型
        :param model_path: 模型路径, 可以是本地路径, 也可以是huggingface上的模型名称
        """
        model_path = model_path if model_path else f"{BertUtil._cache}/bert_base_model"
        if self.predict_model_path != model_path:
            self.predict_model_path = model_path
            # 加载模型 - 确保在正确的设备上加载
            self.predict_tokenizer = BertTokenizer.from_pretrained(model_path)
            self.predict_model = BertForSequenceClassification.from_pretrained(
                model_path,
                low_cpu_mem_usage=True,
                torch_dtype=torch.float32
            )
            self.predict_model = self.predict_model.to(self.device)  # 明确转移到指定设备
            self.predict_model.eval()

    def predict_single(self, query: str, model_path: str = None, max_length: int = 64) -> str:
        """单条文本预测"""
        self.init_predict_model()

        # 预处理
        inputs = self.predict_tokenizer(
            query,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}  # 确保输入在正确设备

        # 预测
        with torch.no_grad():
            outputs = self.predict_model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=1).item()
        pred_label = self.id2label.get(pred_id, f"未知标签_{pred_id}")

        return pred_label

    def predict_single_with_confidence(self, query: str, model_path: str = None, max_length: int = 64) -> Tuple[str, float]:
        """单条文本预测并返回置信度"""
        self.init_predict_model()

        # 预处理
        inputs = self.predict_tokenizer(
            query,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 预测
        with torch.no_grad():
            outputs = self.predict_model(**inputs)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1)

        pred_id = torch.argmax(logits, dim=1).item()
        confidence = torch.max(probabilities).item()
        pred_label = self.id2label.get(pred_id, f"未知标签_{pred_id}")

        return pred_label, confidence

    def predict_batch(self, queries: List[str], model_path: str = None, max_length: int = 64, batch_size: int = 2) -> List[str]:
        """批量文本预测"""
        self.init_predict_model()

        results = []
        # 批量处理
        for i in range(0, len(queries), batch_size):
            batch_queries = queries[i:i + batch_size]

            # 预处理
            inputs = self.predict_tokenizer(
                batch_queries,
                truncation=True,
                padding="max_length",
                max_length=max_length,
                return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # 预测
            with torch.no_grad():
                outputs = self.predict_model(**inputs)
            pred_ids = torch.argmax(outputs.logits, dim=1).tolist()
            pred_labels = [self.id2label.get(id, f"未知标签_{id}") for id in pred_ids]

            results.extend(pred_labels)

        return results

    def extract_entity_by_model(self, text: str, target_labels_set: Optional[Set[str]] = None) -> Optional[List[str]]:
        """
        使用 uer/roberta-base-finetuned-cluener2020-chinese 等模型进行文本信息提取
        注意: 该模型只能提取具体的机构等信息, 无法提取类别数据, 比如: 可以匹配到  '工商银行', 但无法匹配 '银行' 这个大类
        """
        # CLUE 的实体类型映射（我们关心的）, 具体见: https://github.com/CLUEbenchmark/CLUENER2020
        TARGET_LABELS = target_labels_set if target_labels_set else {
            "address",  # 地址: **省**市**区**街**号，**路，**街道，**村等（如单独出现也标记）。地址是标记尽量完全的, 标记到最细。
            # "book",  # 书名: 小说，杂志，习题集，教科书，教辅，地图册，食谱，书店里能买到的一类书籍，包含电子书。
            "company",  # 公司: **公司，**集团，**银行（央行，中国人民银行除外，二者属于政府机构）, 如：新东方，包含新华网/中国军网等。
            # "game",  # 游戏: 常见的游戏，注意有一些从小说，电视剧改编的游戏，要分析具体场景到底是不是游戏
            # "government",  # 政府: 包括中央行政机关和地方行政机关两级。 中央行政机关有国务院、国务院组成部门（包括各部、委员会、中国人民银行和审计署）、国务院直属机构（如海关、税务、工商、环保总局等），军队等。
            # "movie",  # 电影: 也包括拍的一些在电影院上映的纪录片，如果是根据书名改编成电影，要根据场景上下文着重区分下是电影名字还是书名。
            "name",  # 姓名: 一般指人名，也包括小说里面的人物，宋江，武松，郭靖，小说里面的人物绰号：及时雨，花和尚，著名人物的别称，通过这个别称能对应到某个具体人物。
            "organization",  # 组织机构: 篮球队，足球队，乐团，社团等，另外包含小说里面的帮派如：少林寺，丐帮，铁掌帮，武当，峨眉等。
            # "position",  # 职位: 古时候的职称：巡抚，知州，国师等。现代的总经理，记者，总裁，艺术家，收藏家等
            "scene",  # 景点: 常见旅游景点如：长沙公园，深圳动物园，海洋馆，植物园，黄河，长江等。
        }

        results = self.pipeline_ner(text)
        entities = []
        seen = set()
        for ent in results:
            if ent["entity_group"] in TARGET_LABELS:
                word = ent["word"].strip().replace(" ", "")
                if word and word not in seen:
                    entities.append(word)
                    seen.add(word)
        return entities

    @staticmethod
    def update_entity_category(types: Optional[Set[str]] = None, type_file: Optional[str] = None) -> Set[str]:
        """
        拼接类别信息
        :param types: 少量类名信息
        :param type_file: 类名存储文件路径, 每行表示一个类名, 以 # 开头的行 以及 空白行会被剔除
        :return: Set 将以上类别数据 以及内聚的数据进行合并后得到最终的类别信息
        """
        # 预定义的类别
        entity_types = {"咖啡店", "餐厅", "医院", "加油站", "超市", "银行", "学校", "公园", "酒店", "药店"}
        if types:
            entity_types.update(types)

        if FileUtil.isFileExist(type_file):
            lines = FileUtil.readFile(type_file)
            lines = [item.strip() for item in lines if not item.startswith('#') and item.strip()]
            entity_types.update(set(lines))
        return entity_types

    @staticmethod
    def extract_entity_by_type(text: str, types: Set[str], lower_compare: bool = False) -> List[str]:
        """
        根据已知的类别信息, 检测输入文本是否包含该类别, 有就提取并返回
        类别数据有两个来源: 方法内部预定义值, 以及外部传入, 传入数据包含两种: 少量类型的Set 以及  大量类型存储文件 type_file
        :param text: 输入的待匹配文本
        :param types: 少量类名信息
        :param type_file: 类名存储文件路径, 每行表示一个类名, 以 # 开头的行 以及 空白行会被剔除
        :param lower_compare: 是否转小写再比较
        :return: list 匹配到到的类别数据
        """
        # 标准化 & 匹配
        result_list = []
        # 标准化：转小写、去空格（中文无需分词）
        clean_text = re.sub(r"\s+", "", text)
        if lower_compare:
            clean_text = clean_text.lower()
        for poi in sorted(types, key=len, reverse=True):  # 长词优先
            t_poi = poi.lower() if lower_compare else poi
            if t_poi in clean_text:
                result_list.append(t_poi)
        return result_list

    def extract_entity(self, text: str, types: Set[str], print_log: bool = False) -> List[str]:
        """
        提取输入文本中的关键实体信息, 会通过模型 和 类别 数据进行提取, 最后进行合并输出
        由于模型和类别识别时, 可能分别提取到同一个slot, 但长度不一样,因此需要做合并并舍弃掉较短的slot元素
        :param text: 待提取的文本
        :param types: 类别信息列表, 通过 update_entity_category() 生成
        :param print_log: 是否输出日志
        """
        slot_model = self.extract_entity_by_model(text)
        slot_model = slot_model if slot_model else []
        CommonUtil.printLog(f"\tslot_model: {','.join(slot_model) if slot_model else '无'}", condition=print_log, includeTime=False)
        #
        slot_type = BertUtil.extract_entity_by_type(text, types)
        CommonUtil.printLog(f"\tslot_type: {','.join(slot_type) if slot_type else '无'}", condition=print_log, includeTime=False)
        result_list = BertUtil.merge_lists_with_longer_match(slot_model, slot_type)

        # slot.extend([item for item in slot_types if item not in slot])
        CommonUtil.printLog(f"\tresult_slot(模型+类别): {','.join(result_list) if result_list else '无'}", condition=print_log, includeTime=False)
        return result_list

    @staticmethod
    def merge_lists_with_longer_match(list_a: List[str], list_b: List[str]) -> List[str]:
        """
        合并两个字符串列表，保留更长的匹配元素

        规则：
        - 如果一个元素是另一个元素的子串，则保留更长的元素
        - 如果元素完全相同，只保留一个
        - 如果没有包含关系，两个都保留

        Args:
            list_a: 第一个字符串列表
            list_b: 第二个字符串列表

        Returns:
            合并后的列表

        Example:
             A = ['ABC', 'efg']
             B = ['ABCD', 'efg', 'hij']
             merge_lists_with_longer_match(A, B)
             结果: ['ABCD', 'efg', 'hij']
        """
        # 合并两个列表
        combined = list_a + list_b
        result = []

        # 标记要删除的元素索引
        to_remove = set()

        for i in range(len(combined)):
            if i in to_remove:
                continue

            for j in range(i + 1, len(combined)):
                if j in to_remove:
                    continue

                item_i = combined[i]
                item_j = combined[j]

                # 判断包含关系
                if item_i in item_j:
                    # item_i 是 item_j 的子串，保留更长的 item_j，删除 item_i
                    to_remove.add(i)
                    break
                elif item_j in item_i:
                    # item_j 是 item_i 的子串，保留更长的 item_i，删除 item_j
                    to_remove.add(j)

        # 构建结果列表
        for i in range(len(combined)):
            if i not in to_remove:
                result.append(combined[i])

        return result


# ===================== 测试代码 =====================
if __name__ == "__main__":
    """
    基于bert进行短语分类训练
    本类提供了两类数据: 
    1. 预定义的常见query, 具体将:  keyword_queries/nearby_queries/navigation_queries/complex_queries 等定义
    2. 从csv文件中读取的人工标注数据, 具体见: csv_dir 定义的目录, csv文件名固定为: train.csv
        要求包含以下类: query/manual_type/manual_intent, 每种每类的数据量建议保持平衡, 提取数据时会以最少的哪一类为准
        默认各类随机采样300条query (具体见 max_size 便来管理) 结合预定义的 query 组成最终的训练集
        
    id2label: 表示分类的标签, 0: 关键字搜, 1: 周边搜, 2: 简单导航, 3: 复杂
    """

    cache_dir = FileUtil.create_cache_dir(None, __file__)
    id2label = {0: "关键字搜", 1: "周边搜", 2: "简单导航", 3: "复杂"}  # 分类的标签id
    label2id = {v: k for k, v in id2label.items()}
    invalid_id = 999
    usecols = ['query', 'manual_type', 'manual_intent']  # 从csv文件中要读取的列名
    need_train_classify = False  # 是否需要想训练分类, 若为False,则表示本地已有模型,直接预测

    # 训练用的csv文件配置
    csv_dir: str = f'{cache_dir}/bert'
    csv_manual = f'{csv_dir}/train.csv'  # 文件路径
    max_size = 1000  # 从csv中每类最多提取的query条数

    # 模型路径
    classify_model_path = 'bert-base-chinese'  # None  # f"{cache_dir}/models/bert-base-chinese/"  # 分类模型路径
    ner_model_path = 'uer/roberta-base-finetuned-cluener2020-chinese'  # None  # f"{cache_dir}/models/uer/roberta-base-finetuned-cluener2020-chinese/"  # 关键实体提取模型路径

    # 构建平衡的训练数据集
    # 数据源1: 预定义的query
    keyword_queries = [
        "搜索万达广场", "查找咖啡店", "查询银行网点", "餐厅",
        "找加油站", "搜索超市", "查找医院", "帮我搜索学校",
        "搜索酒店", "ATM", "查询酒吧", "电影院",
        "找停车场", "小艺,帮我搜索下药店", "查找图书馆", "小德帮我找一下健身房"
    ]

    nearby_queries = [
        "请问,附近有什么好吃的", "周边有哪些商店", "周边有什么景点",
        "附近有咖啡厅吗", "周围有什么银行", "附近有什么酒店",
        "周边有什么娱乐场所", "搜索附近的咖啡店", "周围有什么超市",
        "附近有什么餐厅推荐", "周边有什么特色小吃", "周围有什么购物中心",
        "找找附近哪里有加油站", "你好小德, 帮我搜索周边书店", "帮我查找周围的快餐店", "请问,附近有美容院吗"
    ]

    navigation_queries = [
        "请问去万达广场怎么走", "你好,导航到火车站", "到机场的路线",
        "去市中心的路", "帮我导航到超市", "到学校的路线",
        "去公园怎么走", "万绿湖导航", "到医院的最佳路线",
        "去海边的路", "导航到展览馆", "到体育馆怎么走",
        "我要去博物馆怎么去", "到图书馆的最快路线", "去动物园怎么走", "到地铁站的路"
    ]

    complex_queries = [
        "从我家到公司最快的路线", "避开拥堵去机场的路",
        "多个地点的最佳游览顺序", "考虑限行的上班路线",
        "带充电桩的停车场推荐", "最近的麦当劳",
        "考虑停车费的购物路线", "多目的地最优路径规划",
        "避开高峰期去火车站", "小德看下前面的路况",
        "包含休息点的长途驾驶路线", "考虑油耗的省油路线",
        "避开施工路段的上班路线", "包含充电站的电动车路线",
        "考虑天气的出行路线", "这条路怎么这么堵啊"
    ]

    size = min(len(keyword_queries), len(nearby_queries), len(navigation_queries), len(complex_queries))
    keyword_queries = keyword_queries[:size]
    nearby_queries = nearby_queries[:size]
    navigation_queries = navigation_queries[:size]  # 修正：使用正确的变量名
    complex_queries = complex_queries[:size]
    CommonUtil.printLog(f'数据集共有{size}条数据')

    # 构建完整的数据集，确保每类都有相同数量的样本(16个)
    all_queries = keyword_queries + nearby_queries + navigation_queries + complex_queries
    all_types = ["简单"] * size + ["简单"] * size + ["复杂"] * size + ["复杂"] * size
    all_intents = ["关键字搜"] * size + ["周边搜"] * size + ["简单导航"] * size + ["复杂"] * size
    all_labels = [0] * size + [1] * size + [2] * size + [3] * size
    # 重复数据以增加训练样本
    data = {
        "query": all_queries * 5,
        "manual_type": all_types * 5,
        "manual_intent": all_intents * 5,
        "label_id": all_labels * 5
    }

    df = pd.DataFrame(data)

    # 数据源2: 从csv文件中获取训练数据, 追加到训练集中, 要求至少包含: usecols 中列名, 以及 label_id 列(可转换生成)
    if FileUtil.isFileExist(csv_manual):
        # def map_label_csv(row) -> int:
        #     """
        #     将标注数据转为id分类值, 根据实际情况修改
        #     若训练csv已经有label_id列了,则可不用转换
        #     """
        #     if row['col_a'] == 'value_a':
        #         return 0
        #     if row['col_a'] == 'value_b':
        #         return 1
        #     if row['col_c'] == 'value_c':
        #         return 2
        #     return 3

        CommonUtil.printLog(f'从csv文件中获取训练数据, 追加到训练集中: {csv_manual}')
        df_csv = CSVUtil.read_csv(csv_manual, usecols=usecols)
        # df_csv["label_id"] = df_csv.apply(map_label_csv, axis=1)

        value_counts_dict = {'关键字搜': max_size, '周边搜': max_size, '简单导航': max_size}
        df_fz = CSVUtil.filter_and_replace(df_csv, {'manual_type': '复杂', 'manual_intent': r'^\s*$'})
        df_fz = CSVUtil.sample_by_column_values(df_fz, 'manual_type', {'复杂': max_size})
        df_jd = CSVUtil.sample_by_column_values(df_csv, 'manual_intent', value_counts_dict)
        df_csv = pd.concat([df_jd, df_fz], ignore_index=True)

        df_csv = df_csv.sample(frac=1).reset_index(drop=True)
        df_train = pd.concat([df, df_csv], ignore_index=True)
    else:
        df_train = df
    CSVUtil.to_csv(df_train, f"{csv_dir}/sample.csv")
    df = df_train

    # 初始化分类器（使用bert-base-chinese模型）
    bertUtil = BertUtil(
        classify_model_path=classify_model_path,
        id2label=id2label,
        ner_model_path=ner_model_path
    )

    # 训练模型
    if need_train_classify:
        bertUtil.train(
            df=df,
            query_col="query",
            label_col="label_id",
            per_device_train_batch_size=3,
            per_device_eval_batch_size=3,
            num_train_epochs=10
        )

    # 预测测试
    test_queries = [
        "万达广场导航",
        "搜索附近的咖啡店",
        "搜索附近的厦门市的咖啡店",
        "复杂的城市路线规划",
        "关键字搜索商场店铺",
        "你好,搜索朝阳公园",
        "小德帮我找一下万绿湖水库",
        "去厦门大学",
        "小德,看下前面的路况",
        "小爱同学,这条路堵不堵",
        "hello小艺,这几天的天气怎么样",
        "小德小德,我要去北京天安门",
        "最近的咖啡店",
        "可以帮我搜周边的加油站吗",
        "请问附近哪里有幼儿园吗",
        "我想找一家酒吧",
        "请问附近哪有青年旅舍吗",
        "请问附近哪里有ATM机吗",
    ]

    # 单条预测
    CommonUtil.printLog("=== 单条预测结果 ===", prefix='\n')
    for query in test_queries:
        result = bertUtil.predict_single(query)
        print(f"{query:<20} → {result}")

    # 单条预测带置信度
    CommonUtil.printLog("=== 单条预测结果（带置信度） ===", prefix='\n')
    amap_poi_types = bertUtil.update_entity_category(type_file='./configs/amap_poi_types.txt')
    for query in test_queries:
        result, confidence = bertUtil.predict_single_with_confidence(query)
        print(f"\n{query:<20} → {result} (置信度: {confidence:.3f})")
        if '复杂' not in result:
            bertUtil.extract_entity(query, amap_poi_types, True)

    # 批量预测
    CommonUtil.printLog("=== 批量预测结果 ===", prefix='\n')
    batch_results = bertUtil.predict_batch(test_queries, batch_size=2)
    for query, result in zip(test_queries, batch_results):
        print(f"{query:<20} → {result}")
    CommonUtil.printLog(f'批量预测结束')
