from http import client

from langchain_huggingface.embeddings import huggingface
from pymilvus import DataType, MilvusClient
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
import os
import torch

load_dotenv()
# 学习如何使用milvus向量数据库
def insert_data():
    # 1.创建向量数据库
    client = MilvusClient(
        uri=os.getenv("MILVUS_URI"),
        token=os.getenv("MILVUS_TOKEN")
    )
    collection_name = os.getenv("MILVUS_COLLECTION")
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)

    # 确定集合中的字段及类型
    schema = MilvusClient.create_schema(auto_id=True)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=768)
    schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=256)

    # 定义索引类型
    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="HNSW",  # 分层导航小世界
        metric_type="IP",  # cosine / ip(内积， 如果embedding模型已经完成了归一化，则建议选择IP效率高)
    )

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )

    # 2. 添加数据

    text = [
        "hello world",
        "how are you?",
        "I am fine, thank you",
        "how old are you ?"
    ]
    # 2.1 生成向量
    embedding = HuggingFaceEmbeddings(
        model_name="./model/bge-base-zh",
        model_kwargs={
            "device": "cuda" if torch.cuda.is_available() else "cpu"
        },
        encode_kwargs={"normalize_embeddings": True}  # 模型进行归一化， 配合IP
    )

    vector_list = embedding.embed_documents(text)
    data_to_insert = [
        {"vector": vec, "text": txt} for vec, txt in zip(vector_list, text)
    ]

    all_ids = client.insert(
        collection_name=collection_name,
        data=data_to_insert
    )
    print(all_ids)

# 3.查询数据
def search_data(query:str):
    client = MilvusClient(
        uri=os.getenv("MILVUS_URI"),
        token=os.getenv("MILVUS_TOKEN")
    )

    embedding = HuggingFaceEmbeddings(
        model_name="./model/bge-base-zh",
        model_kwargs={
            "device": "cuda" if torch.cuda.is_available() else "cpu"
        },
        encode_kwargs={"normalize_embeddings": True}
    )

    vector_query = embedding.embed_query(query)

    # 相似度检索
    search_res = client.search(
        collection_name=os.getenv("MILVUS_COLLECTION"),
        data=[vector_query],
        anns_field="vector",   #指定检索字段
        output_fields=["text"],  #指定输出的字段
        limit=3  #指定输出的条数
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
        return None


if __name__ == "__main__":
    res = search_data("你好吗？")
    print(res)



