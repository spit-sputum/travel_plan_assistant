from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent  # travel_plan_agent 目录


class Settings(BaseSettings):
    """全局配置：全部来自同目录下的 .env，未填写的项自动使用默认值。"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),  # 指向 agent 子文件夹里的 .env
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------------- 大模型 ----------------
    # 供应商：qwen / deepseek / openai / moonshot / zhipu / custom
    model_provider: str = "qwen"
    # 模型名称：留空则使用该供应商的默认模型
    model_name: str = ""
    # 接口地址：留空则使用该供应商默认地址；专属/自建网关必须显式填写
    model_api_url: str = ""
    # 接口密钥
    model_api_key: SecretStr = SecretStr("")
    # 采样温度：越高越随机，行程规划建议 0.3 ~ 0.8
    model_temperature: float = 0.75
    # 是否开启模型思考/推理模式（qwen 关闭更快更省 token）
    enable_thinking: bool = False

    # ---------------- 工具类第三方 API ----------------
    tavily_api_key: str = ""  # 攻略 / 景点 / 餐厅 / 酒店 网络检索
    gaode_key: str = ""  # 高德地图：路线规划
    hefeng_key: str = ""  # 和风天气：天气预报
    hefeng_host: str = ""  # 和风天气专属域名


@lru_cache
def get_settings() -> Settings:
    return Settings()
