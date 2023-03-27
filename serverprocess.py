import io
import os
import subprocess
import threading
import traceback
from subprocess import Popen
from typing import Callable, IO


class ServerProcess(object):
    def __init__(self, *proc_args: str, cwd: str):
        self._args = proc_args
        self.cwd = cwd
        self._proc = None  # type: Popen | None
        self._stdin_content = io.BytesIO()
        self._stdin_content_listeners = set()  # type: set[Callable[[bytes], None]]
        self._term_encoding = "sjis" if os.name == "nt" else "utf-8"

    def start(self):
        if self.is_running:
            return

        self._stdin_content.close()
        self._stdin_content = io.BytesIO()

        self._proc = subprocess.Popen(
            self._args,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.cwd,
        )
        threading.Thread(target=self._reader, args=(self._proc.stdout,), daemon=True).start()

    def stop(self):
        if not self.is_running:
            return

        self.write("stop")
        self._proc.terminate()

    def write(self, text: str):
        if not self.is_running:
            return RuntimeError("Process is not running")

        self._proc.stdin.write(text.encode(self._term_encoding) + b"\n")
        self._proc.stdin.flush()

    def _reader(self, stdout: IO):
        for line in stdout:
            try:
                chunk = line.decode(self._term_encoding).encode("utf-8")
                self._stdin_content.write(chunk)
                self._send_to_stdin_listener(chunk)
            except UnicodeError:
                traceback.print_exc()

    def _send_to_stdin_listener(self, data: bytes):
        for listener in self._stdin_content_listeners:
            try:
                listener(data)
            except (Exception,):
                traceback.print_exc()

    def add_stdin_listener(self, listen: Callable[[bytes], None]):
        if listen in self._stdin_content_listeners:
            return
        self._stdin_content_listeners.add(listen)

    def remove_stdin_listener(self, listen: Callable[[bytes], None]):
        self._stdin_content_listeners.remove(listen)

    @property
    def is_running(self):
        return self._proc is not None and self._proc.returncode is None

    @property
    def stdin_content(self):
        return self._stdin_content.getvalue()
