import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from oficio.dominio import Llamada, Mensaje, ModeloCaido

STOCK = {"arroz": 12, "aji": 4, "limon": 0}


class ConsultarStock:
    nombre = "consultar_stock"

    def __init__(self, stock: dict[str, int] | None = None) -> None:
        self.stock = dict(STOCK if stock is None else stock)

    def ejecutar(self, argumentos: dict) -> str:
        sku = str(argumentos.get("sku", "")).strip().lower()
        cantidad = self.stock.get(sku, 0)
        return json.dumps({"sku": sku, "cantidad": cantidad, "conocido": sku in self.stock}, ensure_ascii=False)


class ModeloLocal:
    def __init__(self, skus: list[str]) -> None:
        self.skus = skus

    def completar(self, mensajes: list[Mensaje], herramientas: list[str]) -> Mensaje:
        if not any(mensaje.rol == "tool" for mensaje in mensajes):
            pregunta = next((mensaje.contenido for mensaje in reversed(mensajes) if mensaje.rol == "user"), "")
            sku = next((item for item in self.skus if item in pregunta.lower()), self.skus[0])
            return Mensaje("assistant", "", Llamada("consultar_stock", {"sku": sku}))
        ultimo = next(mensaje.contenido for mensaje in reversed(mensajes) if mensaje.rol == "tool")
        dato = json.loads(ultimo)
        if int(dato.get("cantidad", 0)) > 0:
            return Mensaje("assistant", json.dumps({
                "decision": "PROCEDER",
                "motivo": f"hay {dato['cantidad']} de {dato['sku']}",
            }, ensure_ascii=False))
        return Mensaje("assistant", json.dumps({
            "decision": "RECHAZAR",
            "motivo": f"no hay {dato.get('sku', 'stock')}",
        }, ensure_ascii=False))


class ModeloHttp:
    def __init__(self, base: str, api_key: str, modelo: str = "oficio") -> None:
        self.base = base.rstrip("/")
        self.api_key = api_key
        self.modelo = modelo

    def completar(self, mensajes: list[Mensaje], herramientas: list[str]) -> Mensaje:
        cuerpo = {
            "model": self.modelo,
            "messages": [{"role": mensaje.rol, "content": mensaje.contenido} for mensaje in mensajes if mensaje.llamada is None],
            "tools": [{"type": "function", "function": {"name": nombre}} for nombre in herramientas],
        }
        pedido = Request(
            self.base + "/v1/chat/completions",
            data=json.dumps(cuerpo).encode(),
            headers={"content-type": "application/json", "authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urlopen(pedido, timeout=5) as respuesta:
                crudo = json.loads(respuesta.read().decode())
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ModeloCaido("el modelo no respondió") from error
        mensaje = crudo["choices"][0]["message"]
        llamadas = mensaje.get("tool_calls") or []
        if llamadas:
            funcion = llamadas[0]["function"]
            argumentos = funcion.get("arguments") or "{}"
            if isinstance(argumentos, str):
                argumentos = json.loads(argumentos)
            return Mensaje("assistant", "", Llamada(funcion["name"], argumentos))
        return Mensaje("assistant", str(mensaje.get("content") or ""))
