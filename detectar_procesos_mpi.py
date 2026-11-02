"""Mide una tarea MPI con N creciente y elige el N más rápido."""

import argparse
from math import isqrt
from pathlib import Path
import statistics
import subprocess
import sys
import time


def es_primo(numero):
    """Comprueba si un número impar mayor que 2 es primo."""
    for divisor in range(3, isqrt(numero) + 1, 2):
        if numero % divisor == 0:
            return False
    return True


def contar_primos_en_mpi(limite):
    from mpi4py import MPI

    comunicador = MPI.COMM_WORLD
    parcial = 1 if comunicador.rank == 0 else 0  # El número 2 es primo.
    for numero in range(3 + 2 * comunicador.rank, limite + 1,
                        2 * comunicador.size):
        if es_primo(numero):
            parcial += 1

    total = comunicador.reduce(parcial, op=MPI.SUM, root=0)
    if comunicador.rank == 0:
        print(total)


def calibrar(limite, repeticiones):
    maximo_n = int(subprocess.check_output(["nproc"], text=True).strip())
    mejor_n = None
    mejor_tiempo = float("inf")
    total_esperado = None
    programa = str(Path(__file__).resolve())
    base = ["mpiexec", "--allow-run-as-root", "--use-hwthread-cpus",
            "--oversubscribe"]

    unidad = "medición" if repeticiones == 1 else "mediciones"
    print(f"Tarea: contar primos hasta {limite}; {repeticiones} {unidad} por N.")
    print(f"Se probará desde N=1 hasta nproc={maximo_n}.\n", flush=True)

    for n in range(1, maximo_n + 1):
        prueba = subprocess.run(base + ["-n", str(n), "/bin/true"],
                                capture_output=True, text=True)
        if prueba.returncode != 0:
            print(f"N={n}: rechazado por MPI.", flush=True)
            continue

        tiempos = []
        for numero in range(1, repeticiones + 1):
            comando = base + ["-n", str(n), sys.executable, programa,
                              "--trabajo", "--limite", str(limite)]
            print(f"N={n}, medición {numero}: contando...", flush=True)
            inicio = time.perf_counter()
            resultado = subprocess.run(comando, capture_output=True, text=True)
            segundos = time.perf_counter() - inicio
            if resultado.returncode != 0:
                print(resultado.stderr.strip() or resultado.stdout.strip())
                sys.exit(f"Falló la tarea con N={n}.")
            total = int(resultado.stdout.strip())
            if total_esperado is None:
                total_esperado = total
            elif total != total_esperado:
                sys.exit(f"Resultado distinto con N={n}: {total} en vez de {total_esperado}.")
            tiempos.append(segundos)
            print(f"N={n}, medición {numero}: {total} primos, "
                  f"tiempo {segundos:.3f} s", flush=True)

        mediana = statistics.median(tiempos)
        print(f"N={n}, mediana: {mediana:.3f} s\n", flush=True)
        if mediana < mejor_tiempo:
            mejor_n = n
            mejor_tiempo = mediana

    if mejor_n is None:
        sys.exit("MPI no aceptó ningún valor de N.")
    print(f"\nN RECOMENDADO: {mejor_n}")
    print(f"Tiempo mediano: {mejor_tiempo:.3f} s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limite", type=int, default=2000000,
                        help="buscar primos hasta este número (por defecto: 2000000)")
    parser.add_argument("--repeticiones", type=int, default=3,
                        help="mediciones por cada N aceptado (por defecto: 3)")
    parser.add_argument("--trabajo", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.limite < 2:
        parser.error("--limite debe ser al menos 2")
    if args.repeticiones < 1:
        parser.error("--repeticiones debe ser al menos 1")

    if args.trabajo:
        contar_primos_en_mpi(args.limite)
    else:
        calibrar(args.limite, args.repeticiones)


if __name__ == "__main__":
    main()
