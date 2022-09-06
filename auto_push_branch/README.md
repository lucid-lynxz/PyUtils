## 功能说明

自动提交指定git目录下指定分支的代码

## 使用

1. 修改 `auto_push_branch/config.ini` 文件
2. 执行 `auto_push_branch/main.py` 即可

## 自定义 config.ini 文件

默认的 `auto_push_branch/config.ini` 文件通常作为模板作为参考

自定义操作:

```shell script
python3 auto_merge_branch/main.py --config {custom_config_path}
```