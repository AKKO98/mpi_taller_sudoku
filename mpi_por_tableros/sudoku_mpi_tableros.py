"""MPI por tableros: cada ID es una tarea que se asigna a un proceso.

El proceso 0 es coordinador (reparte IDs y reúne estados) y además resuelve
tableros: mientras resuelve, un vigilante atiende las peticiones de los demás.
El reparto es dinámico: cada proceso pide un nuevo ID al terminar el anterior.
"""

import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mpi4py import MPI  # noqa: E402

from sudoku import resolver_con_tiempo  # noqa: E402
from sudoku_mpi_comun import (Vigilante, PAUSA_ESPERA, a_celdas, a_tablero,  # noqa: E402
                              crear_parser, es_solucion_valida,
                              esperar_mensaje, imprimir_parcial,
                              imprimir_total, seleccionar)

TAG_PEDIR = 1   # trabajador -> coordinador: resultado anterior (o None)
TAG_TAREA = 2   # coordinador -> trabajador: (indice, celdas) o None (fin)


class Coordinador:
    def __init__(self, comm, seleccionados, solo_id):
        self.comm = comm
        self.seleccionados = seleccionados
        self.solo_id = solo_id
        self.pendientes = deque(range(len(seleccionados)))
        self.resultados = {}
        self.terminados = 0  # trabajadores a los que ya se envió el fin

    def siguiente(self):
        return self.pendientes.popleft() if self.pendientes else None

    def registrar(self, indice, resuelto, segundos, proceso):
        nombre = self.seleccionados[indice][0]
        self.resultados[indice] = (resuelto, segundos)
        imprimir_parcial(nombre, resuelto, segundos, self.solo_id,
                         extra=f" (proceso {proceso})")

    def atender(self):
        """Responde a todas las peticiones pendientes. Siempre devuelve False."""
        estado = MPI.Status()
        while self.comm.Iprobe(MPI.ANY_SOURCE, TAG_PEDIR, estado):
            origen = estado.Get_source()
            mensaje = self.comm.recv(source=origen, tag=TAG_PEDIR)
            if mensaje is not None:
                self.registrar(*mensaje, origen)
            indice = self.siguiente()
            if indice is None:
                self.comm.send(None, dest=origen, tag=TAG_TAREA)
                self.terminados += 1
            else:
                self.comm.send((indice, self.seleccionados[indice][1]),
                               dest=origen, tag=TAG_TAREA)
        return False


def main():
    parser = crear_parser("Sudoku con MPI: un tablero por tarea.")
    args = parser.parse_args()
    seleccionados = seleccionar(parser, args)

    comm = MPI.COMM_WORLD
    rango, tamano = comm.Get_rank(), comm.Get_size()
    comm.Barrier()
    inicio = MPI.Wtime()

    if rango == 0:
        coord = Coordinador(comm, seleccionados, bool(args.id))
        vigilante = Vigilante(coord.atender)
        while True:
            indice = coord.siguiente()
            if indice is None:
                break
            original = seleccionados[indice][1]
            tablero = a_tablero(original)
            inicio_tablero = time.perf_counter()
            resuelto = bool(vigilante.resolver_tablero(tablero))
            segundos = time.perf_counter() - inicio_tablero
            coord.registrar(indice,
                            resuelto and es_solucion_valida(original, a_celdas(tablero)),
                            segundos, 0)
        while coord.terminados < tamano - 1:
            coord.atender()
            time.sleep(PAUSA_ESPERA)
        total = MPI.Wtime() - inicio
        if not args.id:
            suma = sum(s for _, s in coord.resultados.values())
            imprimir_total(total, len(coord.resultados), len(seleccionados), suma)
    else:
        resultado = None
        while True:
            comm.send(resultado, dest=0, tag=TAG_PEDIR)
            mensaje = esperar_mensaje(comm, 0, TAG_TAREA)
            if mensaje is None:
                break
            indice, original = mensaje
            tablero = a_tablero(original)
            resuelto, segundos = resolver_con_tiempo(tablero)
            resultado = (indice,
                         resuelto and es_solucion_valida(original, a_celdas(tablero)),
                         segundos)
    comm.Barrier()


if __name__ == "__main__":
    main()
