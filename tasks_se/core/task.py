import time
from apscheduler.schedulers.blocking import BlockingScheduler
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
import threading
from abc import ABC, abstractmethod
import shutil

from tasks_se.utils.base_utils import *


# TASK 是进行selenium进行自动化操作的任务
# 子类最好重新给name和type
class TASK(ABC):
    TaskNums = 0
    _lock = threading.Lock()

    def __init__(self, x_p, y_p, x_s, y_s, u, name=None):
        self.x_p = x_p
        self.y_p = y_p
        self.x_s = x_s
        self.y_s = y_s
        self.u = u
        if name is None:
            self.name = f"TASK{TASK.TaskNums}"
        else:
            self.name = name
        self.type = "tasks_se"
        self.dr = None  # dr 在每个子类的 type 和 name 重写后再初始化
        with TASK._lock:
            TASK.TaskNums += 1

    def _init_driver(self, shared_dr=None):
        """初始化驱动"""
        ### 共享已有驱动情况
        if shared_dr:
            driver = shared_dr
            current_url = driver.current_url
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(current_url)
            return driver
        ### 创建新驱动情况
        else:
            ## 按优先级尝试不同的驱动路径
            service = None
            driver_dir = "D:/msedgedriver_tmp"
            driver_web = "https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver"
            driver_paths = [
                None,  # 系统PATH
                f"{driver_dir}/msedgedriver.exe"  # 自定义路径
            ]
            for driver_path in driver_paths:
                try:
                    os.makedirs(driver_dir, exist_ok=True)
                    if driver_path:
                        service = Service(executable_path=driver_path)
                    else:
                        service = Service()  # 使用系统PATH
                    # 测试驱动
                    dr_tmp = webdriver.Edge(service=service)
                    dr_tmp.close()
                    print(f"驱动加载成功: {driver_path or '系统PATH'}")
                    break  # 成功则跳出循环
                except Exception as e:
                    print(f"驱动路径 {driver_path or '系统PATH'} 失败: {e}\n"
                          f"请到{driver_web}\n"
                          f"下载最新驱动(msedgedriver.exe)，然后放到 {driver_dir} 下")
                    if driver_path == driver_paths[-1]:  # 最后一个尝试也失败
                        raise RuntimeError(f"所有驱动路径都失败，最后一个错误: {e}")
            ## 确定驱动参数
            opt = Options()
            # opt.add_experimental_option('detach', True)
            opt.page_load_strategy = "eager"
            # 将用户数据保存在 D:/edge_user_data 目录
            user_data_dir = f"D:/edge_user_data/{self.type}/{self.name}"
            if os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir)
            os.makedirs(user_data_dir, exist_ok=True)
            opt.add_argument(f"--user-data-dir={user_data_dir}")
            opt.add_argument("--profile-directory=Default")  # 使用默认配置文件
            # 确保每个任务都使用不同的可用端口
            debug_port = 9222 + TASK.TaskNums
            if is_port_available(debug_port):
                opt.add_argument(f"--remote-debugging-port={debug_port}")
            else:
                # 端口被占用，使用随机端口
                safe_port = find_free_port(9222, 10000)
                opt.add_argument(f"--remote-debugging-port={safe_port}")
            ## 创建驱动实例并调整
            driver = webdriver.Edge(service=service, options=opt)
            driver.get(self.u)
            time.sleep(0.1)
            driver.implicitly_wait(3)
            driver.set_window_position(self.x_p, self.y_p)
            driver.set_window_size(self.x_s, self.y_s)
        return driver

    @abstractmethod
    def run(self):
        pass

    def run_with_schedule(self, point, date=None):
        hour, minute, second = point.split(':')
        scheduler = BlockingScheduler()
        if date is None:
            scheduler.add_job(self.run, 'cron', hour=hour, minute=minute, second=second)
        else:
            scheduler.add_job(self.run, 'date', run_date=date + ' ' + point)
        scheduler.start()

    def reset_loc(self, mode, x_p=None, y_p=None, x_s=None, y_s=None):
        if mode == "cus":
            if x_p is not None and y_p is not None and x_s is not None and y_s is not None:
                self.x_p = x_p
                self.y_p = y_p
                self.x_s = x_s
                self.y_s = y_s
                self.dr.set_window_position(self.x_p, self.y_p)
                self.dr.set_window_size(self.x_s, self.y_s)
        elif mode == "max":
            self.dr.maximize_window()
        elif mode == "min":
            self.dr.minimize_window()

    def log(self, max_nums=100):
        folder_path = f"log/{self.type}"
        os.makedirs(folder_path, exist_ok=True)
        now = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime())
        while True:
            try:
                with open(f"{folder_path}/{self.type}.log", "a+") as f:
                    f.write(now + f"{self.name} successfully run!\n")
                    f.seek(0)
                    lines = f.readlines()
                    if len(lines) > max_nums:
                        f.seek(0)
                        f.truncate()
                        f.writelines(lines[-max_nums:])
                    break
            except FileNotFoundError:
                with open(f"{folder_path}/{self.type}.log", "w") as f0:
                    f0.write("")
                    pass

    def shot(self, max_nums=100):
        folder_path = f"log/{self.type}/{self.type}_ScreenShot"
        os.makedirs(folder_path, exist_ok=True)
        now = time.strftime("%Y%m%d%H%M%S", time.localtime())
        tag = f"{self.name}_" + now
        file_path = os.path.join(folder_path, f"{tag}.png")
        self.dr.get_screenshot_as_file(file_path)
        auto_del_files(folder_path, max_nums)

    def __del__(self):
        self.dr.quit()
