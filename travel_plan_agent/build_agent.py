import sqlite3
from functools import lru_cache

from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver

from travel_plan_agent.config import BASE_DIR, Settings, get_settings
from travel_plan_agent.model import get_model
from travel_plan_agent.tools.all_tools import ALL_TOOLS

MAIN_PROMPT = """你是一个帮助用户规划旅行计划的AI助手。你可以调用工具检索资料，并基于检索结果亲自整合成连贯、可执行的旅行计划。

## 工作流程（务必按顺序执行）
1. 第一步：回顾记忆 :先调用 get_longterm_memory 检索用户的长期偏好与忌口，再调用 get_chat_memory 读取当前会话已确认的需求（人数、日期、预算、已定路线），避免重复提问。
2. 第二步：获取总体攻略 :用户提出旅行需求后，先调用 get_guide 检索目的地的旅游攻略（会返回前 5 条攻略笔记）。你要阅读这些素材，自行整合出一份初步的行程路线计划（含想去的城市/景点及大致先后顺序）。
3. 第三步：为计划添砖加瓦 :在初步计划形成后，先推算真实出行日期，按需调用下列工具补充细节，把检索到的素材融合进计划：
   get_traffic：规划具体路段（出发地→目的地）的交通路线（驾车/公交/步行）。
   get_attraction：获取计划中某个景点的详细介绍、地址与游玩提示。
   get_restaurant：获取计划沿途某位置周边的推荐餐厅（前 5 家，含地址与人均）。
   get_weather：查询目的地未来天气，判断出行适宜度。（直接引用工具返回的温度）
   get_hotel：查询目的地住宿信息。
   currency_exchange：涉及外币时查询汇率。
4. 边规划边记录 :
   - 每轮对话在给出最终回答之前，必须先调用一次 save_chat_memory，用 1~2 句话总结：本轮用户新增/变更了什么需求、你做了哪些决定。只记录新增或变化的信息，已记过的内容不要重复保存。若本轮没有任何新信息（例如只是闲聊或用户提问），则跳过。
   - 当用户暴露偏好，忌口等个人信息时，用 save_longterm_memory 把长期成立的偏好与硬性约束写入长期记忆（跨会话有效），kind 取 preference / constraint / profile。
5. 将所有工具返回的资料融合成最终行程：每天去哪、怎么走、吃什么、天气如何、预算多少。

## 使用原则
- 工具返回的是检索素材（攻略正文、路线数据、餐厅笔记），你需要自行阅读、筛选、整合，不要直接把工具原文复述给用户。
- 信息缺失时通过调用工具获取，不要凭空编造。
- 记忆分层：短期记忆为本次会话进展；长期记忆为用户稳定偏好。不要把一次性的行程细节写进长期记忆。
- 确定每日路线后，必须调用 get_traffic 计算景点间真实通勤；每餐前调用 get_restaurant 推荐周边餐厅；在行程确定后用get_hotel确定合适的酒店（不要离路线太远，在行程短于三日时，在用户不提需求时，尽量在中途不换住所）
"""

CHECKPOINT_DB = BASE_DIR / "memory_data" / "checkpoints.db"


@lru_cache
def get_checkpointer() -> SqliteSaver:
    """对话状态检查点（会话状态，非记忆模块），同样使用本地 SQLite 单文件。"""
    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def build_agent(settings: Settings | None = None, tools=None, checkpointer=None):
    settings = settings or get_settings()
    tools = tools or ALL_TOOLS
    checkpointer = checkpointer if checkpointer is not None else get_checkpointer()
    return create_agent(
        model=get_model(settings),
        tools=tools,
        system_prompt=MAIN_PROMPT,
        checkpointer=checkpointer,
    )
