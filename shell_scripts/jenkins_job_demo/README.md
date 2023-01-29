### `common_shell` job

对于需要定时触发的脚本, 可以通过jenkins实现, 此处定义了一个通用的 `common_shell` job
使用时, 可以直接将 `jenkins_job_demo/common_shell/` 目录拷贝到 `{jenkins_home}/jobs/` 下并重启jenkins即可

该job主要是设置了三个字符串参数, 拼接得到 `common_shell.sh` 的绝对路径后, 进行触发

1. `repo_abs_path`: 本地pyUtils项目根目录,创建job时直接给定默认值即可
2. `shell_script_rel_path`: 待运行的shell脚本相对路径, 相对于pyUtils根目录的路径
3. `other_param`: 其他自定义参数

该job的pipeline如下:

```groovy
import java.lang.String

pipeline {
    agent any
    environment{
        sh_abs_path="$repo_abs_path/$shell_script_rel_path".replace("\\","/")
    }

    stages {
        stage('Hello') {
            steps {
                sh"""
                echo $sh_abs_path
                $sh_abs_path $other_param
                """
            }
        }
    }
}
```

### 其他shell脚本的job

通过jenkins提供的job调用能力, 直接调用 `common_shell` job即可, 以 `get_log.sh` 脚本为例, 其pipeline如下:
其他脚本的触发仅需修改下方代码中的 'value' 值即可

```groovy
pipeline {
    agent any
    stages {
        stage('push') {
            steps {
                build job: 'common_shell', parameters: [string(name: 'shell_script_rel_path', value:"shell_scripts/sh/get_log.sh")]
            }
        }
    }
}
```