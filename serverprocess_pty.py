import io
import os
import pty
import subprocess
import threading
import traceback
from subprocess import Popen
from typing import Callable


class ServerProcess(object):
    def __init__(self, *proc_args: str, cwd: str):
        self._args = proc_args
        self.cwd = cwd
        self._proc = None  # type: Popen | None
        self._stdout_content = io.BytesIO()
        self._stdout_content_listeners = set()  # type: set[Callable[[bytes], None]]
        self._term_encoding = "sjis" if os.name == "nt" else "utf-8"
        self._write = None  # type: Callable[[bytes], None] | None

    def start(self):
        if self.is_running:
            return

        self._stdout_content.close()
        self._stdout_content = io.BytesIO()

        master, slave = pty.openpty()
        self._proc = subprocess.Popen(
            " ".join(self._args),
            shell=True,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=self.cwd,
            close_fds=True,
        )
        self._write = lambda data: os.write(master, data)
        threading.Thread(target=self._reader, args=(master,), daemon=True).start()

    def stop(self):
        if not self.is_running:
            return

        self.write("stop")
        self._proc.terminate()

    def write(self, data: str):
        if not self.is_running:
            return RuntimeError("Process is not running")

        if self._write:
            self._write(data.encode() + b"\n")

    def _reader(self, fd):
        try:
            chunk = os.read(fd, 1024)
            while chunk:
                self._stdout_content.write(chunk)
                self._send_to_stdout_listener(chunk)
                chunk = os.read(fd, 1024)

        except (Exception,):
            traceback.print_exc()
            return

    def _send_to_stdout_listener(self, data: bytes):
        for listener in self._stdout_content_listeners:
            try:
                listener(data)
            except (Exception,):
                traceback.print_exc()

    def add_stdout_listener(self, listen: Callable[[bytes], None]):
        if listen in self._stdout_content_listeners:
            return
        self._stdout_content_listeners.add(listen)

    def remove_stdout_listener(self, listen: Callable[[bytes], None]):
        self._stdout_content_listeners.remove(listen)

    @property
    def is_running(self):
        return self._proc is not None and self._proc.returncode is None

    @property
    def stdout_content(self):
        return self._stdout_content.getvalue()
