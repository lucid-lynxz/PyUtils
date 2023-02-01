### 背景
部分人员(比如产品、黑盒测试等)可能不知道怎么下载android sdk并配置路径，也或者嫌麻烦不想折腾，因此考虑直接内置本项目用到的部分三方应用，简化使用成本
当然弊端就是项目体积增大


### 目录说明
每个子目录包含一个工具， 子目录下还会有 `windows`/`linux`/`macos` 三个子目录， 用于表示三个平台的版本，且：
1. 若平台子目录不存在，表示不支持该平台，比如 [scrcpy](https://github.com/Genymobile/scrcpy/releases)只有windows版本
2. 默认下载的是 x64/x86 版本，比如7z, 虽有单独的arm版本，但本项目未做内置(毕竟我没有相关设备)
3. 对于arm设备或者内置工具不支持的平台(包括没有非安装版的情形)，请自行在各 config.ini 中配置相关命令路径， 具体见 [该文档](../shell_scripts/README.md)
4. 若同一工具不同平台的可执行程序名不一致，则会手动重命名为相同的名称，比如7z
   * linux: `7zz`  --> `7z`
   * macos: `7zz`  --> `7z`
   * windows: `7za.exe` --> `7z.exe`
5. 对于官网下载的工具包，若解压得到的部分子程序非本项目需要，则会尝试进行删除，比如 `android_platform_tools` 中只需要adb工具，其他都做了删除
6. 部分工具由于过大，不做内置，比如 [scrcpy](https://github.com/Genymobile/scrcpy/releases)， 解压后100M

### 各工具目录说明
* `android_platform_tools`
   删除了其他命令，只保留adb工具，应用来源[官网](https://developer.android.google.cn/studio/releases/platform-tools?hl=zh-cn)
* `7z`: 压缩工具[7z](https://www.7-zip.org/download.html)
* ~~`scrcpy`: Android手机投屏工具，只支持windows~~ 
* `python3`: 内置了windows版本的python3 embeddable版本
