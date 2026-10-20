import os

import torch
from langchain_huggingface import HuggingFaceEmbeddings
from pymilvus import MilvusClient


def get_milvus_client():
    client = MilvusClient(
        uri=os.getenv("MILVUS_URI"),
        token=os.getenv("MILVUS_TOKEN")
    )
    return client



def get_embedding():
    embedding = HuggingFaceEmbeddings(
        model_name="./model/bge-base-zh",
        model_kwargs={
            "device": "cuda" if torch.cuda.is_available() else "cpu"
        },
        encode_kwargs={"normalize_embeddings": True}  # 模型进行归一化， 配合IP
    )
    return embedding