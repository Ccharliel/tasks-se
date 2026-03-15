import os
import time
from selenium.common.exceptions import ElementNotInteractableException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
from loguru import logger

from tasks_se.core.task import TASK


# SIMULATEOP 是希施玛证券模拟平台进行操作的任务
class SIMULATEOP(TASK):
    Num = 0
    _num_lock = threading.Lock()

    def __init__(self, cate, race, u=None, username=None, pwd=None, shared_dr=None,
                 x_p=0, y_p=0, x_s=1, y_s=1, name=None):
        super().__init__(u, x_p, y_p, x_s, y_s)
        logger.add(f"{self.log_dir}/{self.class_name}.log", rotation="1 MB",
                   filter=lambda r: r["file"].name == f"{os.path.basename(__file__)}")
        self.category = cate
        self.race = race
        self.pos = SIMULATEOP.Num
        self.name = f"{self.class_name}{SIMULATEOP.Num}" if name is None else name
        if_share = not (u or username or pwd)
        if if_share:
            if shared_dr is None:
                raise ValueError("NO SHARED DRIVER")
            self.dr = self._init_driver(shared_dr)
        else:
            if not u:
                raise ValueError("NO URL")
            if not (username and pwd):
                raise ValueError("NO USER INFO")
            self.username = username
            self.pwd = pwd
            self.dr = self._init_driver()
            time.sleep(4)
            self._login()
        time.sleep(1)
        self._switch_race()
        time.sleep(1)
        self._find_category()
        time.sleep(1)
        with SIMULATEOP._num_lock:
            SIMULATEOP.Num += 1

    def _login(self):
        try:
            entry = self.dr.find_element(By.XPATH, "//span[@class='bannerbtn btn2' and text()='点击进入大赛']")
            self._safe_click(entry)
            username_blank = self.dr.find_element(By.XPATH, "//input[@name='password']")
            self._safe_send_keys(username_blank, self.username)
            pwd_blank = self.dr.find_element(By.XPATH, "//input[@name='pwd1']")
            self._safe_send_keys(pwd_blank, self.pwd)
            login = (
                self.dr.find_element(By.XPATH, "//span[text()='登录']"))
            self._safe_click(login)
            time.sleep(5)
            windows = self.dr.window_handles
            # 关闭登录页（第一个标签页）
            self.dr.switch_to.window(windows[0])
            self.dr.close()
            # 切换到新标签页（最后一个）
            self.dr.switch_to.window(windows[-1])
        except Exception as e:
            logger.critical(f"{self.name} failed to login !!!\n[{e}]")
            raise RuntimeError("Login failed")

    def _switch_race(self):
        try:
            person_bt = self.dr.find_element(By.XPATH,
                                             "//*[@id='content-menu']//span[contains(text(), '个人中心')]/../..")
            if "is-opened" not in person_bt.get_attribute("class"):
                person_bt.click()
            race_bt = self.dr.find_element(By.XPATH, f"//span[@class='pr' and contains(text(), '我的大赛')]/..")
            race_bt.click()
            race_page = self.dr.find_element(By.XPATH,
                                             f"//span[@class='title title-cu' and contains(text(), '{self.race}')]/..")
            race_bt = race_page.find_element(By.ID, "changeMatchBtn")
            race_bt.click()
        except Exception as e:
            logger.critical(f"{self.name} failed to switch race !!!\n[{e}]")
            raise RuntimeError("Switch race failed")

    def _find_category(self):
        try:
            market_bt = self.dr.find_element(By.XPATH,
                                             "//*[@id='content-menu']//span[contains(text(), '沪深京市场')]/../..")
            if "is-opened" not in market_bt.get_attribute("class"):
                market_bt.click()
            category_bt = self.dr.find_element(By.XPATH,
                                               f"//span[@class='pr' and contains(text(), '{self.category}')]/..")
            category_bt.click()
        except Exception as e:
            logger.critical(f"{self.name} failed to find category !!!\n[{e}]")
            raise RuntimeError("Find category failed")

    def find_balance(self):
        try:
            balance_text = self.dr.find_element(By.XPATH, "//*[@id='pane-capitalInfo']/div/table/tr[2]/td[3]").text
            return balance_text
        except Exception as e:
            logger.warning(f"{self.name} failed to find balance !!!\n[{e}]")

    def operate(self, code, op, amount):
        try:
            WebDriverWait(self.dr, 30).until(
                EC.invisibility_of_element_located((By.CLASS_NAME, "el-dialog__wrapper"))
            )
            # 确定操作对象
            code_blank = self.dr.find_element(By.XPATH, "//span[@class='txt' and contains(text(), '代码')]/..//input")
            self._safe_send_keys(code_blank, Keys.CONTROL + "a")
            self._safe_send_keys(code_blank, Keys.DELETE)
            self._safe_send_keys(code_blank, code)
            self._safe_send_keys(code_blank, Keys.RETURN)
            # 确定操作方向
            op_bt = None
            op_selection = self.dr.find_element(By.XPATH, "//span[@class='txt' and contains(text(), '买卖方向')]")
            if op == 'buy':
                op_bt = WebDriverWait(self.dr, 30).until(
                    EC.presence_of_element_located((By.XPATH, "//label[@value='1']/span")))
            elif op == 'sell':
                op_bt = WebDriverWait(self.dr, 30).until(
                    EC.presence_of_element_located((By.XPATH, "//label[@value='2']/span")))
            self.dr.execute_script("arguments[0].click();", op_bt)
            # 确定操作数量
            amount_blank = self.dr.find_element(By.XPATH,
                                                "//span[@class='txt' and contains(text(), '委托数量')]/..//input")
            self._safe_send_keys(amount_blank, Keys.CONTROL + "a")
            self._safe_send_keys(amount_blank, Keys.DELETE)
            self._safe_send_keys(amount_blank, amount)
            # 下单
            confirm_bt = WebDriverWait(self.dr, 30).until(
                EC.presence_of_element_located((By.XPATH, "//span[text()='下单']/..")))
            self._safe_click(confirm_bt)
        except Exception as e:
            logger.warning(f"{self.name} failed to operate !!!\n[{e}]")
            raise RuntimeError("Operate failed")

    def switch_to_page(self):
        windows = self.dr.window_handles
        self.dr.switch_to.window(windows[self.pos])

    def run(self, code=None, op='sell', amount=10):
        try:
            start_time = time.time()
            start_time_str = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime())
            self.switch_to_page()
            self.operate(code, op, amount)
            end_time = time.time()
            time_cost = end_time - start_time
            logger.success(f'{self.name} successfully run !!! [start:{start_time_str} | cost:{time_cost}s]')
        except Exception as e:
            logger.critical(f'{self.name} failed to run !!!\n[{e}]')

    def __del__(self):
        super().__del__()


if __name__ == '__main__':
    from dotenv import load_dotenv

    load_dotenv()
    USERNAME = os.getenv("CSMAR_USERNAME")
    PWD = os.getenv("CSMAR_PASSWORD")
    CATEGORY0 = "债券"
    CATEGORY1 = "沪深A股"
    CODE_list_bond = ["131810", "204001"]
    CODE_list_index = ["000001", "000002"]
    URL = "https://vetp.csmar.com"
    RACE0 = "实训综合大赛"
    s0 = SIMULATEOP(CATEGORY0, RACE0, u=URL, username=USERNAME, pwd=PWD, x_p=0, y_p=0, x_s=1920, y_s=1080)
    # balance = s0.find_balance()
    # print(balance)
    for CODE in CODE_list_bond:
        s0.run(CODE)
    RACE1 = "实训综合大赛"
    s1 = SIMULATEOP(CATEGORY1, RACE1, shared_dr=s0.dr, x_p=1920, y_p=0, x_s=1920, y_s=1080)
    for CODE in CODE_list_index:
        s1.run(CODE)
    time.sleep(100000)
