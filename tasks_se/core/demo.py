from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opt = Options()
opt.binary_location = r"D:\Users\23213\Documents\myCode\python\code\myProject\my_packages\tasks_se\tasks_se\core\chromes\chrome-143_0_7499_192\chrome-143_0_7499_192-win64\chrome.exe"

driver = webdriver.Remote(
    command_executor="http://127.0.0.1:9515",
    options=opt
)
driver.get("https://www.baidu.com")
print(driver.title)
driver.quit()
