import os
import re
import sys
import ast
import glob
import platform
import subprocess
import difflib

def get_unique_filename(path):
    # Checks if filename exists, appends number if it does
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while True:
        new_path = f"{base} ({counter}){ext}"
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def open_file_for_editing(filepath):
    # Opens a file in the default system editor
    # NOTE: Only tested WSL/Windows, others are from copilot, hope they work! 
    print(f"Attempting to open '{filepath}' for manual editing...")
    try:
        is_wsl = 'microsoft' in platform.uname().release.lower() or 'wsl' in platform.uname().release.lower()
        if sys.platform == "win32":
            os.startfile(filepath)
        elif is_wsl:
            # In WSL, use windows to open file, not VIM
            absolute_wsl_path = os.path.abspath(filepath)
            windows_path = subprocess.check_output(['wslpath', '-w', absolute_wsl_path]).strip().decode('utf-8')
            subprocess.call(['explorer.exe', windows_path])
        elif sys.platform == "darwin": # macOS
            subprocess.call(["open", filepath])
        else: # Linux, WSL, etc.
            subprocess.call(["xdg-open", filepath])
    except Exception as e:
        print(f"\n!!! Could not automatically open the file. Error: {e} !!!!")
        print("Open the file manually to make edits.")

def reduce_text_numerics(text):
    # Replaces all digits in a string with a placeholder for pattern matching
    return re.sub(r'\d+', '_NUM_', text)

def stitch_and_save_partial_audio(temp_dir_path, original_output_filename):
    # Method for when voice generation fails - finds existing chunks and stitches them into a partial audio file, if requested
    print("\n--- Attempting to save partial audio ---")
    chunk_files = sorted(glob.glob(os.path.join(temp_dir_path, "chunk_*.mp3")))
    
    if not chunk_files:
        print("No completed chunks found to save.")
        return

    num_chunks_saved = len(chunk_files)
    print(f"Found {num_chunks_saved} completed chunks.")
    
    # Create a new name for the partial file to avoid confusion
    base, ext = os.path.splitext(original_output_filename)
    partial_filename = f"{base}_partial_to_chunk_{num_chunks_saved}{ext}"
    
    print(f"Combining chunks into '{partial_filename}'...")
    with open(partial_filename, "wb") as out_file:
        for chunk_file in chunk_files:
            with open(chunk_file, "rb") as in_chunk:
                out_file.write(in_chunk.read())
    
    print(f"Partial audiobook saved successfully as '{partial_filename}'")

def calculate_tts_cost(character_count, price_per_million_chars):
    # Calculates the estimated cost for a given number of characters
    return (character_count / 1_000_000) * price_per_million_chars

def smart_stitch(previous_text, new_text, search_window=4000):
    # Stitches two texts using word-based matching to ignore whitespace/formatting differences
    if not previous_text:
        return new_text

    tail = previous_text[-search_window:]
    head = new_text[:search_window]

    def tokenize_with_indices(text):
        tokens = []
        for m in re.finditer(r'\S+', text):
            tokens.append({
                "word": m.group(0),
                "start": m.start(),
                "end": m.end()
            })
        return tokens

    tail_tokens = tokenize_with_indices(tail)
    head_tokens = tokenize_with_indices(head)
    
    tail_words = [t["word"] for t in tail_tokens]
    head_words = [t["word"] for t in head_tokens]

    matcher = difflib.SequenceMatcher(None, tail_words, head_words)
    match = matcher.find_longest_match(0, len(tail_words), 0, len(head_words))

    if match.size > 10:
        print(f"    [Stitch] Found overlap of {match.size} words.")
        last_match_word_idx = match.b + match.size - 1
        cut_char_index = head_tokens[last_match_word_idx]["end"]
        return previous_text + new_text[cut_char_index:]
    else:
        print("    [Stitch] No overlap found. Appending with newline.")
        return previous_text + "\n" + new_text
    
def is_likely_heading(text):
    text = text.strip()
    if not text:
        return False
        
    # Checking length, headings are rarely long
    if len(text) > 200:
        return False
    
    # Matches "III.", "IV:", "VI " followed by a capital letter.
    # regex explanation:
    # ^           : Start of string
    # [IVXLCDM]+  : One or more Roman numeral characters (uppercase)
    # \s*[:.]     : Optional space, then MANDATORY punctuation (dot or colon) to avoid matching words like "I" or "MIX"
    # \s+         : Space
    # [A-Z]       : Followed by a capital letter (The title text)
    if re.match(r'^[IVXLCDM]+\s*[:.]\s+[A-Z]', text):
        return True

    # Matches standard keywords like "Chapter 1", "Section IV", "3. Results", "Appendix A"
    if re.match(r'^(?:chapter|section|part|appendix|figure|table)\s+\w+', text, re.IGNORECASE):
        return True
    
    # Looks for numbered sections like "1. Introduction" or "2.3 Methodology"
    # ^\d+          : Starts with a number (e.g., "4")
    # (?:\.\d+)* : Optional repeating groups of ".Number" (e.g., ".1.1")
    # \.?           : OPTIONAL trailing dot (Handles "4.1.1." AND "4.1.1")
    # \s+           : Space
    # [A-Z]         : Followed by a capital letter
    if re.match(r'^\d+(?:\.\d+)*\.?\s+[A-Z]', text):
        return True

    # All caps check, some styles have headings so, allowing for some punctuation so stripping digits and spaces to check if the LETTERS are uppercase
    clean_letters = re.sub(r'[^a-zA-Z]', '', text)
    if len(clean_letters) > 3 and clean_letters.isupper():
        return True

    return False

def clean_common_pdf_artifacts(text, custom_fixes=None):
    # Scan for and removes specific PDF text layer corruption patterns, can add custom features here. 
    if not text:
        return text
    
    # Custom fixes, for my pdf now a superscript becomes "! ®" for example
    if custom_fixes:
        for target, replacement in custom_fixes.items():
            text = text.replace(target, replacement)

    # 2. Fix for question-mark+digit corruption, a common mapping error for superscript citations like '26'
    # Matches any letter/paren/digit, followed by '?', then a digit
    # Example: "1947)?6" -> "1947)" | "Daubert?6" -> "Daubert"
    text = re.sub(r'(?<=[a-zA-Z0-9\)])\?\d+', '', text)

    # 3. Fix for exclamation+digit or similar weird suffixes
    # Matches: word followed immediately by '!' and a digit (if that ever happens)
    text = re.sub(r'(?<=[a-zA-Z])!\d+', '', text)

    return text

def load_custom_fixes_from_file(file_path):
    # Reads .txt file that should contain a Python dictionary of fixes and returns it as object
    # Supports formats:
    #   1. Raw Dict: { "a": "b" }
    #   2. Variable assignment: MY_FIXES = { "a": "b" }
    
    if not os.path.exists(file_path):
        print(f"!!! Warning: Custom fixes file not found at '{file_path}'. Ignoring.")
        return {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # If  user included some name like "CUSTOM_FIXES =" at the start, strip it
        if "=" in content:
            # split on first '=' and take the second part, should be the dict... NOTE: Am I overcomplicating?
            _, content = content.split("=", 1)
            content = content.strip()
            
        # evaluate string as a Python dict
        fixes = ast.literal_eval(content)
        
        if isinstance(fixes, dict):
            print(f"Loaded {len(fixes)} custom replacement rules.")
            return fixes
        else:
            print("!!! Error: The file content did not evaluate to a dictionary.")
            return {}

    except Exception as e:
        print(f"!!! Error parsing custom fixes file: {e}")
        print("Ensure the file contains a valid Python dictionary structure like {'bad': 'good'}.")
        return {}
    
def is_list_item(text):
    # Check if item is a list, must start with bullet + SPACE or something like that.
    # The \s+ ensures "-word" is ignored, but "- Word" is caught, so hyphenation still works...
    match = re.match(r'^\s*([•●\-\*])\s+(.*)', text)
    
    if match:
        content = match.group(2) # text after bullet
        
        # Safety check for lowercase
        # If a line starts with "- word" (dash, space, lowercase), it MIGHT be 
        # a weirdly formatted clause like " - and then he died."
        # A list item usually starts with a Capital letter or a number
        # If the content starts with a lowercase letter, we treat it as 
        # text flow/continuation, instead a bullet point.
        if content and content[0].islower():
            return False
            
        return True

    # Check for numbered lists "1. " or "IV. "
    # Must be followed by space.
    if re.match(r'^\s*(?:\d+\.|[IVX]+\.)\s+[A-Z]', text):
        return True
        
    return False