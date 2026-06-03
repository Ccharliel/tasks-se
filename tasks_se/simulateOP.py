import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tasks_se.core.task import TASK


# SIMULATEOP 是希施玛证券模拟平台进行操作的任务
class SIMULATEOP(TASK):
    def __init__(self, url, login_data, cate, race, window=(None, None, None, None), name=None):
        super().__init__(url, window, name, login_data, cate=cate, race=race)

    def _init_config(self, cate, race):
        self._cate = cate
        self._race = race
        windows = self._dr.window_handles
        self._dr.switch_to.window(windows[0])
        self._dr.close()
        self._dr.switch_to.window(windows[-1])
        self._switch_race()
        time.sleep(1)
        self._find_category()

    def _login(self):
        username, password = super()._login()
        entry = self._dr.find_element(By.XPATH, "//span[@class='bannerbtn btn2' and text()='点击进入大赛']")
        self._safe_click(entry)
        username_blank = self._dr.find_element(By.XPATH, "//input[@name='password']")
        self._safe_send_text(username_blank, username)
        password_blank = self._dr.find_element(By.XPATH, "//input[@name='pwd1']")
        self._safe_send_text(password_blank, password)
        login = self._dr.find_element(By.XPATH, "//span[text()='登录']")
        self._safe_click(login)

    def _after_inject(self):
        entry = self._dr.find_element(By.XPATH, "//span[@class='bannerbtn btn2' and text()='点击进入大赛']")
        self._safe_click(entry)

    def _set_scheduler_trigger(self, *args, **kwargs):
        pass

    def _switch_race(self):
        try:
            person_bt = self._dr.find_element(By.XPATH,
                                              "//*[@id='content-menu']//span[contains(text(), '个人中心')]/../..")
            if "is-opened" not in person_bt.get_attribute("class"):
                person_bt.click()
            race_bt = self._dr.find_element(By.XPATH, f"//span[@class='pr' and contains(text(), '我的大赛')]/..")
            race_bt.click()
            race_page = self._dr.find_element(By.XPATH,
                                              f"//span[@class='title title-cu' and contains(text(), '{self._race}')]/..")
            race_bt = race_page.find_element(By.ID, "changeMatchBtn")
            race_bt.click()
        except Exception as e:
            self._log.critical(f"{self._name} failed to switch race !!!\n[{e}]")
            raise RuntimeError("Switch race failed")

    def _find_category(self):
        try:
            market_bt = self._dr.find_element(By.XPATH,
                                              "//*[@id='content-menu']//span[contains(text(), '沪深京市场')]/../..")
            if "is-opened" not in market_bt.get_attribute("class"):
                market_bt.click()
            category_bt = self._dr.find_element(By.XPATH,
                                                f"//span[@class='pr' and contains(text(), '{self._cate}')]/..")
            category_bt.click()
        except Exception as e:
            self._log.critical(f"{self._name} failed to find category !!!\n[{e}]")
            raise RuntimeError("Find category failed")

    def find_balance(self):
        self._log.info(f"{self._name} is searching balance ...")
        try:
            balance_text = self._dr.find_element(By.XPATH, "//*[@id='pane-capitalInfo']/div/table/tr[2]/td[3]").text
            return balance_text
        except Exception as e:
            self._log.warning(f"{self._name} failed to find balance !!!\n[{e}]")

    def _execute(self, code=None, op='sell', amount=10):
        WebDriverWait(self._dr, 30).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "el-dialog__wrapper"))
        )
        # 确定操作对象
        code_blank = self._dr.find_element(By.XPATH, "//span[@class='txt' and contains(text(), '代码')]/..//input")
        code_blank.send_keys(Keys.CONTROL + "a")
        code_blank.send_keys(Keys.DELETE)
        self._safe_send_text(code_blank, code)
        code_blank.send_keys(Keys.RETURN)
        # 确定操作方向
        op_bt = None
        if op == 'buy':
            op_bt = WebDriverWait(self._dr, 30).until(
                EC.presence_of_element_located((By.XPATH, "//label[@value='1']/span")))
        elif op == 'sell':
            op_bt = WebDriverWait(self._dr, 30).until(
                EC.presence_of_element_located((By.XPATH, "//label[@value='2']/span")))
        self._dr.execute_script("arguments[0].click();", op_bt)
        # 确定操作数量
        amount_blank = self._dr.find_element(By.XPATH,
                                             "//span[@class='txt' and contains(text(), '委托数量')]/..//input")
        amount_blank.send_keys(Keys.CONTROL + "a")
        amount_blank.send_keys(Keys.DELETE)
        self._safe_send_text(amount_blank, amount)
        # 下单
        confirm_bt = WebDriverWait(self._dr, 30).until(
            EC.presence_of_element_located((By.XPATH, "//span[text()='下单']/..")))
        self._safe_click(confirm_bt)


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
    RACE = "实训综合大赛"

    U_D = {"username": USERNAME, "password": PWD}
    s0 = SIMULATEOP(URL, U_D, CATEGORY0, RACE, window=(0, 0, 1440, 900))
    # balance = s0.find_balance()
    # print(f"balance: {balance}")
    # for CODE in CODE_list_bond:
    #     s0.run(code=CODE)
    s0.close()

    s1 = SIMULATEOP(URL, s0.session_data, CATEGORY1, RACE, window=(0, 0, 1440, 900))
    for CODE in CODE_list_index:
        s1.run(code=CODE)

    s1.close()

