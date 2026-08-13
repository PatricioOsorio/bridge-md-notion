# Arquitectura de `bridge-md-notion`

Documentación técnica del motor de sincronización determinista Notion ↔ Markdown.

## Alcance

Un solo paquete en Python, sin dependencias externas: solo la stdlib (`urllib`, `json`, `re`, `argparse`, `pathlib`). Cero llamadas a LLM / IA — es determinista.

## Reglas de desarrollo

- **Cero dependencias externas (`pip`):** solo stdlib de Python 3.
- **Cero llamadas a LLM / IA:** determinista, sin modelos de lenguaje.
- **Modularidad estricta:** `notion.py` API REST, `markdown.py` conversión pura testeable sin red, `commands.py` orquestación.

## Estructura de Capas

```
        cli.py          (CLI entry point)
          │
      commands.py       (orquestación pull/push/delete/unlink)
         ╱    ╲
   markdown.py  notion.py   (núcleo puro / I/O)
       │  ╲     ╱
   links.py  config.py   (traducción / config CWD)
```

Las flechas van solo hacia abajo. Nadie importa hacia arriba.

| Módulo        | Responsabilidad                                                                          | Toca red | Toca disco |
| ------------- | ---------------------------------------------------------------------------------------- | -------- | ---------- |
| `cli.py`      | Parsear args CLI, cargar config del CWD, mapear errores a exit code                      | no       | no         |
| `commands.py` | Secuencia de cada operación (leer → convertir → escribir)                                | vía `notion` | sí     |
| `notion.py`   | HTTP contra la API de Notion: paginación, crear/archivar página, borrar/insertar bloques | **sí**   | no         |
| `markdown.py` | `blocks ↔ md`. Funciones puras sobre dicts y strings                                     | no       | no         |
| `links.py`    | `[[wikilink]] ↔ link de Notion`. Puro, alimentado por el mapa de páginas                 | no       | no         |
| `config.py`   | CWD / project_root, `.env`, leer y reescribir `notion_pages.json`                        | no       | sí         |

## Decisiones Clave

### 1. `markdown.py` es puro
Es el módulo con toda la lógica de conversión AST. No importa `notion`, no abre archivos, no lee variables de entorno: entra un dict o un string, sale un dict o un string.

Los bloques con hijos (`table`, `column_list`) reciben un callable `fetch_children`:
```python
blocks_to_md(blocks, fetch_children)   # commands pasa notion.get_all_blocks
blocks_to_md(blocks, lambda _: rows)   # el test pasa filas fijas
```

### 2. Configuración basada en CWD
`config.py` no asume la ubicación del paquete instalable, sino que resuelve el directorio de trabajo del usuario (`get_project_root()`), buscando ahí el `.env` y el `notion_pages.json`.

### 3. `push` es destructivo, con red de seguridad
Notion no tiene un update parcial cómodo para el cuerpo de una página, así que `push` borra todos los bloques hijos y los recrea. Antes de borrar, `commands.push` vuelca el estado actual de Notion a `.notion-backups/<page>-<timestamp>.md` (gitignored).

### 4. Traducción de links en los bordes
Notion enlaza por URL (`https://www.notion.so/<id>`), Obsidian por nombre de archivo (`[[semana-13]]`). `notion_pages.json` relaciona ambos mundos y `links.LinkMap` traduce sobre la marcha:
- **Solo se traduce lo mapeado.** Un link externo pasa intacto.
- **Wikilink no mapeado sobrevive literal** (`[[algo]]` sube como texto).
- En disco solo vive la sintaxis Obsidian.

### 5. El grafo vive en el frontmatter
`push` elimina el frontmatter antes de subir (`FRONTMATTER_RE`) y `pull` reinyecta el local. El frontmatter **nunca viaja a Notion**, permitiendo tener wikilinks de trazabilidad local en Obsidian sin alterar Notion.

### 6. Correlación de íconos Notion ↔ Obsidian
Propiedad `icon: "<emoji>"` en el frontmatter YAML. `push` llama a `notion.set_page_icon()`, y `pull` refresca el emoji local.

## Verificación

```bash
python3 tests/test_bridge_sync.py
```
