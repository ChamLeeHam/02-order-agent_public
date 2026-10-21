# 将后段能力抽象成具体接口供前端调用
import os
import re
from difflib import SequenceMatcher
from typing import Optional, List

import pymysql
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pymysql.cursors import DictCursor
from starlette.responses import StreamingResponse
from datetime import datetime


from agent.langchain_assistant import assistant_query, delivery
from utils.redis_utils import get_redis_client



app = FastAPI()


_PUNCT_RE = re.compile(r"[\s,，。.!！？?;；:：'\"“”‘’（）()\[\]【】<>《》、/\\|_\-]+")

# 对文本进行清洗的函数：
def _normalize_text(text: str) -> str:
    return _PUNCT_RE.sub("", (text or "").strip())

def get_similarity_score(query: str, fqu_question: str):
    """判断用户的问题和FAQ的问题相似度得分"""
    query = _normalize_text(query)
    faq_question = _normalize_text(fqu_question)
    # 1.计算两个字符串的相似度得分
    similarity_score = SequenceMatcher(None, query, faq_question).ratio()
    query = set(list(query))
    faq_question = set(list(faq_question))
    jaccard_score = len(query.intersection(faq_question)) / len(query.union(faq_question))
    # 3. 计算两个字符串的包含关系得分
    bonus = 0
    if query in faq_question or faq_question in query:
        bonus = 0.5
    return similarity_score * 0.6 + jaccard_score * 0.4 + bonus  # 根据实际需求调整权重




class FAQItem(BaseModel):
    id: str
    question: str
    answer: str



# faq_items = load_faq_from_redis()  # 从redis中加载faq数据

class ChatRequest(BaseModel):
    query: str = Field(description="用户输入的聊天内容")


class DeliveryRequest(BaseModel):
    address: str
    travel_mode: str = "2"

@app.post("/api/delivery")
@app.post("/delivery", include_in_schema=False)
async def delivery_endpoint(request: DeliveryRequest):
    return await delivery.ainvoke(request.model_dump())


class ReservationItem(BaseModel):
    id: int
    num_people: int
    num_children: int
    arrival_time: Optional[str] = None
    seat_preference: Optional[str] = None
    main_dish_preference: Optional[str] = None
    other_comments: Optional[str] = None
    created_at: Optional[str] = None

class MenuItem(BaseModel):
    id: int
    dish_name: str
    price: float
    category: str
    description: Optional[str] = None
    spice_level: Optional[int] = None
    flavor: Optional[str] = None
    main_ingredients: Optional[str] = None
    cooking_method: Optional[str] = None
    is_vegetarian: Optional[bool] = None
    allergens: Optional[str] = None
    is_available: Optional[bool] = None
    is_featured: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    formatted_price: str = ""
    spice_text: str = ""

class FAQRequest(BaseModel):
    success: bool
    query: str
    suggestions: List[FAQItem]




class ReservationListResponse(BaseModel):
    success: bool
    reservations: List[ReservationItem]
    count: int
    message: str

class MenuListResponse(BaseModel):
    success: bool
    menu_items: List[MenuItem]
    count: int
    message: str


def load_faq_from_redis() -> List[FAQItem]:
    """从redis中读取所有的FAQ数据"""
    client = get_redis_client()
    faq_all_ids = client.smembers("faq:ids")
    full_keys = [f"faq:item:{id}" for id in faq_all_ids]
    pipeline = client.pipeline()
    for key in full_keys:
        pipeline.hgetall(key)
    faq_items = pipeline.execute()
    return [FAQItem(**item) for item in faq_items if item]


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    """提供一个聊天接口"""
    #以流式的方式返回给前端
    session_id = "session_001"
    return StreamingResponse(assistant_query(query=request.query, session_id=session_id), media_type="text/event-stream")



# 提供预定接口
@app.get("/reservation/list", response_model=ReservationListResponse)
def book_endpoint(limit: int = 1):
    """获取所有预定的信息
    """
    sql = """
          select id, \
                 num_people, \
                 num_children, \
                 arrival_time, \
                 seat_preference, \
                 main_dish_preference, \
                 other_comments, \
                 created_at
          from reservation_order \

          """
    with pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", "3307")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"), ) as conn:
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
            item_list = []
            for item in result:
                item_list.append(ReservationItem(
                    id=item['id'],
                    num_people=item['num_people'],
                    num_children=item['num_children'],
                    arrival_time=datetime.strftime(item['arrival_time'], "%Y-%m-%d %H:%M:%S"),
                    seat_preference=item['seat_preference'],
                    main_dish_preference=item['main_dish_preference'],
                    other_comments=item['other_comments'],
                    created_at=datetime.strftime(item['created_at'], "%Y-%m-%d %H:%M:%S")
                ))
            return ReservationListResponse(success=True, reservations=item_list, count=len(item_list),
                                           message="success")

# 提供菜单接口
@app.get("/menu/list", response_model=MenuListResponse)
def menu_endpoint():
    sql = """
        SELECT
        id, dish_name, price, description, category,
        spice_level, flavor, main_ingredients,
        cooking_method,
        is_vegetarian, allergens, is_available
        FROM menu_items
        WHERE is_available = 1
        ORDER BY category, dish_name
          """
    with pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", "3307")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"), ) as conn:
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
            item_list = []
            spice_labels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
            for item in result:
                item_list.append(MenuItem(
                    **item,
                    formatted_price=f"￥{item['price']:.2f}",
                    spice_text=spice_labels.get(item['spice_level'], "未标注"),
                ))
            return MenuListResponse(success=True, menu_items=item_list, count=len(item_list),
                                    message="success")



@app.get("/faq/suggest")
def faq_suggest_endpoint(query:str, limit:int):
    """提供FAQ问题的建议列表"""
    # 1.从redis中获取所有的FAQ数据
    faq_items = load_faq_from_redis()

    # 2.根据用户的问题进行匹配
    scores_list = []
    for faq_items in faq_items:
        score = get_similarity_score(query, faq_items.question) #将用户的问题和FAQ的问题进行相似度计算
        scores_list.append((score, faq_items))  #将得分和FAQ问题进行绑定

    # 3.根据得分进行排序
    scores_list.sort(key=lambda x: x[0], reverse=True)
    limit = 2
    top_k_faq_items = [faq_items for _, faq_items in scores_list[:limit]]

    # 4.返回结果
    return FAQRequest(success=True, query=query, suggestions=top_k_faq_items)


