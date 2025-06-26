import re
import pymupdf
from tqdm import tqdm
from collections import defaultdict

from utility_functions import reduce_text_numerics

def extract_and_clean_pdf_text(pdf_path):
    # Core text extraction and cleaning logic 
    print(f"\n --- Starting analysis of '{pdf_path}' ---")
    try:
        doc = pymupdf.open(pdf_path)
    except FileNotFoundError:
        print(f"!!! Error: PDF file not found at '{pdf_path}' !!!")
        return None
    except Exception as e:
        print(f"!!! An error occurred while opening the PDF: {e} !!!")
        return None

    # First loop: collecting potential headers and footers
    header_counts = defaultdict(int)
    footer_counts = defaultdict(int)
    print("Identifying potential headers and footers...")
    for page in tqdm(doc, desc="Analyzing page structure"):
        # Ordering blocks based on height on page
        blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
        if not blocks:
            continue

        # Log the text of the first block as a potential header
        first_block_text = blocks[0][4].strip()
        if first_block_text:
            normalized_header = reduce_text_numerics(first_block_text)
            header_counts[normalized_header] += 1
            
        # Log the text of the last block as a potential footer
        if len(blocks) > 1:
            last_block_text = blocks[-1][4].strip()
            if last_block_text:
                normalized_footer = reduce_text_numerics(last_block_text)
                footer_counts[normalized_footer] += 1

    # Confirm potential headers/footers
    confirmed_headers_footers = set()
    confirmed_headers_footers.add('_NUM_') 
    for text, count in header_counts.items():
        if count > 1:
            confirmed_headers_footers.add(text)
    for text, count in footer_counts.items():
        if count > 1:
            confirmed_headers_footers.add(text)
    
    print(f"Identified {len(confirmed_headers_footers)} unique repeating headers/footers.")

    # Second loop: collecting clean text, excluding confirmed headers/footers
    full_text_parts = []
    skippable_keywords = ['pp.', 'E-mail:', 'doi:'] # Keywords to skip in text extraction, add more as necessary
    
    print("Extracting main content...")
    for page in tqdm(doc, desc="Extracting clean text"):
        blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
        for index, block in enumerate(blocks):
            block_text = block[4]
            stripped_block_text = block_text.strip()

            if reduce_text_numerics(stripped_block_text) in confirmed_headers_footers:
                continue

            is_last_block = (index == len(blocks) - 1)
            if is_last_block and stripped_block_text.startswith(tuple(str(n) for n in range(10))):
                continue
            
            if any(keyword.lower() in stripped_block_text.lower() for keyword in skippable_keywords):
                continue

            full_text_parts.append(block_text)

    # Global text cleanup
    full_text = "\n".join(full_text_parts)
    
    match = re.search(r'^\s*(Acknowledgments?|References)\s*$', full_text, re.MULTILINE | re.IGNORECASE) #TODO: Make this more robust, check for applicability issues (multiple papers in row in pdf?)
    if match:
        print("Found References/Acknowledgments section. Truncating text.")
        full_text = full_text[:match.start()]
    
    # Joining words separated by newline only if they have hyphen in middle
    text = re.sub(r'([a-zA-Z]+)-\n', r'\1', full_text)
    # Replacing remaining newlines with spaces
    text = text.replace('\n', ' ')

    # Targeted citation removal
    text = re.sub(r'\([^)]*((?:19|20)\d{2}|et al\.|p\.|pp\.)[^)]*\)', '', text)
    # Final whitespace cleanup
    text = re.sub(r'\s+', ' ', text).strip()
    
    print("\nText extraction and cleaning complete.")
    return text