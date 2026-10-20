# 将后段能力抽象成具体接口供前端调用
import os
import json
import logging
from contextlib import aclosing
from typing import Optional, List

import pymysql
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pymysql.cursors import DictCursor
from starlette.responses import StreamingResponse
from datetime import datetime

from agent.langchain_assistant import assistant_query, delivery

app = FastAPI()

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
        SELECT * FROM menu_items ORDER BY id
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
