# Informe de resultados

## Entorno

- Equipo: PC con procesador **AMD Ryzen 7 5700X** (8 núcleos físicos / 16 hilos) y **32 GB de RAM**
- Versión del contenedor: `augustosalazar/slim-mpi:2` (Python 3.8, OpenMPI con `mpiexec`)
- Cantidad de repeticiones por medición: 3
- Valor común de `N` elegido: **16** (resultado de `detectar_procesos_mpi.py`; `nproc` = 16)

### Calibración de `N`

Mediana de 3 mediciones del conteo de primos hasta 2 000 000:

| N | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Mediana (s) | 3,764 | 2,116 | 2,124 | 1,391 | 1,376 | 1,452 | 1,133 | 1,052 |

| N | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Mediana (s) | 1,289 | 1,147 | 1,028 | 1,223 | 0,993 | 1,027 | 1,320 | **0,989** |

**N recomendado: 16** (0,989 s). De N = 8 a N = 16 la mejora es pequeña (1,052 s → 0,989 s), coherente con tener 8 núcleos físicos y 16 hilos: los hilos adicionales aportan poco rendimiento. Se usa `N = 16` en las tres comparaciones, como indica el taller.

## Comparación final con el mismo `N`

Mediana de tres ejecuciones de `--all` (30 IDs), obtenidas con `medir_comparacion.py --n 16 --tam-grupo 2 --tam-grupo 8`. Todas las filas MPI usan `N = 16` y `mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe`. En todas las ejecuciones se procesaron los 30 IDs y los 30 quedaron `Resuelto` (el programa de medición lo comprueba y se detendría con error en caso contrario). Estas mediciones se hicieron con el código corregido del temporizador (ver nota al final) y las 18 corridas terminaron sin errores.

| Implementación | Caso | Procesos | Mediana del tiempo total (s) | Aceleración frente a secuencial |
| --- | --- | ---: | ---: | ---: |
| Secuencial | Todos los IDs | 1 | 73,04 | 1,00 |
| MPI por tableros | Todos los IDs | 16 | 14,85 | 4,92 |
| MPI por ramas | Todos los IDs, uno después de otro | 16 | 12,69 | 5,76 |
| MPI híbrido (grupos de 4, por defecto) | Todos los IDs | 16 | 13,10 | 5,58 |

Aceleración = tiempo secuencial / tiempo MPI. El tiempo MPI es tiempo real (`MPI.Wtime`) desde el inicio del reparto hasta recibir todos los resultados; no se suman tiempos de procesos. El tiempo secuencial es la suma de los tiempos de búsqueda de `baseline_secuencial.py --all`.

Corridas individuales (s):

| Implementación | Corrida 1 | Corrida 2 | Corrida 3 | Mediana |
| --- | ---: | ---: | ---: | ---: |
| Secuencial | 72,44 | 73,28 | 73,04 | 73,04 |
| MPI por tableros | 16,62 | 14,85 | 14,82 | 14,85 |
| MPI por ramas | 12,89 | 12,46 | 12,69 | 12,69 |
| MPI híbrido, grupos de 4 (4 grupos, por defecto) | 13,10 | 12,97 | 13,17 | 13,10 |

### Tamaño de grupo en el híbrido

Con 16 procesos, el tamaño de grupo `g` define `16/g` grupos. Los extremos coinciden con las otras estrategias: `g = 1` es repartir tableros y `g = 16` es repartir ramas.

| Configuración | Grupos | Corridas (s) | Mediana (s) | Aceleración |
| --- | ---: | --- | ---: | ---: |
| Grupos de 1 (= por tableros) | 16 | 16,62 / 14,85 / 14,82 | 14,85 | 4,92 |
| Grupos de 2 | 8 | 13,07 / 13,59 / 14,76 | 13,59 | 5,38 |
| Grupos de 4 (por defecto, ≈ √16) | 4 | 13,10 / 12,97 / 13,17 | 13,10 | 5,58 |
| Grupos de 8 | 2 | 12,28 / 12,12 / 11,89 | **12,12** | **6,03** |
| Grupos de 16 (= por ramas) | 1 | 12,89 / 12,46 / 12,69 | 12,69 | 5,76 |

**Cómo se eligió el tamaño de los grupos.** El programa propone por defecto `g = round(√N)` (4 grupos de 4 con N = 16), que equilibra el número de grupos (para repartir los 30 IDs) y los miembros por grupo (para acortar cada tablero). Para comprobar esa regla se midieron además `g = 2` y `g = 8`, y se compararon con los extremos. Resultado: el mejor fue `g = 8` (12,12 s), que superó al valor por defecto (13,10 s, ≈ 8 % más lento) y también a «por ramas» (12,69 s, ≈ 4 % más lento que `g = 8`). Para esta máquina y este `N`, el tamaño recomendado es **8**.

## Conclusiones

- **Menor tiempo y mejora.** La estrategia más rápida fue el **híbrido con grupos de 8 (12,12 s, 6,03× más rápido que el secuencial, una reducción del 83 % del tiempo)**. Entre las tres implementaciones pedidas con su configuración por defecto, «por ramas» fue la mejor (12,69 s, 5,76×), seguida del híbrido por defecto (13,10 s, 5,58×) y de «por tableros» (14,85 s, 4,92×, reducción del 80 %). El orden completo por tamaño de grupo fue: 8 < 16 (ramas) < 4 < 2 < 1 (tableros). Las corridas de `g = 8` (11,89–12,28 s) no se solapan con las de «por ramas» (12,46–12,89 s), pero la diferencia es pequeña (≈ 4 %), por lo que conviene leerla como una mejora modesta.
- **La aceleración queda lejos de 16×.** La eficiencia respecto a 16 procesos es de 31 % (tableros) a 38 % (híbrido, grupos de 8), y de 61 % a 75 % respecto a los 8 núcleos físicos. En una ejecución detallada de «por tableros» la suma de los tiempos individuales fue 172 s frente a ~72 s en secuencial, es decir, cada tablero tardó en promedio unas **2,4 veces más** al correr 16 procesos a la vez (por ejemplo, el ID 7 pasó de 1,36 s a 3,27 s). Esto es coherente con que 16 procesos comparten 8 núcleos físicos (caché y memoria incluidas) y con la calibración, que casi no mejora de N = 8 a N = 16. Es una explicación consistente con las mediciones, pero no se midió por separado.
- **Comunicación y diferencias de duración entre tableros.** En «por tableros» el tiempo total está dominado por los tableros más lentos: en la ejecución detallada, el ID 3 tardó 11,51 s y el ID 8 11,12 s en un total de 14,49 s, así que un solo tablero ocupa cerca del 80 % del tiempo y ninguna asignación de IDs puede bajar de ahí mientras cada tablero lo resuelva un solo proceso. El reparto dinámico (cada proceso pide un nuevo ID al terminar) evita que un proceso acumule tableros largos, pero no acorta el más largo. La comunicación (un par de mensajes pequeños por ID o por rama) es insignificante frente a segundos de cómputo; no se midió por separado. En «por ramas» el costo adicional aparece como sincronización al final de cada tablero y búsqueda descartada en ramas que no contienen la solución.
- **Repartir tableros frente a resolverlos en orden y repartir ramas.** Repartir ramas acelera cada tablero individual: en la ejecución detallada, el ID 3 pasó de 4,96 s (secuencial) a 0,64 s, el ID 8 de 4,67 s a 0,50 s y el ID 20 de 2,02 s a 0,30 s, y la suma de tiempos parciales (12,25 s) coincide con el total porque los tableros se procesan en orden. En algunos tableros la mejora supera 16× (ID 6: de 2,62 s a 0,07 s) porque explorar ramas en paralelo puede hallar la solución mucho antes que el orden secuencial; en otros es menor (ID 2: de 3,21 s a 1,16 s, ≈ 2,8×) porque las ramas no son equilibradas. El costo de esta estrategia es la espera de cierre entre tableros. El híbrido combina ambas ideas: con 2 grupos de 8 aprovecha el paralelismo dentro de cada tablero y, a la vez, solapa el cierre de un tablero con el arranque del siguiente en el otro grupo, lo que explica que supere a «por ramas»; con grupos pequeños se parece más a «por tableros» y hereda su cola larga. Esta última explicación es una interpretación de los tiempos medidos, no se probó de forma aislada.
- **Limitaciones.** Solo se probó `N = 16` (el pedido por el taller) en un único equipo. Con tres repeticiones por caso, diferencias menores al 5 % (por ejemplo, `g = 8` frente a «por ramas») no deben leerse como definitivas. Los tiempos por ID citados provienen de ejecuciones detalladas individuales, no de medianas.
