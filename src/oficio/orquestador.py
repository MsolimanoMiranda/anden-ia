import json

from oficio.dominio import Decision, Mensaje, Modelo, ModeloCaido, Paso, Politica, Recuperador, Respaldo, Respuesta


class Orquestador:
    def __init__(self, modelo: Modelo, herramientas: dict, politica: Politica, respaldo: Respaldo, recuperador: Recuperador) -> None:
        self.modelo = modelo
        self.herramientas = herramientas
        self.politica = politica
        self.respaldo = respaldo
        self.recuperador = recuperador
        self.max_pasos = 4

    def atender(self, pregunta: str) -> Respuesta:
        texto = pregunta.strip()
        if len(texto) < 3:
            raise ValueError("La consulta es demasiado corta")
        mensajes = [
            Mensaje("system", "Contexto:\n" + "\n".join(self.recuperador.buscar(texto)) + "\nResponde JSON con decision y motivo, o llama una herramienta."),
            Mensaje("user", texto),
        ]
        usadas: list[str] = []
        resultados: list[str] = []
        traza: list[Paso] = []
        permitidas = list(self.herramientas)
        for _ in range(self.max_pasos):
            try:
                salida = self.modelo.completar(mensajes, permitidas)
            except ModeloCaido:
                return self._cerrar(texto, resultados, traza + [Paso("respaldo", "el modelo no respondió")])
            if salida.llamada:
                nombre = salida.llamada.nombre
                if nombre not in self.herramientas:
                    traza.append(Paso("politica", f"herramienta no permitida: {nombre}"))
                    mensajes.append(Mensaje("tool", f"herramienta no permitida: {nombre}"))
                    continue
                crudo = self.herramientas[nombre].ejecutar(salida.llamada.argumentos)
                usadas.append(nombre)
                resultados.append(crudo)
                traza.append(Paso("herramienta", f"{nombre} {salida.llamada.argumentos} -> {crudo}"))
                mensajes.append(Mensaje("tool", crudo))
                continue
            leido = _leer(salida.contenido)
            if leido is None:
                traza.append(Paso("politica", "la salida no es JSON"))
                mensajes.append(Mensaje("user", "Responde solo JSON con decision y motivo."))
                continue
            decision, motivo = leido
            final, motivo_final = self.politica.ajustar(decision, motivo, usadas, resultados)
            traza.append(Paso("modelo", motivo))
            if final != decision:
                traza.append(Paso("politica", motivo_final))
            return Respuesta(final, motivo_final, tuple(usadas), tuple(traza))
        return self._cerrar(texto, resultados, traza + [Paso("politica", "se acabó el presupuesto de pasos")])

    def _cerrar(self, pregunta: str, resultados: list[str], traza: list[Paso]) -> Respuesta:
        decision, motivo = self.respaldo.decidir(pregunta, resultados)
        return Respuesta(decision, motivo, tuple(nombre for nombre in dict.fromkeys(
            paso.detalle.split(" ", 1)[0] for paso in traza if paso.tipo == "herramienta"
        )), tuple(traza + [Paso("respaldo", motivo)]))


def _leer(contenido: str) -> tuple[Decision, str] | None:
    try:
        dato = json.loads(contenido)
        return Decision(str(dato["decision"])), str(dato["motivo"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
