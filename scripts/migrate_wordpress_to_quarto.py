#!/usr/bin/env python3
"""
WordPress to Quarto Migration Script for Yonge Letters
Extracts letters, persons, and other references from WordPress database
and converts them to Quarto-compatible markdown files.
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

class YongeLettersMigrator:
    def __init__(self):
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor(dictionary=True)
        self.persons = {}
        self.others = {}
        self.output_dir = Path("/workspaces/yonge/yonge-letters-quarto")
        
    def load_references(self):
        """Load persons and other references into memory for quick lookup"""
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
    
    def _clean_content(self, content):
        """Clean WordPress content and convert annotations"""
        if not content:
            return ""
            
        # Convert person annotations
        def replace_person(match):
            person_id = int(match.group(1))
            display_name = match.group(2) if match.group(2) else ""
            
            if person_id in self.persons:
                person = self.persons[person_id]
                if display_name:
                    return f"[{display_name}](../persons.qmd#{person_id})"
                else:
                    return f"[{person['full_name']}](../persons.qmd#{person_id})"
            else:
                return display_name if display_name else f"[Unknown Person {person_id}]"
        
        # Convert other/institution annotations  
        def replace_other(match):
            other_id = int(match.group(1))
            display_name = match.group(2) if match.group(2) else ""
            
            if other_id in self.others:
                other = self.others[other_id]
                if display_name:
                    return f"[{display_name}](../others.qmd#{other_id})"
                else:
                    return f"[{other['name']}](../others.qmd#{other_id})"
            else:
                return display_name if display_name else f"[Unknown Reference {other_id}]"
        
        # Convert footnote references
        def replace_footnote(match):
            footnote_num = match.group(1)
            return f"[^{footnote_num}]"
        
        # Apply transformations
        content = re.sub(r'\[\[person:(\d+)\]([^\]]*)\]', replace_person, content)
        content = re.sub(r'\[\[other:(\d+)\]([^\]]*)\]', replace_other, content)  
        content = re.sub(r'\[\[footnote:(\d+)\]\]', replace_footnote, content)
        
        # Clean up HTML entities and tags
        content = content.replace('&amp;', '&')
        content = content.replace('&lt;', '<')
        content = content.replace('&gt;', '>')
        content = re.sub(r'<[^>]+>', '', content)  # Remove HTML tags
        
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
            
            # Create letter metadata
            metadata = {
                'title': letter['post_title'],
                'date': letter['letter_date'] if letter['letter_date'] else str(letter['post_date'].date()),
                'from-address': letter['letter_fromAddress'],
                'manuscript-location': letter['manuscript_location'],
                'wordpress-id': letter['ID'],
                'original-date': str(letter['post_date'])
            }
            
            # Clean letter content
            content = self._clean_content(letter['post_content'])
            
            # Build markdown file
            md_content = "---\n"
            md_content += yaml.dump(metadata, default_flow_style=False)
            md_content += "---\n\n"
            md_content += f"# {letter['post_title']}\n\n"
            
            if letter['letter_date']:
                md_content += f"**Date:** {letter['letter_date']}  \n"
            if letter['letter_fromAddress']:
                md_content += f"**From:** {letter['letter_fromAddress']}  \n"
            if letter['manuscript_location']:
                md_content += f"**Manuscript Location:** {letter['manuscript_location']}  \n"
            md_content += "\n"
            
            md_content += content + "\n"
            
            # Add footnotes if they exist
            if footnotes:
                md_content += "\n## Footnotes\n\n"
                for num, text in footnotes.items():
                    md_content += f"[^{num}]: {text}\n\n"
            
            # Write file
            with open(letters_dir / filename, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            # Add to index
            letter_index.append({
                'id': letter['ID'],
                'title': letter['post_title'],
                'date': letter['letter_date'] if letter['letter_date'] else str(letter['post_date'].date()),
                'filename': filename,
                'from_address': letter['letter_fromAddress']
            })
            
        # Save letter index
        with open(self.output_dir / "data" / "letters_index.json", 'w', encoding='utf-8') as f:
            json.dump(letter_index, f, indent=2, ensure_ascii=False, default=str)
            
        print(f"Migrated {len(letters)} letters")
        return letter_index
    
    def create_persons_reference(self):
        """Create persons reference page"""
        print("Creating persons reference...")
        
        md_content = """---
title: "Persons Referenced in the Letters"
---

# Persons Referenced in the Letters

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

# Institutions and Other References

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
        print("Starting Yonge Letters migration to Quarto...")
        
        self.load_references()
        letter_index = self.migrate_letters()
        self.create_persons_reference()
        self.create_others_reference()
        self.create_quarto_config()
        
        print(f"Migration completed! Migrated {len(letter_index)} letters.")
        print(f"Output directory: {self.output_dir}")
        
        self.conn.close()

if __name__ == "__main__":
    migrator = YongeLettersMigrator()
    migrator.run_migration()
