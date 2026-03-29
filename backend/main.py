from fastapi import FastAPI

app = FastAPI(title="StockBot API", version="0.1.0")


@app.get("/")
async def root():
    return {"message": "StockBot API"}
