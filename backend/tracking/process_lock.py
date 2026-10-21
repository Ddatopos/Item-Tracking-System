"""基于神经网络的物品示踪系统 V1.0：单进程数据目录锁。"""
from pathlib import Path
import os


class DataDirectoryLock:
    def __init__(self, directory):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.file = open(Path(directory) / ".runtime.lock", "a+b")
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise RuntimeError("data directory is in use; stop the running backend first") from exc

    def close(self):
        if self.file.closed:
            return
        self.file.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
