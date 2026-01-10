#!/usr/bin/env python3
"""
Improved WordPress to Quarto Migration Script for Yonge Letters
Fixes: dates, paragraphs, links, footnotes, and adds book references
"""

import os
import re
import shutil
from pathlib import Path

import mysql.connector
import yaml

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('YONGE_DB_HOST', os.environ.get('DB_HOST', 'db')),
    'port': int(os.environ.get('YONGE_DB_PORT', os.environ.get('DB_PORT', 3306))),
    'user': os.environ.get('YONGE_DB_USER', os.environ.get('DB_USER', 'mariadb')),
    'password': os.environ.get('YONGE_DB_PASSWORD', os.environ.get('DB_PASSWORD', 'mariadb')),
    'database': os.environ.get('YONGE_DB_NAME', os.environ.get('DB_NAME', 'yongeletters_wp')),
    'charset': 'utf8mb4'
}

OUTPUT_ROOT = Path(os.environ.get("YONGE_QUARTO_DIR", Path(__file__).resolve().parents[1]))

class ImprovedYongeLettersMigrator:
    def __init__(self):
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor(dictionary=True)
        self.persons = {}
        self.others = {}
        self.books = {}
        self.output_dir = OUTPUT_ROOT
        self.letter_dir = self.output_dir / "letter"
        self.person_dir = self.output_dir / "person"
        self.book_dir = self.output_dir / "book"
        self.partials_dir = self.output_dir / "_partials"
        self.prepared_reference_dirs = set()

        self._prepare_entity_dirs()
        self.partials_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_metadata_file(self.letter_dir, "letter-meta.qmd")
        self._ensure_metadata_file(self.person_dir, "person-meta.qmd")
        self._ensure_metadata_file(self.book_dir, "book-meta.qmd")
        
    def load_references(self):
        """Load persons, others, and books references into memory"""
        print("Loading person references...")
        self.cursor.execute("""
            SELECT persons_id, surname, first_name, prefix, title, dates, description, biography
            FROM wp_persons
        """)
        for row in self.cursor.fetchall():
            full_name = self._build_full_name(row)
            self.persons[row['persons_id']] = {
                'id': row['persons_id'],
                'full_name': full_name,
                'surname': row['surname'],
                'first_name': row['first_name'],
                'prefix': row['prefix'],
                'title': row['title'], 
                'dates': row['dates'],
                'description': row['description'],
                'biography': row['biography']
            }
            
        print("Loading other references...")
        self.cursor.execute("SELECT others_id, type, name, description FROM wp_others")
        for row in self.cursor.fetchall():
            self.others[row['others_id']] = {
                'id': row['others_id'],
                'type': row['type'],
                'name': row['name'],
                'description': row['description']
            }
            
        print("Loading book references...")
        self.cursor.execute("""
            SELECT cmy_bookID, title, date, genre, format, publisher, serialization, illustrator, notes
            FROM wp_cmybibliography
        """)
        for row in self.cursor.fetchall():
            # Clean up title (remove HTML italic tags)
            clean_title = re.sub(r'</?i>', '', row['title'])
            clean_title = clean_title.replace("'", "'")  # Fix quotes
            
            self.books[row['cmy_bookID']] = {
                'id': row['cmy_bookID'],
                'title': clean_title,
                'date': row['date'],
                'genre': row['genre'],
                'format': row['format'],
                'publisher': row['publisher'],
                'serialization': row['serialization'],
                'illustrator': row['illustrator'],
                'notes': row['notes']
            }
    
    def _build_full_name(self, person):
        """Build full name from person record"""
        parts = []
        if person['prefix']:
            parts.append(person['prefix'])
        if person['title']:
            parts.append(person['title'])
        if person['first_name']:
            parts.append(person['first_name'])
        if person['surname']:
            parts.append(person['surname'])
        return ' '.join(parts)
    
    def _clean_inline(self, value):
        if value is None:
            return None
        cleaned = re.sub(r'\s+', ' ', str(value)).strip()
        return cleaned or None
    
    def _clean_block(self, value):
        if value is None:
            return None
        return str(value).strip() or None

    def _prepare_entity_dirs(self):
        """Reset the entity directories so we never nest outputs."""
        self._remove_retired_layouts()
        for path in (self.letter_dir, self.person_dir, self.book_dir):
            self._clear_directory(path)

    def _clear_directory(self, path: Path):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

    def _remove_retired_layouts(self):
        """Remove legacy plural directories or nested exports from older runs."""
        retired = [
            self.output_dir / "letters",
            self.output_dir / "persons",
            self.output_dir / "books",
            self.output_dir / "references",
            self.output_dir / "others",
            self.output_dir / "data",
            self.output_dir / "yonge-letters-quarto",
            self.output_dir / "organization",
        ]
        for path in retired:
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()

    def _ensure_reference_dir(self, slug: str) -> Path:
        """Create (and if needed, reset) a reference directory for wp_others types."""
        if slug in self.prepared_reference_dirs:
            return self.output_dir / slug
        path = self.output_dir / slug
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        self._ensure_metadata_file(path, "reference-meta.qmd")
        self.prepared_reference_dirs.add(slug)
        return path

    def _render_yaml(self, metadata: dict) -> str:
        cleaned = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            cleaned[key] = value
        return yaml.safe_dump(cleaned, sort_keys=False, allow_unicode=True).strip()
    
    def _normalise_type(self, raw_type):
        if not raw_type:
            return "Other", "other"
        label = re.sub(r'\s+', ' ', raw_type).strip()
        if not label:
            return "Other", "other"
        if label.lower() in {"organization", "organisation"}:
            label = "Organisation"
        elif label.islower():
            label = label.title()
        slug = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-') or "other"
        slug = slug.replace('organization', 'organisation')
        return label, slug
    
    def _ensure_metadata_file(self, directory: Path, partial_name: str):
        meta_path = directory / "_metadata.yml"
        if not meta_path.exists():
            include_path = f"../_partials/{partial_name}"
            meta_path.write_text(
                "format:\n"
                "  html:\n"
                f"    include-before-body: \"{include_path}\"\n",
                encoding='utf-8'
            )
    
    def _extract_year(self, date_str):
        if not date_str:
            return None
        match = re.search(r'(\d{4})', date_str)
        if match:
            return int(match.group(1))
        return None
    
    def _parse_date(self, date_str):
        """Parse various date formats and convert to ISO format"""
        if not date_str:
            return None
            
        # Try to extract year and convert to ISO format
        # Handle formats like "May 18th 1874", "Jan 31 [1894]", "1863"
        
        # Extract year first
        year_match = re.search(r'(\d{4})', date_str)
        if not year_match:
            year_match = re.search(r'\[(\d{4})\]', date_str)
        
        if not year_match:
            return None  # Unable to parse
            
        year = year_match.group(1)
        
        # Month mapping
        months = {
            'jan': '01', 'january': '01', 'feb': '02', 'febry': '02', 'february': '02',
            'mar': '03', 'march': '03', 'apr': '04', 'april': '04', 'may': '05',
            'jun': '06', 'june': '06', 'jul': '07', 'july': '07', 'aug': '08', 'august': '08',
            'sep': '09', 'september': '09', 'oct': '10', 'october': '10', 'nov': '11', 'november': '11',
            'dec': '12', 'december': '12'
        }
        
        # Try to extract month
        month = '01'  # Default to January
        for month_name, month_num in months.items():
            if month_name in date_str.lower():
                month = month_num
                break
        
        # Try to extract day
        day_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', date_str)
        day = day_match.group(1).zfill(2) if day_match else '01'
        
        return f"{year}-{month}-{day}"
    
    def _clean_content(self, content):
        """Clean WordPress content and convert annotations to inline links."""
        if not content:
            return ""
        
        def replace_person(match):
            person_id = int(match.group(1))
            display_name = match.group(2) if match.group(2) else ""
            trailing_space = match.group(3) if match.group(3) else ""
            
            if person_id in self.persons:
                person = self.persons[person_id]
                label = display_name if display_name else person['full_name']
                return f"[{label}](/person/{person_id}){trailing_space}"
            else:
                return display_name + trailing_space if display_name else f"[Unknown Person {person_id}]{trailing_space}"
        
        def replace_other(match):
            other_id = int(match.group(1))
            display_name = match.group(2) if match.group(2) else ""
            trailing_space = match.group(3) if match.group(3) else ""
            
            if other_id in self.others:
                other = self.others[other_id]
                label = display_name if display_name else other['name']
                _, type_slug = self._normalise_type(other['type'] if other['type'] else 'Other')
                return f"[{label}](/{type_slug}/{other_id}){trailing_space}"
            else:
                return display_name + trailing_space if display_name else f"[Unknown Reference {other_id}]{trailing_space}"
        
        def replace_book(match):
            book_id = int(match.group(1))
            display_name = match.group(2) if match.group(2) else ""
            trailing_space = match.group(3) if match.group(3) else ""
            
            if book_id in self.books:
                book = self.books[book_id]
                label = display_name if display_name else book['title']
                return f"[{label}](/book/{book_id}){trailing_space}"
            else:
                return display_name + trailing_space if display_name else f"[Unknown Book {book_id}]{trailing_space}"
        
        def replace_footnote(match):
            footnote_num = match.group(1)
            trailing_space = match.group(2) if match.group(2) else ""
            return f"[^{footnote_num}]{trailing_space}"
        
        content = re.sub(r'\[\[person:(\d+)\]([^\]]*)\](\s*)', replace_person, content)
        content = re.sub(r'\[\[other:(\d+)\]([^\]]*)\](\s*)', replace_other, content)
        content = re.sub(r'\[\[cmybook:(\d+)\]([^\]]*)\](\s*)', replace_book, content)
        content = re.sub(r'\[\[otherbook:(\d+)\]([^\]]*)\](\s*)', replace_other, content)
        content = re.sub(r'\[\[footnote:(\d+)\]\](\s*)', replace_footnote, content)
        
        content = content.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        content = re.sub(r'<[^>]+>', '', content)
        
        content = re.sub(r'\r\n|\r|\n', '\n', content)
        content = re.sub(r'\n\s*(yours\s+sincerely|yours\s+truly|yours\s+affectionately|yours\s+ever|ever\s+yours)', r'\n\n\1', content, flags=re.IGNORECASE)
        content = re.sub(r'\n\s*(C\s*M\s*Yonge|Charlotte\s+M\s*Yonge)', r'\n\n\1', content, flags=re.IGNORECASE)
        content = re.sub(r'([.!?])\s+([A-Z][a-z])', r'\1\n\n\2', content)
        content = re.sub(r' +', ' ', content)
        content = re.sub(r'\n +', '\n', content)
        content = re.sub(r' +\n', '\n', content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()
    
    def _parse_footnotes(self, footnote_content):
        """Parse footnote content into individual footnotes"""
        if not footnote_content:
            return {}
            
        footnotes = {}
        # Split by footnote markers
        parts = re.split(r'\[\[footnote:(\d+)\]\]', footnote_content)
        
        current_num = None
        for i, part in enumerate(parts):
            if i % 2 == 1:  # This is a footnote number
                current_num = part
            elif current_num and part.strip():  # This is footnote content
                footnotes[current_num] = self._clean_content(part.strip())
                current_num = None
                
        return footnotes
    
    def migrate_letters(self):
        """Extract and convert all letters to markdown"""
        print("Migrating letters...")
        
        query = """
        SELECT p.ID, p.post_title, p.post_content, p.post_date, p.guid,
               li.letter_date, li.letter_fromAddress, li.manuscript_location, li.letter_footnote
        FROM wp_posts p
        LEFT JOIN wp_letterinfo li ON p.ID = li.post_ID
        WHERE p.post_type = 'post' AND p.post_status = 'publish'
        ORDER BY p.post_date
        """
        
        self.cursor.execute(query)
        letters = self.cursor.fetchall()
        
        letter_index = []
        
        for letter in letters:
            post_id = letter['ID']
            letter_file = self.letter_dir / f"{post_id}.qmd"
            
            footnotes = self._parse_footnotes(letter['letter_footnote'])
            parsed_date = self._parse_date(letter['letter_date'])
            post_date = letter['post_date']
            display_date = self._clean_inline(letter['letter_date'])
            if not display_date and post_date:
                display_date = post_date.strftime("%Y-%m-%d")
            title = self._clean_inline(letter['post_title']) or f"Letter {post_id}"
            from_address = self._clean_inline(letter['letter_fromAddress'])
            manuscript_location_raw = re.sub(r'\[\[footnote:\d+\]\]', '', letter['manuscript_location']) if letter['manuscript_location'] else ''
            manuscript_location = self._clean_block(manuscript_location_raw)
            
            metadata = {
                'id': post_id,
                'title': title,
                'date': parsed_date,
                'display-date': display_date,
                'from-name': "Charlotte Mary Yonge",
                'from-address': from_address,
                'to-name': title,
                'manuscript-location': manuscript_location,
            }
            
            front_matter = self._render_yaml(metadata)
            md_parts = ["---", front_matter, "---", ""]
            
            body_content = self._clean_content(letter['post_content'])
            if body_content:
                md_parts.append(body_content + "\n")
            
            if footnotes:
                md_parts.append("")
                for num in sorted(footnotes, key=lambda x: int(x) if x.isdigit() else x):
                    text = footnotes[num]
                    md_parts.append(f"[^{num}]: {text}")
            
            letter_file.write_text("\n".join(md_parts).strip() + "\n", encoding='utf-8')
            
            letter_index.append({
                'id': post_id,
                'title': title,
                'date': display_date,
                'parsed_date': parsed_date,
                'from_address': from_address
            })
        
        self._write_letters_index(letter_index)
        
        print(f"Migrated {len(letters)} letters")
        return letter_index

    def _write_letters_index(self, letter_index):
        index_path = self.output_dir / "letters-index.qmd"
        lines = [
            "---",
            'title: "Letters Index"',
            "---",
            "",
            "Browse every letter in chronological order.",
            "",
        ]
        
        decades = {}
        for entry in letter_index:
            year = self._extract_year(entry['parsed_date'] or entry['date'])
            if year is None:
                decade = "Undated"
            else:
                decade = f"{(year // 10) * 10}s"
            decades.setdefault(decade, []).append(entry)
        
        def decade_sort_key(key):
            if key == "Undated":
                return float("inf")
            return int(key.rstrip('s'))
        
        for decade in sorted(decades.keys(), key=decade_sort_key):
            lines.append(f"## {decade}")
            lines.append("")
            entries = sorted(
                decades[decade],
                key=lambda x: (x['parsed_date'] or "", x['title'])
            )
            for entry in entries:
                date_display = entry['date'] or "Undated"
                from_addr = f" — From: {entry['from_address']}" if entry['from_address'] else ""
                lines.append(f"- **[{entry['title']}](/letter/{entry['id']})** — {date_display}{from_addr}")
            lines.append("")
        
        index_path.write_text("\n".join(lines).strip() + "\n", encoding='utf-8')
    
    def create_books_reference(self):
        """Create individual book reference files plus an index."""
        print("Creating books reference...")
        
        listing_lines = [
            "---",
            'title: "Books by Charlotte Mary Yonge"',
            "---",
            "",
        ]
        
        for book_id in sorted(self.books.keys()):
            book = self.books[book_id]
            metadata = {
                'id': book_id,
                'title': self._clean_inline(book['title']),
                'author': "Charlotte Mary Yonge",
                'date': self._clean_inline(book['date']),
                'genre': self._clean_inline(book['genre']),
                'publication-format': self._clean_inline(book['format']),
                'publisher': self._clean_inline(book['publisher']),
                'serialization': self._clean_inline(book['serialization']),
                'illustrator': self._clean_inline(book['illustrator']),
            }
            if not metadata['title']:
                metadata['title'] = f"Book {book_id}"
            
            notes = self._clean_block(book['notes'])
            front_matter = self._render_yaml(metadata)
            book_md = ["---", front_matter, "---", ""]
            if notes:
                book_md.append(self._clean_content(notes))
            
            book_file = self.book_dir / f"{book_id}.qmd"
            book_file.write_text("\n".join(book_md).strip() + "\n", encoding='utf-8')
            
            listing_lines.append(f"- [{metadata['title']}](/book/{book_id})")
        
        (self.output_dir / "books.qmd").write_text("\n".join(listing_lines).strip() + "\n", encoding='utf-8')
    
    def create_persons_reference(self):
        """Create per-person files plus a root index."""
        print("Creating persons reference...")
        
        listing_lines = [
            "---",
            'title: "Persons Referenced in the Letters"',
            "---",
            "",
        ]
        
        sorted_persons = sorted(self.persons.values(), key=lambda x: (x['surname'] or '', x['full_name']))
        
        for person in sorted_persons:
            person_id = person['id']
            metadata = {
                'id': person_id,
                'full-name': self._clean_inline(person['full_name']),
                'first-name': self._clean_inline(person['first_name']),
                'last-name': self._clean_inline(person['surname']),
                'prefix': self._clean_inline(person['prefix']),
                'title': self._clean_inline(person['title']),
                'dates': self._clean_inline(person['dates']) or "—",
            }
            if not metadata['full-name']:
                metadata['full-name'] = f"Person {person_id}"
            metadata['title'] = metadata['full-name']
            
            body_parts = []
            if person['description']:
                body_parts.append(self._clean_content(person['description']))
            if person['biography']:
                body_parts.append(self._clean_content(person['biography']))
            
            front_matter = self._render_yaml(metadata)
            person_md = ["---", front_matter, "---", ""]
            if body_parts:
                person_md.append("\n\n".join(body_parts))
            
            person_file = self.person_dir / f"{person_id}.qmd"
            person_file.write_text("\n".join(person_md).strip() + "\n", encoding='utf-8')
            
            listing_lines.append(f"- [{metadata['full-name']}](/person/{person_id})")
        
        (self.output_dir / "persons.qmd").write_text("\n".join(listing_lines).strip() + "\n", encoding='utf-8')
    
    def create_others_reference(self):
        """Create reference files for organisations/places/topics."""
        print("Creating references...")
        self.prepared_reference_dirs.clear()
        
        listing_lines = [
            "---",
            'title: "Institutions and Other References"',
            "---",
            "",
        ]
        
        grouped = {}
        for other in self.others.values():
            type_label, type_slug = self._normalise_type(other['type'] if other['type'] else 'Other')
            grouped.setdefault(type_slug, {'label': type_label, 'items': []})
            grouped[type_slug]['items'].append(other)
        
        for type_slug in sorted(grouped.keys()):
            type_label = grouped[type_slug]['label']
            listing_lines.append(f"## {type_label}")
            listing_lines.append("")
            
            type_dir = self._ensure_reference_dir(type_slug)
            
            for other in sorted(grouped[type_slug]['items'], key=lambda x: x['name']):
                other_id = other['id']
                metadata = {
                    'id': other_id,
                    'reference-type': type_label,
                    'name': self._clean_inline(other['name']) or f"Reference {other_id}",
                }
                metadata['title'] = metadata['name']
                
                body = ""
                if other['description']:
                    body = self._clean_content(other['description'])
                
                front_matter = self._render_yaml(metadata)
                ref_md = ["---", front_matter, "---", ""]
                if body:
                    ref_md.append(body)
                
                ref_file = type_dir / f"{other_id}.qmd"
                ref_file.write_text("\n".join(ref_md).strip() + "\n", encoding='utf-8')
                
                listing_lines.append(f"- [{metadata['name']}](/{type_slug}/{other_id})")
            listing_lines.append("")
        
        (self.output_dir / "references.qmd").write_text("\n".join(listing_lines).strip() + "\n", encoding='utf-8')
    
    def create_quarto_config(self):
        """Create _quarto.yml configuration file"""
        print("Creating Quarto configuration...")
        
        config = {
            'project': {
                'type': 'website',
                'title': 'The Letters of Charlotte Mary Yonge'
            },
            'website': {
                'title': 'The Letters of Charlotte Mary Yonge',
                'description': 'A digital collection of the correspondence of Charlotte Mary Yonge (1823-1901), English novelist and educator.',
                'navbar': {
                    'title': 'Yonge Letters',
                    'left': [
                        {'text': 'Home', 'href': 'index.qmd'},
                        {'text': 'Letters', 'href': 'letters-index.qmd'},
                        {'text': 'Persons', 'href': 'persons.qmd'},
                        {'text': 'Books', 'href': 'books.qmd'},
                        {'text': 'References', 'href': 'references.qmd'},
                        {'text': 'About', 'href': 'about.qmd'}
                    ]
                },
                'sidebar': {
                    'style': 'docked',
                    'search': True,
                    'contents': [
                        'index.qmd',
                        'letters-index.qmd',
                        'persons.qmd',
                        'books.qmd',
                        'references.qmd',
                        'about.qmd'
                    ]
                }
            },
            'format': {
                'html': {
                    'theme': 'cosmo',
                    'css': 'styles.css',
                    'toc': True,
                    'toc-depth': 3,
                    'number-sections': False
                }
            }
        }
        
        with open(self.output_dir / "_quarto.yml", 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    
    def run_migration(self):
        """Run the complete migration"""
        print("Starting improved Yonge Letters migration to Quarto...")
        
        self.load_references()
        letter_index = self.migrate_letters()
        self.create_persons_reference()
        self.create_others_reference()
        self.create_books_reference()
        self.create_quarto_config()
        
        print(f"Migration completed! Migrated {len(letter_index)} letters.")
        print(f"Output directory: {self.output_dir}")
        
        self.conn.close()

if __name__ == "__main__":
    migrator = ImprovedYongeLettersMigrator()
    migrator.run_migration()
