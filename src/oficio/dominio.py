import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Decision(str, Enum):
    PROCEDER = "PROCEDER"
    REVISAR = "REVISAR"
    RECHAZAR = "RECHAZAR"


class ModeloCaido(Exception):
    pass


@dataclass(frozen=True)
class Llamada:
    nombre: str
    argumentos: dict


@dataclass(frozen=True)
class Mensaje:
    rol: str
    contenido: str
    llamada: Llamada | None = None


@dataclass(frozen=True)
class Paso:
    tipo: str
    detalle: str


@dataclass(frozen=True)
class Respuesta:
    decision: Decision
    motivo: str
    herramientas: tuple[str, ...]
    traza: tuple[Paso, ...]


class Modelo(Protocol):
    def completar(self, mensajes: list[Mensaje], herramientas: list[str]) -> Mensaje: ...


class Herramienta(Protocol):
    nombre: str

    def ejecutar(self, argumentos: dict) -> str: ...


NOTAS = (
    "Un pedido urgente puede salir hoy solo si consultar_stock devuelve cantidad mayor que cero.",
    "Si la cantidad es cero, no se promete entrega.",
    "El modelo no inventa cantidades. La cifra válida es la de la herramienta.",
)


class Recuperador:
    def __init__(self, notas: tuple[str, ...] = NOTAS) -> None:
        self.notas = notas

    def buscar(self, pregunta: str) -> list[str]:
        palabras = set(pregunta.lower().split())
        puntuadas = []
        for nota in self.notas:
            cruce = palabras & set(nota.lower().split())
            puntuadas.append((len(cruce), nota))
        puntuadas.sort(key=lambda item: item[0], reverse=True)
        return [nota for _, nota in puntuadas[:2]]


class Politica:
    def ajustar(self, decision: Decision, motivo: str, usadas: list[str], resultados: list[str]) -> tuple[Decision, str]:
        cantidades = _cantidades(resultados)
        if decision == Decision.PROCEDER and "consultar_stock" not in usadas:
            return Decision.REVISAR, "nadie consultó el stock"
        if decision == Decision.PROCEDER and cantidades and max(cantidades) <= 0:
            return Decision.RECHAZAR, "no hay stock"
        return decision, motivo


class Respaldo:
    def decidir(self, pregunta: str, resultados: list[str]) -> tuple[Decision, str]:
        cantidades = _cantidades(resultados)
        if cantidades and max(cantidades) <= 0:
            return Decision.RECHAZAR, "el respaldo vio stock en cero"
        if "urgente" in pregunta.lower() and any(cantidad > 0 for cantidad in cantidades):
            return Decision.PROCEDER, "el respaldo encontró stock y el pedido es urgente"
        return Decision.REVISAR, "sin modelo fiable, lo mira una persona"


def _cantidades(resultados: list[str]) -> list[int]:
    halladas = []
    for texto in resultados:
        try:
            dato = json.loads(texto)
        except json.JSONDecodeError:
            continue
        if "cantidad" in dato:
            halladas.append(int(dato["cantidad"]))
    return halladas
