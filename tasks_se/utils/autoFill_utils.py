import pandas as pd
from loguru import logger

from tasks_se.utils.base_utils import *
from tasks_se.core.config import LOG_DIR


# AUTOFILL 任务所需专属工具
def _creat_info(name: str):
    data = {"": ["姓名", "性别", "学号", "学院", "专业", "年级", "班级", "手机", "邮箱", "微信", "QQ", "身份证"],
            "info": ['', '', '', '', '', '', '', '', '', '', '', '']
            }
    df = pd.DataFrame(data)
    os.makedirs("info", exist_ok=True)
    path = f"info/{name}.xlsx"
    if os.path.exists(path):
        logger.info(f"{path} Exists !!!")
        return 1
    else:
        logger.warning(f"{path} not Exists !!! Creating {path} ...")
        df.to_excel(path, index=False, sheet_name="Sheet1")
        auto_del_files("info", 10)
        return 0


def get_info(name: str):
    os.makedirs(f"{LOG_DIR}/AUTOFILL", exist_ok=True)
    logger.add(f"{LOG_DIR}/AUTOFILL/AUTOFILL.log", rotation="1 MB",
               filter=lambda r: r["file"].name == f"{os.path.basename(__file__)}")

    path = f"info/{name}.xlsx"
    ret = _creat_info(name)
    if ret == 0:
        logger.warning(f"Please fill in the basic info in {path} and retry !!!")
        return None
    df = pd.read_excel(path, index_col=0, dtype=str)
    try:
        df["info"]
    except KeyError:
        raise KeyError(f"必须保留列名‘info’!!!")

    tag = "专业和年级"
    try:
        if pd.isna(df.loc["年级", "info"]) or pd.isna(df.loc["专业", "info"]):
            raise KeyError
        df.loc["专业年级"] = df.loc["年级"] + df.loc["专业"]
        df = (pd.concat([df.loc[["专业年级"]], df.drop("专业年级")]).reset_index())  # 将专业年级行排到首行
        df = df.rename(columns={"index": ''})
        df = df.set_index(df.columns[0])
    except KeyError:
        raise KeyError(f"请填写 {path} 中的 {tag} 后重试")

    tag = "手机"
    try:
        if pd.isna(df.loc["手机", "info"]):
            raise KeyError
        df.loc["联系方式"] = df.loc["手机"]
    except KeyError:
        raise KeyError(f"请填写 {path} 中的 {tag} 后重试")

    tag = "邮箱"
    try:
        if pd.isna(df.loc["邮箱", "info"]):
            raise KeyError
        df.loc["Email"] = df.loc["邮箱"]
    except KeyError:
        raise KeyError(f"请填写 {path} 中的 {tag} 后重试")

    df = df.astype(str)
    df = df.reset_index().rename(columns={'': "key"})
    df["key"] = df["key"].str.lower()
    return df
