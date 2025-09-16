## 功能说明

自动编译多个项目,并将生成的文件拷贝到指定目录下, 然后出发其他脚本命令进行后续操作

使用场景: 某些自动化测试依赖于特定版本的apk, 需要本地按需编译, 编译完成后进行上传服务器操作

## 使用

1. 修改 `auto_build_copy_apks/config.ini` 文件
2. 执行 `auto_build_copy_apks/main.py` 即可

## 自定义 config.ini 文件

默认的 `auto_build_copy_apks/config.ini` 文件通常作为模板作为参考

自定义操作:

```shell script
python3 auto_build_copy_apks/main.py --config {custom_config_path}
```
