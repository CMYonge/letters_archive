#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

declare -a DIRS_TO_REMOVE=(
  "letter"
  "person"
  "book"
  "organisation"
  "periodical"
  "place"
  "topic"
  "_site"
)

declare -a FILES_TO_REMOVE=(
  "letters-index.qmd"
  "persons.qmd"
  "books.qmd"
  "references.qmd"
)

for dir in "${DIRS_TO_REMOVE[@]}"; do
  rm -rf "${ROOT}/${dir}"
done

for file in "${FILES_TO_REMOVE[@]}"; do
  rm -f "${ROOT}/${file}"
done
