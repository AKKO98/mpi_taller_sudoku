"""Utilidades compartidas por las tres implementaciones MPI del taller.

Idea central: TODOS los procesos resuelven Sudokus (también el proceso 0, que
además hace de coordinador). Para que el coordinador pueda atender mensajes
mientras resuelve, el resolvedor original de ``sudoku.py`` (sin modificar) se
ejecuta bajo un ``Vigilante``: un temporizador (SIGALRM) que cada pocos
milisegundos llama a una función de atención. Esa función puede, por ejemplo,
repartir tareas a otros procesos o pedir que se abandone la búsqueda actual.
"""

import argparse
import atexit
import signal
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from baseline_secuencial import leer_seeds  # noqa: E402
from sudoku import puede_colocar, resolver  # noqa: E402

PAUSA_ESPERA = 0.0005  # segundos entre sondeos cuando un proceso está ocioso
INTERVALO_VIGILANTE = 0.005  # segundos entre llamadas del vigilante


# --------------------------------------------------------------------------
# Conversión y verificación de tableros
# --------------------------------------------------------------------------
def a_tablero(celdas):
    """Lista de 81 enteros -> matriz 9x9 (copia)."""
    return [list(celdas[i:i + 9]) for i in range(0, 81, 9)]


def a_celdas(tablero):
    """Matriz 9x9 -> lista de 81 enteros."""
    return [v for fila in tablero for v in fila]


def es_solucion_valida(original, solucion):
    """True si ``solucion`` (81 enteros) respeta las pistas y las reglas."""
    if solucion is None or len(solucion) != 81:
        return False
    if any(o != 0 and o != s for o, s in zip(original, solucion)):
        return False
    esperado = set(range(1, 10))
    for i in range(9):
        if set(solucion[i * 9:(i + 1) * 9]) != esperado:
            return False
        if set(solucion[i::9]) != esperado:
            return False
    for bf in range(0, 9, 3):
        for bc in range(0, 9, 3):
            bloque = {solucion[(bf + f) * 9 + bc + c]
                      for f in range(3) for c in range(3)}
            if bloque != esperado:
                return False
    return True


# --------------------------------------------------------------------------
# Generación de ramas (tareas)
# --------------------------------------------------------------------------
def generar_ramas(celdas, minimo):
    """Divide un tablero en ramas independientes.

    Se expande, nivel a nivel, la primera casilla vacía de cada rama con sus
    valores válidos (en el orden 1..9 del backtracking serial) hasta tener al
    menos ``minimo`` ramas. Cada rama es un tablero de 81 enteros con las
    primeras casillas vacías ya fijadas. Una lista vacía significa que el
    tablero no tiene solución.
    """
    frontera = [list(celdas)]
    while len(frontera) < minimo:
        nueva = []
        expandido = False
        for rama in frontera:
            if 0 not in rama:
                nueva.append(rama)
                continue
            expandido = True
            pos = rama.index(0)
            fila, columna = divmod(pos, 9)
            tablero = a_tablero(rama)
            for valor in range(1, 10):
                if puede_colocar(tablero, fila, columna, valor):
                    hija = list(rama)
                    hija[pos] = valor
                    nueva.append(hija)
        frontera = nueva
        if not expandido:
            break
    return frontera


# --------------------------------------------------------------------------
# Vigilante: ejecuta el resolvedor original con atención periódica
# --------------------------------------------------------------------------
class _Abandonar(Exception):
    """Se lanza desde el temporizador para abandonar la búsqueda actual."""


class Vigilante:
    """Ejecuta ``sudoku.resolver`` llamando a ``atencion()`` periódicamente.

    ``atencion()`` devuelve True para pedir que se abandone la búsqueda.
    ``resolver_tablero`` devuelve True (resuelto), False (sin solución en esa
    rama) o None (abandonado por petición de ``atencion``).
    """

    def __init__(self, atencion, intervalo=INTERVALO_VIGILANTE):
        self.atencion = atencion
        self.intervalo = intervalo
        self.activo = False
        self.en_atencion = False  # evita que el manejador se anide a sí mismo
        if atencion is not None:
            signal.signal(signal.SIGALRM, self._manejador)
            signal.siginterrupt(signal.SIGALRM, False)  # reintentar syscalls
            atexit.register(signal.setitimer, signal.ITIMER_REAL, 0)

    @staticmethod
    def _dentro_del_resolvedor(marco):
        """True si el código interrumpido está dentro de sudoku.resolver."""
        while marco is not None:
            if marco.f_code is resolver.__code__:
                return True
            marco = marco.f_back
        return False

    def _manejador(self, _senal, marco):
        # Solo se actúa mientras se ejecuta el resolvedor: así la excepción
        # nunca sale en medio de la lógica del programa ni impide desarmar
        # el temporizador.
        if (self.en_atencion or not self.activo
                or not self._dentro_del_resolvedor(marco)):
            return
        self.en_atencion = True
        try:
            abandonar = self.atencion()
        finally:
            self.en_atencion = False
        if abandonar:
            self.activo = False
            raise _Abandonar()

    def resolver_tablero(self, tablero):
        if self.atencion is None:
            return resolver(tablero)
        self.activo = True
        signal.setitimer(signal.ITIMER_REAL, self.intervalo, self.intervalo)
        try:
            return resolver(tablero)
        except _Abandonar:
            # Si justo se completó el tablero, es una solución válida.
            return True if all(v != 0 for fila in tablero for v in fila) \
                else None
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            self.activo = False


def esperar_mensaje(comm, origen, etiqueta, estado=None, sondear=None):
    """Espera un mensaje sin consumir CPU (sondeo con pausas cortas).

    ``sondear`` es una función opcional que se llama en cada vuelta (el
    coordinador la usa para seguir atendiendo peticiones mientras espera).
    """
    from mpi4py import MPI
    while not comm.Iprobe(source=origen, tag=etiqueta, status=estado):
        if sondear is not None:
            sondear()
        time.sleep(PAUSA_ESPERA)
    if estado is not None and origen == MPI.ANY_SOURCE:
        origen = estado.Get_source()
    return comm.recv(source=origen, tag=etiqueta)


# --------------------------------------------------------------------------
# Línea de comandos y salida
# --------------------------------------------------------------------------
def crear_parser(descripcion):
    parser = argparse.ArgumentParser(description=descripcion)
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt",
                        help="archivo de seeds (por defecto: seeds.txt del proyecto)")
    seleccion = parser.add_mutually_exclusive_group()
    seleccion.add_argument("--id", "--seed", dest="id",
                           help="resolver solo la seed con este ID")
    seleccion.add_argument("--all", action="store_true",
                           help="resolver todos los seeds (por defecto)")
    return parser


def seleccionar(parser, args):
    """Devuelve la lista [(id, [81 enteros]), ...] según --id / --all."""
    try:
        seeds = leer_seeds(args.archivo)
    except OSError as error:
        parser.error(f"no se pudo leer {args.archivo}: {error}")
    if not seeds:
        parser.error(f"no se encontraron seeds en {args.archivo}")
    if args.id:
        if args.id not in seeds:
            parser.error(f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}")
        nombres = [args.id]
    else:
        nombres = list(seeds)
    return [(n, a_celdas(seeds[n])) for n in nombres]


def imprimir_parcial(nombre, resuelto, segundos, solo_id, extra=""):
    etiqueta = "Tiempo" if solo_id else "Tiempo parcial"
    print(f"\nID: {nombre}")
    print("Resuelto" if resuelto else "Sin solución")
    print(f"{etiqueta}: {segundos:.6f} segundos{extra}", flush=True)


def imprimir_total(total, procesados, esperados, suma_individual):
    print(f"\nTiempo total: {total:.6f} segundos")
    print(f"IDs procesados: {procesados}/{esperados}")
    print(f"(informativo) suma de tiempos individuales: {suma_individual:.6f} segundos",
          flush=True)
