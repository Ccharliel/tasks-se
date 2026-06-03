from enum import Enum
import os
import time
from datetime import datetime, timedelta
from typing import Tuple, Any, Mapping
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.base import BaseTrigger
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
import threading
from abc import ABC, abstractmethod
from loguru import logger
from urllib.parse import urlparse

from tasks_se.utils.base_utils import *
from tasks_se.core.config import CORE_DIR, LOG_DIR, CHROME_VERSION, CHROME_VERSION_TESTING


os.makedirs(os.path.join(LOG_DIR, "init"), exist_ok=True)
logger.add(os.path.join(LOG_DIR, "init", "window.log"),
           rotation="1 MB",
           filter=lambda record: record["function"] == "_check_window_valid")
logger.add(os.path.join(LOG_DIR, "init", "driver.log"),
           rotation="1 MB",
           filter=lambda record: record["function"] == "_init_driver")
logger.add(os.path.join(LOG_DIR, "init", "login.log"),
           rotation="1 MB",
           filter=lambda record: record["function"] == "_login_pipe")

class TASK(ABC):
    """
    TASK 是进行selenium进行自动化操作的任务

    类变量操作要加线程锁，确保多线程同时创建实例时，类变量操作不会竞争
    """
    _num: int
    _num_lock: threading.Lock
    _logger_configured: bool
    _logger_configured_lock: threading.Lock
    __windows = []  # 记录已分配显示窗口的坐标和大小
    __windows_lock = threading.Lock()

    # Properties: read-only access to instance attributes
    # 核心
    @property
    def _url(self):
        return self.__url

    @property
    def _dr(self):
        return self.__dr

    # 显示
    @property
    def _window(self):
        return self.__window

    @property
    def _display(self):
        return self.__display

    # 定时
    @property
    def _scheduler(self):
        return self.__scheduler

    # 登陆
    @property
    def _login_data(self):
        return self.__login_data

    @property
    def _user_data(self):
        return self.__user_data

    @property
    def session_data(self):
        return self.__session_data

    # 名称
    @property
    def _name(self):
        return self.__name

    # 日志和下载
    @property
    def _log_dir(self):
        return self.__log_dir

    @property
    def _download_dir(self):
        return self.__download_dir

    @property
    def _log(self):
        return self.__log

    # ====================================================================================
    # 初始化阶段：过程中的异常直接抛出并记录 critical 级别 log（目前包括 window.log 和 driver.log）
    # ====================================================================================
    # 基本初始化方法
    def __init_subclass__(cls, **kwargs):
        """
        为子类初始化并校验类变量
        """
        super().__init_subclass__(**kwargs)
        LOCK_TYPE = type(threading.Lock())
        if not hasattr(cls, "_num"):
            cls._num = 0
        elif not isinstance(cls._num, int):
            raise TypeError(
                f"Type Error: '{cls.__name__}._num' must be an integer, "
                f"got {type(cls._num).__name__}."
            )
        if not hasattr(cls, "_num_lock"):
            cls._num_lock = threading.Lock()
        elif not isinstance(cls._num_lock, LOCK_TYPE):
            raise TypeError(
                f"Type Error: '{cls.__name__}._num_lock' must be a threading.Lock instance, "
                f"got {type(cls._num_lock).__name__}."
            )
        if not hasattr(cls, "_logger_configured"):
            cls._logger_configured = False
        elif not isinstance(cls._logger_configured, bool):
            raise TypeError(
                f"Type Error: '{cls.__name__}._logger_configured' must be a boolean, "
                f"got {type(cls._logger_configured).__name__}."
            )
        if not hasattr(cls, "_logger_configured_lock"):
            cls._logger_configured_lock = threading.Lock()
        elif not isinstance(cls._logger_configured_lock, LOCK_TYPE):
            raise TypeError(
                f"Type Error: '{cls.__name__}._logger_configured_lock' must be a threading.Lock instance, "
                f"got {type(cls._logger_configured_lock).__name__}."
            )

    def __init__(self, url: str, window: Tuple[int, int, int, int] = (None, None, None, None),
                 name: str = None, login_data: Mapping[str, str | None] = None, *args, **kwargs):
        """
        子类必须继承该初始化方法
        url 必须传入
        window 在只使用无头模式时可以不传，建议传入
        name 在不需要自定义任务名时可以不传，建议传入
        login_data 在不需要登陆时不用传，需要登陆时必须传入
        以上参数的具体要求在 _check_*_valid 中

        建议：不需要登陆的子类任务传入前三个参数，需要登陆的子类任务传入前四个参数
        """
        ## 初始化属性
        # 初始化核心属性
        self.__url = url
        self._check_url_valid()
        self.__dr = None
        self.__lock = threading.RLock()
        # 初始化显示属性
        self.__window = window
        self.__display = False
        # 初始化定时属性
        self.__scheduler = None
        self._scheduler_trigger = None # 唯一允许子类修改的属性
        # 初始化登陆属性
        self.__login_data = login_data
        self.__user_data = None
        self.__session_data = None # 唯一运行外部访问的属性
        # 初始化名称
        with self.__class__._num_lock:
            self.__name = f"{self.__class__.__name__}{self.__class__._num}" if name is None else name
            self.__class__._num += 1
        self._check_name_valid()
        # 初始化日志和下载目录
        self.__log_dir = os.path.join(LOG_DIR, self.__class__.__name__)
        os.makedirs(self.__log_dir, exist_ok=True)
        self.__download_dir = os.path.join(self.__log_dir, "download")
        os.makedirs(self.__download_dir, exist_ok=True)
        # 初始化日志文件
        with self.__class__._logger_configured_lock:
            if not self.__class__._logger_configured:
                # 配置 logger，向 logger 中添加一条子类专属的过滤规则
                logger.add(
                    os.path.join(self.__log_dir, f"{self.__class__.__name__}.log"),
                    filter=lambda record: record["extra"].get("class_name") == self.__class__.__name__,
                    rotation="1 MB",
                    encoding="utf-8"
                )
                self.__class__._logger_configured = True
        self.__log = logger.bind(class_name=self.__class__.__name__)
        ## 配置属性
        try:
            self.__display = not all(x is None for x in self.__window)
            if self.__display:
                self._check_window_valid()
            self.__dr = self._init_driver()
            if self.__login_data is not None:
                self._check_login_data_valid()  # 同时更新 user_data or session_data
                self._login_pipe()
            # 使用钩子函数强迫子类调用父类初始化
            self._init_config(*args, **kwargs)
            self._verify_init_config()
        except Exception:
            self.close()
            raise 

    def _check_url_valid(self):
        """
        要求 url 为 str 类型
        且 以 "http://" or "https://" 开头
        """
        if not isinstance(self.__url, str):
            raise TypeError("Invalid url")
        if not self.__url.startswith(("http://", "https://", "file:///")):
            raise ValueError("Invalid url")

    def _check_window_valid(self):
        """
        要求 window 为 int四元组 (x_p, y_p, x_s, y_s) 类型
        且不能超出屏幕分辨率
        且不能与已有窗口重叠
        """
        if (not isinstance(self.__window, tuple) or len(self.__window) != 4 or
                not all(isinstance(i, int) for i in self.__window)):
            logger.critical(f"{self.__name} with invalid window: window must "
                            f"be a tuple of 4 ints (x_p, y_p, x_s, y_s) !!!")
            raise TypeError("Invalid window")
        screen_w, screen_h = get_screen_resolution()
        if not (0 <= self.__window[0] <= screen_w - self.__window[2] and
                0 <= self.__window[1] <= screen_h - self.__window[3]):
            logger.critical(f"{self.__name} with invalid window: window must "
                            f"fit within the screen resolution ({screen_w}, {screen_h}) !!!")
            raise ValueError("Invalid window")
        with TASK.__windows_lock:
            for win in TASK.__windows:
                if not (self.__window[0] + self.__window[2] <= win[0] or self.__window[0] >= win[0] + win[2] or
                        self.__window[1] + self.__window[3] <= win[1] or self.__window[1] >= win[1] + win[3]):
                    logger.critical(f"{self.__name} with invalid window: window overlaps with window {win} !!!")
                    raise ValueError("Invalid window")
            TASK.__windows.append(self.__window)
        logger.success(f"{self.__name} with valid window {self.__window} !!!")

    def _check_name_valid(self):
        """
        要求 name 可以强制转换为 str 类型
        """
        try:
            self.__name = str(self.__name)
        except Exception as e:
            raise TypeError("Invalid name")

    def _check_login_data_valid(self):
        """
        要求 login_data 为 Mapping[str, str] 类型
        且 keys 中必须包含 {'username', 'password'} or {'cookies', 'localStorage', 'sessionStorage', 'url'}
        """
        if not isinstance(self.__login_data, Mapping):
            raise TypeError("Invalid login_data")
        user_keys = {'username', 'password'}
        if user_keys.issubset(self.__login_data.keys()):
            self.__user_data = {k: self.__login_data[k] for k in user_keys}
            self._check_user_data_valid()
        else:
            session_keys = {'cookies', 'localStorage', 'sessionStorage', 'url'}
            if session_keys.issubset(self.__login_data.keys()):
                self.__session_data = {k: self.__login_data[k] for k in session_keys}
                self._check_session_data_valid()
            else:
                raise ValueError("Invalid login_data")

    def _check_user_data_valid(self):
        """
        要求 username 和 password 为 str 类型
        且长度大于 0
        """
        username = self.__user_data['username']
        password = self.__user_data['password']
        if not isinstance(username, str):
            raise TypeError("Invalid username")
        if len(username) <= 0 :
            raise ValueError("Invalid username")
        if not isinstance(password, str):
            raise TypeError("Invalid password")
        if len(password) <= 0 :
            raise ValueError("Invalid password")

    def _check_session_data_valid(self):
        """
        要求 cookies 为 list 类型
        """
        if not isinstance(self.__login_data['cookies'], list):
            raise TypeError("Invalid cookies")

    # 初始化驱动方法
    def _init_driver(self):
        """初始化驱动"""
        try:
            logger.info(f'{self.__name} is initializing driver ...')
            def _set_option(option, chrome_path=None):
                """设置通用驱动选项"""
                # 指定 chrome 浏览器路径
                if chrome_path:
                    option.binary_location = chrome_path
                # 提高页面加载速度，减少等待时间
                option.page_load_strategy = "eager"
                # 无头模式
                if not self.__display:
                    option.add_argument("--headless=new")  # chrome 109+ 的无头模式
                    option.add_argument('--window-size=1920,1080')  # 设置无头模式下的窗口大小
                # 提高 Linux 下兼容性
                option.add_argument("--no-sandbox")  # 禁用沙盒
                option.add_argument("--disable-dev-shm-usage")  # 禁用共享内存
                option.add_argument("--disable-gpu") # 禁用显卡硬件加速
                option.add_argument("--disable-blink-features=AutomationControlled") # 添加反检测参数
                return option
            try:
                # 优先尝试使用 undetected_chromedriver
                logger.info(f'{self.__name} is trying use undetected_chromedriver ...')
                # raise ValueError
                opt = uc.ChromeOptions()
                opt = _set_option(opt)
                # 直接让 undetected_chromedriver 自动适配 Chrome 浏览器版本
                driver = uc.Chrome(options=opt, version_main=int(CHROME_VERSION.split(".")[0]))
            except Exception as e:
                # undetected_chromedriver 失败后降级使用 webdriver (本地)
                logger.warning(f'{self.__name} failed use undetected_chromedriver \n[{e}]')
                logger.info(f'{self.__name} is trying use local webdriver ...')
                opt = Options()
                chrome_path, driver_path = chrome_driver_downloading(CHROME_VERSION_TESTING, CORE_DIR)
                opt = _set_option(opt, chrome_path)
                service = Service(executable_path=driver_path)
                driver = webdriver.Chrome(options=opt, service=service)
            driver.get(self.__url)
            time.sleep(0.1)
            driver.implicitly_wait(3)
            if self.__display:
                # 设置窗口位置等会儿大小
                driver.set_window_position(self.__window[0], self.__window[1])
                driver.set_window_size(self.__window[2], self.__window[3])
            logger.success(f'{self.__name} successfully initialize driver !!!')
            return driver
        except Exception:
            logger.opt(exception=True).critical(f'{self.__name} failed initialize driver !!!')
            raise RuntimeError(f"Failed initialize driver")

    # 登陆方法
    def _login_pipe(self):
        """
        根据 login_data (user_data, session_data) 来确定是否登陆以及登录方式
        """
        try:
            logger.info(f'{self.__name} is trying login ...')
            if self.__user_data is not None:
                self._login()
                logger.success(f'{self.__name} successfully login (using user data) !!!')
                # 登陆成功后尝试记录 session_data
                try:
                    logger.info(f'{self.__name} is trying save session data ...')
                    time.sleep(1)  # 等待登录后页面加载完成，确保 Set-Cookie 已到达浏览器
                    hostname = urlparse(self.__dr.current_url).hostname
                    all_cookies = self.__dr.execute_cdp_cmd('Network.getAllCookies', {})
                    target_cookies = [c for c in all_cookies['cookies']
                                      if not c.get('domain')
                                      or c.get('domain') == hostname
                                      or (c['domain'].startswith('.')
                                          and hostname.endswith(c['domain']))]
                    self.__session_data = {
                        'cookies': target_cookies,
                        'localStorage': self.__dr.execute_script("return JSON.stringify(window.localStorage);"),
                        'sessionStorage': self.__dr.execute_script("return JSON.stringify(window.sessionStorage);"),
                        'url': self.__dr.current_url,
                    }
                    logger.success(f'{self.__name} successfully save session data !!!')
                except Exception:
                    logger.warning(f'{self.__name} failed save session data')
            elif self.__session_data is not None:
                logger.info(f'{self.__name} is injecting session data ...')
                self.__dr.get(self.__session_data['url'])  # 注入前需要重定向
                time.sleep(0.1)
                self._inject()
                logger.success(f'{self.__name} successfully inject session data !!!')
                self._after_inject()
                logger.success(f'{self.__name} successfully login (using session data) !!!')
            time.sleep(1)
        except Exception:
            logger.opt(exception=True).critical(f'{self.__name} failed to login !!!')
            raise RuntimeError(f"Failed to login")

    @abstractmethod
    def _login(self):
        """
        子类实现 login 逻辑，根据字典 self.__user_data 中 {'username', 'password'} 这两个字段值
        """
        return self.__user_data["username"], self.__user_data["password"]

    def _inject(self):
        """
        注入会话数据（通过 CDP 注入，可处理 httpOnly cookie）
        """
        cookies_to_set = []
        for c in self.__session_data['cookies']:
            cookie = {k: v for k, v in c.items()
                      if k in ('name', 'value', 'domain', 'path', 'secure', 'httpOnly', 'sameSite')}
            expires = c.get('expires')
            if expires and expires > 0:
                cookie['expires'] = int(expires)
            if not cookie.get('domain'):
                cookie.pop('domain', None)
                cookie['url'] = self.__session_data['url']
            cookies_to_set.append(cookie)
        if cookies_to_set:
            self.__dr.execute_cdp_cmd('Network.setCookies', {'cookies': cookies_to_set})
        if self.__session_data['localStorage'] != '{}':
            self.__dr.execute_script("const d = JSON.parse(arguments[0]);"
                                  "for (const [k, v] of Object.entries(d)) localStorage.setItem(k, v);",
                                  self.__session_data['localStorage'])
        if self.__session_data['sessionStorage'] != '{}':
            self.__dr.execute_script("const d = JSON.parse(arguments[0]);"
                                  "for (const [k, v] of Object.entries(d)) sessionStorage.setItem(k, v);",
                                  self.__session_data['sessionStorage'])
        self.__dr.refresh()

    @abstractmethod
    def _after_inject(self):
        """有时 inject 后还需一些操作才能和 login 后的页面一致，需按照子类实际情况实现"""
        pass

    @abstractmethod
    def _init_config(self, *args, **kwargs):
        """子类额外初始化，需要在子类中实现"""
        pass

    def _verify_init_config(self):
        """校验子类额外初始化中是否进行必要配置"""
        pass

    # ==========================================================================================
    # 运行阶段：过程中的异常捕获但不抛出并记录 erro 或 warning 级别 log 到各子类对应的 .log 中
    # ==========================================================================================
    # 核心运行方法
    def run(self, *args, **kwargs):
        """
        非定时模式：run 直接执行业务代码

        定时模式：run 会向当前 self.__scheduler 添加业务代码的定时任务
        定时详情由 self._scheduler_trigger 决定
        可通过 set_scheduler 来更改

        注意：一个实例只能拥有一个定时任务，因为多个定时任务可能会产生竞争，所以需要 id 和 replace
        """
        with self.__lock:
            if self.__scheduler is None:
                # 非定时模式
                self._run_pipe(*args, **kwargs)
            else:
                # 定时模式
                try:
                    if self.__scheduler.running:
                        self.__log.warning(f'{self.__name} has already been run, '
                                           f'you can set scheduler again to run again')
                        raise RuntimeError(f'Repeat Run')
                    self.__log.info(f"{self.__name} is setting run job with trigger "
                                   f"{str(self._scheduler_trigger)} ...")
                    self.__scheduler.add_job(self._run_pipe, self._scheduler_trigger,
                                             max_instances=1, args=args, kwargs=kwargs)
                    self.__log.success(f"{self.__name} successfully set run job with trigger "
                                      f"{str(self._scheduler_trigger)} !!!")
                    self.__scheduler.start()
                except Exception:
                    self.__log.exception(f"{self.__name} failed set run job with trigger "
                                        f"{str(self._scheduler_trigger)}  !!!")

    def _run_pipe(self, *args, **kwargs):
        try:
            self.__log.info(f'{self.__name} is runnig ...')
            start_time = time.time()
            start_time_str = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime())
            self._execute(*args, **kwargs)
            end_time = time.time()
            time_cost = round(end_time - start_time, 4)
            self.__log.success(f'{self.__name} successfully run !!! '
                               f'[start: {start_time_str} | cost: {time_cost}s]')
        except Exception:
            self.__log.exception(f'{self.__name} failed run !!!')

    @abstractmethod
    def _execute(self, *args, **kwargs):
        """
        业务代码，需要在子类中实现
        """
        pass

    # 设置定时方法
    def set_scheduler(self, type: str = None, *args, **kwargs):
        """
        设置 apscheduler
        """
        with self.__lock:
            if isinstance(self.__scheduler, BaseScheduler):
                # 清除之前设置的 scheduler
                self.__log.info(f"{self.__name} is clearing setted scheduler ...")
                self.__scheduler.shutdown(wait=True)
                self.__scheduler = None
                self._scheduler_trigger = None
                self.__log.success(f"{self.__name} successfully clear setted scheduler !!!")
            if type is None:
                return

            type_list = ["blocking", "background"]
            if not isinstance(type, str) or type not in type_list:
                self.__log.error(f"{self.__name} failed set scheduler: type must be one of {type_list} !!!")
                return
            if type == "blocking":
                self.__scheduler = BlockingScheduler()
            if type == "background":
                self.__scheduler = BackgroundScheduler()

            self._set_scheduler_trigger(*args, **kwargs)
            if not isinstance(self._scheduler_trigger, BaseTrigger):
                next_second = (datetime.now() + timedelta(seconds=1)).strftime("%H:%M:%S")
                time_parts = next_second.split(':')
                hour, minute, second = map(int, time_parts)
                self._scheduler_trigger = CronTrigger(hour=hour, minute=minute, second=second)
                self.__log.warning(f"{self.__name} find scheduler trigger is not "
                                  f"apscheduler.BaseTrigger when setting trigger: "
                                  f"using default trigger {str(self._scheduler_trigger)} instead")

            self.__log.success(f"{self.__name} successfully set scheduler with triggerr "
                               f"{str(self._scheduler_trigger)} !!!")

    @abstractmethod
    def _set_scheduler_trigger(self, *args, **kwargs):
        """
        设置 apscheduler 的 trigger，因不同业务定时需求不同，需要在子类中实现
        """
        pass

    # 关闭方法
    def close(self):
        with self.__lock:
            self.__log.info(f"{self.__name} is closing ...")
            if self.__scheduler is not None:
                self.__scheduler.shutdown(wait=True)
                self.__scheduler = None
            if self.__display and self.__window in TASK.__windows:
                with TASK.__windows_lock:
                    TASK.__windows.remove(self.__window)
            if self.__dr is not None:
                self.__dr.quit()
                self.__dr = None

    # ==========================================================================================
    # 子类复用工具方法：包括常规元素操作方法(操作元素前需要先确保元素可见且可交互) 和 截屏方法
    # ==========================================================================================
    # 常规元素操作方法
    def _ensure_element_visible(self, element):
        """滚动到元素可见，不改变窗口状态"""
        try:
            self.__dr.execute_script("window.focus();")  # 确保窗口获得焦点，避免滚动失效
        except:
            pass
        self.__dr.execute_script(
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
                self.__dr.execute_script("arguments[0].click();", element)
            except Exception as e:
                raise RuntimeError(f"Failed to click element: {e}")

    def _safe_send_text(self, element, text):
        """安全的输入文本操作"""
        self._ensure_element_visible(element)
        try:
            # 先点击元素获得焦点
            try:
                element.click()
            except:
                self.__dr.execute_script("arguments[0].click();", element)
            # 清空原有内容
            element.clear()
            # 输入文本
            element.send_keys(text)
        except:
            # 如果普通输入文本失败，用JS设置值
            try:
                self.__dr.execute_script(f"arguments[0].value = '{text}';", element)
            except Exception as e:
                raise RuntimeError(f"Failed to send text to element: {e}")

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
        except Exception as e:
            raise RuntimeError(f"Failed to select option: {e}")

    def _safe_download(self, element, download_path, timeout=60):
        """安全的下载操作，点击元素后等待下载完成"""
        self._ensure_element_visible(element)
        try:
            # 通过 CDP 强制接管下载，确保下载路径设置生效
            self.__dr.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': download_path
            })
            element.click()
            wait_for_download(download_path, timeout)
        except Exception as e:
            raise RuntimeError(f"Failed to download file: {e}")

    # 截屏方法
    def _shot(self, max_nums=100):
        folder_path = f"{self.__log_dir}/{self.__class__.__name__}_ScreenShot"
        os.makedirs(folder_path, exist_ok=True)
        now = time.strftime("%Y%m%d%H%M%S", time.localtime())
        tag = f"{self.__name}_" + now
        file_path = os.path.join(folder_path, f"{tag}.png")
        self.__dr.get_screenshot_as_file(file_path)
        auto_del('f', folder_path, max_nums)

    def __del__(self):
        pass
