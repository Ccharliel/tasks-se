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
logger.add(f"{LOG_DIR}/download.log",
           rotation="1 MB",
           filter=lambda record: record["function"] == "wait_for_download")


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

# def is_port_available(port):
#     """检查端口是否可用"""
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: # 相当于说：创建一个使用IPv4地址的TCP连接
#         try:
#             s.bind(('127.0.0.1', port))
#             return True
#         except socket.error:
#             return False

def find_free_port(start_port, max_attempts):
    """查找空闲端口（端口被占用，向后寻找下一个可用端口）"""
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

def chrome_driver_downloading(version, save_dir):
    """下载指定版本 chrome for testing 的浏览器以及驱动，返回浏览器路径以及驱动路径"""
    try:
        version_tag = version.replace(".", "_")
        if not version_tag:
            raise ValueError("Version resulted in empty string")
    except Exception as e:
        raise ValueError(f"Invalid version format: {version}")
    platform_tag = get_platform_chromedriver()
    if platform_tag in ["win64", "win32"]:
        extention = ".exe"
    else:
        extention = ''

    chrome_dir = os.path.join(save_dir, "chromes", f"chrome-{version_tag}", f"chrome-{version_tag}-{platform_tag}")
    os.makedirs(chrome_dir, exist_ok=True)
    chrome_save_path = os.path.abspath(os.path.join(chrome_dir, f"chrome{extention}"))
    driver_dir = os.path.join(save_dir, "drivers", f"chromedriver-{version_tag}")
    os.makedirs(driver_dir, exist_ok=True)
    driver_save_path = os.path.abspath(os.path.join(driver_dir, f"chromedriver-{version_tag}-{platform_tag}{extention}"))
    if_download_chrome, if_download_driver = True, True
    if os.path.exists(chrome_save_path):
        logger.info(f"Chrome existed: {chrome_save_path}")
        if_download_chrome = False
    if os.path.exists(driver_save_path):
        logger.info(f"ChromeDriver existed: {driver_save_path}")
        if_download_driver = False

    if if_download_chrome or if_download_driver:
        def download_chrome_for_testing(version, platform_tag, is_driver=False):
            """根据版本和平台标签下载 chrome for testing (driver) 的二进制内容"""
            base_url_list = [
                "https://cdn.npmmirror.com/binaries/chrome-for-testing",
                "https://storage.googleapis.com/chrome-for-testing-public"
            ]
            for base_url in base_url_list:
                logger.info(f"Trying download from origin: {base_url}")
                url = (f"{base_url}/{version}/{platform_tag}/"
                       f"{'chromedriver' if is_driver else 'chrome'}-{platform_tag}.zip")
                try:
                    response = requests.get(url, timeout=(5, 60))
                    response.raise_for_status()
                    logger.success(f"Successfully download from origin: {base_url}")
                    return response.content
                except Exception as e:
                    logger.warning(f"Failed download from origin: {base_url}")
                    continue
            raise TimeoutError(f"Failed download {'ChromeDriver' if is_driver else 'Chrome'} from any origin")

        def write_and_extract_zip(binary_content, save_dir):
            # 写入 zip
            tmp_zip_path = os.path.join(save_dir, "tmp.zip")
            with open(tmp_zip_path, 'wb') as f:
                f.write(binary_content)
            # 解压
            tmp_dir = os.path.join(save_dir, "tmp")
            with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            return tmp_zip_path, tmp_dir

        if if_download_chrome:
            try:
                tmp_zip_path, tmp_dir = None, None
                logger.info(f"Downloading Chrome {version} for {platform_tag} ...")
                zip_binary = download_chrome_for_testing(version, platform_tag, False)
                tmp_zip_path, tmp_dir = write_and_extract_zip(zip_binary, chrome_dir)
                # 移动 chrome 所有文件
                for item in os.listdir(tmp_dir):
                    src_path = os.path.join(tmp_dir, item)
                    if os.path.isdir(src_path):
                        for sub_item in os.listdir(src_path):
                            sub_src = os.path.join(src_path, sub_item)
                            sub_dst = os.path.join(chrome_dir, sub_item)
                            shutil.move(sub_src, sub_dst)
                    else:
                        shutil.move(src_path, os.path.join(chrome_dir, item))
                logger.success(f"Successfully download Chrome: {chrome_save_path}")
            except Exception as e:
                raise RuntimeError(f"Failed do download Chrome: {e}")
            finally:
                # 清理临时文件
                if tmp_zip_path and os.path.exists(tmp_zip_path):
                    os.remove(tmp_zip_path)
                if tmp_dir and os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir)
        if if_download_driver:
            try:
                tmp_zip_path, tmp_dir = None, None
                logger.info(f"Downloading ChromeDriver {version} for {platform_tag} ...")
                zip_binary = download_chrome_for_testing(version, platform_tag, True)
                tmp_zip_path, tmp_dir = write_and_extract_zip(zip_binary, driver_dir)
                # 移动 chromedrive 文件
                for root, dirs, files in os.walk(tmp_dir):
                    if f"chromedriver{extention}" in files:
                        src = os.path.join(root, f"chromedriver{extention}")
                        shutil.move(src, driver_save_path)
                        os.chmod(driver_save_path, 0o755) # 加权限，全局通用，Windows不报错，Linux/Mac正常生效
                        break
                logger.success(f"Successfully download ChromeDriver: {driver_save_path}")
            except Exception as e:
                raise RuntimeError(f"Failed do download ChromeDriver: {e}")
            finally:
                # 清理临时文件
                if tmp_zip_path and os.path.exists(tmp_zip_path):
                    os.remove(tmp_zip_path)
                if tmp_dir and os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir)

    return chrome_save_path, driver_save_path


def wait_for_download(download_dir, timeout):
    """等待下载完成，返回下载的文件名，会自动清理下载目录"""
    start_time = time.time()
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    os.makedirs(download_dir, exist_ok=True)
    logger.info(f"Waiting for download to complete in {download_dir} ...")
    while time.time() - start_time < timeout:
        files = os.listdir(download_dir)
        # 检查是否有 .crdownload 临时文件
        has_temp = any(f.endswith('.crdownload') for f in files)
        # 检查是否有新文件（排除 .tmp 等临时文件）
        completed = [f for f in files if not f.endswith(('.crdownload', '.tmp', '.htm'))]
        if not has_temp and completed:
            logger.success(f"Download completed: {completed[0]}")
            return completed[0]  # 返回最新完成的文件
        time.sleep(0.5)
    logger.error(f"Download timed out after waiting for {timeout} seconds")
    raise TimeoutError(f"Download timed out")
