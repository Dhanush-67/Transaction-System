from fastapi import FastAPI

app = FastAPI(title="Inventory Service")

class inventoryResponse(BaseModel):
    item_id: int
    status: str

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/inventory/{item_id}")
def get_inventory(item_id: int):
    return {"item_id": item_id, "status": "retrieved"}

@app.post("/inventory")
def create_inventory(item_id: int):
    return {"item_id": item_id, "status": "created"}




