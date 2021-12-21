## 功能说明

自动更新指定目录及其子目录下的所有git仓库代码 要求各待更新的本地目录下, 代码均已commit,否则不执行pull操作

## 使用

1. 修改 `auto_update_repository/config.ini` 文件
2. 执行 `auto_update_repository/main.py` 即可

## 自定义 config.ini 文件

默认的 `auto_update_repository/config.ini` 文件通常作为模板作为参考

自定义操作:

```shell script
python3 auto_merge_branch/main.py --config {custom_config_path}
```