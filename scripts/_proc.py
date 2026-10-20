"""子进程助手:**进程树**超时 + 安全的管道收口(共享模块)。

为什么不用 `subprocess.run(timeout=N)`(实测踩坑,写进 ADR 口径):
  Windows 上 `run(timeout)` 超时只 `kill()` **直接子进程**。Kiln 会再拉起浏览器
  子进程,它们**继承** stdout/stderr 管道 → 父进程被杀后 `communicate()` 仍在等
  管道 EOF,于是 timeout 形同虚设:实测 45s 上限被拖到分钟级,`export.py` 的
  `timeout=900` 被拖到十几分钟(用户侧表现为「卡住、杀不掉、也不报错」)。

`run()` 的做法:读线程持续排空管道,`proc.wait(timeout)` 负责期限。Windows 创建时先挂起
根进程、加入 Job Object 后再恢复;所有后代从创建起继承 Job membership,即使短命中间进程
退出也不会丢失。超时或根退出后仍有 Job 成员时终止整个 Job 并标记 `timed_out`。POSIX
默认使用独立进程组与 `killpg`;由有界 WebGPU wrapper 启动的嵌套 Kiln 进程继承 wrapper
进程组,使外层超时可以一并清理浏览器后代。
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


def _windows_process_table() -> dict[int, int] | None:
    """Return PID->parent PID so descendants remain trackable after reparenting."""
    import ctypes
    from ctypes import wintypes

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        snapshot_fn = kernel32.CreateToolhelp32Snapshot
        snapshot_fn.argtypes = [wintypes.DWORD, wintypes.DWORD]
        snapshot_fn.restype = wintypes.HANDLE
        first_fn = kernel32.Process32FirstW
        first_fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
        first_fn.restype = wintypes.BOOL
        next_fn = kernel32.Process32NextW
        next_fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
        next_fn.restype = wintypes.BOOL
        close_fn = kernel32.CloseHandle
        close_fn.argtypes = [wintypes.HANDLE]
        close_fn.restype = wintypes.BOOL
        snapshot = snapshot_fn(0x00000002, 0)  # TH32CS_SNAPPROCESS
        if not snapshot or snapshot == ctypes.c_void_p(-1).value:
            return None
        table = {}
        try:
            entry = ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(entry)
            if first_fn(snapshot, ctypes.byref(entry)):
                while True:
                    pid, parent = int(entry.th32ProcessID), int(entry.th32ParentProcessID)
                    if pid:
                        table[pid] = parent
                    if not next_fn(snapshot, ctypes.byref(entry)):
                        break
        finally:
            close_fn(snapshot)
        return table
    except (AttributeError, OSError, TypeError, ValueError):
        return None


class _WindowsJob:
    """Contain a launched process tree atomically and terminate all members together."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self._handle = self._kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        self._kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel32.TerminateJobObject.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        self._kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD]
        self._kernel32.SetInformationJobObject.restype = wintypes.BOOL

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]
        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]
        limits = ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self._kernel32.SetInformationJobObject(
                self._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            self._kernel32.CloseHandle(self._handle)
            self._handle = None
            raise OSError(error, "SetInformationJobObject(KILL_ON_JOB_CLOSE) failed")

        class BasicAccountingInformation(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("PageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]
        self._accounting_type = BasicAccountingInformation

    def assign(self, process_handle) -> bool:
        return bool(self._kernel32.AssignProcessToJobObject(
            self._handle, self._wintypes.HANDLE(int(process_handle))))

    def active_processes(self) -> int | None:
        info = self._accounting_type()
        returned = self._wintypes.DWORD()
        ok = self._kernel32.QueryInformationJobObject(
            self._handle, 1, self._ctypes.byref(info), self._ctypes.sizeof(info),
            self._ctypes.byref(returned))
        return int(info.ActiveProcesses) if ok else None

    def wait_empty(self, timeout: float = 0.5) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            count = self.active_processes()
            if count == 0:
                return True
            if count is None or time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    def terminate(self) -> bool:
        return bool(self._kernel32.TerminateJobObject(self._handle, 1))

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def popen_with_tree(cmd, **kwargs):
    """Start a child suspended, assign it to a Windows Job, then resume atomically."""
    if os.name != "nt":
        return subprocess.Popen(cmd, **kwargs), None
    job = _WindowsJob()
    proc = None
    try:
        popen_kw = dict(kwargs)
        popen_kw["creationflags"] = int(popen_kw.get("creationflags", 0)) | 0x00000004 | 0x00000200
        proc = subprocess.Popen(cmd, **popen_kw)  # CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP
        if not job.assign(proc._handle):
            raise OSError(job._ctypes.get_last_error(), "AssignProcessToJobObject failed")
        import ctypes
        from ctypes import wintypes
        ntdll = ctypes.WinDLL("ntdll")
        resume = ntdll.NtResumeProcess
        resume.argtypes = [wintypes.HANDLE]
        resume.restype = ctypes.c_long
        status = int(resume(wintypes.HANDLE(int(proc._handle))))
        if status < 0:
            raise OSError(f"NtResumeProcess failed with NTSTATUS {status:#x}")
        return proc, job
    except Exception as exc:  # noqa: BLE001
        job.terminate()
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        job.close()
        raise RuntimeError(
            "Unable to contain exporter in a Windows Job Object; refusing untracked launch") from exc


def kill_tree(pid: int, descendants=()) -> bool:
    """Kill the root and tracked descendants (works even after the root exits)."""
    if os.name == "nt":
        succeeded = False
        try:
            result = subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                                    capture_output=True, creationflags=_FLAGS, timeout=15)
            succeeded = result.returncode == 0
        except Exception:  # noqa: BLE001
            pass
        for child_pid in sorted({int(child) for child in descendants if int(child) != int(pid)},
                                reverse=True):
            try:
                result = subprocess.run(["taskkill", "/T", "/F", "/PID", str(child_pid)],
                                        capture_output=True, creationflags=_FLAGS, timeout=15)
                succeeded = result.returncode == 0 or succeeded
            except Exception:  # noqa: BLE001
                pass
        return succeeded
    try:
        import signal
        os.killpg(os.getpgid(pid), signal.SIGKILL)
        return True
    except ProcessLookupError:
        return False
    except Exception:  # noqa: BLE001
        try:
            os.kill(pid, 9)
            return True
        except Exception:  # noqa: BLE001
            return False


def _kill_process_group(pgid: int) -> bool:
    """Kill a previously captured POSIX process-group ID without re-querying its root PID."""
    try:
        import signal
        os.killpg(int(pgid), getattr(signal, "SIGKILL", signal.SIGTERM))
        return True
    except ProcessLookupError:
        return True  # The group is already gone; no inherited pipe holder remains.
    except Exception:  # noqa: BLE001
        return False


def run(cmd, timeout: float = 300.0, cwd=None, env=None, stdin_null: bool = True) -> Result:
    """跑一条命令,`timeout` 秒后**连子树一起**强杀并如实标记 `timed_out`。

    Windows 在子进程首线程挂起时先加入 Job Object 再恢复,避免短命启动器在
    轮询之间退出而让孙进程脱离 PID 祖先链。POSIX 默认使用独立进程组；
    wrapper 可通过 ARTBOARD_INHERIT_PROCESS_GROUP=1 让内层进程继承其进程组。
    """
    inherit_parent_group = (os.name != "nt"
                            and os.environ.get("ARTBOARD_INHERIT_PROCESS_GROUP") == "1")
    popen_kw = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=cwd, env=env, creationflags=_FLAGS)
    if stdin_null:
        popen_kw["stdin"] = subprocess.DEVNULL
    if os.name != "nt" and not inherit_parent_group:
        popen_kw["start_new_session"] = True
    proc, job = popen_with_tree(cmd, **popen_kw)
    # A normal POSIX run owns a session; wrapper-managed nested export runs inherit
    # the wrapper's group so its outer timeout can kill Kiln and browser descendants.
    process_group = (int(proc.pid) if os.name != "nt" and not inherit_parent_group else None)

    sink: list = []
    threads = [threading.Thread(target=_drain, args=(proc.stdout, sink, "out"), daemon=True),
               threading.Thread(target=_drain, args=(proc.stderr, sink, "err"), daemon=True)]
    for thread in threads:
        thread.start()

    t0 = time.monotonic()
    timed_out = False
    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if job is not None:
            job.terminate()
        elif process_group is not None:
            _kill_process_group(process_group)
        elif inherit_parent_group:
            # The wrapper owns this shared group; kill only this direct tool here.
            # Its structured timeout result makes the wrapper terminate the group.
            try:
                proc.kill()
            except OSError:
                pass
        else:
            kill_tree(proc.pid)
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rc = -9
    else:
        if job is not None:
            # A short-lived intermediate can disappear between PID snapshots; Job
            # membership persists across reparenting, so any remaining member is orphaned.
            if not job.wait_empty(timeout=0.5):
                timed_out = True
                job.terminate()
                if proc.poll() is None:
                    try:
                        rc = proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        rc = -9
        else:
            cleanup_deadline = time.monotonic() + 0.2
            for thread in threads:
                thread.join(max(0, cleanup_deadline - time.monotonic()))
            if any(thread.is_alive() for thread in threads):
                timed_out = True
                if process_group is not None:
                    _kill_process_group(process_group)
                elif inherit_parent_group:
                    try:
                        proc.kill()
                    except OSError:
                        pass
                else:
                    kill_tree(proc.pid)
                if proc.poll() is None:
                    try:
                        rc = proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        rc = -9
    finally:
        if job is not None:
            job.close()

    seconds = time.monotonic() - t0
    join_deadline = time.monotonic() + 5
    for thread in threads:
        thread.join(max(0, join_deadline - time.monotonic()))
    out = b"".join(c for tag, c in sink if tag == "out")
    err = b"".join(c for tag, c in sink if tag == "err")
    return Result(rc, out.decode(_ENC, errors="replace"),
                  err.decode(_ENC, errors="replace"), timed_out, cmd, seconds)
