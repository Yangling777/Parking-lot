#!/usr/bin/env python3
"""
智能停车场管理系统 — 一键环境配置脚本

用法:
  python setup.py              # 完整安装
  python setup.py --backend     # 仅后端
  python setup.py --tools       # 仅工具环境
  python setup.py --db          # 仅初始化数据库
  python setup.py --check       # 仅环境检查

自动完成:
  1. 检测 Python 版本 (>= 3.10)
  2. 创建 Python 虚拟环境
  3. 安装所有依赖包
  4. 初始化数据库
  5. 运行烟雾测试
  6. 输出启动命令
"""

import sys
import os
import subprocess
import platform
import shutil
from pathlib import Path

# ---- 配置 ----
PROJECT_ROOT = Path(__file__).parent.resolve()
CODE_DIR = PROJECT_ROOT / "code"
TOOLS_DIR = PROJECT_ROOT / "tools" / "image_converter"

BACKEND_VENV = CODE_DIR / ".venv"
TOOLS_VENV = TOOLS_DIR / ".venv"
MIN_PYTHON = (3, 10)

# Pi5 需要额外安装的包 (无 GPU)
PI5_PACKAGES = [
    "ultralytics", "paddleocr",
]

# 后端核心依赖
BACKEND_PACKAGES = [
    "flask", "flask-sqlalchemy", "flask-socketio", "flask-cors", "eventlet",
    "scikit-learn", "numpy", "pandas",
    "opencv-python", "hyperlpr3",
    "tencentcloud-sdk-python",
    "pyserial", "python-docx", "python-multipart",
    "requests", "loguru", "lxml",
]

# 工具环境依赖
TOOLS_PACKAGES = [
    "opencv-python", "numpy",
]

# ---- 颜色输出 ----
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def enable():
        if platform.system() == "Windows":
            os.system("")  # 启用 ANSI

Colors.enable()


def cprint(msg, color=Colors.END):
    print(f"{color}{msg}{Colors.END}")


def header(msg):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.END}")
    cprint(f"  {msg}", Colors.HEADER)
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.END}\n")


def ok(msg):
    cprint(f"  [OK] {msg}", Colors.GREEN)


def warn(msg):
    cprint(f"  [WARN] {msg}", Colors.WARN)


def fail(msg):
    cprint(f"  [FAIL] {msg}", Colors.FAIL)


def info(msg):
    cprint(f"  [..] {msg}", Colors.BLUE)


# ---- 核心函数 ----
def get_python():
    """查找可用的 Python 解释器"""
    for name in ["python3", "python"]:
        path = shutil.which(name)
        if path:
            return path
    return sys.executable


def check_python_version(python_path):
    """Check Python version"""
    try:
        result = subprocess.run(
            [python_path, "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
            capture_output=True, text=True, timeout=10
        )
        parts = result.stdout.strip().split()
        if len(parts) >= 2:
            major, minor = int(parts[0]), int(parts[1])
            version = f"{major}.{minor}"
            if (major, minor) >= MIN_PYTHON:
                return True, version
            return False, version
        return False, "unknown"
    except Exception as e:
        return False, str(e)


def run_pip(python_path, args, desc="", timeout=300):
    """运行 pip 命令"""
    info(desc or f"pip {' '.join(args[:3])}...")
    try:
        result = subprocess.run(
            [python_path, "-m", "pip"] + args,
            capture_output=True, text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            last_line = result.stderr.strip().split('\n')[-1] if result.stderr else ""
            if "Successfully installed" in result.stdout:
                ok(f"Installed successfully")
                return True
            warn(f"pip warning: {last_line[:100]}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        warn(f"Timeout, continuing...")
        return True
    except Exception as e:
        fail(f"pip error: {e}")
        return False


def run_python(python_path, code, desc="", timeout=30):
    """运行 Python 代码"""
    info(desc)
    try:
        result = subprocess.run(
            [python_path, "-c", code],
            capture_output=True, text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(CODE_DIR)}
        )
        if result.returncode == 0:
            ok("OK")
            return True
        fail(f"Failed: {result.stderr[:200]}")
        return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


def create_venv(python_path, venv_path, desc=""):
    """创建虚拟环境"""
    info(desc or f"Creating venv: {venv_path}")
    if venv_path.exists():
        info(f"  Removing existing venv...")
        shutil.rmtree(venv_path, ignore_errors=True)
    try:
        subprocess.run(
            [python_path, "-m", "venv", str(venv_path)],
            capture_output=True, timeout=60, check=True
        )
        ok("Venv created")
        return True
    except Exception as e:
        fail(f"Venv creation failed: {e}")
        return False


def install_requirements():
    """主安装流程"""
    python = get_python()
    cprint(f"  Python: {python}", Colors.BLUE)

    # 检查版本
    valid, version = check_python_version(python)
    if not valid:
        if version < "3.10":
            fail(f"Python {version} is too old. Need >= 3.10")
            return False
        else:
            warn(f"Python version check: {version}")

    ok(f"Python {version} OK")

    # ---- 后端环境 ----
    header("Step 1/4: Backend Environment")
    if not create_venv(python, BACKEND_VENV, "backend .venv"):
        return False

    venv_python = str(BACKEND_VENV / ("Scripts" if platform.system() == "Windows" else "bin") / "python")
    if platform.system() != "Windows":
        venv_python = str(BACKEND_VENV / "bin" / "python")

    # 安装核心依赖
    run_pip(venv_python, ["install", "--upgrade", "pip"], "upgrade pip", timeout=120)
    run_pip(venv_python, ["install"] + BACKEND_PACKAGES, "backend core packages", timeout=600)

    # 可选: 安装 AI 包
    info("Installing AI packages (YOLO + PaddleOCR)...")
    run_pip(venv_python, ["install"] + PI5_PACKAGES, "AI packages", timeout=600)

    # 验证后端导入
    header("Step 2/4: Verify Backend")
    verify_code = (
        "import flask, flask_sqlalchemy, flask_socketio, sklearn, numpy, cv2; "
        "print('Core OK')"
    )
    run_python(venv_python, verify_code, "core imports")

    # ---- 工具环境 ----
    header("Step 3/4: Tools Environment")
    if create_venv(python, TOOLS_VENV, "tools .venv"):
        tools_python = str(TOOLS_VENV / ("Scripts" if platform.system() == "Windows" else "bin") / "python")
        if platform.system() != "Windows":
            tools_python = str(TOOLS_VENV / "bin" / "python")
        run_pip(tools_python, ["install"] + TOOLS_PACKAGES, "tools packages")
        ok("Tools environment ready")

    # ---- 数据库初始化 ----
    header("Step 4/4: Database Init")
    db_init_code = "; ".join([
        "import sys, os",
        f"sys.path.insert(0, r'{PROJECT_ROOT}')",
        f"sys.path.insert(0, r'{CODE_DIR}')",
        f"os.chdir(r'{CODE_DIR}')",
        "from app import create_app",
        "from database_init import init_database",
        "app = create_app()",
        "with app.app_context(): init_database(app)",
        "print('Database initialized')"
    ])
    run_python(venv_python, db_init_code, "init database", timeout=30)

    return True


def check_environment():
    """环境检查"""
    header("Environment Check")

    python = get_python()
    valid, version = check_python_version(python)
    if valid:
        ok(f"Python {version}")
    else:
        fail(f"Python {version} (need >= 3.10)")

    for name, path in [("Backend venv", BACKEND_VENV), ("Tools venv", TOOLS_VENV)]:
        if path.exists():
            ok(f"{name}: {path}")
        else:
            warn(f"{name}: not found")

    # 检查关键包
    if BACKEND_VENV.exists():
        venv_python = str(BACKEND_VENV / ("Scripts" if platform.system() == "Windows" else "bin") / "python")
        if platform.system() != "Windows":
            venv_python = str(BACKEND_VENV / "bin" / "python")
        for pkg in ["flask", "sklearn", "numpy"]:
            result = subprocess.run(
                [venv_python, "-c", f"import {pkg}"],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                ok(f"  {pkg}")
            else:
                warn(f"  {pkg} (not installed)")


def init_database():
    """仅初始化数据库"""
    python = get_python()
    venv_python = str(BACKEND_VENV / ("Scripts" if platform.system() == "Windows" else "bin") / "python")
    if platform.system() != "Windows":
        venv_python = str(BACKEND_VENV / "bin" / "python")

    db_init_code = "; ".join([
        "import sys, os",
        f"sys.path.insert(0, r'{PROJECT_ROOT}')",
        f"sys.path.insert(0, r'{CODE_DIR}')",
        f"os.chdir(r'{CODE_DIR}')",
        "from app import create_app",
        "from database_init import init_database",
        "app = create_app()",
        "with app.app_context(): init_database(app)",
        "print('Database initialized')"
    ])
    return run_python(venv_python, db_init_code, "init database")


def print_usage():
    """打印使用说明"""
    print(f"""
{Colors.BOLD}{Colors.GREEN}===== Setup Complete! ====={Colors.END}

{Colors.BOLD}Start Backend:{Colors.END}
  cd {CODE_DIR}
  {".venv\\Scripts\\python" if platform.system() == "Windows" else ".venv/bin/python"} app.py

{Colors.BOLD}With WebSocket:{Colors.END}
  ENABLE_SOCKETIO=1 {".venv\\Scripts\\python" if platform.system() == "Windows" else ".venv/bin/python"} app.py

{Colors.BOLD}Test Accounts:{Colors.END}
  User:  13800138000 / 123456  (张三, 京A88888)
  Admin: admin / admin
  Guard: anbao / anbao

{Colors.BOLD}Access:{Colors.END}
  Login:    http://localhost:5000
  Admin:    http://localhost:5000/admin
  Sim:      http://localhost:5000/simulator
  API Docs: see README.md

{Colors.BOLD}Pi5 Edge Node:{Colors.END}
  cd {PROJECT_ROOT / "hardware" / "pi5"}
  python3 main.py
""")


# ---- 入口 ----
def main():
    args = sys.argv[1:]

    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("  智能停车场管理系统 — 环境配置脚本")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print(f"  Project: {PROJECT_ROOT}")
    print(f"{Colors.END}")

    if "--check" in args:
        check_environment()
        return

    if "--db" in args:
        init_database()
        return

    if "--backend" in args:
        header("Backend Only")
        python = get_python()
        create_venv(python, BACKEND_VENV, "backend .venv")
        venv_python = str(BACKEND_VENV / ("Scripts" if platform.system() == "Windows" else "bin") / "python")
        if platform.system() != "Windows":
            venv_python = str(BACKEND_VENV / "bin" / "python")
        run_pip(venv_python, ["install"] + BACKEND_PACKAGES, "backend packages", timeout=600)
        return

    if "--tools" in args:
        header("Tools Only")
        python = get_python()
        create_venv(python, TOOLS_VENV, "tools .venv")
        tools_python = str(TOOLS_VENV / ("Scripts" if platform.system() == "Windows" else "bin") / "python")
        if platform.system() != "Windows":
            tools_python = str(TOOLS_VENV / "bin" / "python")
        run_pip(tools_python, ["install"] + TOOLS_PACKAGES, "tools packages")
        return

    # 完整安装
    success = install_requirements()
    if success:
        print_usage()
    else:
        cprint("\nSetup encountered errors. Try running with --check to diagnose.", Colors.FAIL)
        sys.exit(1)


if __name__ == "__main__":
    main()
