# Bridge Markdown ↔ Notion

Sincronizador determinista entre notas Markdown (Obsidian) y páginas de Notion usando únicamente la biblioteca estándar de Python (`stdlib`).

## Instalación

```bash
cd /Users/1147839/Documents/dev/projects/bridge-md-notion
pip install -e .
```

## Uso CLI

Desde cualquier directorio de proyecto con `.env` (`NOTION_TOKEN=...`) y `notion_pages.json`:

```bash
bridge-sync pull --page semana-14
bridge-sync push --page semana-14
bridge-sync pull --all
bridge-sync push --all
```
