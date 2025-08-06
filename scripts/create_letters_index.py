#!/usr/bin/env python3
"""
Create a comprehensive letters index page
"""

import json
from datetime import datetime
import re

def create_letters_index():
    # Load the letters index
    with open('/workspaces/yonge/yonge-letters-quarto/data/letters_index.json', 'r') as f:
        letters = json.load(f)

    # Create the letters index page
    content = f'''---
title: "Letters Index"
---

# Letters Index

Browse all {len(letters)} letters in chronological order. Click on any letter title to read the full text.

## Search Tips

Use your browser's search function (Ctrl/Cmd+F) to find:
- Specific correspondents (e.g., "Bullock", "Morshead")
- Locations (e.g., "Otterbourne", "Winchester") 
- Topics or keywords from the letters

---

'''

    # Group letters by decade for better organization
    decades = {}
    for letter in letters:
        date_str = letter['date'] if letter['date'] else '1850'  # Default for undated
        
        # Extract year from date string 
        year_match = re.search(r'(\d{4})', date_str)
        if year_match:
            year = int(year_match.group(1))
        else:
            # Try to extract from partial dates like "Jan 31 [1894]"
            bracket_match = re.search(r'\[(\d{4})\]', date_str)
            if bracket_match:
                year = int(bracket_match.group(1))
            else:
                year = 1850  # Default fallback
        
        decade = (year // 10) * 10
        if decade not in decades:
            decades[decade] = []
        decades[decade].append(letter)

    # Sort decades and create sections
    for decade in sorted(decades.keys()):
        decade_letters = sorted(decades[decade], key=lambda x: x['date'])
        content += f"## {decade}s\n\n"
        
        for letter in decade_letters:
            content += f"**[{letter['title']}](letters/{letter['filename']})**  \n"
            if letter['date']:
                content += f"*{letter['date']}*"
            if letter['from_address']:
                content += f" • From: {letter['from_address']}"
            content += "  \n\n"

    # Write the file
    with open('/workspaces/yonge/yonge-letters-quarto/letters-index.qmd', 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Created letters index with {len(letters)} letters organized by decade")

if __name__ == "__main__":
    create_letters_index()
