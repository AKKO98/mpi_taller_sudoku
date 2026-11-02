# Tarea 2: repartir ramas de cada tablero

Implementación: [`sudoku_mpi_ramas.py`](sudoku_mpi_ramas.py) (usa utilidades de [`../sudoku_mpi_comun.py`](../sudoku_mpi_comun.py) y el resolvedor `../sudoku.py`).

## Cómo funciona

1. Con `--all`, el coordinador (proceso 0) recorre los 30 IDs **en orden**; cada tablero se termina antes de empezar el siguiente.
2. Para cada tablero crea las **ramas**: expande la primera casilla vacía con sus valores válidos (orden 1..9, igual que el backtracking serial) y, si hace falta, las siguientes, hasta tener al menos `8·N` ramas (`--tareas-por-proceso`, por defecto 8). Cada rama es el tablero con esas primeras casillas ya fijadas.
3. Reparto dinámico: se entrega una rama a cada proceso y, cada vez que uno termina, recibe otra. Cada proceso explora su rama con el backtracking de `sudoku.py`.
4. Cuando algún proceso encuentra la solución, se la envía al coordinador y este manda un mensaje **STOP** a los procesos que siguen buscando; un temporizador (SIGALRM, cada 5 ms) revisa ese mensaje, así que abandonan la búsqueda enseguida. No se reparten más ramas de ese tablero.
5. El coordinador espera a que todos hayan respondido, verifica la solución, imprime estado y **tiempo parcial** del ID y pasa al siguiente.
6. El coordinador también explora ramas (el temporizador le permite atender a los demás mientras tanto), así que trabajan los `N` procesos.

El tiempo total es el tiempo real (`MPI.Wtime`) desde que empieza el primer tablero hasta que termina el último. Un tablero sin solución se informa como `Sin solución` (todas las ramas fallan).

## Ejecutar con el contenedor

Reemplaza `N` por el valor calibrado con `detectar_procesos_mpi.py` (el mismo en las tres implementaciones).

**Un tablero (`--id`, por ejemplo el 7)**

```bash
# macOS
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/sudoku_mpi_ramas.py --id 7
```

```powershell
# Windows (PowerShell)
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/sudoku_mpi_ramas.py --id 7
```

**Todos los tableros (`--all`)**

```bash
# macOS
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/sudoku_mpi_ramas.py --all
```

```powershell
# Windows (PowerShell)
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/sudoku_mpi_ramas.py --all
```

## Resultado

Medido con `N = 16` en un Ryzen 7 5700X con 32 GB de RAM (detalle en [`../INFORME.md`](../INFORME.md)): mediana **12,54 s** (12,25 / 12,54 / 12,55 s) frente a 73,35 s de la versión secuencial (aceleración 5,85×). Los 30 IDs quedaron `Resuelto`.
