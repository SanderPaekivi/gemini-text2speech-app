import os
import re
import sys

# specific recurring junk here
CUSTOM_INTRUSIONS = [
    "Roy, Petitot, Pachoud, and Varela",
    "Jean-Michel Roy, Jean Petitot, Bernard",
    "Pachoud, and Francisco J. Varela",
    "CHAPTER ONE",
    # ... add as necessary
]

def clean_extracted_text(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    print(f"Reading '{filepath}'...")
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    original_len = len(text)

    # Intrusions inside words
    print("Performing surgical removal of intrusions...")
    for intrusion in CUSTOM_INTRUSIONS:
        # Escape special chars like dots in "J. Varela" just in case 
        pattern_str = re.escape(intrusion)
        
        # Matches: Letter + (optional newline/space) + Intrusion + (optional newline/space) + Letter
        surgery_pattern = r'([a-zA-Z])\s*' + pattern_str + r'\s*\n*\s*([a-zA-Z])'
        text = re.sub(surgery_pattern, r'\1\2', text, flags=re.IGNORECASE)
        
        # Just remove the phrase if floating on its own
        text = re.sub(pattern_str, '', text, flags=re.IGNORECASE)

    print("Stripping page numbers...")
    # Remove lines that are just numbers
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    # Remove "104 Author Name" style headers
    text = re.sub(r'^\s*\d+\s+[A-Z][^\n]{1,80}\s*$', '', text, flags=re.MULTILINE)
    # Remove "Author Name 105" style headers
    text = re.sub(r'^\s*[A-Z][^\n]{1,80}\s+\d+\s*$', '', text, flags=re.MULTILINE)

    # Fix hyphen issues, "unwaver- \n ing" -> "unwavering"
    print("Bridging hyphenated splits...")
    text = re.sub(r'([a-zA-Z])\s*-\s*\n+\s*([a-zA-Z])', r'\1\2', text)

    print("Normalizing whitespace...")
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove trailing/leading whitespace per line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    base, ext = os.path.splitext(filepath)
    output_path = f"{base}_cleaned{ext}"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"Done! Saved to: {output_path}")
    print(f"Removed {original_len - len(text)} characters.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        clean_extracted_text(sys.argv[1])
    else:
        user_input = input(">>> Enter path to .txt file: ").strip().strip('"').strip("'")
        clean_extracted_text(user_input)