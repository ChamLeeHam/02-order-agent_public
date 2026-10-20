import json
import os
import time
from contextlib import aclosing

from langchain.agents.middleware import ToolCallLimitMiddleware, ToolRetryMiddleware, ModelRetryMiddleware, \
    ModelFallbackMiddleware, ModelCallLimitMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from anyio import current_time
from dotenv import load_dotenv
from pathlib import Path
import pymysql
from langchain.tools import tool
import sys

from pydantic import BaseModel, Field

ROOT_PATH = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_PATH))

from utils.milvus_utils import get_milvus_client, get_embedding

ROOT_DIR = Path(__file__).parent.parent   #获取项目根目录

load_dotenv()

agent = None


class ReservationToolArgsInfo(BaseModel):

    num_people:int = Field(description="预约的总人数")
    num_children:int = Field(description="预约的0-2岁儿童人数")
    arrival_time:str = Field(description="预约的到达时间,格式：YYYY-MM-DD HH")
    seat_preference:str = Field(description="预约的座位偏好，当用户没有特殊需求时，传递空字符串即可")
    main_dish_preference:str = Field(description="预约的主菜偏好，当用户没有特殊需求时，传递空字符串即可")
    other_comments:str = Field(description="预约的其他备注，当用户没有特殊需求时，传递空字符串即可")




@tool
def search_featured_dish():
    """用来搜索餐厅的特色菜"""
    sql = """
    select
        menu_items.dish_name as 菜品名称,
        menu_items.price as 价格,
        menu_items.category as 菜品类别,
        menu_items.description as 描述,
        menu_items.spice_level as 麻辣程度,
        menu_items.flavor as 口味,
        menu_items.main_ingredients as 主料,
        menu_items.cooking_method as 烹饪方法,
        menu_items.is_vegetarian as 是否素食,
        menu_items.allergens as 过敏源
        from menu_items 
    where is_featured=1
        
    """
    with pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE")
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
    return result

@tool
def user_favourite_dish(query: str):
    """根据用户的口味要求推荐菜品"""
    client = get_milvus_client()

    embedding = get_embedding()

    vector_query = embedding.embed_query(query)

    # 相似度检索
    search_res = client.search(
        collection_name=os.getenv("MILVUS_COLLECTION"),
        data=[vector_query],   # 查询向量
        anns_field="vector",  # 指定检索字段
        output_fields=["text"],  # 指定输出的字段
        limit=3  # 指定输出的条数
    )
    # print(search_res)

    # 获取结果
    if search_res:
        all_results = search_res[0]
        final_res = []
        for result in all_results:
            distance = result["distance"]
            if distance > 0.5:
                text = result["entity"]["text"]
                final_res.append(text)
        return final_res
    else:
        return "当前菜单中没有找到和用户喜好匹配的菜品！"

@tool(args_schema=ReservationToolArgsInfo)
def make_reservation(num_people:int,num_children:int,arrival_time:str,seat_preference
:str,main_dish_preference:str,other_comments:str):
    """餐厅座位预定"""
    try:
        sql = """
            insert into reservation_order (num_people, num_children, arrival_time, seat_preference, main_dish_preference, other_comments) values (%s, %s, %s, %s, %s, %s)
        """
        with pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", "3307")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (num_people, num_children, arrival_time, seat_preference, main_dish_preference, other_comments))
                conn.commit()
                return "预定成功！"
    except Exception as e:
        return  f"预定失败：{str(e)}"


mcp_client = MultiServerMCPClient(
    {
        "amap-maps":{
            "transport":"streamable-http",
            "url":f"https://mcp.amap.com/mcp?key={os.getenv('AMAP_API_KEY', '')}"
        }
    }
)


@tool
async def delivery(address: str, travel_mode: str = "2") -> dict:
    """查询配送范围。address 是收货地址；travel_mode：1 骑行、2 驾车、3 直线距离，默认驾车。"""
    modes = {"1": "骑行", "2": "驾车", "3": "直线距离"}
    address = address.strip()
    if not address:
        return {"success": False, "message": "地址无法解析，请重新输入"}
    if travel_mode not in modes:
        return {"success": False, "message": "请选择 1（骑行）、2（驾车）或 3（直线距离）"}

    try:
        async with mcp_client.session("amap-maps") as session:
            # 1. 高德把两个地址转成坐标。
            start = await _call_amap(session, "maps_geo", {"address": "上海黄浦区人民广场六合大厦", "city": "上海"})
            end = await _call_amap(session, "maps_geo", {"address": address, "city": "上海"})
            if not start["results"] or not end["results"]:
                return {"success": False, "message": "地址无法解析，请重新输入"}
            origin = start["results"][0]["location"]
            destination = end["results"][0]["location"]

            # 2. 高德查询距离，骑行和驾车另外返回路线时间。
            if travel_mode == "3":
                data = await _call_amap(session, "maps_distance", {"origins": origin, "destination": destination, "type": "0"})
                paths = data["results"]
            else:
                name = "maps_direction_bicycling" if travel_mode == "1" else "maps_direction_driving"
                data = await _call_amap(session, name, {"origin": origin, "destination": destination})
                paths = data["paths"]
            if not paths:
                return {"success": False, "message": "未找到可用路线，请更换地址或出行方式"}
            distance_km = float(paths[0]["distance"]) / 1000
            duration_min = None if travel_mode == "3" else round(float(paths[0]["duration"]) / 60, 1)

        # 3. 距离不超过 5 公里，就在配送范围内。
        in_range = distance_km <= 5
        return {
            "success": True,
            "address": address,
            "distance_km": round(distance_km, 3),
            "duration_min": duration_min,
            "in_range": in_range,
            "travel_mode": modes[travel_mode],
            "message": "在配送范围内" if in_range else "超出配送范围",
        }
    except Exception:
        return {"success": False, "message": "地图服务暂不可用，请稍后重试"}


async def _call_amap(session, tool_name: str, arguments: dict) -> dict:
    """读取高德 MCP 返回的 JSON。"""
    try:
        result = await session.call_tool(tool_name, arguments)

        return json.loads(result.content[0].text)

    except Exception as e:
        return {"success": False, "message": f"地图服务暂不可用，请稍后重试: {str(e)}"}


async def get_agent():
    global agent

    if agent is None:
        from langchain.agents import create_agent
        from langgraph.checkpoint.memory import InMemorySaver
        gaode_mcp_tools = await mcp_client.get_tools()
        all_tools = [
            search_featured_dish,
            user_favourite_dish,
            make_reservation,
            delivery,
            *gaode_mcp_tools,
        ]
        checkpoint = InMemorySaver()


        #         获取系统提示词
        with open(str(ROOT_DIR/"agent"/"prompt"/"system_prompt.txt"), "r", encoding="utf-8") as f:
            system_prompt = f.read()

        agent = create_agent(
            model = "gpt-4o",
            tools = all_tools,
            system_prompt = system_prompt,   #系统提示词
            checkpointer = checkpoint,   #开启短期记忆,
            middleware=[
                ToolCallLimitMiddleware(thread_limit=20, run_limit=10),
                ToolRetryMiddleware(
                    max_retries=3,
                    backoff_factor=2.0,
                    initial_delay=1.0
                ),
                ModelRetryMiddleware(
                    max_retries=3,
                    backoff_factor=2.0,
                    initial_delay=1.0,
                ),
                ModelCallLimitMiddleware(
                    thread_limit=10,
                    run_limit=5,
                    exit_behavior="end"
                )
            ]
        )
    return agent


async def assistant_query(query:str, session_id:str):
    """将agent流式处理的内容，使用sse流式返回"""
    agent = await get_agent()
    config = {"configurable":{"thread_id":session_id}}
    current_data = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # 1. 调用agent的流式输出
    stream = agent.astream({
        "messages":[
                {"role":"system","content":f"你是六合餐厅的智能助手，请根据用户的输入，进行回答，或者完成预订任务,当前时间：{current_data}"},
                {"role": "user","content": query}
        ]
    },config, stream_mode="messages")
    # 即使消费端提前退出，也在当前上下文中释放上游生成器。
    async with aclosing(stream):
        async for chunk, metadata in stream:
            if not isinstance(chunk, AIMessage) or not chunk.text:
                continue
            payload_str = json.dumps({"type": "token", "content": chunk.text}, ensure_ascii=False)
            yield f"data: {payload_str}\n\n"



async def test_agent():
    agent = await get_agent()
    config = {"configurable":{"thread_id":"12345"}}
    current_data = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    res = await agent.ainvoke({
        "messages":
            [
                {
                    "role":"system",
                    "content":f"你是六合餐厅的只能助手，请根据用户输入，进行回答，或者完成预定任务，当前时间，{current_data}"
                },
                {
                    "role":"user",
                    "content":"请帮我约定一下明天下午4点的座位，总共4个人，其中有一位朋友，位置最好靠窗，菜品主要偏辣一点，位置不要太吵闹！"
                }
            ]

    },config)

    res2 = await  agent.ainvoke({
        "messages":
            [
                {
                    "role": "user",
                    "content": "好的，以上信息没问题，请帮我预定！"
                }]
    }, config)

    res3 = await  agent.ainvoke({
        "messages":
            [
                {
                    "role": "user",
                    "content": "从武康路怎么过去餐厅？"
                }]
    }, config)

    print(res3["messages"][-1].content)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent())
    # res = search_featured_dish.invoke({})
    # print(res)
