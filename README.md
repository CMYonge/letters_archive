# Quarto Migration Toolkit

Scripts and docs for migrating the Charlotte Mary Yonge WordPress corpus into this Quarto-driven static archive. The migration is intentionally a one-off operation: once the Quarto site is generated, editors maintain the Markdown files directly and the helper JSON/YAML “glue” files from earlier experiments are no longer produced.

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
- ensures each entity directory contains `_metadata.yml` files that pull in the shared `_partials/*-meta.qmd` templates so key metadata is surfaced automatically;
- regenerates `_quarto.yml` so navigation stays current.

Until the migration is re-run, the legacy `letters/` directory (and the long-form reference listing) stays in the tree so editors can continue to consult the WordPress-derived material. The next migration pass will replace it with the normalised layout under `letter/`, `person/`, `book/`, and the per-type reference folders.

No JSON bridges (`data/entities.yml`, `data/letters_index.json`, etc.) are written anymore. The Markdown files themselves are the system of record.

## Content architecture reference

All identifier, linking, and front-matter conventions live in [`docs/content-architecture.md`](../docs/content-architecture.md). Review that document before editing generated content by hand so that inline links and metadata stay consistent.

## Quarto enhancements to explore later

- Built-in crossrefs / citations for recurring references. If you move books into a BibTeX (or keep them as QMD but register them via `bibliography:`), Quarto can auto-format citations (`[@book24]`) and footnotes.
- Callouts / margin notes to highlight editorial commentary or transcription notes inline (`::: {.callout-note}`) so contextual notes stand out without custom HTML.
- Search + sidebar navigation powered by `website.search` plus Quarto listings (`listing:`) or `search.json`, giving users filtering and search without hand-coded indexes.
- Quarto extensions (e.g., `quarto-embeds`, `quarto-hover-code`) that can add hovercards or interactive footnotes if we want richer UI later; install via `_extensions/`.
