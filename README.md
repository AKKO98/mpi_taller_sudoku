# Taller: resolver Sudoku y preparar el salto a MPI

Este taller parte de una solución **serial** pequeña, escrita en Python y basada en backtracking. La estructura deja a la vista el trabajo que más adelante se podrá repartir entre procesos con MPI.

## Requisitos

- Docker instalado y en ejecución.

## Ejecutar con el contenedor

Abre una terminal en la carpeta del proyecto. El comando monta esa carpeta en `/app`, donde están `baseline_secuencial.py`, `sudoku.py` y `seeds.txt`. El archivo contiene 30 tableros con IDs del **1 al 30**.

### macOS (Terminal)

```bash
cd /ruta/a/mpi_sudoku_solver
```

Un tablero, por ejemplo el ID 7:

```bash
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 python /app/baseline_secuencial.py --id 7
```

Todos los tableros:

```bash
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 python /app/baseline_secuencial.py --all
```

### Windows (PowerShell)

```powershell
Set-Location C:\ruta\a\mpi_sudoku_solver
```

Un tablero, por ejemplo el ID 7:

```powershell
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 python /app/baseline_secuencial.py --id 7
```

Todos los tableros:

```powershell
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 python /app/baseline_secuencial.py --all
```

Para leer otro archivo ubicado en la carpeta del proyecto, usa su ruta **dentro del contenedor**:

```powershell
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 python /app/baseline_secuencial.py --archivo /app/mis_seeds.txt --id 7
```

La salida muestra el ID y si se resolvió cada tablero; no imprime las respuestas. Con `--id` muestra el tiempo de ese tablero. Con `--all` muestra el **tiempo parcial de cada tablero en cuanto termina** y el **tiempo total** al final. El tiempo total es la suma de los tiempos de búsqueda medidos con `time.perf_counter()`; no incluye lectura del archivo ni impresión de resultados.

Los 30 tableros incluidos tienen solución única. Al seleccionarlos en este contenedor, cada uno tardó aproximadamente entre 2 y 10 segundos con el backtracking serial. Una ejecución completa con `--all` tardó **111,72 segundos**. Los tiempos variarán según el equipo; usa el mismo archivo y entorno al comparar la versión serial con MPI.

## Elegir `N` por equipo

Ejecuta el siguiente comando para determinar el mejor `N` del equipo en que se va a realizar el informe. El programa cuenta números primos como tarea independiente del Sudoku, prueba cada `N` desde 1 hasta `nproc` y mide tres veces cada valor. Copia ese valor en el informe y úsalo en las tres implementaciones MPI; no necesitas calcularlo.

### Windows (PowerShell)

```powershell
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 python /app/detectar_procesos_mpi.py
```

### macOS (Terminal)
```bash
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 python /app/detectar_procesos_mpi.py
```

## Formato de `seeds.txt`

Una semilla por línea: `id|tablero`. El archivo incluido usa los IDs del 1 al 30. El tablero debe tener 81 caracteres entre `1` y `9`, `0` y `.`; estos dos últimos representan casillas vacías. Se ignoran líneas vacías y comentarios que empiezan con `#`.

```text
1|080007020000605080500904000000400009200000000900008004032000000700800000009002168
```

El lector supone que las seeds del archivo tienen el formato indicado y son válidas. Si un tablero no tiene solución, se informa como “Sin solución”.

## Cómo funciona el backtracking

1. Busca la primera casilla vacía.
2. Prueba los valores del 1 al 9 y comprueba fila, columna y bloque 3×3.
3. Se llama a sí misma para continuar con el siguiente espacio.
4. Si una elección lleva a un callejón sin salida, vuelve a dejar la casilla vacía y prueba el siguiente valor.
5. Cuando no hay espacios vacíos, encontró una solución.

## Organización del código

- `baseline_secuencial.py` lee `seeds.txt`, selecciona los IDs, llama al resolvedor y muestra el tiempo parcial de cada tablero y el total.
- `sudoku.py` resuelve un tablero por backtracking y ofrece `resolver_con_tiempo(tablero)`, que devuelve `(resuelto, segundos)`.
- `detectar_procesos_mpi.py` calibra el valor común de `N` con una tarea de conteo de primos.

`resolver()` modifica el tablero recibido. El programa principal hace una copia antes de cada búsqueda para conservar la seed original.

## Tarea por resolver: tres formas de usar MPI

Implementa las tres propuestas en carpetas separadas. Cada carpeta contiene la consigna de su estrategia y debe incluir el código y las instrucciones para ejecutarlo **con el contenedor**:

1. [mpi_por_tableros](mpi_por_tableros/README.md): repartir los IDs entre procesos para resolver los 30 tableros con `--all`.
2. [mpi_por_ramas](mpi_por_ramas/README.md): recorrer los 30 IDs en orden con `--all` y repartir entre procesos las ramas de cada tablero; terminar uno antes de comenzar el siguiente.
3. [mpi_hibrido](mpi_hibrido/README.md): combinar el reparto de IDs con el reparto de ramas dentro de cada tablero.

Entrega también el [informe de resultados](INFORME.md) con los tiempos de la versión secuencial y de las tres implementaciones y conclusiones sustentadas por esas mediciones. Elige **un solo valor de `N` por equipo** con la calibración descrita arriba y usa ese mismo `N` en las tres comparaciones MPI. Agrega `--allow-run-as-root --use-hwthread-cpus --oversubscribe` a `mpiexec` en las tres implementaciones, como en el calibrador. Para MPI, mide el tiempo real desde que empieza el trabajo hasta que llegan todos los resultados; no sumes los tiempos de los procesos como tiempo total.
