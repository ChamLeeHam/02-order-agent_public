from redis import Redis
from dotenv import load_dotenv
import os

load_dotenv()

def redis_command_demo1():
    """每个指令独立"""
    client = Redis.from_url(os.getenv("REDIS_URL"),decode_responses=True)
    if client.ping():
        # set key value
        client.set("test", "test_value")

         # get key
        value = client.get("test")
        print(value)

        # 创建hash结构
        # client.hset("test_hash", "name", "zhangsan")
        client.hset("test_hash", mapping={
            "name":"zhangsan",
            "location":"shanghai",
            "level":2
        })

        # 获取hash结构中的某个字段
        print(client.hgetall("test_hash"))


def redis_command_demo2():

    client = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
    if client.ping():
        # 1.构建管道
        pipe = client.pipeline()

        # 2.打包
        # set key value
        pipe.set("test", "test_value") #该指令不会立马去执行

        # get key
        pipe.get("test") #该指令不会立马去执行


        # 创建hash结构
        # client.hset("test_hash", "name", "zhangsan")
        pipe.hset("test_hash", mapping={
            "name": "zhangsan",
            "location": "shanghai",
            "level": 2
        })

        # 打包：获取hash结构中的某个字段
        pipe.hgetall("test_hash")

        # 执行
        results = pipe.execute()
        print(results)

if __name__ == "__main__":
    redis_command_demo2()



