import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from fastapi.testclient import TestClient

from oficio.adaptadores import ConsultarStock, ModeloHttp, ModeloLocal
from oficio.api import crear_app
from oficio.dominio import Decision, Llamada, Mensaje, ModeloCaido, Politica, Recuperador, Respaldo
from oficio.orquestador import Orquestador


def armar(modelo, stock=None):
    herramienta = ConsultarStock(stock)
    return Orquestador(modelo, {herramienta.nombre: herramienta}, Politica(), Respaldo(), Recuperador())


def test_el_modelo_local_consulta_el_stock_antes_de_proceder():
    respuesta = armar(ModeloLocal(["arroz", "aji", "limon"])).atender("¿hay arroz para el pedido urgente?")
    assert respuesta.decision == Decision.PROCEDER
    assert respuesta.herramientas == ("consultar_stock",)
    assert any(paso.tipo == "herramienta" and "arroz" in paso.detalle for paso in respuesta.traza)


def test_proceder_sin_herramienta_lo_baja_la_politica():
    class Directo:
        def completar(self, mensajes, herramientas):
            return Mensaje("assistant", json.dumps({"decision": "PROCEDER", "motivo": "hay 99 seguros"}))

    respuesta = armar(Directo()).atender("entrega hoy el arroz")
    assert respuesta.decision == Decision.REVISAR
    assert respuesta.motivo == "nadie consultó el stock"


def test_una_herramienta_fuera_de_la_lista_no_se_ejecuta():
    class Intrusa:
        def __init__(self):
            self.veces = 0

        def completar(self, mensajes, herramientas):
            self.veces += 1
            if self.veces == 1:
                return Mensaje("assistant", "", Llamada("borrar_cuentas", {"todo": True}))
            return Mensaje("assistant", json.dumps({"decision": "PROCEDER", "motivo": "listo"}))

    respuesta = armar(Intrusa()).atender("borra todo y entrega")
    assert respuesta.decision == Decision.REVISAR
    assert any("borrar_cuentas" in paso.detalle for paso in respuesta.traza)
    assert respuesta.herramientas == ()


def test_stock_en_cero_no_se_promete():
    respuesta = armar(ModeloLocal(["limon"]), {"limon": 0}).atender("¿hay limon?")
    assert respuesta.decision == Decision.RECHAZAR


def test_el_presupuesto_de_pasos_corta_el_bucle():
    class Insistente:
        def completar(self, mensajes, herramientas):
            return Mensaje("assistant", "", Llamada("consultar_stock", {"sku": "arroz"}))

    respuesta = armar(Insistente()).atender("sigue preguntando el arroz")
    assert respuesta.decision == Decision.REVISAR
    assert any("presupuesto" in paso.detalle for paso in respuesta.traza)


def test_si_el_modelo_cae_entra_el_respaldo():
    class Caido:
        def completar(self, mensajes, herramientas):
            raise ModeloCaido("timeout")

    respuesta = armar(Caido()).atender("pedido urgente de arroz")
    assert respuesta.decision == Decision.REVISAR
    assert any(paso.tipo == "respaldo" for paso in respuesta.traza)


def test_el_adaptador_http_lee_una_tool_call():
    cuerpo = json.dumps({
        "choices": [{
            "message": {
                "tool_calls": [{
                    "function": {"name": "consultar_stock", "arguments": "{\"sku\":\"aji\"}"},
                }],
            },
        }],
    }).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        modelo = ModeloHttp(f"http://127.0.0.1:{server.server_address[1]}", "demo")
        mensaje = modelo.completar([Mensaje("user", "aji")], ["consultar_stock"])
        assert mensaje.llamada == Llamada("consultar_stock", {"sku": "aji"})
    finally:
        server.shutdown()


def test_la_api_devuelve_la_traza():
    client = TestClient(crear_app(armar(ModeloLocal(["arroz"]))))
    assert client.get("/salud").json()["servicio"] == "ia-oficio"
    corto = client.post("/consultas", json={"pregunta": "ok"})
    assert corto.status_code == 422
    respuesta = client.post("/consultas", json={"pregunta": "¿hay arroz?"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["decision"] == "PROCEDER"
    assert "consultar_stock" in cuerpo["herramientas"]
    assert cuerpo["traza"]
