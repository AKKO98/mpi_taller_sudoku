"""MPI por ramas: los tableros se resuelven en orden y, dentro de cada uno,
las ramas (opciones válidas de las primeras casillas vacías) se reparten
entre los procesos.

El proceso 0 es coordinador y también explora ramas (un vigilante atiende a
los demás mientras resuelve). Cuando alguien encuentra la solución, el
coordinador avisa (STOP) a los que siguen buscando y no empieza el tablero
siguiente hasta que todos hayan terminado con el actual.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mpi4py import MPI  # noqa: E402

from sudoku_mpi_comun import (Vigilante, PAUSA_ESPERA, a_celdas, a_tablero,  # noqa: E402
                              crear_parser, es_solucion_valida,
                              esperar_mensaje, generar_ramas,
                              imprimir_parcial, imprimir_total, seleccionar)

TAG_TAREA = 1   # coordinador -> trabajador: (id, indice, celdas) o None (fin)
TAG_RESULTADO = 2   # trabajador -> coordinador: (id, indice, solucion o None)
TAG_STOP = 3    # coordinador -> trabajador: id del tablero ya resuelto


class Reparto:
    """Estado del coordinador para el tablero en curso."""

    def __init__(self, comm, min_tareas):
        self.comm = comm
        self.min_tareas = min_tareas

    def iniciar(self, nombre, celdas):
        self.nombre = nombre
        self.tareas = generar_ramas(celdas, self.min_tareas)
        self.siguiente = 0
        self.solucion = None
        self.en_curso = set()

    def tomar(self):
        """Índice de la siguiente rama, o None si no quedan o ya hay solución."""
        if self.solucion is not None or self.siguiente >= len(self.tareas):
            return None
        indice = self.siguiente
        self.siguiente += 1
        return indice

    def despachar(self, trabajador):
        indice = self.tomar()
        if indice is None:
            return
        self.comm.send((self.nombre, indice, self.tareas[indice]),
                       dest=trabajador, tag=TAG_TAREA)
        self.en_curso.add(trabajador)

    def declarar(self, solucion):
        if self.solucion is None:
            self.solucion = solucion
            for trabajador in self.en_curso:
                self.comm.send(self.nombre, dest=trabajador, tag=TAG_STOP)

    def atender(self):
        """Procesa resultados pendientes. True si el tablero ya tiene solución."""
        estado = MPI.Status()
        while self.comm.Iprobe(MPI.ANY_SOURCE, TAG_RESULTADO, estado):
            trabajador = estado.Get_source()
            _, _, solucion = self.comm.recv(source=trabajador, tag=TAG_RESULTADO)
            self.en_curso.discard(trabajador)
            if solucion is not None:
                self.declarar(solucion)
            else:
                self.despachar(trabajador)
        return self.solucion is not None


def hay_stop(comm, nombre):
    """Consume mensajes STOP; True si alguno corresponde al tablero actual."""
    while comm.Iprobe(source=0, tag=TAG_STOP):
        if comm.recv(source=0, tag=TAG_STOP) == nombre:
            return True
    return False


def trabajador(comm):
    actual = [None]
    vigilante = Vigilante(lambda: hay_stop(comm, actual[0]))
    while True:
        mensaje = esperar_mensaje(comm, 0, TAG_TAREA)
        if mensaje is None:
            break
        nombre, indice, celdas = mensaje
        actual[0] = nombre
        tablero = a_tablero(celdas)
        resuelto = vigilante.resolver_tablero(tablero)
        comm.send((nombre, indice, a_celdas(tablero) if resuelto else None),
                  dest=0, tag=TAG_RESULTADO)


def main():
    parser = crear_parser("Sudoku con MPI: ramas de cada tablero en paralelo.")
    parser.add_argument("--tareas-por-proceso", type=int, default=8,
                        help="mínimo de ramas por proceso al dividir un tablero "
                             "(por defecto: 8)")
    args = parser.parse_args()
    seleccionados = seleccionar(parser, args)

    comm = MPI.COMM_WORLD
    rango, tamano = comm.Get_rank(), comm.Get_size()
    if rango != 0:
        comm.Barrier()
        trabajador(comm)
        comm.Barrier()
        return

    reparto = Reparto(comm, max(1, args.tareas_por_proceso * tamano))
    vigilante = Vigilante(reparto.atender)
    solo_id = bool(args.id)
    suma = 0.0
    procesados = 0

    comm.Barrier()
    inicio_total = MPI.Wtime()
    for nombre, original in seleccionados:
        inicio = MPI.Wtime()
        reparto.iniciar(nombre, original)
        for destino in range(1, tamano):
            reparto.despachar(destino)
        while True:
            indice = reparto.tomar()
            if indice is not None:  # el coordinador también explora ramas
                tablero = a_tablero(reparto.tareas[indice])
                if vigilante.resolver_tablero(tablero):
                    reparto.declarar(a_celdas(tablero))
                continue
            if not reparto.en_curso:
                break
            reparto.atender()
            time.sleep(PAUSA_ESPERA)
        segundos = MPI.Wtime() - inicio
        resuelto = es_solucion_valida(original, reparto.solucion)
        suma += segundos
        procesados += 1
        imprimir_parcial(nombre, resuelto, segundos, solo_id)
    total = MPI.Wtime() - inicio_total
    for destino in range(1, tamano):
        comm.send(None, dest=destino, tag=TAG_TAREA)
    if not solo_id:
        imprimir_total(total, procesados, len(seleccionados), suma)
    comm.Barrier()


if __name__ == "__main__":
    main()
