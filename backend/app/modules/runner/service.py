import asyncio
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.modules.runner.schemas import ExecuteRequest, ExecuteResponse, RuntimeInfo


class RunnerService:
    def __init__(self) -> None:
        self.temp_root = settings.data_dir / "runner_temp"
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def get_available_runtimes(self) -> list[RuntimeInfo]:
        runtimes: list[RuntimeInfo] = []

        # 1. Python
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        runtimes.append(
            RuntimeInfo(
                id="python",
                name="Python 3",
                version=py_ver,
                available=True,
                extension=".py",
                example_code='def greet(name: str) -> str:\n    return f"Hello from CodeHaven, {name}!"\n\nprint(greet("Student"))\n',
            )
        )

        # 2. Node.js / JavaScript
        node_bin = shutil.which("node")
        runtimes.append(
            RuntimeInfo(
                id="javascript",
                name="JavaScript (Node.js)",
                version="v22+" if node_bin else "Not Found",
                available=bool(node_bin),
                extension=".js",
                example_code='function fib(n) {\n  if (n <= 1) return n;\n  return fib(n - 1) + fib(n - 2);\n}\n\nconsole.log("Fibonacci(10) =", fib(10));\n',
            )
        )

        # 3. TypeScript
        runtimes.append(
            RuntimeInfo(
                id="typescript",
                name="TypeScript",
                version="Node v22 Native" if node_bin else "Not Found",
                available=bool(node_bin),
                extension=".ts",
                example_code='interface User {\n  name: string;\n  role: string;\n}\n\nconst user: User = { name: "Rasil", role: "Developer" };\nconsole.log(`User: ${user.name} [${user.role}]`);\n',
            )
        )

        # 4. Java
        javac_bin = shutil.which("javac")
        java_bin = shutil.which("java")
        java_avail = bool(javac_bin and java_bin)
        runtimes.append(
            RuntimeInfo(
                id="java",
                name="Java",
                version="OpenJDK" if java_avail else "Not Found",
                available=java_avail,
                extension=".java",
                example_code='public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello from CodeHaven Java Runtime!");\n    }\n}\n',
            )
        )

        # 5. C / C++
        gcc_bin = shutil.which("gcc") or shutil.which("g++")
        runtimes.append(
            RuntimeInfo(
                id="c",
                name="C / C++ (GCC)",
                version="GCC" if gcc_bin else "Not Installed",
                available=bool(gcc_bin),
                extension=".c",
                example_code='#include <stdio.h>\n\nint main() {\n    printf("Hello from C in CodeHaven!\\n");\n    return 0;\n}\n',
            )
        )

        # 6. PowerShell / Shell
        pwsh_bin = shutil.which("powershell") or shutil.which("pwsh")
        runtimes.append(
            RuntimeInfo(
                id="powershell",
                name="PowerShell",
                version="Windows PowerShell" if pwsh_bin else "Not Found",
                available=bool(pwsh_bin),
                extension=".ps1",
                example_code='Write-Output "CodeHaven Terminal Shell: OK"\nGet-Date\n',
            )
        )

        return runtimes

    async def execute(self, req: ExecuteRequest) -> ExecuteResponse:
        lang = req.language.lower().strip()
        work_dir = Path(tempfile.mkdtemp(prefix="codehaven_run_", dir=self.temp_root))
        start_time = time.perf_counter()

        try:
            if lang in ("python", "py"):
                return await self._run_python(req, work_dir, start_time)
            elif lang in ("javascript", "js", "react"):
                return await self._run_javascript(req, work_dir, start_time)
            elif lang in ("typescript", "ts"):
                return await self._run_typescript(req, work_dir, start_time)
            elif lang == "java":
                return await self._run_java(req, work_dir, start_time)
            elif lang in ("c", "cpp", "c++"):
                return await self._run_c(req, work_dir, start_time)
            elif lang in ("bash", "sh", "shell"):
                return await self._run_bash(req, work_dir, start_time)
            elif lang in ("powershell", "ps1"):
                return await self._run_powershell(req, work_dir, start_time)
            else:
                elapsed = (time.perf_counter() - start_time) * 1000
                return ExecuteResponse(
                    status="error",
                    stdout="",
                    stderr=f"Unsupported execution language: '{req.language}'. Supported: python, javascript, typescript, java, c, powershell.",
                    exit_code=1,
                    execution_time_ms=round(elapsed, 2),
                    language=lang,
                )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    async def _execute_subprocess(
        self,
        args: list[str],
        work_dir: Path,
        stdin_text: str,
        timeout: float,
        lang: str,
        start_time: float,
        version_str: str = "",
    ) -> ExecuteResponse:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(work_dir),
                stdin=asyncio.subprocess.PIPE if stdin_text else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdin_bytes = stdin_text.encode("utf-8") if stdin_text else None
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(input=stdin_bytes),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                elapsed = (time.perf_counter() - start_time) * 1000
                return ExecuteResponse(
                    status="timeout",
                    stdout="",
                    stderr=f"[EXECUTION TIMED OUT]: Process exceeded limit of {timeout}s (possible infinite loop or blocking input).",
                    exit_code=-1,
                    execution_time_ms=round(elapsed, 2),
                    language=lang,
                    runtime_version=version_str,
                )

            elapsed = (time.perf_counter() - start_time) * 1000
            stdout_str = stdout_data.decode("utf-8", errors="replace")
            stderr_str = stderr_data.decode("utf-8", errors="replace")
            exit_code = proc.returncode if proc.returncode is not None else 0

            status = "success" if exit_code == 0 else "error"
            return ExecuteResponse(
                status=status,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=exit_code,
                execution_time_ms=round(elapsed, 2),
                language=lang,
                runtime_version=version_str,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr=f"[EXECUTION FAILURE]: {exc}",
                exit_code=1,
                execution_time_ms=round(elapsed, 2),
                language=lang,
                runtime_version=version_str,
            )

    async def _run_python(self, req: ExecuteRequest, work_dir: Path, start_time: float) -> ExecuteResponse:
        script_path = work_dir / "script.py"
        script_path.write_text(req.code, encoding="utf-8")

        py_bin = sys.executable
        py_ver = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return await self._execute_subprocess(
            [py_bin, "-u", str(script_path)],
            work_dir,
            req.stdin,
            req.timeout_seconds,
            "python",
            start_time,
            py_ver,
        )

    async def _run_javascript(self, req: ExecuteRequest, work_dir: Path, start_time: float) -> ExecuteResponse:
        node_bin = shutil.which("node")
        if not node_bin:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr="Node.js is not found on your system PATH. Please install Node.js to execute JavaScript code.",
                exit_code=1,
                execution_time_ms=round(elapsed, 2),
                language="javascript",
            )

        script_path = work_dir / "script.js"
        script_path.write_text(req.code, encoding="utf-8")
        return await self._execute_subprocess(
            [node_bin, str(script_path)],
            work_dir,
            req.stdin,
            req.timeout_seconds,
            "javascript",
            start_time,
            "Node.js",
        )

    async def _run_typescript(self, req: ExecuteRequest, work_dir: Path, start_time: float) -> ExecuteResponse:
        node_bin = shutil.which("node")
        if not node_bin:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr="Node.js is required to execute TypeScript.",
                exit_code=1,
                execution_time_ms=round(elapsed, 2),
                language="typescript",
            )

        script_path = work_dir / "script.ts"
        script_path.write_text(req.code, encoding="utf-8")
        # Node v22 supports running TypeScript with --no-warnings / type stripping
        return await self._execute_subprocess(
            [node_bin, "--no-warnings", str(script_path)],
            work_dir,
            req.stdin,
            req.timeout_seconds,
            "typescript",
            start_time,
            "Node.js (TypeScript)",
        )

    async def _run_java(self, req: ExecuteRequest, work_dir: Path, start_time: float) -> ExecuteResponse:
        javac_bin = shutil.which("javac")
        java_bin = shutil.which("java")
        if not (javac_bin and java_bin):
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr="Java Development Kit (JDK/javac) not found on PATH. Install OpenJDK to run Java.",
                exit_code=1,
                execution_time_ms=round(elapsed, 2),
                language="java",
            )

        # Detect class name if declared
        match = re.search(r"public\s+class\s+([A-Za-z0-9_]+)", req.code)
        class_name = match.group(1) if match else "Main"
        java_file = work_dir / f"{class_name}.java"
        java_file.write_text(req.code, encoding="utf-8")

        # 1. Compile
        compile_proc = await asyncio.create_subprocess_exec(
            javac_bin,
            "-encoding",
            "UTF-8",
            str(java_file),
            cwd=str(work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, c_stderr = await compile_proc.communicate()
        if compile_proc.returncode != 0:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr=f"[JAVA COMPILATION ERROR]:\n{c_stderr.decode('utf-8', errors='replace')}",
                exit_code=compile_proc.returncode or 1,
                execution_time_ms=round(elapsed, 2),
                language="java",
            )

        # 2. Run
        return await self._execute_subprocess(
            [java_bin, class_name],
            work_dir,
            req.stdin,
            req.timeout_seconds,
            "java",
            start_time,
            "Java OpenJDK",
        )

    async def _run_c(self, req: ExecuteRequest, work_dir: Path, start_time: float) -> ExecuteResponse:
        is_cpp = req.language.lower().strip() in ("cpp", "c++")
        if is_cpp:
            gcc_bin = shutil.which("g++") or shutil.which("clang++")
        else:
            gcc_bin = shutil.which("gcc") or shutil.which("clang")
        if not gcc_bin:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr="No C/C++ compiler found (gcc, g++, or clang). Install MinGW or GCC on Windows to compile C/C++ code.",
                exit_code=1,
                execution_time_ms=round(elapsed, 2),
                language="c",
            )

        src_file = work_dir / ("program.cpp" if is_cpp else "program.c")
        src_file.write_text(req.code, encoding="utf-8")
        out_exe = work_dir / ("program.exe" if os.name == "nt" else "program.out")

        compile_proc = await asyncio.create_subprocess_exec(
            gcc_bin,
            str(src_file),
            "-o",
            str(out_exe),
            cwd=str(work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, c_stderr = await compile_proc.communicate()
        if compile_proc.returncode != 0:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr=f"[C COMPILATION ERROR]:\n{c_stderr.decode('utf-8', errors='replace')}",
                exit_code=compile_proc.returncode or 1,
                execution_time_ms=round(elapsed, 2),
                language="c",
            )

        return await self._execute_subprocess(
            [str(out_exe)],
            work_dir,
            req.stdin,
            req.timeout_seconds,
            "c",
            start_time,
            "GCC C/C++",
        )

    async def _run_bash(self, req: ExecuteRequest, work_dir: Path, start_time: float) -> ExecuteResponse:
        bash_bin = shutil.which("bash") or shutil.which("sh")
        if not bash_bin:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr="bash executable not found.",
                exit_code=1,
                execution_time_ms=round(elapsed, 2),
                language="bash",
            )

        script_file = work_dir / "script.sh"
        script_file.write_text(req.code, encoding="utf-8")
        return await self._execute_subprocess(
            [bash_bin, str(script_file)],
            work_dir,
            req.stdin,
            req.timeout_seconds,
            "bash",
            start_time,
            "Bash",
        )

    async def _run_powershell(self, req: ExecuteRequest, work_dir: Path, start_time: float) -> ExecuteResponse:
        pwsh_bin = shutil.which("powershell") or shutil.which("pwsh")
        if not pwsh_bin:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ExecuteResponse(
                status="error",
                stdout="",
                stderr="PowerShell executable not found.",
                exit_code=1,
                execution_time_ms=round(elapsed, 2),
                language="powershell",
            )

        script_file = work_dir / "script.ps1"
        script_file.write_text(req.code, encoding="utf-8")
        return await self._execute_subprocess(
            [
                pwsh_bin,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_file),
            ],
            work_dir,
            req.stdin,
            req.timeout_seconds,
            "powershell",
            start_time,
            "PowerShell",
        )


runner_service = RunnerService()
