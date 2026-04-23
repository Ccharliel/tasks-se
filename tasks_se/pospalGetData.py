import os
import time
from datetime import datetime, timedelta
from selenium.common import ElementNotInteractableException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import create_engine

from tasks_se.core.task import TASK


# POSPALGETDATA 是通过银豹系统获得某时间段每天的营业数据的任务
class POSPALGETDATA(TASK):
    Num = 0
    _num_lock = threading.Lock()

    def __init__(self, u, user_name, password, display=False, cover=None, name=None):
        super().__init__(u, display)
        logger.add(f"{self.log_dir}/{self.class_name}.log", rotation="1 MB",
                   filter=lambda re: re["file"].name == f"{os.path.basename(__file__)}")
        self.user_name = user_name
        self.password = password
        t = time.localtime()
        self.__period = time.strftime("%Y-%m-%d~%Y-%m-%d", t)
        self.__start_date = datetime(*t[:3])
        self.__end_date = datetime(*t[:3])
        self.result = pd.DataFrame()
        self.name = f"{self.class_name}{POSPALGETDATA.Num}" if name is None else name
        if self.display:
            self._check_cover_valid(cover)
            self.x_p = cover[0]
            self.y_p = cover[1]
            self.x_s = cover[2]
            self.y_s = cover[3]
        self.dr = self._init_driver()
        with POSPALGETDATA._num_lock:
            POSPALGETDATA.Num += 1

    # 只能通过 set_period 修改 self.__period, self.__start_date, self.__end_date
    @property
    def period(self):
        """获取 period (只读)"""
        return self.__period
    
    @property
    def start_date(self):
        """获取 start_date (只读)"""
        return self.__start_date

    @property
    def end_date(self):
        """获取 end_date (只读)"""
        return self.__end_date

    # 根据 user_name 和 password 登录
    def _login(self):
        u_bt = self.dr.find_element(By.XPATH, '//*[@id="txt_userName"]')
        p_bt = self.dr.find_element(By.XPATH, '//*[@id="txt_password"]')
        s_bt = self.dr.find_element(By.XPATH, '//*[@id="submitLoginBtn"]')
        self._safe_send_text(u_bt, self.user_name)
        self._safe_send_text(p_bt, self.password)
        self._safe_click(s_bt)

    # 爬取银豹每天的数据
    def _get_data_daily(self, date, type, verbose) -> pd.DataFrame:
        df = pd.DataFrame()
        if type == "sale":
            if verbose:
                download_btn = self.dr.find_element(By.XPATH, '//*[@id="btnExport"]')
                download_path = os.path.join(self.download_dir, type, datetime.strftime(date, "%Y-%m-%d"))
                self._safe_download(download_btn, download_path)
                files = [f for f in os.listdir(download_path) if f.endswith('.xlsx')]
                latest_file = max([os.path.join(download_path, f) for f in files], key=os.path.getctime)
                df = pd.read_excel(latest_file, engine='calamine')
                return df
            else:
                # 数据包括：销售额（产品 / 服务）
                sale_info = self.dr.find_element(By.XPATH, '//*[@id="mainTable"]/tbody/tr[1]/td[2]/div')
                total_sale = sale_info.find_element(By.XPATH, './span[1]').text
                sale_comp = sale_info.get_attribute('textContent').split(')')[0].split('(')[1].split("; ")
                sale_prod, sale_ser = [i.split(' ')[1] for i in sale_comp]
                df = pd.DataFrame([sale_prod, sale_ser, total_sale]).T
                df.columns = ['产品销售额', '服务销售额', '总销售额']
                df[['产品销售额', '服务销售额', '总销售额']] = df[['产品销售额', '服务销售额', '总销售额']].astype(float)
                sale_num = sale_info.find_element(By.XPATH, './span[4]').text
                df["单数"] = sale_num
                df['单数'] = df['单数'].astype(int)
        df['日期'] = date
        df['日期'] = df['日期'].astype(str)
        df = df.set_index('日期')
        return df

    def _switch_page(self, type, verbose):
        if type == "sale":
            if verbose:
                self.dr.get(f"{self.u}/Report/ProductSaleDetails")
            else:
                self.dr.get(f"{self.u}/Report/BusinessSummaryV2")

    def _get_data(self, type, verbose):
        logger.info(f"{self.name} is getting {self.__period} {type} data ...")
        ## 查询操作
        # 按照查询数据种类切换页面
        self._switch_page(type, verbose)
        # 获取选择时间的按钮
        WebDriverWait(self.dr, 10).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "loadingBg"))
        )
        try:
            start_bt = self.dr.find_element(By.XPATH, '//*[@id="dateTimeRangeBox"]/input[1]')
            end_bt = self.dr.find_element(By.XPATH, '//*[@id="dateTimeRangeBox"]/input[2]')
            searching_bt = self.dr.find_element(
                By.XPATH, '//*[@id="dateTimeRangeBox"]/following-sibling::div[@class="submitBtn"][1]')
        except (NoSuchElementException, ElementNotInteractableException):
            raise RuntimeError("Fatal Error: Can't find date selecting buttons!!!")
        data_list = []
        current_date = self.__start_date
        year_lag, month_lag, day_lag = None, None, None
        while current_date <= self.__end_date:
            current_str = current_date.strftime("%Y-%m-%d")
            year, month, day = current_str.split('-')
            # 模拟点击来选择时间段中的每一天
            for i in range(2):
                # 点击起始或结束时间按钮
                if i == 0:
                    self._safe_click(start_bt)
                else:
                    self._safe_click(end_bt)
                # 点击改年份
                if year != year_lag:
                    try:
                        year_sel = self.dr.find_element(By.XPATH, '//*[@id="ui-datepicker-div"]/div[1]/div/select[1]')
                    except (NoSuchElementException, ElementNotInteractableException) as e:
                        raise RuntimeError(f"Fatal Error: Can't find year selector!!! {e}")
                    self._safe_select(year_sel, "text", f"{year}")
                # 点击改月份
                if month != month_lag:
                    try:
                        mon_sel = self.dr.find_element(By.XPATH, '//*[@id="ui-datepicker-div"]/div[1]/div/select[2]')
                    except (NoSuchElementException, ElementNotInteractableException):
                        raise RuntimeError("Fatal Error: Can't find month selector!!!")
                    self._safe_select(mon_sel, "text",f"{month}")
                # 点击改日期
                try:
                    day_op = self.dr.find_element(
                        By.XPATH, f'//*[@id="ui-datepicker-div"]/table/tbody/tr/td/a[text()="{int(day)}"]')
                except (NoSuchElementException, ElementNotInteractableException):
                    raise RuntimeError("Fatal Error: Can't find day operator!!!")
                self._safe_click(day_op)
            self._safe_click(searching_bt)
            WebDriverWait(self.dr, 10).until(
                EC.invisibility_of_element_located((By.CLASS_NAME, "loadingBg"))
            )
            df_daily = self._get_data_daily(current_date, type, verbose)
            data_list.append(df_daily)
            year_lag, month_lag = year, month
            current_date = current_date + timedelta(days=1)
        df = pd.concat(data_list)
        return df

    def _save_to_database(self, database_url):
        if self.result.empty:
            logger.warning(f"{self.name} has no data to save to database !!!")
            return
        engine = create_engine(database_url)
        self.result = self.result.replace([np.nan, np.inf, -np.inf], None)
        self.result.to_sql('sale_data', engine, if_exists='append')

    # 手动设置想获取数据的时间段
    def set_period(self, period: str = ''):
        try:
            start_str, end_str = period.split('~')
            datetime.strptime(start_str, "%Y-%m-%d")
            datetime.strptime(end_str, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"{self.name} set period failed !!! [Wrong Format: {period}]")
            return
        self.__period = period
        self.__start_date = datetime.strptime(start_str, "%Y-%m-%d")
        self.__end_date = datetime.strptime(end_str, "%Y-%m-%d")
        logger.success(f"{self.name} successfully set period to {self.__period} !!!")

    # 运行自动化任务
    def run(self, type_dict: dict = None, database_url: str = None):
        # type_dict 格式为 {查询数据类型:是否verbose}
        if type_dict is None:
            type_dict = {"sale": False}
        if database_url is not None:
            t = time.localtime()
            self.set_period(time.strftime("%Y-%m-%d~%Y-%m-%d", t))
        try:
            start_time = time.time()
            start_time_str = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime())
            self._login()
            time.sleep(1)
            df_list = []
            for ty, ty_v in type_dict.items():
                df = self._get_data(ty, ty_v)
                df_list.append(df)
            self.result = pd.concat(df_list, axis=1)
            end_time = time.time()
            time_cost = end_time - start_time
            logger.success(f'{self.name} successfully run !!! [start:{start_time_str} | cost:{time_cost}s]')
            if database_url is not None:
                try:
                    self._save_to_database(database_url)
                except Exception as e:
                    logger.critical(f"{self.name} failed to save data to database !!!\n[{e}]")
        except Exception as e:
            logger.critical(f'{self.name} failed to run !!!\n[{e}]')
        finally:
            # time.sleep(1000)
            self.dr.quit()

    def __del__(self):
        super().__del__()


## AUTOGETSALE测试
if __name__ == '__main__':
    from dotenv import load_dotenv
    url = "https://beta33.pospal.cn"
    load_dotenv()
    un = os.getenv("POSPAL_USERNAME")
    p = os.getenv("POSPAL_PASSWORD")
    s = POSPALGETDATA(url, un, p, display=True, cover=(0, 0, 1440, 900))
    s.set_period("2025-6-1~2025-6-3")
    # s.run({"sale": True})
    # print(s.result)
    # 测试定时任务
    ex_time = datetime.now() + timedelta(seconds=1)
    date = ex_time.strftime("%Y-%m-%d")
    point = ex_time.strftime("%H:%M:%S")
    s.run_with_schedule(point=point, date=date, type_dict={"sale": True}, if_auto=True)
