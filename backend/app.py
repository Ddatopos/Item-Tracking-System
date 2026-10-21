"""基于神经网络的物品示踪系统 V1.0：兼容 python app.py 启动入口。"""
from tracking.app_factory import create_app

if __name__ == "__main__":
    from run import main
    main()
