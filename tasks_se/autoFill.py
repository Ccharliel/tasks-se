import time
from selenium.common import ElementNotInteractableException, NoSuchElementException
from selenium.webdriver.common.by import By
import threading
from difflib import get_close_matches
from loguru import logger

from tasks_se.core.task import TASK
from tasks_se.utils.autoFill_utils import *


# AUTOFILL 是填写问卷星的任务
class AUTOFILL(TASK):
    Num = 0
    _num_lock = threading.Lock()

    def __init__(self, u, info: pd.DataFrame, x_p=0, y_p=0, x_s=1, y_s=1, name=None):
        super().__init__(u, x_p, y_p, x_s, y_s)
        logger.add(f"{self.log_dir}/{self.class_name}.log", rotation="1 MB",
                   filter=lambda r: r["file"].name == f"{os.path.basename(__file__)}")
        self.info = info
        self.name = f"{self.class_name}{AUTOFILL.Num}" if name is None else name
        self.dr = self._init_driver()
        with AUTOFILL._num_lock:
            AUTOFILL.Num += 1

    # 探测题目页数和每页题数
    def detect(self):
        q_list = []
        page_num = len(self.dr.find_elements(By.XPATH, '//*[@id="divQuestion"]/fieldset'))
        for i in range(1, page_num + 1):
            questions = self.dr.find_elements(By.XPATH, f'//*[@id="fieldset{i}"]/div')
            valid_count = sum(1 for question in questions if question.get_attribute("topic").isdigit())
            q_list.append(valid_count)
        return q_list

    # 判断此题是否填写基础信息
    def searching_basic_info(self, q_current):
        try:
            question = q_current.find_element(By.XPATH, f'./div[1]/div[2]').text.lower()
        except NoSuchElementException:
            logger.warning("Fatal Error: Can't find question !!!")
            return None
        df = self.info
        # 返回第一个匹配的基础信息， 如果没有匹配的返回None
        return next((row.info for row in df.itertuples() if row.key in question), None)

    # 填空题实现
    def vacant(self, q_current_num, q_current):
        basic_info = self.searching_basic_info(q_current)
        try:
            blank = q_current.find_element(By.CSS_SELECTOR, f"#q{q_current_num}")
        except NoSuchElementException:
            logger.warning(f"[Question {q_current_num}] Fatal Error: Can't find blank !!!")
            return 0
        if basic_info:
            self._safe_send_keys(blank, basic_info)
        else:
            self._safe_send_keys(blank, "无")
            logger.info(f"[Question {q_current_num}] This vacant is not related to basic info")
        return 1

    # 单选题实现
    def single(self, q_current_num, q_current):
        basic_info = self.searching_basic_info(q_current)
        try:
            op_num = len(q_current.find_elements(By.XPATH, './div[2]/div'))
            options = [q_current.find_element(By.XPATH, f'./div[2]/div[{i}]/div').text.lower()
                       for i in range(1, op_num + 1)]
        except NoSuchElementException:
            logger.warning(f"[Question {q_current_num}] Fatal Error: Can't find option !!!")
            return 0
        if basic_info:
            matches = get_close_matches(basic_info, options, n=1, cutoff=0.4)
            if matches:
                selection = q_current.find_element(By.XPATH, f'./div[2]//div[text()="{matches[0]}"]')
            else:
                selection = q_current.find_element(By.XPATH, './div[2]/div[1]/div')
                logger.info(f"[Question {q_current_num}] No close option found for '{basic_info}'")
        else:
            selection = q_current.find_element(By.XPATH, './div[2]/div[1]/div')
            logger.info(f"[Question {q_current_num}] This selection is not related to basic info")
        self._safe_click(selection)
        return 1

    # 下拉题实现
    def down_pull(self, q_current_num, q_current):
        basic_info = self.searching_basic_info(q_current)
        try:
            button = q_current.find_element(By.XPATH, f'.//span[@id="select2-q{q_current_num}-container"]')
        except NoSuchElementException:
            logger.warning(f"[Question {q_current_num}] Fatal Error: Can't find down_pull button !!!")
            return 0
        self._safe_click(button)
        try:
            op_num = len(self.dr.find_elements(By.XPATH, f'//*[@id="select2-q{q_current_num}-results"]/li')) - 1
            options = [self.dr.find_element
                       (By.XPATH, f'//*[@id="select2-q{q_current_num}-results"]/li[{i}]').text.lower()
                       for i in range(2, 2 + op_num)]
        except NoSuchElementException:
            logger.warning(f"[Question {q_current_num}] Fatal Error: Can't find option !!!")
            return 0
        if basic_info:
            matches = get_close_matches(basic_info, options, n=1, cutoff=0.4)
            if matches:
                selection = (self.dr.find_element
                             (By.XPATH, f'//*[@id="select2-q{q_current_num}-results"]/li[text()="{matches[0]}"]'))
            else:
                selection = self.dr.find_element(By.XPATH, f'//*[@id="select2-q{q_current_num}-results"]/li[2]')
                logger.info(f"[Question {q_current_num}] No close option found for '{basic_info}'")
        else:
            selection = self.dr.find_element(By.XPATH, f'//*[@id="select2-q{q_current_num}-results"]/li[2]')
            logger.info(f"[Question {q_current_num}] This selection is not related to basic info")
        self._safe_click(selection)
        return 1

    # 填写问卷
    def fill(self):
        q_list = self.detect()
        q_current_num = 0
        for j in q_list:
            for k in range(1, j + 1):
                q_current_num += 1
                q_current = self.dr.find_element(By.CSS_SELECTOR, f"#div{q_current_num}")
                q_current_type = q_current.get_attribute("type")
                # 填空题
                if q_current_type == '1' or q_current_type == '2':
                    ret = self.vacant(q_current_num, q_current)
                elif q_current_type == '3':
                    ret = self.single(q_current_num, q_current)
                elif q_current_type == '4':
                    # 问卷报名一般没有多选题， 如果有可能是发布人设置错误， 就当成单选填
                    ret = self.single(q_current_num, q_current)
                elif q_current_type == '7':
                    ret = self.down_pull(q_current_num, q_current)
                else:
                    ret = 0
                    logger.warning(f"[Question {q_current_num}] Fatal Error: Other type !!!")
                if not ret:
                    raise RuntimeError(f"Failed to answer question {q_current_num}")
                # time.sleep(3)
            try:
                ne = self.dr.find_element(By.CSS_SELECTOR, "#divNext")
                ne.click()  # 这里不能用_safe_click，因为其中的 js 点击会点击到前几页的按钮
            except ElementNotInteractableException:
                try:
                    acp = self.dr.find_element(By.XPATH, "//label[@for='checkxiexi']")
                    self._safe_click(acp)
                    sub = self.dr.find_element(By.CSS_SELECTOR, "#ctlNext")
                    self._safe_click(sub)
                except Exception as e:
                    raise RuntimeError(f"Failed to submit or turn page: {e}")
            except Exception as e:
                raise RuntimeError(f"Failed to turn page: {e}")

    # 运行自动化任务
    def run(self):
        try:
            start_time = time.time()
            start_time_str = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime())
            self.fill()
            time.sleep(1)
            self._shot()
            end_time = time.time()
            time_cost = end_time - start_time
            logger.success(f'{self.name} successfully run !!! [start:{start_time_str} | cost:{time_cost}s]')
        except Exception as e:
            logger.critical(f'{self.name} failed to run !!!\n[{e}]')
        finally:
            time.sleep(100)
            self.dr.quit()

    def __del__(self):
        super().__del__()


## AUTOFILL测试
if __name__ == '__main__':
    cl_info = get_info("chenliang")
    if cl_info is not None:
        url1 = "https://www.wjx.top/vm/r0AgKQO.aspx# "
        s1 = AUTOFILL(url1, cl_info, x_p=0, y_p=0, x_s=1920, y_s=1080)
        # s1.run_with_schedule("18:00:00")
        s1.run()
