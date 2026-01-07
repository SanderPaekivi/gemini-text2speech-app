import os
from ebooklib import epub
from utility_functions import is_likely_heading

def create_epub_from_text(text_content, output_path, title="Paper Audio"):
    # 1. Initializing
    book = epub.EpubBook()
    
    filename_base = os.path.splitext(os.path.basename(output_path))[0]
    book.set_identifier(filename_base)
    book.set_title(title)
    book.set_language('en')
    book.add_author('Auto-Extractor')

    # 2. Parsing text into chapters, split by double newlines, which the cleaner ensures for paragraphs
    blocks = text_content.split('\n\n')
    
    chapters = []
    current_chapter_content = []
    current_chapter_title = "Start"
    chapter_count = 1

    def flush_chapter(title, content_list, count):
        if not content_list: return None
        
        # Create HTML file name
        chap_file = f'chap_{count}.xhtml'
        c = epub.EpubHtml(title=title, file_name=chap_file, lang='en')
        
        # Build HTML content, wrap title in h1, and rest in p tags
        html_body = f"<h1>{title}</h1>"
        for para in content_list:
            # NOTE: some cleanup here?
            html_body += f"<p>{para}</p>"
            
        c.content = html_body
        return c

    for block in blocks:
        clean_block = block.strip()
        if not clean_block: 
            continue

        # Check if block is a heading
        if is_likely_heading(clean_block):
            # If have previous content, save old chapter first
            if current_chapter_content:
                chap = flush_chapter(current_chapter_title, current_chapter_content, chapter_count)
                if chap: 
                    book.add_item(chap)
                    chapters.append(chap)
                    chapter_count += 1
            
            # Reset for new chapter
            current_chapter_title = clean_block
            current_chapter_content = [] # title does not go to body text list, but as H1
        else:
            current_chapter_content.append(clean_block)

    # Flush remaining text
    if current_chapter_content:
        chap = flush_chapter(current_chapter_title, current_chapter_content, chapter_count)
        if chap:
            book.add_item(chap)
            chapters.append(chap)

    # 3. Define table of contents and spine...
    book.toc = (tuple(chapters))
    
    # Add default NCX and Nav files (required for epub readers to navigate aparently, not sure what they are exactly)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # CSS style, sloppy
    style = 'body { font-family: Helvetica, Arial, sans-serif; } h1 { text-align: left; } p { text-align: justify; }'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)

    # read order
    book.spine = ['nav'] + chapters

    # 4. Write output
    epub.write_epub(output_path, book, {})
    print(f"EPUB successfully saved to: {output_path}")