"""MPI híbrido: IDs repartidos entre grupos de procesos y, dentro de cada
grupo, ramas distintas del tablero asignado a cada miembro.

* Los N procesos se dividen en G = N // g grupos consecutivos (tamaño g; los
  procesos sobrantes se reparten entre los primeros grupos).
* El primer proceso de cada grupo es su líder. El líder del grupo 0 es el
  proceso 0, que además es el coordinador global: reparte los IDs entre los
  líderes (reparto dinámico) y reúne los estados.
* Para cada ID, el líder envía el tablero a su grupo. Todos los miembros
  (líder incluido) generan las mismas ramas y cada uno explora las de
  posición ``i % tamaño == suya``. Quien halla la solución avisa (STOP) al
  resto del grupo; al terminar, cada miembro informa al líder.
"""

import math
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mpi4py import MPI  # noqa: E402

from sudoku_mpi_comun import (Vigilante, PAUSA_ESPERA, a_celdas, a_tablero,  # noqa: E402
                              crear_parser, es_solucion_valida,
                              esperar_mensaje, generar_ramas,
                              imprimir_parcial, imprimir_total, seleccionar)

TAG_PEDIR = 1     # líder -> proceso 0: resultado anterior (o None) = petición
TAG_ASIGNA = 2    # proceso 0 -> líder: (indice, nombre, celdas) o None (fin)
TAG_TRABAJO = 3   # líder -> miembro: (nombre, celdas) o None (fin)
TAG_LISTO = 4     # miembro -> líder: (nombre, solucion o None)
TAG_STOP = 5      # miembro -> compañeros: nombre del tablero resuelto


def formar_grupos(tamano, tam_grupo):
    """Lista de grupos (listas de rangos consecutivos)."""
    cantidad = max(1, tamano // tam_grupo)
    base, extra = divmod(tamano, cantidad)
    grupos, inicio = [], 0
    for i in range(cantidad):
        largo = base + (1 if i < extra else 0)
        grupos.append(list(range(inicio, inicio + largo)))
        inicio += largo
    return grupos


def tam_grupo_por_defecto(tamano):
    """Grupos de tamaño ~ raíz cuadrada de N (equilibra #grupos y #miembros)."""
    return max(1, round(math.sqrt(tamano)))


class Explorador:
    """Explora la parte de las ramas que le toca a un miembro del grupo."""

    def __init__(self, comm, grupo, tareas_por_proceso, atencion_extra=None):
        self.comm = comm
        self.grupo = grupo
        self.posicion = grupo.index(comm.Get_rank())
        self.companeros = [r for r in grupo if r != comm.Get_rank()]
        self.tareas_por_proceso = tareas_por_proceso
        self.atencion_extra = atencion_extra
        self.actual = None
        self.vigilante = Vigilante(self._atencion)

    def _hay_stop(self):
        while self.comm.Iprobe(source=MPI.ANY_SOURCE, tag=TAG_STOP):
            if self.comm.recv(source=MPI.ANY_SOURCE, tag=TAG_STOP) == self.actual:
                return True
        return False

    def _atencion(self):
        if self.atencion_extra is not None:
            self.atencion_extra()
        return self._hay_stop()

    def explorar(self, nombre, celdas):
        """Devuelve la solución (81 enteros) si la encontró este miembro."""
        self.actual = nombre
        tam = len(self.grupo)
        if tam == 1:
            tareas = [list(celdas)]
        else:
            tareas = generar_ramas(celdas, self.tareas_por_proceso * tam)
        for i in range(self.posicion, len(tareas), tam):
            if self._hay_stop():
                return None
            tablero = a_tablero(tareas[i])
            resultado = self.vigilante.resolver_tablero(tablero)
            if resultado:
                for otro in self.companeros:
                    self.comm.send(nombre, dest=otro, tag=TAG_STOP)
                return a_celdas(tablero)
            if resultado is None:
                return None
        return None


def procesar_como_lider(comm, explorador, nombre, celdas, sondear=None):
    """Resuelve un tablero con el grupo. Devuelve (solucion o None, segundos)."""
    inicio = MPI.Wtime()
    for miembro in explorador.companeros:
        comm.send((nombre, celdas), dest=miembro, tag=TAG_TRABAJO)
    solucion = explorador.explorar(nombre, celdas)
    pendientes = set(explorador.companeros)
    estado = MPI.Status()
    while pendientes:
        if comm.Iprobe(MPI.ANY_SOURCE, TAG_LISTO, estado):
            miembro = estado.Get_source()
            _, parcial = comm.recv(source=miembro, tag=TAG_LISTO)
            pendientes.discard(miembro)
            if parcial is not None:
                solucion = parcial
        else:
            if sondear is not None:
                sondear()
            time.sleep(PAUSA_ESPERA)
    return solucion, MPI.Wtime() - inicio


class Coordinador:
    """Reparto global de IDs (proceso 0)."""

    def __init__(self, comm, seleccionados, solo_id):
        self.comm = comm
        self.seleccionados = seleccionados
        self.solo_id = solo_id
        self.pendientes = deque(range(len(seleccionados)))
        self.resultados = {}
        self.terminados = 0

    def siguiente(self):
        return self.pendientes.popleft() if self.pendientes else None

    def registrar(self, indice, resuelto, segundos, grupo):
        nombre = self.seleccionados[indice][0]
        self.resultados[indice] = (resuelto, segundos)
        imprimir_parcial(nombre, resuelto, segundos, self.solo_id,
                         extra=f" (grupo {grupo})")

    def atender(self):
        estado = MPI.Status()
        while self.comm.Iprobe(MPI.ANY_SOURCE, TAG_PEDIR, estado):
            lider = estado.Get_source()
            mensaje = self.comm.recv(source=lider, tag=TAG_PEDIR)
            if mensaje is not None:
                self.registrar(*mensaje)
            indice = self.siguiente()
            if indice is None:
                self.comm.send(None, dest=lider, tag=TAG_ASIGNA)
                self.terminados += 1
            else:
                nombre, celdas = self.seleccionados[indice]
                self.comm.send((indice, nombre, celdas), dest=lider, tag=TAG_ASIGNA)


def main():
    parser = crear_parser("Sudoku con MPI híbrido: grupos de procesos.")
    parser.add_argument("--tam-grupo", type=int, default=None,
                        help="procesos por grupo (por defecto ~ raíz de N)")
    parser.add_argument("--tareas-por-proceso", type=int, default=8,
                        help="mínimo de ramas por miembro del grupo (por defecto: 8)")
    args = parser.parse_args()
    seleccionados = seleccionar(parser, args)

    comm = MPI.COMM_WORLD
    rango, tamano = comm.Get_rank(), comm.Get_size()
    tam_grupo = args.tam_grupo or tam_grupo_por_defecto(tamano)
    if not 1 <= tam_grupo <= tamano:
        parser.error(f"--tam-grupo debe estar entre 1 y N={tamano}")
    grupos = formar_grupos(tamano, tam_grupo)
    numero_grupo = next(i for i, g in enumerate(grupos) if rango in g)
    grupo = grupos[numero_grupo]
    lider = grupo[0]

    comm.Barrier()
    if rango == 0:
        coord = Coordinador(comm, seleccionados, bool(args.id))
        explorador = Explorador(comm, grupo, args.tareas_por_proceso, coord.atender)
        print(f"Procesos: {tamano}; grupos: {len(grupos)} "
              f"(tamaños {[len(g) for g in grupos]})", flush=True)
        inicio = MPI.Wtime()
        while True:
            indice = coord.siguiente()
            if indice is None:
                break
            nombre, celdas = seleccionados[indice]
            solucion, segundos = procesar_como_lider(
                comm, explorador, nombre, celdas, sondear=coord.atender)
            coord.registrar(indice, es_solucion_valida(celdas, solucion),
                            segundos, numero_grupo)
        for miembro in explorador.companeros:
            comm.send(None, dest=miembro, tag=TAG_TRABAJO)
        while coord.terminados < len(grupos) - 1:
            coord.atender()
            time.sleep(PAUSA_ESPERA)
        total = MPI.Wtime() - inicio
        if not args.id:
            suma = sum(s for _, s in coord.resultados.values())
            imprimir_total(total, len(coord.resultados), len(seleccionados), suma)
    elif rango == lider:
        explorador = Explorador(comm, grupo, args.tareas_por_proceso)
        resultado = None
        while True:
            comm.send(resultado, dest=0, tag=TAG_PEDIR)
            mensaje = esperar_mensaje(comm, 0, TAG_ASIGNA)
            if mensaje is None:
                for miembro in explorador.companeros:
                    comm.send(None, dest=miembro, tag=TAG_TRABAJO)
                break
            indice, nombre, celdas = mensaje
            solucion, segundos = procesar_como_lider(comm, explorador, nombre, celdas)
            resultado = (indice, es_solucion_valida(celdas, solucion),
                         segundos, numero_grupo)
    else:
        explorador = Explorador(comm, grupo, args.tareas_por_proceso)
        while True:
            mensaje = esperar_mensaje(comm, lider, TAG_TRABAJO)
            if mensaje is None:
                break
            nombre, celdas = mensaje
            solucion = explorador.explorar(nombre, celdas)
            comm.send((nombre, solucion), dest=lider, tag=TAG_LISTO)
    comm.Barrier()


if __name__ == "__main__":
    main()
