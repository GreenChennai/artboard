"""子进程助手:**进程树**超时 + 安全的管道收口(共享模块)。

为什么不用 `subprocess.run(timeout=N)`(实测踩坑,写进 ADR 口径):
  Windows 上 `run(timeout)` 超时只 `kill()` **直接子进程**。Kiln 会再拉起浏览器
  子进程,它们**继承** stdout/stderr 管道 → 父进程被杀后 `communicate()` 仍在等
  管道 EOF,于是 timeout 形同虚设:实测 45s 上限被拖到分钟级,`export.py` 的
  `timeout=900` 被拖到十几分钟(用户侧表现为「卡住、杀不掉、也不报错」)。

`run()` 的做法:读线程先把两条管道排空(不依赖 EOF 才返回)+ `proc.wait(timeout)`
看门狗 + 超时**强杀整棵进程树**(Windows `taskkill /T /F`;POSIX `killpg`)。
因此 timeout 是真正的**墙钟上限**,且超时能被调用方区分出来(`timed_out`)。
"""

import os
import subprocess
import threading
import time

__all__ = ["Result", "run", "kill_tree"]

_ENC = "utf-8"

if os.name == "nt":  # 不弹黑框(Kiln 是 GUI 子系统 exe,但 taskkill 会)
    _FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
else:
    _FLAGS = 0


class Result:
    """最小号 CompletedProcess 替身(只保留调用方实际用到的字段)。

    `stdout` / `stderr` 已是 **str**(utf-8,errors="replace"),调用方不必再 decode。
    """

    __slots__ = ("returncode", "stdout", "stderr", "timed_out", "cmd", "seconds")

    def __init__(self, returncode, stdout, stderr, timed_out, cmd, seconds):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.cmd = cmd
        self.seconds = seconds


def _drain(pipe, sink, tag) -> None:
    """把一条管道读空(逐块),按 chunk 存进 sink 供最后解码。"""
    try:
        for chunk in iter(lambda: pipe.read(65536), b""):
            sink.append((tag, chunk))
    except Exception:  # noqa: BLE001 —— 管道被强杀打断是预期情况
        pass
    finally:
        try:
            pipe.close()
        except Exception:  # noqa: BLE001
            pass


def kill_tree(pid: int) -> None:
    """强杀以 pid 为根的整棵进程树(POSIX:进程组;Windows:taskkill /T /F)。"""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                           capture_output=True, creationflags=_FLAGS)
            return
        except Exception:  # noqa: BLE001
            pass
    try:
        import signal
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:  # noqa: BLE001
        try:
            os.kill(pid, 9)
        except Exception:  # noqa: BLE001
            pass


def run(cmd, timeout: float = 300.0, cwd=None, env=None, stdin_null: bool = True) -> Result:
    """跑一条命令,`timeout` 秒后**连子树一起**强杀并如实标记 `timed_out`。

    参数与 `subprocess.run` 的常用子集一致(不做 shell=True:命令行由调用方给 list,
    避免 Windows 引号转义地狱)。
    """
    popen_kw = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=cwd, env=env, creationflags=_FLAGS)
    if stdin_null:
        popen_kw["stdin"] = subprocess.DEVNULL
    if os.name != "nt":
        popen_kw["start_new_session"] = True      # 自成进程组,killpg 才能连根拔
    proc = subprocess.Popen(cmd, **popen_kw)

    sink: list = []
    threads = [threading.Thread(target=_drain, args=(proc.stdout, sink, "out"), daemon=True),
               threading.Thread(target=_drain, args=(proc.stderr, sink, "err"), daemon=True)]
    for t in threads:
        t.start()

    t0 = time.time()
    timed_out = False
    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(proc.pid)
        try:
            rc = proc.wait(timeout=15)            # 兜底:子树死后父进程必然退出
        except subprocess.TimeoutExpired:
            rc = -9
    seconds = time.time() - t0
    for t in threads:
        t.join(5)
    out = b"".join(c for tag, c in sink if tag == "out")
    err = b"".join(c for tag, c in sink if tag == "err")
    return Result(rc, out.decode(_ENC, errors="replace"),
                  err.decode(_ENC, errors="replace"), timed_out, cmd, seconds)
