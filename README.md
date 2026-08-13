# Bridge Markdown ↔ Notion

Sincronizador determinista y de alto rendimiento entre notas Markdown (Obsidian) y páginas de Notion usando exclusivamente la biblioteca estándar de Python (`stdlib`).

Tus archivos locales `.md` son la **fuente de verdad inmutable**. Notion se utiliza como interfaz móvil y visualizador.

---

## Requisitos Previos

- Python >= 3.9
- Un token de integración de Notion (creado en [notion.so/my-integrations](https://www.notion.so/my-integrations))

---

## Instalación Global (Modo Editable)

Clona/ubica el repositorio e instálalo globalmente en tu entorno Python:

```bash
cd /Users/1147839/Documents/dev/projects/bridge-md-notion
python3 -m pip install --user --no-build-isolation -e .
```

*Tip:* Asegúrate de tener `export PATH="$HOME/Library/Python/3.9/bin:$PATH"` en tu `~/.zshrc` para invocar `bridge-sync` directamente.

---

## Getting Started: Cómo usarlo en un Proyecto Nuevo

Para habilitar la sincronización en **cualquier nuevo directorio de proyecto**, solo debes seguir 3 pasos sencillos:

### 1. Configurar el Token (`.env`)
Crea un archivo `.env` en la raíz de tu nuevo proyecto (asegúrate de agregarlo a `.gitignore`):

```env
NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

*Importante:* En Notion, debes compartir la página raíz o contenedor con tu integración a través del menú **Connect to / Conectar a**.

### 2. Crear el Mapeo Inicial (`scripts/notion_pages.json`)
Crea el archivo `scripts/notion_pages.json` relacionando los nombres de página (targets de wikilinks en Obsidian) con sus IDs de Notion y rutas locales:

```json
{
  "_comment": "Mapeo de páginas Notion ID <-> Ruta local Obsidian",
  "mi-nota": {
    "id": "3a30b31fce98801dbdf9d153cf7c2f34",
    "path": "notas/mi-nota.md"
  }
}
```

### 3. Validar el Workspace
Ejecuta la herramienta de diagnóstico para confirmar que tu configuración es válida:

```bash
bridge-sync check
```

---

## Comandos CLI

### Sincronizar desde Notion hacia Markdown (`pull`)
```bash
bridge-sync pull --page mi-nota    # Trae una sola página
bridge-sync pull --all            # Trae todas las páginas registradas
```

### Sincronizar desde Markdown hacia Notion (`push`)
```bash
bridge-sync push --page mi-nota    # Sube una sola página (crea backup automático en .notion-backups/)
bridge-sync push --all            # Sube todas las páginas
```

### Registrar una Nueva Página (`create`)
Crea la página en Notion y la registra automáticamente en `notion_pages.json`:
```bash
bridge-sync create \
  --name nueva-nota \
  --title "Nueva Nota de Trabajo" \
  --parent 3b00b31fce9881908398e5517b3f8aff \
  --path notas/nueva-nota.md
```

### Eliminar / Desvincular Páginas
```bash
bridge-sync delete --page mi-nota   # Trae lo último a local, manda la página en Notion a la papelera y la desregistra
bridge-sync delete --id <url-or-id> # Manda una página no registrada a la papelera guardando backup
bridge-sync unlink --page mi-nota   # Quita la página del mapa json sin borrar nada en Notion ni en disco
```

---

## Características Clave

- **Wikilinks nativos de Obsidian:** Los enlaces `[[nombre]]` o `[[nombre|Alias]]` se traducen automáticamente a enlaces nativos de Notion y viceversa.
- **Íconos Emoji en Frontmatter:** Agrega `icon: "🧠"` en el frontmatter YAML de tu Markdown local para sincronizar el ícono de la página en Notion.
- **Backups Automáticos:** Cada `push` realiza un respaldo en `.notion-backups/` antes de reemplazar los bloques en Notion.
- **Auto-formateo con Prettier:** Si Prettier está instalado, los archivos `.md` descargados en `pull` se formatean automáticamente.
