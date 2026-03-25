"""
Jenkins 工具类
支持:
1. 账号密码/API Token 认证
2. 查询 Job 历史记录
3. 触发 Job 构建
4. 获取构建状态和日志
5. 删除构建记录(单条/多条/失败的记录)
"""
import time
from enum import Enum
from typing import Optional, List, Dict, Any

# # 设置控制台编码为 UTF-8
# sys.stdout.reconfigure(encoding='utf-8')
# # 确保环境变量 LANG 设置为 UTF-8
# os.environ['LANG'] = 'en_US.UTF-8'

try:
    import jenkins
except ImportError:
    raise ImportError("请先安装 python-jenkins 库：pip install python-jenkins")


class JenkinsAuthType(Enum):
    """Jenkins 认证方式"""
    API_TOKEN = "api_token"
    USERNAME_PASSWORD = "username_password"


class JenkinsUtil:
    """Jenkins 工具类"""

    def __init__(self,
                 url: str,
                 user_name: Optional[str] = None,
                 password: Optional[str] = None,
                 api_token: Optional[str] = None,
                 timeout: int = 10,
                 lazy_connect: bool = True):
        """
        初始化 Jenkins 客户端

        :param url: Jenkins 服务器 URL，如：http://localhost:8080
        :param user_name: 用户名 (可选，匿名访问时可不传)
        :param password: 密码 (当不提供 api_token 时使用)
        :param api_token: API Token (优先级高于 password, 在 {url}/user/{user_name}/security/ 中创建)
        :param timeout: 请求超时时间 (秒)
        :param lazy_connect: 是否延迟连接，True-初始化时不立即连接，False-初始化时立即测试连接
        """
        self.url = url.rstrip('/')

        # 自动识别认证方式：优先使用 API Token，其次使用用户名密码，否则匿名
        if api_token:
            # 优先使用 API Token 模式
            self.auth_type = JenkinsAuthType.API_TOKEN
            self.username = user_name
            self.password = api_token
        elif user_name and password:
            # 其次使用用户名密码模式
            self.auth_type = JenkinsAuthType.USERNAME_PASSWORD
            self.username = user_name
            self.password = password
        else:
            # 匿名访问
            self.auth_type = None
            self.username = None
            self.password = None

        self.timeout = timeout
        self.lazy_connect = lazy_connect
        self.server = None

        # 如果不是延迟连接，则立即创建连接
        if not lazy_connect:
            self._create_server()

    def _create_server(self) -> jenkins.Jenkins:
        """创建 Jenkins 服务器连接"""
        if self.server is not None:
            return self.server

        try:
            if self.username and self.password:
                server = jenkins.Jenkins(
                    self.url,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout
                )
            else:
                # 匿名访问
                server = jenkins.Jenkins(self.url, timeout=self.timeout)

            # 仅在非延迟连接模式下测试连接
            if not self.lazy_connect:
                # 使用 requests 库来测试连接，而不是使用 jenkins 库的 get_version 方法
                import requests
                from requests.auth import HTTPBasicAuth

                print(f"[DEBUG] 尝试使用 requests 库直接调用 API")
                print(f"[DEBUG] URL: {self.url}")
                print(f"[DEBUG] Username: {self.username}")
                print(f"[DEBUG] Password: {self.password[:5]}..." if self.password else "[DEBUG] No password")

                try:
                    response = requests.get(
                        f"{self.url}/api/json",
                        auth=HTTPBasicAuth(self.username, self.password) if self.username and self.password else None,
                        timeout=self.timeout
                    )
                    print(f"[DEBUG] Response status code: {response.status_code}")
                    print(f"[DEBUG] Response headers: {dict(response.headers)}")
                    print(f"[DEBUG] Response content: {response.text[:200]}..." if response.text else "[DEBUG] No content")

                    # 检查响应状态码
                    if response.status_code == 200:
                        print("[DEBUG] 连接测试成功")
                    else:
                        raise ConnectionError(f"连接测试失败，状态码：{response.status_code}")
                except Exception as e:
                    print(f"[DEBUG] Requests error: {e}")
                    raise ConnectionError(f"连接 Jenkins 失败：{e}")

            self.server = server
            return server
        except Exception as e:
            raise ConnectionError(f"连接 Jenkins 失败：{e}")

    def _ensure_connected(self):
        """确保已连接到 Jenkins 服务器"""
        if self.server is None:
            self._create_server()

    # ==================== Job 查询相关 ====================

    def get_job_info(self, job_name: str) -> Optional[Dict[str, Any]]:
        """
        获取 Job 的详细信息

        :param job_name: Job 名称
        :return: Job 信息字典
        """
        try:
            self._ensure_connected()
            return self.server.get_job_info(job_name)
        except jenkins.NotFoundException:
            print(f"Job '{job_name}' 不存在")
            return None
        except Exception as e:
            print(f"获取 Job 信息失败：{e}")
            return None

    def get_all_jobs(self, recursive: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有 Job 列表

        :param recursive: 是否递归获取文件夹中的 Job
        :return: Job 列表
        """
        try:
            self._ensure_connected()
            if recursive:
                return self.server.get_all_jobs()
            else:
                jobs = self.server.get_jobs()
                return jobs if jobs else []
        except Exception as e:
            print(f"获取 Job 列表失败：{e}")
            return []

    def job_exists(self, job_name: str) -> bool:
        """
        判断 Job 是否存在

        :param job_name: Job 名称
        :return: True/False
        """
        try:
            self._ensure_connected()
            return self.server.job_exists(job_name)
        except Exception as e:
            print(f"检查 Job 存在性失败：{e}")
            return False

    # ==================== 构建历史查询相关 ====================

    def get_build_history(self,
                          job_name: str,
                          limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取 Job 的构建历史记录

        :param job_name: Job 名称
        :param limit: 返回最近 N 条记录
        :return: 构建历史列表, 示例如下:
        [ {'_class': 'org.jenkinsci.plugins.workflow.job.WorkflowRun', 'number': 13, 'url': 'http://127.0.0.1:8081/job/test/13/'} ]
        """
        try:
            self._ensure_connected()
            job_info = self.get_job_info(job_name)
            if not job_info:
                return []

            builds = job_info.get('builds', [])
            return builds[:limit]
        except Exception as e:
            print(f"获取构建历史失败：{e}")
            return []

    def get_build_info(self, job_name: str, build_number: int) -> Optional[Dict[str, Any]]:
        """
        获取指定构建的详细信息

        :param job_name: Job 名称
        :param build_number: 构建编号
        :return: 构建信息, 示例如下:

        {
            "_class": "org.jenkinsci.plugins.workflow.job.WorkflowRun",
            "actions": [
                {
                    "_class": "hudson.model.CauseAction",
                    "causes": [
                        {
                            "_class": "hudson.model.Cause$UserIdCause",
                            "shortDescription": "Started by user lucid lynxz",
                            "userId": "lynxz",
                            "userName": "lucid lynxz"
                        }
                    ]
                },
                {
                    "_class": "org.jenkinsci.plugins.workflow.libs.LibrariesAction"
                },
                {
                    "_class": "org.jenkinsci.plugins.displayurlapi.actions.RunDisplayAction"
                },
                {
                    "_class": "org.jenkinsci.plugins.pipeline.modeldefinition.actions.RestartDeclarativePipelineAction"
                },
                {
                    "_class": "org.jenkinsci.plugins.workflow.job.views.FlowGraphAction"
                },
            ],
            "artifacts": [],
            "building": False,
            "description": None,
            "displayName": "#17",
            "duration": 103784,
            "estimatedDuration": 49706,
            "executor": None,
            "fullDisplayName": "test #17",
            "id": "17",
            "keepLog": False,
            "number": 17,
            "queueId": 40,
            "result": "SUCCESS",
            "timestamp": 1705807661679,
            "url": "http://127.0.0.1:8081/job/test/17/",
            "changeSets": [],
            "culprits": [],
            "inProgress": False,
            "nextBuild": None,
            "previousBuild": {
                "number": 16,
                "url": "http://127.0.0.1:8081/job/test/16/"
            }
        }
        """
        try:
            self._ensure_connected()
            return self.server.get_build_info(job_name, build_number)
        except jenkins.NotFoundException:
            print(f"构建 #{build_number} 不存在")
            return None
        except Exception as e:
            print(f"获取构建信息失败：{e}")
            return None

    def get_build_status(self, job_name: str, build_number: int) -> Optional[str]:
        """
        获取指定构建的状态

        :param job_name: Job 名称
        :param build_number: 构建编号
        :return: 构建状态 (SUCCESS, FAILURE, ABORTED, IN_PROGRESS 等)
        """
        self._ensure_connected()
        build_info = self.get_build_info(job_name, build_number)
        if not build_info:
            return None

        building = build_info.get('building', False)
        if building:
            return 'IN_PROGRESS'

        result = build_info.get('result')
        return result if result else 'UNKNOWN'

    def get_last_build_number(self, job_name: str) -> Optional[int]:
        """
        获取最后一次构建的编号

        :param job_name: Job 名称
        :return: 构建编号
        """
        try:
            self._ensure_connected()
            job_info = self.get_job_info(job_name)
            if not job_info:
                return None

            last_build = job_info.get('lastBuild')
            return last_build.get('number') if last_build else None
        except Exception as e:
            print(f"获取最后构建编号失败：{e}")
            return None

    def get_last_build_status(self, job_name: str) -> Optional[str]:
        """
        获取最后一次构建的状态

        :param job_name: Job 名称
        :return: 构建状态
        """
        last_build_number = self.get_last_build_number(job_name)
        if last_build_number is None:
            return None

        return self.get_build_status(job_name, last_build_number)

    def get_build_console_output(self,
                                 job_name: str,
                                 build_number: int,
                                 output_file: Optional[str] = None) -> Optional[str]:
        """
        获取构建的控制台输出日志

        :param job_name: Job 名称
        :param build_number: 构建编号
        :param output_file: 可选，保存日志到文件
        :return: 控制台输出文本
        """
        try:
            self._ensure_connected()
            console_output = self.server.get_build_console_output(job_name, build_number)

            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(console_output)
                print(f"日志已保存到：{output_file}")

            return console_output
        except Exception as e:
            print(f"获取控制台输出失败：{e}")
            return None

    def get_build_artifacts(self,
                            job_name: str,
                            build_number: int) -> List[Dict[str, Any]]:
        """
        获取构建的产物列表

        :param job_name: Job 名称
        :param build_number: 构建编号
        :return: 产物列表
        """
        self._ensure_connected()
        build_info = self.get_build_info(job_name, build_number)
        if not build_info:
            return []

        artifacts = build_info.get('artifacts', [])
        return artifacts if artifacts else []

    # ==================== 触发构建相关 ====================

    def trigger_build(self,
                      job_name: str,
                      parameters: Optional[Dict[str, Any]] = None,
                      block: bool = False,
                      poll_interval: int = 5,
                      timeout: int = 3600) -> Optional[int]:
        """
        触发 Job 构建

        :param job_name: Job 名称
        :param parameters: 构建参数 (可选)
        :param block: 是否阻塞等待构建完成
        :param poll_interval: 轮询间隔 (秒)
        :param timeout: 超时时间 (秒), 仅当 block=True 时有效
        :return: 构建编号
        """
        try:
            self._ensure_connected()
            # 获取当前最新的构建编号
            before_build_number = self.get_last_build_number(job_name)

            # 触发构建
            if parameters:
                self.server.build_job(job_name, parameters)
            else:
                self.server.build_job(job_name)

            print(f"已触发构建：{job_name}")

            # 等待新构建启动
            max_wait = 30  # 最多等待 30 秒
            wait_count = 0
            while wait_count < max_wait:
                current_build_number = self.get_last_build_number(job_name)
                if current_build_number and current_build_number != before_build_number:
                    new_build_number = current_build_number
                    break
                time.sleep(1)
                wait_count += 1
            else:
                print("等待构建启动超时")
                return None

            print(f"构建已启动，编号：{new_build_number}")

            # 如果需要阻塞等待
            if block:
                start_time = time.time()
                while True:
                    status = self.get_build_status(job_name, new_build_number)

                    if status not in ['IN_PROGRESS', None]:
                        print(f"构建完成，状态：{status}")
                        break

                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        print(f"等待构建超时 ({timeout}秒)")
                        break

                    time.sleep(poll_interval)

            return new_build_number

        except Exception as e:
            print(f"触发构建失败：{e}")
            return None

    def stop_build(self, job_name: str, build_number: int) -> bool:
        """
        停止正在运行的构建

        :param job_name: Job 名称
        :param build_number: 构建编号
        :return: 是否成功停止
        """
        try:
            self._ensure_connected()
            self.server.stop_build(job_name, build_number)
            print(f"已停止构建：{job_name} #{build_number}")
            return True
        except Exception as e:
            print(f"停止构建失败：{e}")
            return False

    # ==================== 高级查询功能 ====================

    def search_jobs(self,
                    keyword: str,
                    regex: bool = False) -> List[Dict[str, Any]]:
        """
        搜索 Job

        :param keyword: 搜索关键字
        :param regex: 是否使用正则表达式
        :return: 匹配的 Job 列表
        """
        self._ensure_connected()
        all_jobs = self.get_all_jobs(recursive=True)
        matched_jobs = []

        for job in all_jobs:
            job_name = job.get('name', '')

            if regex:
                import re
                if re.search(keyword, job_name):
                    matched_jobs.append(job)
            else:
                if keyword.lower() in job_name.lower():
                    matched_jobs.append(job)

        return matched_jobs

    def get_job_config(self, job_name: str) -> Optional[str]:
        """
        获取 Job 的 XML 配置

        :param job_name: Job 名称
        :return: XML 配置字符串
        """
        try:
            self._ensure_connected()
            return self.server.get_job_config(job_name)
        except Exception as e:
            print(f"获取 Job 配置失败：{e}")
            return None

    def get_view_jobs(self, view_name: str) -> List[Dict[str, Any]]:
        """
        获取指定视图中的 Job 列表

        :param view_name: 视图名称
        :return: Job 列表
        """
        try:
            self._ensure_connected()
            view_info = self.server.get_view_info(view_name)
            return view_info.get('jobs', [])
        except Exception as e:
            print(f"获取视图信息失败：{e}")
            return []

    # ==================== 统计功能 ====================

    def get_job_statistics(self, job_name: str, limit: int = 10) -> Dict[str, Any]:
        """
        获取 Job 的统计信息

        :param job_name: Job 名称
        :param limit: 统计最近 N 次构建
        :return: 统计信息字典
        """
        self._ensure_connected()
        builds = self.get_build_history(job_name, limit)

        if not builds:
            return {}

        stats = {
            'total': len(builds),
            'success': 0,
            'failure': 0,
            'aborted': 0,
            'in_progress': 0,
            'other': 0,
            'success_rate': 0.0
        }

        for build in builds:
            # 需要获取详细的构建信息
            build_number = build.get('number')
            build_info = self.get_build_info(job_name, build_number)

            if not build_info:
                continue

            if build_info.get('building'):
                stats['in_progress'] += 1
            else:
                result = build_info.get('result')
                if result == 'SUCCESS':
                    stats['success'] += 1
                elif result == 'FAILURE':
                    stats['failure'] += 1
                elif result == 'ABORTED':
                    stats['aborted'] += 1
                else:
                    stats['other'] += 1

        # 计算成功率 (排除进行中的构建)
        completed = stats['success'] + stats['failure'] + stats['aborted'] + stats['other']
        if completed > 0:
            stats['success_rate'] = (stats['success'] / completed) * 100

        return stats

    # ==================== 批量操作 ====================

    def batch_trigger_builds(self,
                             job_names: List[str],
                             parameters_list: Optional[List[Dict[str, Any]]] = None,
                             delay: float = 1.0) -> Dict[str, Optional[int]]:
        """
        批量触发多个 Job 的构建

        :param job_names: Job 名称列表
        :param parameters_list: 构建参数列表 (与 job_names 一一对应)
        :param delay: 每个构建间的延迟时间 (秒)
        :return: 字典 {job_name: build_number}
        """
        results = {}

        if parameters_list is None:
            parameters_list = [None] * len(job_names)

        for i, job_name in enumerate(job_names):
            params = parameters_list[i] if i < len(parameters_list) else None
            build_number = self.trigger_build(job_name, params)
            results[job_name] = build_number

            if i < len(job_names) - 1 and delay > 0:
                time.sleep(delay)

        return results

    def batch_get_status(self, job_names: List[str]) -> Dict[str, str]:
        """
        批量获取多个 Job 的最后一次构建状态

        :param job_names: Job 名称列表
        :return: 字典 {job_name: status}
        """
        results = {}

        for job_name in job_names:
            status = self.get_last_build_status(job_name)
            results[job_name] = status if status else 'UNKNOWN'

        return results

    def delete_build(self, job_name: str, build_number: int) -> bool:
        """
        删除指定 Job 的指定构建记录

        :param job_name: Job 名称
        :param build_number: 构建编号
        :return: 是否成功删除
        """
        try:
            self._ensure_connected()
            self.server.delete_build(job_name, build_number)
            print(f"已删除构建记录：{job_name} #{build_number}")
            return True
        except Exception as e:
            print(f"删除构建记录失败：{e}")
            return False

    def batch_delete_builds(self, job_name: str, build_numbers: List[int]) -> Dict[int, bool]:
        """
        批量删除指定 Job 的多个构建记录

        :param job_name: Job 名称
        :param build_numbers: 构建编号列表
        :return: 字典 {build_number: success}
        """
        results = {}

        for build_number in build_numbers:
            success = self.delete_build(job_name, build_number)
            results[build_number] = success

        return results

    def delete_failed_builds(self, job_name: str, limit: int = 100) -> Dict[int, bool]:
        """
        删除指定 Job 所有编译失败的构建记录

        :param job_name: Job 名称
        :param limit: 最多处理的构建记录数量
        :return: 字典 {build_number: success}
        """
        try:
            self._ensure_connected()

            # 获取构建历史
            build_history = self.get_build_history(job_name, limit=limit)

            # 筛选出失败的构建记录
            failed_builds = []
            for build in build_history:
                build_number = build.get('number')
                if build_number:
                    build_info = self.get_build_info(job_name, build_number)
                    if build_info and build_info.get('result') == 'FAILURE':
                        failed_builds.append(build_number)

            if not failed_builds:
                print(f"Job {job_name} 没有失败的构建记录")
                return {}

            print(f"找到 {len(failed_builds)} 个失败的构建记录，准备删除")

            # 批量删除失败的构建记录
            return self.batch_delete_builds(job_name, failed_builds)
        except Exception as e:
            print(f"删除失败构建记录失败：{e}")
            return {}

    def get_build_parameters(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """
        获取指定 Job 的指定构建的 Build with Parameters 参数数据

        :param job_name: Job 名称
        :param build_number: 构建编号
        :return: 构建参数字典
        """
        try:
            self._ensure_connected()
            build_info = self.get_build_info(job_name, build_number)
            if not build_info:
                return {}

            # 从构建信息中获取参数
            actions = build_info.get('actions', [])
            for action in actions:
                if action.get('_class') == 'hudson.model.ParametersAction':
                    parameters = action.get('parameters', [])
                    params_dict = {}
                    for param in parameters:
                        param_name = param.get('name')
                        param_value = param.get('value')
                        if param_name:
                            params_dict[param_name] = param_value
                    return params_dict

            return {}
        except Exception as e:
            print(f"获取构建参数失败：{e}")
            return {}


# ==================== 使用示例 ====================
def main_demo(url: str = 'http://localhost:8080', user_name: str = None, password: str = None, api_token: str = None, test_delete: bool = False) -> Optional[JenkinsUtil]:
    # 示例 1: 使用 账号 + 密码 或 账号+apiToken 认证
    print("=" * 50)
    print(f"Connecting to: {url}")
    print(f"Auth type: {'API Token' if api_token else ('Username/Password' if user_name and password else 'Anonymous')}")
    print("=" * 50)

    try:
        jenkins_util = JenkinsUtil(url, user_name, password, api_token, lazy_connect=False)

        # 获取所有 Job
        jobs = jenkins_util.get_all_jobs()
        print(f"\n找到 {len(jobs)} 个 Job:")
        for job in jobs[:5]:  # 只显示前 5 个
            job_name = job['name']
            print(f"  - {job_name}")

            print(f"    - 状态: {jenkins_util.get_last_build_status(job_name)}")
            print(f"    - 序号: {jenkins_util.get_last_build_number(job_name)}")

        # 测试删除构建记录功能
        if jobs and test_delete:
            test_job = jobs[-1]['name']
            print(f"\n测试删除构建记录功能，使用 Job: {test_job}")

            # 获取构建历史
            build_history = jenkins_util.get_build_history(test_job, limit=5)
            if build_history:
                print(f"找到 {len(build_history)} 个构建记录:")
                for build in build_history:
                    print(f"  - 构建 #{build['number']} ({build['result'] if 'result' in build else 'IN_PROGRESS'})")

                # 测试删除单个构建记录
                test_build_number = build_history[-1]['number']  # 删除最后一个构建记录
                print(f"\n测试删除构建记录 #{test_build_number}")
                success = jenkins_util.delete_build(test_job, test_build_number)
                print(f"删除结果: {'成功' if success else '失败'}")

                # 测试批量删除构建记录
                if len(build_history) > 1:
                    test_build_numbers = [build['number'] for build in build_history[-2:]]  # 删除最后两个构建记录
                    print(f"\n测试批量删除构建记录: {test_build_numbers}")
                    results = jenkins_util.batch_delete_builds(test_job, test_build_numbers)
                    for build_number, success in results.items():
                        print(f"  - 构建 #{build_number}: {'成功' if success else '失败'}")

                # 测试删除失败的构建记录
                print(f"\n测试删除失败的构建记录")
                failed_results = jenkins_util.delete_failed_builds(test_job)
                if failed_results:
                    print("删除失败构建记录结果:")
                    for build_number, success in failed_results.items():
                        print(f"  - 构建 #{build_number}: {'成功' if success else '失败'}")
                else:
                    print("没有失败的构建记录需要删除")

                # 测试获取构建参数
                print(f"\n测试获取构建参数")
                for build in build_history:
                    build_number = build.get('number')
                    if build_number:
                        params = jenkins_util.get_build_parameters(test_job, build_number)
                        if params:
                            print(f"构建 #{build_number} 的参数:")
                            for param_name, param_value in params.items():
                                print(f"  - {param_name}: {param_value}")
                        else:
                            print(f"构建 #{build_number} 没有参数")
            else:
                print(f"Job {test_job} 没有构建记录")

        print("\n连接成功!")
        return jenkins_util
    except Exception as e:
        print(f"\n❌ 连接或使用 Jenkins 失败：{e}")
        print("\n请检查:")
        print("  1. Jenkins 服务是否正常运行")
        print(f"  2. URL 是否正确：{url}")
        print("  3. 账号密码/API Token 是否正确")
        print("  4. 网络连接是否正常")
    return None


if __name__ == '__main__':
    util = main_demo('http://127.0.0.1:8081/', 'lynxz', None, '110efcab4d13d5c431d7f542edaa890e46', test_delete=False)
    if util is not None:
        job_name = 'common_shell'
        build_history = util.get_build_history(job_name, limit=5)
        last_build = build_history[0]
        print(f'{job_name} last_build={last_build}')

        last_build_number1 = last_build.get('number', -1)
        last_build_number = util.get_last_build_number(job_name)
        print(f'last_build_number {last_build_number1} V.S. {last_build_number}')

        # 获取构建参数
        build_params = util.get_build_parameters(job_name, last_build_number)
        print(f'build_params={build_params}')

        # info = util.get_build_info(job_name, 17)
        # print(f'info={info}')
