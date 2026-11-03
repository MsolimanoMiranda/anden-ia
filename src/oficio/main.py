import os

import uvicorn

from oficio.adaptadores import ConsultarStock, ModeloHttp, ModeloLocal
from oficio.api import crear_app
from oficio.dominio import Politica, Recuperador, Respaldo
from oficio.orquestador import Orquestador


def construir() -> Orquestador:
    stock = ConsultarStock()
    url = os.environ.get("ANDEN_MODELO_URL", "").strip()
    if url:
        modelo = ModeloHttp(url, os.environ.get("ANDEN_MODELO_KEY", "demo"))
    else:
        modelo = ModeloLocal(list(stock.stock))
    return Orquestador(modelo, {stock.nombre: stock}, Politica(), Respaldo(), Recuperador())


app = crear_app(construir())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "3048")))
