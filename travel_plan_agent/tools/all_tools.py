from travel_plan_agent.tools.attraction import get_attraction
from travel_plan_agent.tools.currency import currency_exchange
from travel_plan_agent.tools.guide import get_guide
from travel_plan_agent.tools.hotel import get_hotel
from travel_plan_agent.tools.memory.get_chat_memory import get_chat_memory
from travel_plan_agent.tools.memory.get_longterm_memory import get_longterm_memory
from travel_plan_agent.tools.memory.save_chat_memory import save_chat_memory
from travel_plan_agent.tools.memory.save_longterm_memory import save_longterm_memory
from travel_plan_agent.tools.restaurant import get_restaurant
from travel_plan_agent.tools.traffic import get_traffic
from travel_plan_agent.tools.weather import get_weather

ALL_TOOLS = [
    get_attraction,
    get_hotel,
    get_restaurant,
    get_traffic,
    get_weather,
    get_guide,
    currency_exchange,
    get_chat_memory,
    get_longterm_memory,
    save_chat_memory,
    save_longterm_memory,
]
