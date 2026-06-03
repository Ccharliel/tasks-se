from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from difflib import get_close_matches

from tasks_se.core.task import TASK
from tasks_se.utils.autoFill_utils import *


class AUTOFILL(TASK):
    def __init__(self, url, info, window=(None, None, None, None), name=None):
        super().__init__(url, window, name, info=info)

    def _init_config(self, info):
        self._info = info

    def _set_scheduler_trigger(self):
        pass

    def _login(self):
        pass

    def _after_inject(self):
        pass

    # 探测题目页数和每页题数
    def _detect(self):
        q_list = []
        page_num = len(self._dr.find_elements(By.XPATH, '//*[@id="divQuestion"]/fieldset'))
        for i in range(1, page_num + 1):
            questions = self._dr.find_elements(By.XPATH, f'//*[@id="fieldset{i}"]/div')
            valid_count = sum(1 for question in questions if question.get_attribute("topic").isdigit())
            q_list.append(valid_count)
        return q_list

    # 判断此题是否填写基础信息
    def _searching_basic_info(self, q_current):
        try:
            question = q_current.find_element(By.XPATH, f'./div[1]/div[2]').text.lower()
        except NoSuchElementException:
            self._log.warning("Fatal Error: Can't find question !!!")
            return None
        df = self._info
        return next((row.info for row in df.itertuples() if row.key in question), None)

    # 填空题实现
    def _vacant(self, q_current_num, q_current):
        basic_info = self._searching_basic_info(q_current)
        try:
            blank = q_current.find_element(By.CSS_SELECTOR, f"#q{q_current_num}")
        except NoSuchElementException:
            self._log.warning(f"[Question {q_current_num}] Fatal Error: Can't find blank !!!")
            return 0
        if basic_info:
            self._safe_send_text(blank, basic_info)
        else:
            self._safe_send_text(blank, "无")
            self._log.info(f"[Question {q_current_num}] This vacant is not related to basic info")
        return 1

    # 单选题实现
    def _single(self, q_current_num, q_current):
        basic_info = self._searching_basic_info(q_current)
        try:
            op_num = len(q_current.find_elements(By.XPATH, './div[2]/div'))
            options = [q_current.find_element(By.XPATH, f'./div[2]/div[{i}]/div').text.lower()
                       for i in range(1, op_num + 1)]
        except NoSuchElementException:
            self._log.warning(f"[Question {q_current_num}] Fatal Error: Can't find option !!!")
            return 0
        if basic_info:
            matches = get_close_matches(str(basic_info), options, n=1, cutoff=0.4)
            if matches:
                selection = q_current.find_element(By.XPATH, f'./div[2]//div[text()="{matches[0]}"]')
            else:
                selection = q_current.find_element(By.XPATH, './div[2]/div[1]/div')
                self._log.info(f"[Question {q_current_num}] No close option found for '{basic_info}'")
        else:
            selection = q_current.find_element(By.XPATH, './div[2]/div[1]/div')
            self._log.info(f"[Question {q_current_num}] This selection is not related to basic info")
        self._safe_click(selection)
        return 1

    # 下拉题实现
    def _down_pull(self, q_current_num, q_current):
        basic_info = self._searching_basic_info(q_current)
        try:
            button = q_current.find_element(By.XPATH, f'.//span[@id="select2-q{q_current_num}-container"]')
        except NoSuchElementException:
            self._log.warning(f"[Question {q_current_num}] Fatal Error: Can't find down_pull button !!!")
            return 0
        self._safe_click(button)
        try:
            op_num = len(self._dr.find_elements(By.XPATH, f'//*[@id="select2-q{q_current_num}-results"]/li')) - 1
            options = [self._dr.find_element
                       (By.XPATH, f'//*[@id="select2-q{q_current_num}-results"]/li[{i}]').text.lower()
                       for i in range(2, 2 + op_num)]
        except NoSuchElementException:
            self._log.warning(f"[Question {q_current_num}] Fatal Error: Can't find option !!!")
            return 0
        if basic_info:
            matches = get_close_matches(str(basic_info), options, n=1, cutoff=0.4)
            if matches:
                selection_xpath = f'//*[@id="select2-q{q_current_num}-results"]/li[text()="{matches[0]}"]'
            else:
                selection_xpath = f'//*[@id="select2-q{q_current_num}-results"]/li[2]'
                self._log.info(f"[Question {q_current_num}] No close option found for '{basic_info}'")
        else:
            selection_xpath = f'//*[@id="select2-q{q_current_num}-results"]/li[2]'
            self._log.info(f"[Question {q_current_num}] This selection is not related to basic info")
        selection = WebDriverWait(self._dr, 10).until(
            EC.element_to_be_clickable((By.XPATH, selection_xpath))
        )
        self._safe_click(selection)
        return 1

    # 填写问卷
    def _fill(self):
        q_list = self._detect()
        q_current_num = 0
        for j in q_list:
            for k in range(1, j + 1):
                q_current_num += 1
                q_current = self._dr.find_element(By.CSS_SELECTOR, f"#div{q_current_num}")
                q_current_type = q_current.get_attribute("type")
                # 填空题
                if q_current_type == '1' or q_current_type == '2':
                    ret = self._vacant(q_current_num, q_current)
                elif q_current_type == '3':
                    ret = self._single(q_current_num, q_current)
                elif q_current_type == '4':
                    # 问卷报名一般没有多选题， 如果有可能是发布人设置错误， 就当成单选填
                    ret = self._single(q_current_num, q_current)
                elif q_current_type == '7':
                    ret = self._down_pull(q_current_num, q_current)
                else:
                    ret = 0
                    self._log.warning(f"[Question {q_current_num}] Fatal Error: Other type !!!")
                if not ret:
                    raise RuntimeError(f"Failed to answer question {q_current_num}")
            try:
                ne = self._dr.find_element(By.CSS_SELECTOR, "#divNext")
                if ne.is_displayed():
                    self._safe_click(ne)
                else:
                    acp = self._dr.find_element(By.XPATH, "//label[@for='checkxiexi']")
                    self._safe_click(acp)
                    sub = self._dr.find_element(By.CSS_SELECTOR, "#ctlNext")
                    self._safe_click(sub)
            except Exception as e:
                raise RuntimeError(f"Failed to turn page or submit: {e}")

    # 运行自动化任务
    def _execute(self):
        self._fill()
        time.sleep(1)
        self._shot()


## AUTOFILL测试
if __name__ == '__main__':
    cl_info = get_info("chenliang")
    if cl_info is not None:
        url1 = "https://www.wjx.top/vm/r0AgKQO.aspx# "
        s1 = AUTOFILL(url1, cl_info)
        # s1.set_scheduler("blocking")
        # s1.set_scheduler("background")
        s1.run()
        time.sleep(3)
        s1.close()

