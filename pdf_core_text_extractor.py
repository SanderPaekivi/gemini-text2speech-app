import re
import pymupdf
from tqdm import tqdm
from collections import defaultdict

from utility_functions import reduce_text_numerics, is_likely_heading, clean_common_pdf_artifacts, load_custom_fixes_from_file, is_list_item

DEFAULT_FIXES = {
    "! ®": "",
    "!®": "",
    "'?": "",
    "?°": "",
    "?!": "",
    "!?": "",
    "??": "",
    "!!": "",
    "*,": "",
    ",*": "",
    " , ": " ",
    "*°": "",
    ".*": ".",
    ".?": "."
    }

def extract_and_clean_pdf_text(pdf_path, start_page_index=0, end_page_index=None, custom_replacements=None):
    final_fixes = DEFAULT_FIXES.copy()
    if custom_replacements:
        final_fixes.update(custom_replacements)

    print(f"\n Starting analysis of '{pdf_path}'.")
    try:
        doc = pymupdf.open(pdf_path)
    except FileNotFoundError:
        print(f"!!! Error: PDF file not found at '{pdf_path}' !!!")
        return None
    except Exception as e:
        print(f"!!! An error occurred while opening the PDF: {e} !!!")
        return None
    
    total_pages = len(doc)
    if end_page_index is None or end_page_index > total_pages:
        actual_end_index = total_pages
    else:
        actual_end_index = end_page_index
    
    if start_page_index >= actual_end_index:
        print(f"!!! Error: Start page ({start_page_index+1}) is after End page ({actual_end_index}).")
        return None
        
    print(f"Processing range: Page {start_page_index + 1} to Page {actual_end_index}")

    # First loop: collecting potential headers and footers
    header_counts = defaultdict(int)
    footer_counts = defaultdict(int)
    print("Identifying potential headers and footers...")
    
    for page_num in tqdm(range(start_page_index, actual_end_index), desc="Analyzing page structure"):
        page = doc[page_num]
        blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
        if not blocks:
            continue

        first_block_text = blocks[0][4].strip()
        if first_block_text:
            normalized_header = reduce_text_numerics(first_block_text)
            header_counts[normalized_header] += 1
            
        if len(blocks) > 1:
            last_block_text = blocks[-1][4].strip()
            if last_block_text:
                normalized_footer = reduce_text_numerics(last_block_text)
                footer_counts[normalized_footer] += 1

    confirmed_headers_footers = set()
    confirmed_headers_footers.add('_NUM_') 
    for text, count in header_counts.items():
        if count > 1: confirmed_headers_footers.add(text)
    for text, count in footer_counts.items():
        if count > 1: confirmed_headers_footers.add(text)
    
    print(f"Identified {len(confirmed_headers_footers)} unique repeating headers/footers.")

    # Second loop: collecting clean text
    full_text_parts = []
    skippable_keywords = ['pp.', 'E-mail:', 'doi:'] 
    
    print("Extracting main content...")
    for page_num in tqdm(range(start_page_index, actual_end_index), desc="Extracting clean text"):
        page = doc[page_num]
        blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
        
        for index, block in enumerate(blocks):
            block_text = block[4]
            stripped_block_text = block_text.strip()

            # 1. Block-level filters
            if reduce_text_numerics(stripped_block_text) in confirmed_headers_footers:
                continue
            
            # Skip lone page numbers at bottom
            # is_last_block = (index == len(blocks) - 1)
            # if is_last_block and stripped_block_text.startswith(tuple(str(n) for n in range(10))):
            #     continue
            # Only delete if it starts with a number AND is short (e.g. < 10 chars)
            # This allows "1. Large issues..." (len 200+) to pass, but deletes "341" (len 3).
            is_last_block = (index == len(blocks) - 1)
            if is_last_block and stripped_block_text[0].isdigit():
                # Check length! Page numbers are rarely longer than 4-5 digits/chars
                if len(stripped_block_text) < 10:
                    continue
            
            if any(keyword.lower() in stripped_block_text.lower() for keyword in skippable_keywords):
                continue

            # 2. Line by line processing, split block into lines to detect headings
            lines = block_text.split('\n')
            
            for line in lines:
                clean_line = line.strip()
                if not clean_line:
                    continue
                
                is_heading = is_likely_heading(clean_line)

                if is_heading:
                    merged = False
                    if full_text_parts:
                        last_entry = full_text_parts[-1]
                        
                        # Checking if last entry is a heading tag, to consider merging
                        if last_entry.startswith(" <<<HEADING>>>"):
                            # Extract actual text inside previous tag
                            # Format is: " <<<HEADING>>>TEXT<<<END_HEADING>>> "
                            prev_text = last_entry.replace(" <<<HEADING>>>", "").replace("<<<END_HEADING>>> ", "")
                            
                            # Are both ALL CAPS? Want to allow for non-letters like numbers/punctuation
                            prev_is_caps = re.sub(r'[^a-zA-Z]', '', prev_text).isupper()
                            curr_is_caps = re.sub(r'[^a-zA-Z]', '', clean_line).isupper()
                            
                            if prev_is_caps and curr_is_caps:
                                # Merging, remove old tag, append current line to previous text, re-tag
                                new_combined_text = f"{prev_text} {clean_line}"
                                full_text_parts[-1] = f" <<<HEADING>>>{new_combined_text}<<<END_HEADING>>> "
                                merged = True
                    
                    if not merged:
                        # independent new heading
                        marked_text = f" <<<HEADING>>>{clean_line}<<<END_HEADING>>> "
                        full_text_parts.append(marked_text)
                elif is_list_item(clean_line):
                    # Remove bullet symbol (•, -, or other) to standardize later
                    # This regex should remove start symbol and any surrounding whitespace
                    content = re.sub(r'^\s*[•●\-\*]\s*', '', clean_line)
                    
                    # Wraps in tags to protect from being merged into a paragraph
                    marked_text = f" <<<LIST_ITEM>>>{content}<<<END_LIST_ITEM>>> "
                    full_text_parts.append(marked_text)
                
                else:
                    # its normal text
                    full_text_parts.append(line)

    # General text cleanup
    full_text = "\n".join(full_text_parts)
    
    # 1. Hyphenation fix
    # Uses full_text as source, so must be done BEFORE collapsing newlines
    text = re.sub(r'([a-zA-Z]+)-\s*\n\s*', r'\1', full_text)

    # 2. Apply common PDF artifact fixes, including custom ones
    text = clean_common_pdf_artifacts(text, custom_fixes=final_fixes)
    
    # 3. Collapsing normal newlines to spaces
    text = text.replace('\n', ' ')
    
    # 4. Collapsing multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # 5. Expanding Heading tags into structure
    # This must be done AFTER space collapse, so these newlines survive
    text = text.replace("<<<HEADING>>>", "\n\n")
    text = text.replace("<<<END_HEADING>>>", "\n\n")

    # lists -> newline + dash
    # ensure items are separated and paused correctly in TTS
    text = text.replace(" <<<LIST_ITEM>>>", "\n- ")
    text = text.replace("<<<END_LIST_ITEM>>> ", "")

    # 6. Citation removal
    text = re.sub(r'\([^)]*((?:19|20)\d{2}|et al\.|p\.|pp\.)[^)]*\)', '', text)
    
    # 7. Final cleanup of any weird spaces created by tags
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    print("\nText extraction and cleaning complete.")
    return text