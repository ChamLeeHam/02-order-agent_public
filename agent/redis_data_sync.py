# 实现FAQ数据的同步
# 将FAQ数据同步到Redis中
import sys
from pathlib import Path
from typing import List, Dict

ROOT_PATH = Path(__file__).parent.parent   # 获取项目根目录
sys.path.insert(0, str(ROOT_PATH))   # 将项目的根目录添加到系统环境变量中
from utils.redis_utils import get_redis_client

FAQ_ITEMS: List[Dict[str, str]] = [
{"id": "business_hours", "question": "营业时间是什么时候？", "answer": "我们的营业时间是每天早9点至晚10点。"},
{"id": "address", "question": "位置在哪里？", "answer": "我们位于上海人民广场。"},
{"id": "phone", "question": "联系方式是什么？", "answer": "您可以添加官方微信shanghai_123，或拨打电话 021-11111111。"},
{"id": "parking", "question": "停车方便吗？", "answer": "可优先使用附近公共停车场或路边划线车位；车位实时情况建议电话确认：021-11111111。"},
{"id": "promotion", "question": "有什么优惠活动？", "answer": "优惠活动：单次消费满200九折，满500八折。"},
]
# 1. 菜品数据同步到向量数据库中
def faq_to_redis():
    """将FAQ数据同步到Redis"""
    redis_client = get_redis_client()
    pipeline = redis_client.pipeline()

    all_faq_ids = "faq:ids"   #用来记录所有的FAQ问题的id

    for item in FAQ_ITEMS:
        key = f"faq:item:{item['id']}"
        pipeline.hset(key, mapping={
            "id":item['id'],
            "question":item['question'],
            "answer":item['answer']
        })

        pipeline.sadd(all_faq_ids, item['id'])    #使用set集合存储所有的FAQ的id

    # 执行管道中的所有命令
    pipeline.execute()
    print("FAQ数据同步到Redis成功")



if __name__ == "__main__":
    faq_to_redis()