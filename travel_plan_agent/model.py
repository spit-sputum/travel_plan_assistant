from langchain_openai import ChatOpenAI

from travel_plan_agent.config import Settings

# 内置供应商预设：OpenAI 兼容协议下的默认接口地址与默认模型。
# 客户只想换模型时，把 .env 的 MODEL_PROVIDER 改成下面的名字即可。
PROVIDERS: dict[str, dict[str, str]] = {
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen3-max",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2-0711-preview",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4.5",
    },
    "custom": {"base_url": "", "model": ""},
}


def get_model(
    settings: Settings, model_name: str = "", temperature: float | None = None
):
    """按 .env 配置构造大模型（任意 OpenAI 兼容服务均可）。

    取值优先级：函数参数 > .env 显式填写 > 供应商默认值。
    换模型不需要改代码，只改 .env 里的 MODEL_PROVIDER / MODEL_NAME 等即可。
    """
    provider = (settings.model_provider or "custom").strip().lower()
    preset = PROVIDERS.get(provider, PROVIDERS["custom"])

    base_url = (settings.model_api_url or "").strip() or preset["base_url"]
    name = (model_name or settings.model_name or "").strip() or preset["model"]
    temp = settings.model_temperature if temperature is None else temperature

    if not base_url:
        raise ValueError(
            "未配置模型接口地址：请在 .env 填写 MODEL_API_URL，"
            + f"或把 MODEL_PROVIDER 设为内置供应商（{', '.join(PROVIDERS)}）"
        )
    if not name:
        raise ValueError(
            "未配置模型名称：请在 .env 填写 MODEL_NAME，"
            + f"或把 MODEL_PROVIDER 设为内置供应商（{', '.join(PROVIDERS)}）"
        )

    # 思考模式开关只对 qwen 系列有意义，其他供应商不传该参数以免接口报错
    extra_body: dict[str, bool] = {}
    if provider == "qwen" or settings.enable_thinking:
        extra_body["enable_thinking"] = settings.enable_thinking

    return ChatOpenAI(
        model=name,
        temperature=temp,
        api_key=settings.model_api_key,
        base_url=base_url,
        extra_body=extra_body or None,
    )
