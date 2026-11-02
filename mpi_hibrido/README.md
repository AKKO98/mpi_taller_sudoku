# Tarea 3: combinar tableros y ramas

Implementación: [`sudoku_mpi_hibrido.py`](sudoku_mpi_hibrido.py) (usa [`../sudoku_mpi_comun.py`](../sudoku_mpi_comun.py) y `../sudoku.py`).

## Cómo funciona

- Los `N` procesos se dividen en `G = N // g` **grupos** de `g` procesos consecutivos (si sobran, se reparten entre los primeros grupos).
- El primer proceso de cada grupo es su **líder**. El proceso 0 es líder del grupo 0 y además **coordinador global**: reparte los IDs dinámicamente entre los líderes (cada líder pide uno al terminar el anterior) y reúne los estados.
- Dentro de un grupo, el líder envía el tablero a los miembros; todos generan las mismas ramas (`8·g` como mínimo, ver `--tareas-por-proceso`) y cada miembro explora las que le tocan (`rama i` → miembro `i mod g`). Quien encuentra la solución manda **STOP** a sus compañeros de grupo, que abandonan la búsqueda; al terminar, cada miembro informa al líder y este reporta el resultado al coordinador.
- Todos los procesos trabajan (también líderes y coordinador; el proceso 0 atiende peticiones con un temporizador mientras explora).
- Con `g = 1` el híbrido equivale a repartir tableros; con `g = N`, a repartir ramas. El tiempo total es el tiempo real desde el inicio del reparto hasta que llegan los 30 resultados.

## Cómo elegir el tamaño de los grupos

- Repartir **tableros** casi no tiene sobrecoste (no hay trabajo repetido), pero depende de que haya suficientes tableros para ocupar a todos y deja desequilibrio al final (el último tablero lo resuelve un solo proceso, 2–10 s). Repartir **ramas** equilibra el final, pero con solución única hay búsqueda descartada y comunicación por cada tablero.
- Regla por defecto: `g = round(√N)`, que da `G ≈ g` (p. ej. `N = 9` → 3 grupos de 3; `N = 16` → 4 grupos de 4): suficientes grupos para repartir los 30 IDs y suficientes miembros por grupo para acortar la cola. Se puede cambiar con `--tam-grupo g`.
- Verificación medida (N = 16, una ejecución por configuración): `g = 2` → 13,45 s; `g = 4` (por defecto) → 13,00 s; `g = 8` → 11,80 s; para comparar, `g = 1` (por tableros) → 15,75 s y `g = 16` (por ramas) → 12,54 s. En esta máquina convino más agrupar (g = 8), aunque la diferencia con g = 4 y con «por ramas» es pequeña y conviene repetirla con `medir_comparacion.py --n 16 --tam-grupo 2 --tam-grupo 8`.

## Ejecutar con el contenedor

Reemplaza `N` por el valor calibrado con `detectar_procesos_mpi.py` (el mismo en las tres implementaciones).

**Todos los tableros (tamaño de grupo por defecto)**

```bash
# macOS
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/sudoku_mpi_hibrido.py --all
```

```powershell
# Windows (PowerShell)
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/sudoku_mpi_hibrido.py --all
```

**Tamaño de grupo explícito (por ejemplo 2)**

```bash
# macOS
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/sudoku_mpi_hibrido.py --all --tam-grupo 2
```

```powershell
# Windows (PowerShell)
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/sudoku_mpi_hibrido.py --all --tam-grupo 2
```

**Un tablero (ID 7)**

```bash
# macOS
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/sudoku_mpi_hibrido.py --id 7
```

```powershell
# Windows (PowerShell)
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/sudoku_mpi_hibrido.py --id 7
```

## Resultado

Medido con `N = 16` en un Ryzen 7 5700X con 32 GB de RAM (detalle en [`../INFORME.md`](../INFORME.md)), una ejecución por configuración: grupos de 2 → 13,45 s; grupos de 4 (por defecto) → **13,00 s** (5,64× frente a 73,35 s); grupos de 8 → **11,80 s** (6,22×). Los 30 IDs quedaron `Resuelto`.
