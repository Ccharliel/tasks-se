import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import threading
from loguru import logger

from tasks_se.core.task import TASK


# AUTOSCREENSHOT 是截取HTML课件每一页的任务
class AUTOSCREENSHOT(TASK):
    Num = 0
    _num_lock = threading.Lock()

    def __init__(self, u, display=False, cover=None, name=None):
        super().__init__(u, display)
        logger.add(f"{self.log_dir}/{self.class_name}.log", rotation="1 MB",
                   filter=lambda re: re["file"].name == f"{os.path.basename(__file__)}")
        self.name = f"{self.class_name}{AUTOSCREENSHOT.Num}" if name is None else name
        if self.display:
            self._check_cover_valid(cover)
            self.x_p = cover[0]
            self.y_p = cover[1]
            self.x_s = cover[2]
            self.y_s = cover[3]
        self.dr = self._init_driver()
        with AUTOSCREENSHOT._num_lock:
            AUTOSCREENSHOT.Num += 1

    # 自动翻页截屏并保存
    def constant_shot(self):
        saving_path = f"{self.log_dir}/results/{self.name}"
        os.makedirs(saving_path, exist_ok=True)
        page_num = int(self.dr.find_element(By.XPATH, '//*[@class="slide-number"]//*[@class="slide-number-b"]').text)
        body = self.dr.find_element(By.TAG_NAME, "body")
        for i in range(1, page_num + 1):
            body.screenshot(f"{saving_path}/page{i}.png")
            body.send_keys(Keys.ARROW_RIGHT)

    # 运行自动化任务
    def run(self, if_with_schedule=False):
        try:
            if not isinstance(if_with_schedule, bool):
                raise TypeError("if_with_schedule must be bool")
            start_time = time.time()
            start_time_str = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime())
            self.constant_shot()
            end_time = time.time()
            time_cost = end_time - start_time
            logger.success(f'{self.name} successfully run !!! [start:{start_time_str} | cost:{time_cost}s]')
        except Exception as e:
            logger.critical(f'{self.name} failed to run !!!\n[{e}]')
        finally:
            self.dr.quit()

    def __del__(self):
        super().__del__()


## AUTOSCREENSHOT测试
if __name__ == '__main__':
    folder_path = r"D:\Users\23213\Documents\myDocument\课\bin\R语言"
    for f in os.listdir(folder_path):
        url = "file:///" + os.path.join(folder_path, f)
        file_name = f.split(".")[0]
        s = AUTOSCREENSHOT(url, name=file_name)
        s.run()
