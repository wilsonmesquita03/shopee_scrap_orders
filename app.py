from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from main import extrair_pedidos  # seu script separado como módulo

app = FastAPI(title="Shopee Orders API")

class OrdersResponse(BaseModel):
    separacao: List[dict]
    pedidos: List[dict]


@app.get("/orders", response_model=OrdersResponse)
def get_orders():
    lista_separacao, lista_pedidos = extrair_pedidos()

    return {
        "separacao": lista_separacao,
        "pedidos": lista_pedidos
    }