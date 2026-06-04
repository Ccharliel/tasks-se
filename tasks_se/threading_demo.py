from dotenv import load_dotenv


from tasks_se import *
from tasks_se.utils.autoFill_utils import *
from tasks_se.utils.threading_utils import threading_running

if __name__ == '__main__':
    ## 多线程测试（实例在线程内创建，演示竞态条件）
    cl_info = get_info("chenliang")
    url1 = "https://www.wjx.top/vm/r0AgKQO.aspx# "
    url2 = "https://beta33.pospal.cn"
    load_dotenv()
    un = os.getenv("POSPAL_USERNAME")
    p = os.getenv("POSPAL_PASSWORD")
    u_d = {"username": un, "password": p}

    # 测试多线程同时创建并操作不同实例
    def task1():
        s1 = AUTOFILL(url1, cl_info, window=(0, 0, 400, 800))
        s1.run()
        s1.close()

    def task2():
        s2 = POSPALGETDATA(url2, u_d)
        s2.set_period("2025-6-1~2025-6-1")
        s2.run()
        s2.close()

    # 测试多线程同时操作同一实例，不建议（会导致日志混乱）
    ss = POSPALGETDATA(url2, u_d, window=(400, 0, 400, 800))

    def task3():
        ss.set_period("2025-7-1~2025-7-1")
        ss.run(task_list=[{"sale": {"verbose": True, "database_url": None}}])

    def task4():
        ss.set_scheduler("background")
        ss.run(task_list=[{"sale": {"verbose": True,
                                    "database_url": "mysql+pymysql://root:123456@localhost:3306/pospal"}}])


    tml = [task1, task2, task3, task4]
    threading_running(tml)
    ss.close()
