"""Mide la versión secuencial y las tres versiones MPI (mediana de k corridas).

Uso (dentro del contenedor, con el mismo N en las tres versiones MPI):

    python /app/medir_comparacion.py --n 8
    python /app/medir_comparacion.py --n 8 --tam-grupo 2 --tam-grupo 4   # variantes del híbrido

Imprime una tabla lista para copiar a INFORME.md. Comprueba además que cada
corrida procesó los 30 IDs y que ninguno quedó "Sin solución".
"""

import argparse
import re
import statistics
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MPIEXEC = ["mpiexec", "--allow-run-as-root", "--use-hwthread-cpus", "--oversubscribe"]


def ejecutar(comando, esperados):
    salida = subprocess.run(comando, capture_output=True, text=True, check=True).stdout
    total = float(re.search(r"Tiempo total: ([0-9.]+) segundos", salida).group(1))
    procesados = re.search(r"IDs procesados: (\d+)/(\d+)", salida)
    if procesados and (int(procesados.group(1)) != esperados):
        sys.exit(f"Se procesaron {procesados.group(1)} IDs en vez de {esperados}")
    if "Sin solución" in salida:
        sys.exit("Algún tablero quedó sin solución")
    if salida.count("Resuelto") != esperados:
        sys.exit(f"Se esperaban {esperados} tableros resueltos")
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, required=True, help="procesos MPI (N calibrado)")
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--tam-grupo", type=int, action="append", default=[],
                        help="tamaño de grupo adicional a medir en el híbrido (repetible)")
    args = parser.parse_args()
    py = sys.executable
    esperados = sum(1 for linea in (RAIZ / "seeds.txt").read_text().splitlines()
                    if linea.strip() and not linea.startswith("#"))
    n = str(args.n)

    casos = [
        ("Secuencial", 1, [py, str(RAIZ / "baseline_secuencial.py"), "--all"]),
        ("MPI por tableros", args.n,
         MPIEXEC + ["-n", n, py, str(RAIZ / "mpi_por_tableros/sudoku_mpi_tableros.py"), "--all"]),
        ("MPI por ramas", args.n,
         MPIEXEC + ["-n", n, py, str(RAIZ / "mpi_por_ramas/sudoku_mpi_ramas.py"), "--all"]),
        ("MPI híbrido (tamaño de grupo por defecto)", args.n,
         MPIEXEC + ["-n", n, py, str(RAIZ / "mpi_hibrido/sudoku_mpi_hibrido.py"), "--all"]),
    ]
    for g in args.tam_grupo:
        casos.append((f"MPI híbrido (grupos de {g})", args.n,
                      MPIEXEC + ["-n", n, py, str(RAIZ / "mpi_hibrido/sudoku_mpi_hibrido.py"),
                                 "--all", "--tam-grupo", str(g)]))

    medianas = {}
    for nombre, procesos, comando in casos:
        tiempos = []
        for k in range(1, args.repeticiones + 1):
            t = ejecutar(comando, esperados)
            tiempos.append(t)
            print(f"{nombre} | corrida {k}: {t:.3f} s", flush=True)
        medianas[nombre] = statistics.median(tiempos)
        print(f"{nombre} | mediana: {medianas[nombre]:.3f} s\n", flush=True)

    base = medianas["Secuencial"]
    print("| Implementación | Procesos | Mediana (s) | Aceleración |")
    print("| --- | ---: | ---: | ---: |")
    for nombre, procesos, _ in casos:
        m = medianas[nombre]
        print(f"| {nombre} | {procesos} | {m:.2f} | {base / m:.2f} |")


if __name__ == "__main__":
    main()
