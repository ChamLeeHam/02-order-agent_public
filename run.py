import uvicorn  # 是一个ASGI服务器，用于运行我们的FastAPI应用


if __name__ == "__main__":
    # 在api目录下有个main模块，该模块有一个app实例
    uvicorn.run("api.main:app", host="0.0.0.0", port=8080, reload=True)