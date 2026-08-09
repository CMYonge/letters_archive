
# Archived: Cristian Dinu's Quarto Migration Toolkit (archived May 2026)

This repository holds Cristian Dinu's original, independent Python-based
effort to migrate the Charlotte Mary Yonge WordPress letters corpus into
a Quarto-driven static site. It predates, and is unrelated to, the R-based
pipeline (STEP0-STEP3) that Clare Hanmer built and that generates the
live site at github.com/CMYonge/letters.

The two approaches were compared during the project's early stages;
Clare's R pipeline was the one carried forward into production. This
repository is kept for reference and historical record only - it is not
actively maintained, and its generated content is not the live site.

The rest of this document describes how Cristian's toolkit worked, for
anyone wanting to understand or revisit that approach.

## Restore the MariaDB dump

1. Start the development containers (`Dev Containers: Reopen in Container…` inside VS Code). The bundled compose file exposes the database on `localhost:3306`.
2. Create a clean database and grant access to the `mariadb` application user:

   ```bash
   mariadb -h db -u root -pmariadb -e "
     DROP DATABASE IF EXISTS yongeletters_wp;
     CREATE DATABASE yongeletters_wp
       CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
     GRANT ALL ON yongeletters_wp.* TO 'mariadb'@'%';
     FLUSH PRIVILEGES;"
   ```

3. Import the dump that lives at the repo root:

   ```bash
   mariadb -h db -u mariadb -pmariadb yongeletters_wp < ../yongeletters_wp-2025_04_27.sql
   ```

## Python toolchain

This repo is configured for [uv](https://github.com/astral-sh/uv). Create or refresh the environment once:

```bash
cd yonge-letters-quarto
UV_CACHE_DIR=.uv-cache uv sync
```

If `uv` is unavailable on your host you can fall back to the checked-in `.venv` by running `.venv/bin/pip install -r pyproject.toml` requirements, but `uv` keeps everyone on the same Python 3.13 toolchain.

## Run the migration

```bash
cd yonge-letters-quarto
UV_CACHE_DIR=.uv-cache uv run python scripts/migrate_wordpress_to_quarto_improved.py
```

The script:

- trims and normalises every field pulled from WordPress so the YAML front matter is clean;
- writes one QMD per entity using singular directories and numeric IDs (`letter/1827.qmd`, `person/263.qmd`, `book/24.qmd`, `organisation/3.qmd`, etc.);
- renders inline Markdown links such as `[Ann Smith](/person/263)` directly in the body copy instead of generating reference-definition blocks;
- emits aggregate listing pages (`letters-index.qmd`, `persons.qmd`, `books.qmd`, `references.qmd`);
- drops WordPress-only provenance fields (`wordpress-id`, `source-url`, `source-post-date`, etc.) now that IDs are numeric and stable;
- ensures each entity directory contains `_metadata.yml` files that enable the shared `filters/entity-meta.lua` filter so key metadata renders from front matter (without duplicating values into the page body);
- regenerates `_quarto.yml` so navigation stays current.

No JSON bridges (`data/entities.yml`, `data/letters_index.json`, etc.) are written anymore. The Markdown files themselves are the system of record.

### Speeding up previews

- Use the sampling flag to generate only a handful of records per entity while debugging layouts:
  ```bash
  UV_CACHE_DIR=.uv-cache uv run python scripts/migrate_wordpress_to_quarto_improved.py --sample-limit 20
  ```
- When you want to wipe every generated directory, run `./clean.sh` from `yonge-letters-quarto/` and then re-run the migration.

## Content architecture reference

All identifier, linking, and front-matter conventions live in [`docs/content-architecture.md`](../docs/content-architecture.md). Review that document before editing generated content by hand so that inline links and metadata stay consistent.

## Quarto enhancements to explore later

- Built-in crossrefs / citations for recurring references. If you move books into a BibTeX (or keep them as QMD but register them via `bibliography:`), Quarto can auto-format citations (`[@book24]`) and footnotes.
- Callouts / margin notes to highlight editorial commentary or transcription notes inline (`::: {.callout-note}`) so contextual notes stand out without custom HTML.
- Search + sidebar navigation powered by `website.search` plus Quarto listings (`listing:`) or `search.json`, giving users filtering and search without hand-coded indexes.
- Quarto extensions (e.g., `quarto-embeds`, `quarto-hover-code`) that can add hovercards or interactive footnotes if we want richer UI later; install via `_extensions/`.
