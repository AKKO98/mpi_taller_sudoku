# Tarea 1: repartir tableros

Implementación: [`sudoku_mpi_tableros.py`](sudoku_mpi_tableros.py). Cada ID es una tarea independiente; se reutiliza sin cambios el resolvedor de `../sudoku.py` (`resolver_con_tiempo`).

## Cómo funciona

- El proceso 0 es el **coordinador**: lleva la cola de IDs, reparte y reúne los estados (`Resuelto` / `Sin solución`, tiempo de cada tablero y proceso que lo resolvió).
- El reparto es **dinámico**: cada proceso pide un ID al terminar el anterior. Así los tableros rápidos y lentos (2–10 s) se equilibran solos, sin asignaciones fijas.
- El coordinador **también resuelve tableros**: mientras lo hace, un temporizador (SIGALRM, cada 5 ms) atiende las peticiones de los demás, de modo que los `N` procesos trabajan y ninguno queda dedicado solo a repartir.
- Cada solución se verifica (pistas respetadas y filas/columnas/bloques completos) antes de informar `Resuelto`.
- El tiempo total es el **tiempo real** (`MPI.Wtime`) desde el inicio del reparto hasta que el coordinador recibe el último resultado. Al final se imprime `IDs procesados: 30/30`.

## Ejecutar con el contenedor

Reemplaza `N` por el valor calibrado con `detectar_procesos_mpi.py` (el mismo en las tres implementaciones).

**Todos los tableros (30 IDs)**

```bash
# macOS
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/sudoku_mpi_tableros.py --all
```

```powershell
# Windows (PowerShell)
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/sudoku_mpi_tableros.py --all
```

**Un tablero (ID 7)**

```bash
# macOS
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/sudoku_mpi_tableros.py --id 7
```

```powershell
# Windows (PowerShell)
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/sudoku_mpi_tableros.py --id 7
```

Salida de `--all`: por cada ID, su estado y `Tiempo parcial`; al final `Tiempo total`, `IDs procesados: 30/30` y (solo informativo) la suma de tiempos individuales.

## Resultado

Medido con `N = 16` en un Ryzen 7 5700X con 32 GB de RAM (detalle en [`../INFORME.md`](../INFORME.md)): mediana de 3 corridas **15,75 s** (15,75 / 16,32 / 14,40 s) frente a 73,35 s de la versión secuencial (aceleración 4,66×). Se procesaron los 30 IDs, todos `Resuelto`.
