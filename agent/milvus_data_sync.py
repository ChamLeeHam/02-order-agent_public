# 将各种菜品数据同步到向量库数据中，这样可以从语义层面进行相似度的检索

import pymysql
from langchain_huggingface.embeddings import huggingface
from pymilvus import DataType, MilvusClient
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
import os
import torch
from pymysql.cursors import DictCursor
import sys
from pathlib import Path

ROOT_PATH = Path(__file__).parent.parent #获取项目根目录
sys.path.insert(0, str(ROOT_PATH))  #将项目的根目录添加到系统环境变量中

# 如何引入其他模块的代码，先需要确保这个模块已经添加到项目目录中
from utils.milvus_utils import get_milvus_client, get_embedding


load_dotenv()


# 1.菜品数据同步到向量数据库中
def insert_data():
    # 1.创建向量数据库
    client = get_milvus_client()

    collection_name = os.getenv("MILVUS_COLLECTION")
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)

    # 确定集合中的字段及类型
    schema = MilvusClient.create_schema(auto_id=True)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=768)
    schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=325)

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

    #  select spice_level, case when spice_level =0 then '不辣' when spice_level=1 then '微辣' when spice_level=2 then '中辣' when spice_level=3 then '特辣' end as 辣度 from menu_items;
    main_dishes = []
    sql = """
          SELECT CONCAT(
                         '菜品名称:', IFNULL(menu_items.dish_name, ''), ';',
                         '价格:', IFNULL(menu_items.price, ''), ';',
                         '菜品类别:', IFNULL(menu_items.category, ''), ';',
                         '描述:', IFNULL(menu_items.description, ''), ';',
                         '麻辣程度:',
                         CASE menu_items.spice_level
                             WHEN 0 THEN '不辣'
                             WHEN 1 THEN '微辣'
                             WHEN 2 THEN '中辣'
                             WHEN 3 THEN '特辣'
                             ELSE '无辣'
                         END, ';',
                         '口味:', IFNULL(menu_items.flavor, ''), ';',
                         '主料:', IFNULL(menu_items.main_ingredients, ''), ';',
                         '烹饪方法:', IFNULL(menu_items.cooking_method, ''), ';',
                         '是否素食:',
                         CASE menu_items.is_vegetarian
                                WHEN 0 THEN '否'
                                WHEN 1 THEN '是'
                                ELSE ''
                         END, ';', 
                         '过敏源:', IFNULL(menu_items.allergens, '')
                 ) AS text
          FROM menu_items
          """

    with pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", "3307")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")) as conn:
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
            main_dishes = [row["text"] for row in result]
    print(main_dishes)



    # 2.1 生成向量
    embedding = get_embedding()

    vector_list = embedding.embed_documents(main_dishes)
    data_to_insert = [
        {"vector": vec, "text": txt} for vec, txt in zip(vector_list, main_dishes)
    ]

    all_ids = client.insert(
        collection_name=collection_name,
        data=data_to_insert
    )
    print(all_ids)

if __name__ == "__main__":
    insert_data()




# 2.