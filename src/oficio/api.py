from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from oficio.orquestador import Orquestador


class Consulta(BaseModel):
    pregunta: str


def crear_app(orquestador: Orquestador) -> FastAPI:
    app = FastAPI(title="Oficio de la IA")

    @app.get("/salud")
    def salud():
        return {"servicio": "ia-oficio"}

    @app.post("/consultas")
    def consultas(body: Consulta):
        try:
            respuesta = orquestador.atender(body.pregunta)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "decision": respuesta.decision.value,
            "motivo": respuesta.motivo,
            "herramientas": list(respuesta.herramientas),
            "traza": [{"tipo": paso.tipo, "detalle": paso.detalle} for paso in respuesta.traza],
        }

    return app
