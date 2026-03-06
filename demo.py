import threading
import requests
from tasks_se import *
from tasks_se.utils.autoFill_utils import *
import time


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
creat_info("chenliang")
cl_info = get_info("chenliang")
url1 = "https://www.wjx.top/vm/r0AgKQO.aspx# "
s1 = AUTOFILL(0, 0, 500, 1440, url1, cl_info)
url2 = "https://www.wjx.top/vm/YDgQxM3.aspx#"
s2 = AUTOFILL(1000, 0, 500, 1440, url2, cl_info, "AUTOFILL_schedule2")
date = time.strftime("%Y-%m-%d", time.localtime())
point = time.strftime("%H:%M:%S", time.localtime())
# date = "2025-3-31"
# point = "22:10:00"
tml = [(s1.run_with_schedule, (point, date), {}),
       (s2.run_with_schedule, (point, date), {}),
       ]
threading_running(tml)
