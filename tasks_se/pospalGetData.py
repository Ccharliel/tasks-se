import os
import time
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger
from selenium.common import ElementNotInteractableException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from sqlalchemy import create_engine, String

from tasks_se.core.task import TASK
from tasks_se.utils.base_utils import auto_del


class POSPALGETDATA(TASK):
    def __init__(self, url, login_data,
                 window=(None, None, None, None), name=None):
        super().__init__(url, window, name, login_data)

    def _init_config(self):
        self._date_tag = "date_tag"
        t = time.localtime()
        self._period = time.strftime("%Y-%m-%d~%Y-%m-%d", t)
        self._start_date = datetime(*t[:3])
        self._end_date = datetime(*t[:3])
        self.results = list()

    def _set_scheduler_trigger(self, hour=None, minute=None):
        if hour is None and minute is None:
            return
        else:
            if hour is None:
                hour = 20
            elif minute is None:
                minute = 0
        self._scheduler_trigger = CronTrigger(hour=hour, minute=minute)

    # 根据 username 和 password 登录
    def _login(self):
        username, password = super()._login()
        u_bt = self._dr.find_element(By.XPATH, '//*[@id="txt_userName"]')
        p_bt = self._dr.find_element(By.XPATH, '//*[@id="txt_password"]')
        s_bt = self._dr.find_element(By.XPATH, '//*[@id="submitLoginBtn"]')
        self._safe_send_text(u_bt, username)
        self._safe_send_text(p_bt, password)
        self._safe_click(s_bt)

    def _after_inject(self):
        pass

    # 爬取银豹每天的数据
    def _get_data_daily(self, date, data_type, verbose) -> pd.DataFrame:
        df = pd.DataFrame()
        if data_type == "sale":
            if verbose:
                download_btn = self._dr.find_element(By.XPATH, '//*[@id="btnExport"]')
                download_path = os.path.join(self._download_dir, data_type, datetime.strftime(date, "%Y-%m-%d"))
                self._safe_download(download_btn, download_path)
                files = [f for f in os.listdir(download_path) if f.endswith('.xlsx')]
                latest_file = max([os.path.join(download_path, f) for f in files], key=os.path.getctime)
                df = pd.read_excel(latest_file, engine='calamine')
                auto_del('d', os.path.join(self._download_dir, data_type), 366)
            else:
                # 数据包括：销售额（产品 / 服务）
                sale_info = self._dr.find_element(By.XPATH, '//*[@id="mainTable"]/tbody/tr[1]/td[2]/div')
                total_sale = sale_info.find_element(By.XPATH, './span[1]').text
                sale_comp = sale_info.get_attribute('textContent').split(')')[0].split('(')[1].split("; ")
                sale_prod, sale_ser = [i.split(' ')[1] for i in sale_comp]
                df = pd.DataFrame([sale_prod, sale_ser, total_sale]).T
                df.columns = ['产品销售额', '服务销售额', '总销售额']
                df[['产品销售额', '服务销售额', '总销售额']] = df[['产品销售额', '服务销售额', '总销售额']].astype(
                    float)
                sale_num = sale_info.find_element(By.XPATH, './span[4]').text
                df["单数"] = sale_num
                df['单数'] = df['单数'].astype(int)
        # date_tag 作为是否查询过该日期的标识
        df[self._date_tag] = date
        df[self._date_tag] = df[self._date_tag].astype(str)
        df = df.set_index(self._date_tag)
        return df

    def _switch_page(self, data_type, verbose):
        if data_type == "sale":
            if verbose:
                self._dr.get(f"{self._url}/Report/ProductSaleDetails")
            else:
                self._dr.get(f"{self._url}/Report/BusinessSummaryV2")

    def _get_data(self, data_type, verbose):
        self._log.info(f"{self._name} is getting {self._period} {data_type} data ...")
        ## 查询操作
        # 按照查询数据种类切换页面
        self._switch_page(data_type, verbose)
        # 获取选择时间的按钮
        WebDriverWait(self._dr, 10).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "loadingBg"))
        )
        try:
            start_bt = WebDriverWait(self._dr, 15).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="dateTimeRangeBox"]/input[1]'))
            )
            end_bt = WebDriverWait(self._dr, 15).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="dateTimeRangeBox"]/input[2]'))
            )
            searching_bt = WebDriverWait(self._dr, 15).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//*[@id="dateTimeRangeBox"]/following-sibling::div[@class="submitBtn"][1]'))
            )
        except (NoSuchElementException, ElementNotInteractableException):
            raise RuntimeError("Fatal Error: Can't find date selecting buttons!!!")
        data_list = []
        current_date = self._start_date
        year_lag, month_lag, day_lag = None, None, None
        while current_date <= self._end_date:
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
                        year_sel = self._dr.find_element(By.XPATH, '//*[@id="ui-datepicker-div"]/div[1]/div/select[1]')
                    except (NoSuchElementException, ElementNotInteractableException) as e:
                        raise RuntimeError(f"Fatal Error: Can't find year selector!!! {e}")
                    self._safe_select(year_sel, "text", f"{year}")
                # 点击改月份
                if month != month_lag:
                    try:
                        mon_sel = self._dr.find_element(By.XPATH, '//*[@id="ui-datepicker-div"]/div[1]/div/select[2]')
                    except (NoSuchElementException, ElementNotInteractableException):
                        raise RuntimeError("Fatal Error: Can't find month selector!!!")
                    self._safe_select(mon_sel, "text", f"{month}")
                # 点击改日期
                try:
                    day_op = self._dr.find_element(By.XPATH,
                                                   f'//*[@id="ui-datepicker-div"]/table/tbody/tr/td/a[text()="{int(day)}"]')
                except (NoSuchElementException, ElementNotInteractableException):
                    raise RuntimeError("Fatal Error: Can't find day operator!!!")
                self._safe_click(day_op)
            self._safe_click(searching_bt)
            WebDriverWait(self._dr, 10).until(
                EC.invisibility_of_element_located((By.CLASS_NAME, "loadingBg"))
            )
            df_daily = self._get_data_daily(current_date, data_type, verbose)
            data_list.append(df_daily)
            year_lag, month_lag = year, month
            current_date = current_date + timedelta(days=1)
        df = pd.concat(data_list)
        return df

    def _save_to_database(self, df, database_url, table_name):
        try:
            self._log.info(f"{self._name} is saving data to database: {database_url}")
            if df.empty:
                self._log.warning(f"No data to save to database !!!")
                return
            engine = create_engine(database_url)
            dtype_mapping: dict = {col: String(255) for col in df.columns}
            dtype_mapping[self._date_tag] = String(20)  # 单独控制日期字段
            # 写入空表，如果表不存在就创建
            df.iloc[:0].to_sql(table_name, engine, if_exists='append', index=True, dtype=dtype_mapping)
            current_dates = set(df.index.unique())
            df_new = pd.DataFrame()
            if current_dates:
                # 查询哪些时间点已存在
                placeholders = ','.join(['%s'] * len(current_dates))
                query = f"SELECT DISTINCT {self._date_tag} FROM {table_name} WHERE {self._date_tag} IN ({placeholders})"
                # 使用 pandas 读取，自动处理参数
                existing_df = pd.read_sql(query, engine, params=tuple(current_dates))
                existing_dates = set(existing_df[f'{self._date_tag}'])
                # 只保留未存在日期的数据
                df_new = df.loc[~df.index.isin(existing_dates)].copy(deep=True)
            # 插入新数据
            if not df_new.empty:
                df_new.to_sql(table_name, engine, if_exists='append', index=True, dtype=dtype_mapping)
                self._log.success(
                    f"{self._name} successfully save {len(df_new)} records "
                    f"for {len(df_new.index.unique())} new dates to database: {database_url} !!!")
            else:
                self._log.info(f"{self._name} all dates already exist in database, no data to save")
        except Exception as e:
            self._log.warning(f"{self._name} failed to save data to database: {database_url} \n[{e}]")

    # 运行自动化任务
    def _execute(self, task_list: list[dict] = None):
        """
        task_list example: [{str(type): {"verbose": bool, "database_url": str/None}}, ...]
        """
        self.results = []
        if task_list is None:
            # 默认值
            task_list = []
            defalut_type_dict = {"sale": {"verbose": False, "database_url": None}}
            task_list.append(defalut_type_dict)
        if not isinstance(task_list, list):
            raise TypeError("task_list must be list")
        if self._scheduler is not None:
            # 如果定时运行，获取当天数据
            t = time.localtime()
            self.set_period(time.strftime("%Y-%m-%d~%Y-%m-%d", t))
        for type_dict in task_list:
            for ty, ty_details in type_dict.items():
                df = self._get_data(ty, ty_details["verbose"])
                df = df.replace([float('nan'), float('inf'), float('-inf')], None)
                if ty_details["database_url"] is not None:
                    table_name = ty + "_data"
                    self._save_to_database(df, ty_details["database_url"], table_name)
                self.results.append(df)

    # 手动设置想获取数据的时间段
    def set_period(self, period: str = ''):
        with self._lock:
            try:
                start_str, end_str = period.split('~')
                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_str, "%Y-%m-%d")
            except ValueError:
                self._log.warning(f"{self._name} set period failed !!! [Wrong Format: {period}]")
                return
            if start_date > end_date:
                self._log.warning(
                    f"{self._name} set period failed !!! [Start date {start_str} is later than End date {end_str}]")
                return
            self._period = period
            self._start_date = datetime.strptime(start_str, "%Y-%m-%d")
            self._end_date = datetime.strptime(end_str, "%Y-%m-%d")
            self._log.success(f"{self._name} successfully set period to {self._period} !!!")


## AUTOGETSALE测试
if __name__ == '__main__':
    from dotenv import load_dotenv

    u = "https://beta33.pospal.cn"
    load_dotenv()
    un = os.getenv("POSPAL_USERNAME")
    p = os.getenv("POSPAL_PASSWORD")
    u_d = {"username": un, "password": p}
    s = POSPALGETDATA(u, u_d, window=(0, 0, 1440, 900))
    # s = POSPALGETDATA(u, u_d, window=(400, 0, 400, 800))
    # s = POSPALGETDATA(u, u_d)
    # s.set_period("2025-6-1~2025-6-3")
    # s.set_period("2026-04-29~2026-04-29")

    # 测试运行定时任务
    next_second = (datetime.now() + timedelta(minutes=1)).strftime("%H:%M:%S")
    time_parts = next_second.split(':')
    h, m, _ = map(int, time_parts)
    s.set_scheduler("background", hour=h, minute=m)
    s.run(task_list=[{"sale": {"verbose": True,
                               "database_url": "mysql+pymysql://root:123456@localhost:3306/pospal"}}])
    time.sleep(60.1)  # 确保定时任务触发

    # s.set_scheduler("background")
    # s.run(task_list=[{"sale": {"verbose": True,
    #                            "database_url": "mysql+pymysql://root:123456@localhost:3306/pospal"}}])
    # time.sleep(1.1)  # 确保定时任务触发
    # print(f"results: {s.results}")

    # 测试运行
    s.set_scheduler()
    print(f"results: {s.results}")  # 说明 set_scheduler 的确会等待正在运行的job完成
    s.set_period("2026-03-29~2026-03-29")
    s.run()
    # s.run(task_list=[{"sale": {"verbose": True, "database_url": None}}])
    # s.run(task_list=[{"sale": {"verbose": True,
    #                            "database_url": "mysql+pymysql://root:123456@localhost:3306/pospal"}}])
    for idx, r in enumerate(s.results):
        print(f"result{idx}: \n{r}")

    time.sleep(5)
    s.close()

    # # 测试 session_data
    # ss = POSPALGETDATA(u, s.session_data, window=(0, 0, 1440, 900))
    # # ss = POSPALGETDATA(u, s.session_data, window=(0, 0, 400, 800))
    # ss.run()
    # for idx, r in enumerate(ss.results):
    #     print(f"result{idx}: \n{r}")
    # ss.close()
