import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import threading

from tasks_se.core.task import TASK
from tasks_se.utils.threading_utils import threading_running


class AUTOSCREENSHOT(TASK):
    def __init__(self, url, window=(None, None, None, None), name=None):
        super().__init__(url, window, name)

    def _init_config(self):
        pass

    def _set_scheduler_trigger(self):
        pass

    def _login(self):
        pass

    def _after_inject(self):
        pass

    # 自动翻页截屏并保存
    def _execute(self):
        saving_path = f"{self._log_dir}/results/{self._name}"
        os.makedirs(saving_path, exist_ok=True)
        page_num = int(self._dr.find_element(By.XPATH, '//*[@class="slide-number"]//*[@class="slide-number-b"]').text)
        body = self._dr.find_element(By.TAG_NAME, "body")
        for i in range(1, page_num + 1):
            body.screenshot(f"{saving_path}/page{i}.png")
            body.send_keys(Keys.ARROW_RIGHT)


## AUTOSCREENSHOT测试
if __name__ == '__main__':
    folder_path = r"D:\Users\23213\Documents\myDocument\课\bin\R语言"
    tml = []
    sl = []
    for f in os.listdir(folder_path):
        u = "file:///" + os.path.join(folder_path, f)
        file_name = f.split(".")[0]
        s = AUTOSCREENSHOT(u, name=file_name)
        sl.append(s)
        tml.append(s.run)
    threading_running(tml)
    for s in sl:
        s.close()
