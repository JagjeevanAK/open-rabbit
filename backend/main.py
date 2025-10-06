from fastapi import FastAPI, Query, Request
from pydantic import BaseModel
from typing import Optional
from routes import demo

app = FastAPI()

app.include_router(demo.router)

class User(BaseModel):
    name: str
    age: Optional[int] = None

class PrDetails(BaseModel):
    pass
    
# @app.middleware("http")
# async def log(req: Request, call_next):
#     print("Incoming request:", req.url)
#     response = await call_next(req)
#     return response
    
@app.get('/')
def root():
    return { 'msg': "Hello, World"}

@app.post('/eventCollector')
def Collector(body= PrDetails):
    
    return {"status": "Data recived Successfully"}

@app.get('/healthz')
def health():
    return { "status": "Server is running"}
