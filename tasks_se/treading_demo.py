import threading
import requests
import time
from dotenv import load_dotenv
import os

from tasks_se import *
from tasks_se.utils.autoFill_utils import *


def threading_running(task_method_list):
    threads = []
    for task_method, args, kwargs in task_method_list:
        thread = threading.Thread(target=task_method, args=args, kwargs=kwargs)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    # 如果子进程里用了BlockingScheduler，子进程阻塞就不会执行print
    print("所有子进程结束")


## 多线程测试
# AUTOFILL测试
cl_info = get_info("chenliang")
url1 = "https://www.wjx.top/vm/r0AgKQO.aspx# "
s1 = AUTOFILL(url1, cl_info, display=True, cover=(0, 0, 400, 800))

url2 = "https://beta33.pospal.cn/Report/BusinessSummaryV2"
load_dotenv()
un = os.getenv("POSPAL_USERNAME")
p = os.getenv("POSPAL_PASSWORD")
s2 = POSPALGETDATA(url2, un, p, display=True, cover=(400, 0, 400, 800))
s2.set_period("2025-6-1~2025-6-3")

url3 = "https://beta33.pospal.cn/Report/BusinessSummaryV2"
load_dotenv()
un = os.getenv("POSPAL_USERNAME")
p = os.getenv("POSPAL_PASSWORD")
s3 = POSPALGETDATA(url2, un, p)
s3.set_period("2025-7-1~2025-7-3")

date = time.strftime("%Y-%m-%d", time.localtime())
point = time.strftime("%H:%M:%S", time.localtime())
# date = "2025-3-31"
# point = "22:10:00"
tml = [(s1.run_with_schedule, (point, date), {}),
       (s2.run_with_schedule, (point, date), {}),
       (s3.run_with_schedule, (point, date), {})
       ]
# tml = [(s1.run, (), {}),
#        (s2.run, (), {}),
#        (s3.run, (), {})
#        ]
threading_running(tml)
