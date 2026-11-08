"""树莓派 Camera Module 3（IMX708）取帧实现，输出 BGR uint8 图像。"""
import logging

import numpy as np

LOG = logging.getLogger("device.camera.source")


class Picamera2Source:
    """基于 Picamera2 的摄像头取帧源，输出尺寸与对焦模式可配置。"""

    source_type = "picamera2"

    def __init__(self, width=1280, height=720, fps=15, autofocus="continuous", lens_position=1.0):
        self.width = int(width)
        self.height = int(height)
        self.fps = fps
        self.autofocus = autofocus
        self.lens_position = lens_position
        self.camera = None
        self._started = False
        self._sensor = "imx708"

    def open(self):
        """打开并启动摄像头；重复调用不会重复初始化。"""
        if self.camera is not None:
            return
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise OSError("缺少 Picamera2，请在树莓派执行 sudo apt-get install -y python3-picamera2") from exc
        camera = None
        try:
            camera = Picamera2()
            configuration = camera.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": self.fps},
                buffer_count=4,
            )
            camera.configure(configuration)
            camera.start()
            self.camera = camera
            self._started = True
            self._read_sensor(camera)
        except Exception as exc:
            if camera is not None:
                try:
                    camera.close()
                except Exception:
                    LOG.debug("清理未完成初始化的摄像头失败", exc_info=True)
            self.camera = None
            self._started = False
            raise OSError("初始化摄像头失败：%s" % exc) from exc
        self._apply_autofocus()

    def _read_sensor(self, camera):
        try:
            properties = camera.camera_properties or {}
        except Exception:
            properties = {}
        model = properties.get("SensorModel") if isinstance(properties, dict) else None
        if isinstance(model, str) and model.strip():
            self._sensor = model.strip()

    def _apply_autofocus(self):
        try:
            from libcamera import controls
        except ImportError:
            LOG.warning("未找到 libcamera controls，跳过对焦设置，沿用摄像头默认对焦")
            return
        try:
            if self.autofocus == "manual":
                self.camera.set_controls({
                    "AfMode": controls.AfModeEnum.Manual,
                    "LensPosition": float(self.lens_position),
                })
            else:
                self.camera.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except Exception:
            LOG.warning("设置对焦模式失败，沿用摄像头默认对焦", exc_info=True)

    def read(self):
        """读取一帧并转换为 BGR uint8 HxWx3。"""
        if self.camera is None or not self._started:
            raise OSError("摄像头尚未打开，无法读取画面")
        try:
            # 注意：在树莓派 picamera2 + libcamera 实测中，RGB888 流经 capture_array
            # 返回的数组实际已是 BGR 顺序（已用 rpicam-still 参考图逐通道对照验证），
            # 这里不能再做 RGB→BGR 转换，否则红蓝通道互换、画面偏蓝。
            bgr = self.camera.capture_array("main")
        except Exception as exc:
            raise OSError("读取摄像头画面失败：%s" % exc) from exc
        if bgr is None or bgr.ndim != 3 or bgr.shape[2] != 3:
            raise OSError("摄像头返回的画面格式不是 HxWx3")
        if bgr.dtype != np.uint8:
            bgr = bgr.astype(np.uint8)
        return bgr

    def close(self):
        """停止并释放摄像头；重复调用安全，且不抛出异常。"""
        camera, self.camera = self.camera, None
        started, self._started = self._started, False
        if camera is None:
            return
        if started:
            try:
                camera.stop()
            except Exception:
                LOG.debug("停止摄像头失败", exc_info=True)
        try:
            camera.close()
        except Exception:
            LOG.debug("关闭摄像头失败", exc_info=True)

    def describe(self):
        """返回数据源描述，sensor 取不到时回退为 imx708。"""
        return {
            "source_type": self.source_type,
            "width": self.width,
            "height": self.height,
            "sensor": self._sensor,
        }
