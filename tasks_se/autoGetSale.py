import os
import time
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
import pandas as pd

from tasks_se.core.task import TASK


# AUTOGETSALE 是通过银豹系统获得某时间段每天的营业数据的任务
class AUTOGETSALE(TASK):
    AutoGetSaleNums = 0
    _lock = threading.Lock()

    def __init__(self, x_p, y_p, x_s, y_s, u, user_name, password, name=None):
        super().__init__(x_p, y_p, x_s, y_s, u)
        if name is None:
            self.name = f"AUTOGETSALE{AUTOGETSALE.AutoGetSaleNums}"
        else:
            self.name = name
        self.type = "AutoGetSale"
        self.period = time.strftime("%Y-%m-%d~%Y-%m-%d", time.localtime())
        self.user_name = user_name
        self.password = password
        self.result = None
        try:
            self.dr = self._init_driver()
        except Exception as e:
            raise RuntimeError(f'驱动初始化失败: {e}')
        with AUTOGETSALE._lock:
            AUTOGETSALE.AutoGetSaleNums += 1

    # 根据 user_name 和 password 登录
    def login(self):
        u_bt = self.dr.find_element(By.XPATH, '//*[@id="txt_userName"]')
        p_bt = self.dr.find_element(By.XPATH, '//*[@id="txt_password"]')
        s_bt = self.dr.find_element(By.XPATH, '//*[@id="submitLoginBtn"]')
        u_bt.send_keys(self.user_name)
        p_bt.send_keys(self.password)
        s_bt.click()

    # 手动设置想获取数据的时间段
    def set_period(self, period: str = ''):
        try:
            start_str, end_str = period.split('~')
            datetime.strptime(start_str, "%Y-%m-%d")
            datetime.strptime(end_str, "%Y-%m-%d")
        except ValueError:
            print("手动设置时间段失败！")
            return
        if start_str and end_str:
            self.period = period
        return

    # 爬取某天银豹每天的销售额（产品/服务）和单数 [后续可根据需求改变该函数]
    def filter_data(self) -> pd.DataFrame:
        sale_info = self.dr.find_element(By.XPATH, '//*[@id="mainTable"]/tbody/tr[1]/td[2]/div')
        total_sale = sale_info.find_element(By.XPATH, './span[1]').text
        sale_comp = sale_info.get_attribute('textContent').split(')')[0].split('(')[1].split("; ")
        sale_prod, sale_ser = [i.split(' ')[1] for i in sale_comp]
        sale_num = sale_info.find_element(By.XPATH, './span[4]').text
        df = pd.DataFrame([sale_prod, sale_ser, total_sale, sale_num]).T
        df.columns = ['产品销售额', '服务销售额', '总销售额', '单数']
        return df

    # 爬取银豹某时间段每天的数据
    def get_data(self):
        # 获取起始与结束时间
        print(self.period)
        start_str, end_str = self.period.split('~')
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
        # 获取选择时间的按钮
        WebDriverWait(self.dr, 30).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "loadingBg"))
        )
        start_bt = self.dr.find_element(By.XPATH, '//*[@id="dateTimeRangeBox"]/input[1]')
        end_bt = self.dr.find_element(By.XPATH, '//*[@id="dateTimeRangeBox"]/input[2]')
        searching_bt = self.dr.find_element(
            By.XPATH, '//*[@id="dateTimeRangeBox"]/following-sibling::div[@class="submitBtn"][1]')

        data_list = []
        current_date = start_date
        year_lag, month_lag, day_lag = None, None, None
        while current_date <= end_date:
            current_str = current_date.strftime("%Y-%m-%d")
            year, month, day = current_str.split('-')
            # 模拟点击来选择时间段中的每一天
            for i in range(2):
                # 点击起始或结束时间按钮
                if i == 0:
                    start_bt.click()
                else:
                    end_bt.click()
                # 点击改年份
                if year != year_lag:
                    year_sel = self.dr.find_element(By.XPATH, '//*[@id="ui-datepicker-div"]/div[1]/div/select[1]')
                    Select(year_sel).select_by_visible_text(f"{year}")
                # 点击改月份
                if month != month_lag:
                    mon_sel = self.dr.find_element(By.XPATH, '//*[@id="ui-datepicker-div"]/div[1]/div/select[2]')
                    Select(mon_sel).select_by_visible_text(f"{month}")
                day_op = self.dr.find_element(
                    By.XPATH, f'//*[@id="ui-datepicker-div"]/table/tbody/tr/td/a[text()="{int(day)}"]')
                day_op.click()
            searching_bt.click()
            WebDriverWait(self.dr, 30).until(
                EC.invisibility_of_element_located((By.CLASS_NAME, "loadingBg"))
            )
            df_daily = self.filter_data()
            df_daily['日期'] = current_date
            data_list.append(df_daily)
            year_lag, month_lag = year, month
            current_date = current_date + timedelta(days=1)
        df = pd.concat(data_list, ignore_index=True)
        df[['产品销售额', '服务销售额', '总销售额']] = df[['产品销售额', '服务销售额', '总销售额']].astype(float)
        df['单数'] = df['单数'].astype(int)
        df['日期'] = df['日期'].astype(str)
        df = df.set_index('日期')
        self.result = df

    # 运行自动化任务
    def run(self):
        self.dr.refresh()
        self.login()
        time.sleep(1)
        start_time = time.time()
        start_time_str = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime())
        self.get_data()
        end_time = time.time()
        time_cost = end_time - start_time
        print(f"开始：{start_time_str} 用时：{time_cost}")
        self.log()
        # time.sleep(1000)
        self.dr.quit()

    def __del__(self):
        super().__del__()


## AUTOGETSALE测试
if __name__ == '__main__':
    from dotenv import load_dotenv
    url = "https://beta33.pospal.cn/Report/BusinessSummaryV2"
    name = "demo"
    load_dotenv()
    un = os.getenv("POSPAL_USERNAME")
    p = os.getenv("POSPAL_PASSWORD")
    s = AUTOGETSALE(0, 0, 2560, 1440, url, un, p, "demo")
    s.set_period("2025-6-1~2025-6-3")
    s.run()
    print(s.result)
