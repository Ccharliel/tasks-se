import time
import tempfile
from apscheduler.schedulers.blocking import BlockingScheduler
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.select import Select
import threading
from abc import ABC, abstractmethod
import shutil
from dotenv import load_dotenv
from pathlib import Path
from loguru import logger

from tasks_se.utils.base_utils import *


CURRENT_FILE = Path(__file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent
log_dir = f"{CURRENT_DIR.parent}/logs"
os.makedirs(log_dir, exist_ok=True)
logger.add(f"{log_dir}/driver.log",
           rotation="1 MB",
           filter=lambda record: record["function"] == "_init_driver")

# TASK 是进行selenium进行自动化操作的任务
class TASK(ABC):
    NUM = 0
    _num_lock = threading.Lock()

    def __init__(self, u, x_p, y_p, x_s, y_s, name=None):
        self.u = u
        self.x_p = x_p
        self.y_p = y_p
        self.x_s = x_s
        self.y_s = y_s
        self.class_name = self.__class__.__name__
        self.log_dir = f"logs/{self.class_name}"
        os.makedirs(self.log_dir, exist_ok=True)
        self.name = f"{self.class_name}{TASK.NUM}" if name is None else name
        self.dr = None  # 子类 name 重写后再初始化驱动
        with TASK._num_lock:
            TASK.NUM += 1

    def _init_driver(self, shared_dr=None):
        """初始化驱动"""
        ### 共享已有驱动情况
        try:
            logger.info(f'{self.name} is initializing driver ...')
            if shared_dr:
                logger.info(f'{self.name} is using shared driver ...')
                driver = shared_dr
                current_url = driver.current_url
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[-1])
                driver.get(current_url)
            ### 创建新驱动情况
            else:
                ## 确定驱动参数
                opt = uc.ChromeOptions()
                opt.page_load_strategy = "eager"
                # 将用户数据保存在 各系统临时目录下的 crawler_{self.class_name}_{随机字符串} 子目录
                user_data_dir = tempfile.mkdtemp(prefix=f"crawler_{self.class_name}_")
                opt.add_argument(f"--user-data-dir={user_data_dir}")
                # 确保每个任务都使用不同的可用端口
                debug_port = 9222 + TASK.NUM
                if is_port_available(debug_port):
                    opt.add_argument(f"--remote-debugging-port={debug_port}")
                else:
                    # 端口被占用，向后寻找下一个可用端口
                    safe_port = find_free_port(debug_port+1, 10000)
                    opt.add_argument(f"--remote-debugging-port={safe_port}")
                # 添加反检测参数
                opt.add_argument("--disable-blink-features=AutomationControlled")
                # 提高 Linux 下兼容性
                opt.add_argument("--no-sandbox")  # 禁用沙盒
                opt.add_argument("--disable-dev-shm-usage")  # 禁用共享内存
                ## 创建驱动实例并调整
                load_dotenv()
                ver = os.getenv("CHROME_VERSION")
                driver_path = chromedriver_downloading(ver, CURRENT_DIR / "drivers")
                driver = uc.Chrome(
                    options=opt,
                    driver_executable_path=driver_path
                )
                driver.get(self.u)
                time.sleep(0.1)
                driver.implicitly_wait(3)
                driver.set_window_position(self.x_p, self.y_p)
                driver.set_window_size(self.x_s, self.y_s)
            logger.success(f'{self.name} successfully initialize driver !!!')
            return driver
        except Exception as e:
            logger.critical(f'{self.name} failed to initialize driver !!!\n[{e}]')
            raise RuntimeError(f"Failed to initialize driver")

    # 常规的元素操作方法，需要先确保元素可见且可交互
    def _ensure_element_visible(self, element):
        """滚动到元素可见，不改变窗口状态"""
        self.dr.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            element
        )
        time.sleep(0.1)  # 等待滚动完成

    def _safe_click(self, element):
        """安全的点击操作"""
        self._ensure_element_visible(element)
        try:
            # 点击元素
            element.click()
        except:
            # 如果普通点击失败，用JS设置值
            try:
                self.dr.execute_script("arguments[0].click();", element)
            except Exception as e:
                raise RuntimeError(f"Failed to click element: {e}")

    def _safe_send_keys(self, element, text):
        """安全的输入文本操作"""
        self._ensure_element_visible(element)
        try:
            # 先点击元素获得焦点
            try:
                element.click()
            except:
                self.dr.execute_script("arguments[0].click();", element)
            # 清空原有内容
            element.clear()
            # 输入文本
            element.send_keys(text)
        except:
            # 如果普通输入文本失败，用JS设置值
            try:
                if isinstance(key, str):
                    self.dr.execute_script(f"arguments[0].value = '{text}';", element)
            except Exception as e:
                raise RuntimeError(f"Failed to send keys to element: {e}")

    def _safe_select(self, element, by="text", value=None):
        """安全选择方法"""
        self._ensure_element_visible(element)
        try:
            select = Select(element)
            if by == "text":
                select.select_by_visible_text(value)
            elif by == "value":
                select.select_by_value(value)
            elif by == "index":
                select.select_by_index(int(value))
        except:
            pass

    def _shot(self, max_nums=100):
        folder_path = f"{self.log_dir}/{self.class_name}_ScreenShot"
        os.makedirs(folder_path, exist_ok=True)
        now = time.strftime("%Y%m%d%H%M%S", time.localtime())
        tag = f"{self.name}_" + now
        file_path = os.path.join(folder_path, f"{tag}.png")
        self.dr.get_screenshot_as_file(file_path)
        auto_del_files(folder_path, max_nums)

    # 核心运行方法
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
            if (x_p is not None) and (y_p is not None) and (x_s is not None) and (y_s is not None):
                self.dr.set_window_position(x_p, y_p)
                self.dr.set_window_size(x_s, y_s)
            else:
                raise Exception("Custom mode requires x_p, y_p, x_s, y_s parameters!")
        elif mode == "max":
            self.dr.maximize_window()
        elif mode == "min":
            self.dr.minimize_window()
        elif mode == "recover":
            self.dr.set_window_position(self.x_p, self.y_p)
            self.dr.set_window_size(self.x_s, self.y_s)
        time.sleep(0.5)

    def __del__(self):
        self.dr.quit()
