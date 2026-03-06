from pathlib import Path
import os
import socket

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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return True
        except socket.error:
            return False

def find_free_port(start_port=9222, max_attempts=100):
    """查找空闲端口"""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except socket.error:
                continue
    raise Exception("找不到可用端口")


