# 基于神经网络的物品示踪系统 V1.0 第三方依赖

本次后端通过依赖包调用第三方库，未修改或附带第三方源码。生产版本固定在 backend/requirements-lock.txt，测试额外使用 requirements-dev.txt。运行测量环境为 Windows x64 和 Python 3.12。此清单依据本次实际安装包的元数据及所附 LICENSE 文件整理，完整文本保留在 docs/third-party-licenses。

| 依赖 | 实际版本 | 用途 | 包附许可证 |
| --- | --- | --- | --- |
| Flask | 3.1.2 | Web 和应用工厂 | BSD 3 Clause |
| Werkzeug | 3.1.9 | HTTP 与安全文件响应 | BSD 3 Clause |
| Jinja2 | 3.1.6 | Flask 传递依赖 | BSD 3 Clause |
| MarkupSafe | 3.0.4 | Jinja2 传递依赖 | BSD 3 Clause |
| itsdangerous | 2.2.0 | Flask 传递依赖 | BSD 3 Clause |
| click | 8.5.0 | Flask 传递依赖 | BSD 3 Clause |
| blinker | 1.9.0 | Flask 信号依赖 | MIT |
| colorama | 0.4.6 | Windows 终端颜色依赖 | BSD 3 Clause |
| opencv-python-headless | 4.12.0.88 | 取帧 JPEG 标注 | Apache 2 及包内所列第三方许可 |
| numpy | 2.2.6 | 图像数组 | BSD 3 Clause 及所附二进制依赖许可 |
| waitress | 3.0.2 | 单进程 Windows 正式服务 | ZPL 2.1 |
| pytest | 8.4.2 | 自动测试 不用于生产服务 | MIT |
| psutil | 7.1.0 | 持续测试采集进程指标 | BSD 3 Clause |
| iniconfig | 2.3.1 | pytest 传递依赖 | MIT |
| pluggy | 1.7.0 | pytest 传递依赖 | MIT |
| packaging | 26.3 | pytest 传递依赖 | Apache 2 或 BSD 2 Clause |
| Pygments | 2.21.0 | pytest 输出依赖 | BSD 2 Clause |

OpenCV 和 NumPy 的 wheel 包含其他二进制组件，其版权声明随完整 LICENSE/第三方许可文件保存，不能仅用主许可证名称代替分发时的完整声明。

原前端及其 React 等依赖未改写或重新锁定；第一版 pandas、Flask-Cors 不在本版运行主流程中，旧 data/processor.py 仅作历史参考。YOLO、Ultralytics 和模型权重未在本交付中安装或打包，由模型集成人员按实际使用版本保留声明并核对分发条件。新增模型依赖后应更新此清单及最终部署环境。

原创功能是本项目编写的运行调度、帧缓存、API、SQLite 仓库、事件合并、迁移维护和测试；依赖源码、权重、构建文件、自动生成报告和操作文档不计入原创程序代码。仓库原有代码的授权不在本次修改中另行改定。
