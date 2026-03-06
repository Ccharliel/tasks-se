from setuptools import setup, find_packages

setup(
    name="tasks-se",          # 包名
    version="1.0.0",               # 版本号
    author="Charlie",            # 作者
    description="some different Tasks using selenium",  # 描述
    packages=find_packages(),      # 自动找到所有包
    python_requires=">=3.6",       # Python版本要求
)