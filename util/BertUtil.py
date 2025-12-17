#!/usr/bin/env python3
# -*- coding:utf-8 -*-

# pip install torch transformers datasets scikit-learn evaluate pandas numpy -U
import torch
import warnings
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Union, Tuple
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset, DatasetDict, ClassLabel
from sklearn.utils.class_weight import compute_class_weight
import os
import re
import platform

from util.CSVUtil import CSVUtil
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

# ===================== 基础配置 & 内存保护 =====================
os.environ["WANDB_DISABLED"] = "true"  # 关闭wandb日志
# os.environ["CUDA_VISIBLE_DEVICES"] = "-1" # 强制使用CPU避免显存错误

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
            model_path: str = "bert-base-chinese",
            id2label: Optional[Dict[int, str]] = None,
            device: Optional[str] = None
    ):
        """
        初始化工具类
        :param model_path: 模型路径, 也支持本地路径, 默认是下载到 HF_HOME 所在的目录,若未设置, 默认位置: 'C:/Users/{用户名}/.cache/huggingface/' 目录
                            bert-base-chinese 模型下载地址:  https://huggingface.co/google-bert/bert-base-chinese/tree/main
                           若训练速度太慢, 且对精度要求不高, 可以使用模型: "prajjwal1/bert-tiny"  下载地址:  https://huggingface.co/prajjwal1/bert-tiny/tree/main
        :param id2label: 标签id到名称的映射, 格式: {0: "测试", 1: "其他"}   key-数字 value-名称
        :param device: 运行设备（自动检测或手动指定）
        """
        # 基础配置
        self.model_path = model_path
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

        # 初始化模型/分词器
        self.tokenizer = None
        self.model = None
        self.trainer = None
        self.training_args = None

        # 标签映射相关
        self.data_label_classes = None
        self.data_label2idx = None
        self.idx2data_label = None

        CommonUtil.printLog(f"\n初始化完成 | 设备：{self.device} | 标签数：{self.num_labels} | 模型：{model_path} | 缓存路径: {BertUtil._cache}")

    def _init_tokenizer_and_model(self):
        """初始化bert-base-chinese分词器和模型"""
        if self.tokenizer is None:
            self.tokenizer = BertTokenizer.from_pretrained(self.model_path)
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

    def predict_single(self, query: str, model_path: str = None, max_length: int = 64) -> str:
        """单条文本预测"""
        model_path = model_path if model_path else f"{BertUtil._cache}/bert_base_model"

        # 加载模型 - 确保在正确的设备上加载
        tokenizer = BertTokenizer.from_pretrained(model_path)
        model = BertForSequenceClassification.from_pretrained(
            model_path,
            low_cpu_mem_usage=True,
            torch_dtype=torch.float32
        )
        model = model.to(self.device)  # 明确转移到指定设备
        model.eval()

        # 预处理
        inputs = tokenizer(
            query,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}  # 确保输入在正确设备

        # 预测
        with torch.no_grad():
            outputs = model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=1).item()
        pred_label = self.id2label.get(pred_id, f"未知标签_{pred_id}")

        return pred_label

    def predict_single_with_confidence(self, query: str, model_path: str = None, max_length: int = 64) -> Tuple[str, float]:
        """单条文本预测并返回置信度"""
        model_path = model_path if model_path else f"{BertUtil._cache}/bert_base_model"

        # 加载模型
        tokenizer = BertTokenizer.from_pretrained(model_path)
        model = BertForSequenceClassification.from_pretrained(
            model_path,
            low_cpu_mem_usage=True,
            torch_dtype=torch.float32
        )
        model = model.to(self.device)
        model.eval()

        # 预处理
        inputs = tokenizer(
            query,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 预测
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1)

        pred_id = torch.argmax(logits, dim=1).item()
        confidence = torch.max(probabilities).item()
        pred_label = self.id2label.get(pred_id, f"未知标签_{pred_id}")

        return pred_label, confidence

    def predict_batch(self, queries: List[str], model_path: str = None, max_length: int = 64, batch_size: int = 2) -> List[str]:
        """批量文本预测"""
        model_path = model_path if model_path else f"{BertUtil._cache}/bert_base_model"

        # 加载模型
        tokenizer = BertTokenizer.from_pretrained(model_path)
        model = BertForSequenceClassification.from_pretrained(
            model_path,
            low_cpu_mem_usage=True,
            torch_dtype=torch.float32
        )
        model = model.to(self.device)
        model.eval()

        results = []
        # 批量处理
        for i in range(0, len(queries), batch_size):
            batch_queries = queries[i:i + batch_size]

            # 预处理
            inputs = tokenizer(
                batch_queries,
                truncation=True,
                padding="max_length",
                max_length=max_length,
                return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # 预测
            with torch.no_grad():
                outputs = model(**inputs)
            pred_ids = torch.argmax(outputs.logits, dim=1).tolist()
            pred_labels = [self.id2label.get(id, f"未知标签_{id}") for id in pred_ids]

            results.extend(pred_labels)

        return results


# ===================== 测试代码 =====================
if __name__ == "__main__":
    cache_dir = FileUtil.create_cache_dir(None, __file__)
    id2label = {0: "关键字搜", 1: "周边搜", 2: "简单导航", 3: "复杂"}  # 分类的标签id
    usecols = ['query', 'manual_type', 'manual_intent']  # 从csv文件中要读取的列名
    csv_dir: str = f'{cache_dir}/bert'
    csv_manual = f'{csv_dir}/train.csv'
    max_size = 300

    # 构建平衡的训练数据集
    # 数据源1: 预定义的query
    keyword_queries = [
        "搜索万达广场", "查找咖啡店", "查询银行网点", "餐厅",
        "找加油站", "搜索超市", "查找医院", "搜索学校",
        "搜索酒店", "查找ATM机", "查询公交站", "搜索电影院",
        "找停车场", "小艺,帮我搜索下药店", "查找图书馆", "小德帮我找一下健身房"
    ]

    nearby_queries = [
        "附近有什么好吃的", "周边有哪些商店", "最近有什么景点",
        "附近有咖啡厅吗", "周围有什么银行", "附近有什么酒店",
        "周边有什么娱乐场所", "附近有医院吗", "周围有什么超市",
        "附近有什么餐厅推荐", "周边有什么特色小吃", "周围有什么购物中心",
        "找找附近哪里有加油站", "搜索周边书店", "查找周围的快餐店", "附近有美容院吗"
    ]

    navigation_queries = [
        "去万达广场怎么走", "导航到火车站", "到机场的路线",
        "去市中心的路", "导航到超市", "到学校的路线",
        "去公园怎么走", "万绿湖导航", "到医院的最佳路线",
        "去海边的路", "导航到展览馆", "到体育馆怎么走",
        "我要去博物馆怎么去", "到图书馆的最快路线", "去动物园怎么走", "到地铁站的路"
    ]

    complex_queries = [
        "从我家到公司最快的路线", "避开拥堵去机场的路",
        "多个地点的最佳游览顺序", "考虑限行的上班路线",
        "带充电桩的停车场推荐", "避开收费站去景点的路",
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
    all_types = ["简单"] * size + ["简单"] * size + ["简单"] * size + ["复杂"] * size
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

        df_csv = CSVUtil.read_csv(csv_manual, usecols=usecols)
        # df_csv["label_id"] = df_csv.apply(map_label_csv, axis=1)

        value_counts_dict = {'关键字搜': max_size, '周边搜': max_size, '简单导航': max_size}
        df_fz = CSVUtil.sample_by_column_values(df_csv, 'manual_type', {'复杂': max_size})
        df_jd = CSVUtil.sample_by_column_values(df_csv, 'manual_intent', value_counts_dict)
        df_csv = pd.concat([df_jd, df_fz], ignore_index=True)

        df_csv = df_csv.sample(frac=1).reset_index(drop=True)
        df_train = pd.concat([df, df_csv], ignore_index=True)
    else:
        df_train = df
    CSVUtil.to_csv(df_train, f"{csv_dir}/sample.csv")

    # 初始化分类器（使用bert-base-chinese模型）
    classifier = BertUtil(
        model_path=f"{cache_dir}/models/bert-base-chinese/",
        id2label=id2label
    )

    # 训练模型
    classifier.train(
        df=df,
        query_col="query",
        label_col="label_id",
        num_train_epochs=5
    )

    # 预测测试
    test_queries = [
        "万达广场导航",
        "搜索附近的咖啡店",
        "复杂的城市路线规划",
        "关键字搜索商场店铺",
        "你好,搜索朝阳公园",
        "小德帮我找一下万绿湖水库",
        "去厦门大学",
        "小德,看下前面的路况",
        "小爱同学,这条路堵不堵",
        "hello小艺,这几天的天气怎么样",
        "小德小德,我要去北京天安门",
    ]

    # 单条预测
    print("\n=== 单条预测结果 ===")
    for query in test_queries:
        result = classifier.predict_single(query)
        print(f"{query:<20} → {result}")

    # 单条预测带置信度
    print("\n=== 单条预测结果（带置信度） ===")
    for query in test_queries:
        result, confidence = classifier.predict_single_with_confidence(query)
        print(f"{query:<20} → {result} (置信度: {confidence:.3f})")

    # 批量预测
    print("\n=== 批量预测结果 ===")
    batch_results = classifier.predict_batch(test_queries, batch_size=2)
    for query, result in zip(test_queries, batch_results):
        print(f"{query:<20} → {result}")
