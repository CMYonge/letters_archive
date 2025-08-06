#!/usr/bin/env python3
"""
Improved WordPress to Quarto Migration Script for Yonge Letters
Fixes: dates, paragraphs, links, footnotes, and adds book references
"""

import mysql.connector
import json
import os
import re
from datetime import datetime
from pathlib import Path
import yaml

# Database configuration
DB_CONFIG = {
    'host': 'db',
    'user': 'wordpress',
    'password': 'wordpress_password',
    'database': 'yongeletters_wp',
    'charset': 'utf8mb4'
}

class ImprovedYongeLettersMigrator:
    def __init__(self):
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor(dictionary=True)
        self.persons = {}
        self.others = {}
        self.books = {}
        self.output_dir = Path("/workspaces/yonge/yonge-letters-quarto")
        
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
            return date_str  # Return as-is if can't parse
            
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
        """Clean WordPress content and convert annotations"""
        if not content:
            return ""
            
        # Convert person annotations - fix links to use relative paths and .html
        def replace_person(match):
            person_id = int(match.group(1))
            display_name = match.group(2) if match.group(2) else ""
            trailing_space = match.group(3) if match.group(3) else ""
            
            if person_id in self.persons:
                person = self.persons[person_id]
                if display_name:
                    return f"[{display_name}](../persons.html#{person_id}){trailing_space}"
                else:
                    return f"[{person['full_name']}](../persons.html#{person_id}){trailing_space}"
            else:
                return display_name + trailing_space if display_name else f"[Unknown Person {person_id}]{trailing_space}"
        
        # Convert other/institution annotations
        def replace_other(match):
            other_id = int(match.group(1))
            display_name = match.group(2) if match.group(2) else ""
            trailing_space = match.group(3) if match.group(3) else ""
            
            if other_id in self.others:
                other = self.others[other_id]
                if display_name:
                    return f"[{display_name}](../others.html#{other_id}){trailing_space}"
                else:
                    return f"[{other['name']}](../others.html#{other_id}){trailing_space}"
            else:
                return display_name + trailing_space if display_name else f"[Unknown Reference {other_id}]{trailing_space}"
        
        # Convert book annotations
        def replace_book(match):
            book_id = int(match.group(1))
            display_name = match.group(2) if match.group(2) else ""
            trailing_space = match.group(3) if match.group(3) else ""
            
            if book_id in self.books:
                book = self.books[book_id]
                if display_name:
                    return f"[{display_name}](../books.html#{book_id}){trailing_space}"
                else:
                    return f"[{book['title']}](../books.html#{book_id}){trailing_space}"
            else:
                return display_name + trailing_space if display_name else f"[Unknown Book {book_id}]{trailing_space}"
        
        # Convert footnote references
        def replace_footnote(match):
            footnote_num = match.group(1)
            trailing_space = match.group(2) if match.group(2) else ""
            return f"[^{footnote_num}]{trailing_space}"
        
        # Apply transformations - updated regex to capture trailing spaces
        content = re.sub(r'\[\[person:(\d+)\]([^\]]*)\](\s*)', replace_person, content)
        content = re.sub(r'\[\[other:(\d+)\]([^\]]*)\](\s*)', replace_other, content)  
        content = re.sub(r'\[\[cmybook:(\d+)\]([^\]]*)\](\s*)', replace_book, content)
        content = re.sub(r'\[\[otherbook:(\d+)\]([^\]]*)\](\s*)', replace_other, content)  # These seem to be in others table
        content = re.sub(r'\[\[footnote:(\d+)\]\](\s*)', replace_footnote, content)
        
        # Clean up HTML entities and tags
        content = content.replace('&amp;', '&')
        content = content.replace('&lt;', '<')
        content = content.replace('&gt;', '>')
        content = re.sub(r'<[^>]+>', '', content)  # Remove HTML tags
        
        # Fix paragraph breaks and line endings
        # First, normalize line breaks
        content = re.sub(r'\r\n|\r|\n', '\n', content)
        
        # Handle common letter ending patterns that should be separate paragraphs
        content = re.sub(r'\n\s*(yours\s+sincerely|yours\s+truly|yours\s+affectionately|yours\s+ever|ever\s+yours)', r'\n\n\1', content, flags=re.IGNORECASE)
        content = re.sub(r'\n\s*(C\s*M\s*Yonge|Charlotte\s+M\s*Yonge)', r'\n\n\1', content, flags=re.IGNORECASE)
        
        # Fix sentences that should start new paragraphs (period/!/? followed by capital letter)
        content = re.sub(r'([.!?])\s+([A-Z][a-z])', r'\1\n\n\2', content)
        
        # Clean up multiple consecutive spaces and normalize whitespace
        content = re.sub(r' +', ' ', content)  # Multiple spaces to single space
        content = re.sub(r'\n +', '\n', content)  # Remove spaces at beginning of lines
        content = re.sub(r' +\n', '\n', content)  # Remove spaces at end of lines
        content = re.sub(r'\n{3,}', '\n\n', content)  # Multiple line breaks to double breaks
        
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
        SELECT p.ID, p.post_title, p.post_content, p.post_date,
               li.letter_date, li.letter_fromAddress, li.manuscript_location, li.letter_footnote
        FROM wp_posts p
        LEFT JOIN wp_letterinfo li ON p.ID = li.post_ID
        WHERE p.post_type = 'post' AND p.post_status = 'publish'
        ORDER BY p.post_date
        """
        
        self.cursor.execute(query)
        letters = self.cursor.fetchall()
        
        letters_dir = self.output_dir / "letters"
        letters_dir.mkdir(exist_ok=True)
        
        letter_index = []
        
        for letter in letters:
            # Create safe filename
            title = letter['post_title'][:100]  # Truncate long titles
            safe_title = re.sub(r'[^\w\s-]', '', title).strip()
            safe_title = re.sub(r'[\s_-]+', '-', safe_title).lower()
            filename = f"{letter['ID']:04d}-{safe_title}.qmd"
            
            # Parse footnotes
            footnotes = self._parse_footnotes(letter['letter_footnote'])
            
            # Parse and format date
            parsed_date = self._parse_date(letter['letter_date'])
            display_date = letter['letter_date'] if letter['letter_date'] else str(letter['post_date'].date())
            
            # Create letter metadata
            # Clean manuscript location of footnote markers
            clean_manuscript_location = re.sub(r'\[\[footnote:\d+\]\]', '', letter['manuscript_location']) if letter['manuscript_location'] else ''
            
            metadata = {
                'title': letter['post_title'],
                'date': parsed_date if parsed_date else str(letter['post_date'].date()),
                'display-date': display_date,
                'from-address': letter['letter_fromAddress'],
                'manuscript-location': clean_manuscript_location,
                'wordpress-id': letter['ID'],
                'original-date': str(letter['post_date'])
            }
            
            # Clean letter content
            content = self._clean_content(letter['post_content'])
            
            # Build markdown file with Quarto inline variables
            md_content = "---\n"
            md_content += yaml.dump(metadata, default_flow_style=False)
            md_content += "---\n\n"
            
            # Use Quarto inline variables instead of duplicating metadata
            md_content += "**Date:** {{< meta display-date >}}  \n"
            md_content += "**From:** {{< meta from-address >}}  \n"
            md_content += "**Manuscript Location:** {{< meta manuscript-location >}}  \n"
            md_content += "\n"
            
            md_content += content + "\n"
            
            # Add footnotes if they exist - but don't add ## Footnotes header
            if footnotes:
                md_content += "\n"
                for num, text in footnotes.items():
                    md_content += f"[^{num}]: {text}\n\n"
            
            # Write file
            with open(letters_dir / filename, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            # Add to index
            letter_index.append({
                'id': letter['ID'],
                'title': letter['post_title'],
                'date': display_date,
                'parsed_date': parsed_date,
                'filename': filename,
                'from_address': letter['letter_fromAddress']
            })
            
        # Save letter index
        with open(self.output_dir / "data" / "letters_index.json", 'w', encoding='utf-8') as f:
            json.dump(letter_index, f, indent=2, ensure_ascii=False, default=str)
            
        print(f"Migrated {len(letters)} letters")
        return letter_index
    
    def create_books_reference(self):
        """Create books reference page"""
        print("Creating books reference...")
        
        md_content = """---
title: "Books by Charlotte Mary Yonge"
---

This page contains information about Charlotte Mary Yonge's published works mentioned in her correspondence.

"""
        
        # Group by genre
        by_genre = {}
        for book in self.books.values():
            genre = book['genre'] if book['genre'] else 'Other'
            if genre not in by_genre:
                by_genre[genre] = []
            by_genre[genre].append(book)
        
        for genre in sorted(by_genre.keys()):
            md_content += f"## {genre}\n\n"
            
            for book in sorted(by_genre[genre], key=lambda x: x['title']):
                md_content += f"### {book['title']} {{#{book['id']}}}\n\n"
                
                if book['date']:
                    md_content += f"**Date:** {book['date']}  \n"
                if book['publisher']:
                    md_content += f"**Publisher:** {book['publisher']}  \n"
                if book['format']:
                    md_content += f"**Format:** {book['format']}  \n"
                if book['serialization']:
                    md_content += f"**Serialization:** {book['serialization']}  \n"
                if book['illustrator']:
                    md_content += f"**Illustrator:** {book['illustrator']}  \n"
                if book['notes']:
                    md_content += f"\n{self._clean_content(book['notes'])}\n"
                md_content += "\n"
        
        with open(self.output_dir / "books.qmd", 'w', encoding='utf-8') as f:
            f.write(md_content)
    
    def create_persons_reference(self):
        """Create persons reference page"""
        print("Creating persons reference...")
        
        md_content = """---
title: "Persons Referenced in the Letters"
---

This page contains biographical information about the people mentioned in Charlotte Mary Yonge's letters.

"""
        
        # Sort persons by surname
        sorted_persons = sorted(self.persons.values(), key=lambda x: x['surname'])
        
        for person in sorted_persons:
            md_content += f"## {person['full_name']} {{#{person['id']}}}\n\n"
            
            if person['dates']:
                md_content += f"**Dates:** {person['dates']}  \n"
            if person['description']:
                md_content += f"**Description:** {person['description']}  \n"
            if person['biography']:
                md_content += f"\n{self._clean_content(person['biography'])}\n"
            md_content += "\n"
        
        with open(self.output_dir / "persons.qmd", 'w', encoding='utf-8') as f:
            f.write(md_content)
    
    def create_others_reference(self):
        """Create others/institutions reference page"""
        print("Creating others reference...")
        
        md_content = """---
title: "Institutions and Other References"
---

This page contains information about institutions, organizations, and other entities mentioned in Charlotte Mary Yonge's letters.

"""
        
        # Group by type
        by_type = {}
        for other in self.others.values():
            type_name = other['type'] if other['type'] else 'Other'
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(other)
        
        for type_name in sorted(by_type.keys()):
            md_content += f"## {type_name}\n\n"
            
            for other in sorted(by_type[type_name], key=lambda x: x['name']):
                md_content += f"### {other['name']} {{#{other['id']}}}\n\n"
                if other['description']:
                    md_content += f"{self._clean_content(other['description'])}\n\n"
        
        with open(self.output_dir / "others.qmd", 'w', encoding='utf-8') as f:
            f.write(md_content)
    
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
                        {'text': 'References', 'href': 'others.qmd'},
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
                        'others.qmd',
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
