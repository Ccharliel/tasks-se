from pathlib import Path
import os
import socket
import requests
import zipfile
import shutil
import platform
import sys
from loguru import logger
import tkinter as tk
import time

from tasks_se.core.config import LOG_DIR


os.makedirs(LOG_DIR, exist_ok=True)
logger.add(f"{LOG_DIR}/driver.log",
           rotation="1 MB",
           filter=lambda record: record["function"] == "chromedriver_downloading")


def get_screen_resolution():
    root = tk.Tk()
    # 获取屏幕宽度和高度
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.destroy()  # 关闭窗口
    return width, height

def auto_del_files(folder_path, max_nums):
    """
    folder_path 中文件数量超过 max_nums 时，自动删除时间较早的文件
    """
    folder = Path(folder_path)
    all_files = sorted(folder.glob("*.*"), key=lambda x: os.path.getmtime(x))
    if len(all_files) > max_nums:
        for old_file in all_files[: -max_nums]:
            old_file.unlink()

def is_port_available(port):
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: # 相当于说：创建一个使用IPv4地址的TCP连接
        try:
            s.bind(('127.0.0.1', port))
            return True
        except socket.error:
            return False

def find_free_port(start_port, max_attempts):
    """查找空闲端口"""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except socket.error:
                continue
    raise Exception("找不到可用端口")


def get_platform_chromedriver():
    "获取当前平台信息, 返回符合 ChromeDriver 命名规范的字符串"
    system = platform.system().lower()
    machine = platform.machine().lower()
    # 处理操作系统
    if system == "windows":
        # 检查是32位还是64位
        if sys.maxsize > 2 ** 32:
            return "win64"
        else:
            return "win32"
    elif system == "linux":
        return "linux64"
    elif system == "darwin":  # macOS
        # 检查ARM架构（Apple Silicon）
        if machine in ["arm64", "aarch64"]:
            return "mac-arm64"
        else:
            return "mac-x64"
    else:
        raise Exception(f"Unsupported platform: {system}")

def chromedriver_downloading(version, save_dir):
    """通过国内镜像下载指定版本浏览器驱动，返回驱动路径"""
    try:
        version_tag = version.replace(".", "_")
        if not version_tag:
            raise ValueError("Version resulted in empty string")
    except Exception as e:
        raise ValueError(f"Invalid version format: {version}")
    platform_tag = get_platform_chromedriver()
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"chromedriver-{version_tag}-{platform_tag}.exe")
    save_path = os.path.abspath(save_path)
    if os.path.exists(save_path):
        logger.info(f"ChromeDriver existed: {save_path}")
        return save_path
    try:
        logger.info(f"Downloading ChromeDriver {version} for {platform_tag} ...")
        url_huawei = f"https://repo.huaweicloud.com/chromedriver/{version}/chromedriver-{platform_tag}.zip"
        # 下载 zip
        response = requests.get(url_huawei)
        if response.status_code != 200:
            raise Exception(f"mirro erro: {response.status_code}")
        # 保存 zip
        zip_path = save_path + ".zip"
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        # 解压
        tmp_dir = os.path.join(save_dir, "temp_driver")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)
        # 移动exe文件
        for root, dirs, files in os.walk(tmp_dir):
            if "chromedriver.exe" in files:
                src = os.path.join(root, "chromedriver.exe")
                shutil.move(src, save_path)
                break
        logger.success(f"Successfully download ChromeDriver: {save_path}")
        return save_path
    except Exception as e:
        raise RuntimeError(f"Failed do download ChromeDriver: {e}")
    finally:
        # 清理临时文件
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)


def wait_for_download(download_dir, timeout):
    """等待下载完成，返回下载的文件名，会自动清理下载目录"""
    start_time = time.time()
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    os.makedirs(download_dir, exist_ok=True)
    while time.time() - start_time < timeout:
        files = os.listdir(download_dir)
        # 检查是否有 .crdownload 临时文件
        has_temp = any(f.endswith('.crdownload') for f in files)
        # 检查是否有新文件（排除 .tmp 等临时文件）
        completed = [f for f in files if not f.endswith(('.crdownload', '.tmp'))]
        if not has_temp and completed:
            return completed[0]  # 返回最新完成的文件
        time.sleep(0.5)
    raise TimeoutError("下载超时")
