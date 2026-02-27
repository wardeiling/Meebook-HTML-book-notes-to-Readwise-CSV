#!/usr/bin/env python3
"""
HTML Book Notes to CSV Converter
Converts ereader book notes from HTML format to CSV for Readwise import
"""

import os
import re
import csv
import argparse
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Optional


class BookNotesConverter:
    def __init__(self):
        self.csv_headers = [
            'Highlight',
            'Title', 
            'Author',
            'URL',
            'Note',
            'Location',
            'Location Type',
            'Date'
        ]
    
    def extract_title_author(self, soup: BeautifulSoup) -> tuple[str, str]:
        """Extract book title and author from the H2 tag"""
        h2_tag = soup.find('h2')
        if not h2_tag:
            return "", ""
        
        title_author = h2_tag.get_text().strip()
        
        # Split on ' - ' to separate title and author
        if ' - ' in title_author:
            parts = title_author.rsplit(' - ', 1)  # rsplit to handle titles with dashes
            title = parts[0].strip()
            author = parts[1].strip()
        else:
            title = title_author
            author = ""
        
        return title, author
    
    def parse_date(self, date_str: str) -> str:
        """Parse date string and convert to YYYY-MM-DD HH:MM:SS format"""
        try:
            # Expected format: "2025-10-12 19:38"
            date_str = date_str.strip()
            
            # Handle case where only date is provided (add default time)
            if len(date_str) == 10:  # YYYY-MM-DD
                date_str += " 00:00"
            
            # Parse the datetime
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
            
        except ValueError:
            # If parsing fails, return the original string
            return date_str
    
    def extract_highlights(self, soup: BeautifulSoup, title: str, author: str) -> List[Dict[str, str]]:
        """Extract all highlights from the HTML"""
        highlights = []
        
        # Find all highlight containers (divs with padding-top and padding-bottom)
        highlight_divs = soup.find_all('div', style=lambda x: x and 'padding-top: 1em; padding-bottom: 1em' in x)
        
        current_chapter = ""
        location_counter = 1
        
        for div in highlight_divs:
            # Check if this div contains a chapter header
            chapter_span = div.find('span', style=lambda x: x and 'color: #48b4c1' in x and 'font-weight: bold' in x)
            if chapter_span:
                current_chapter = chapter_span.get_text().strip()
                continue
            
            # Extract date
            date_div = div.find('div', style=lambda x: x and 'border-left: 5px solid rgb(237,108,0)' in x)
            date_str = ""
            if date_div:
                date_str = self.parse_date(date_div.get_text().strip())
            
            # Extract highlight text (the main content div)
            highlight_div = div.find('div', style=lambda x: x and 'font-size: 12pt' in x and 'border-left' not in (x or ''))
            if not highlight_div:
                continue
                
            highlight_text = highlight_div.get_text().strip()
            if not highlight_text:
                continue
            
            # Extract note from the remark table
            note = ""
            table = div.find('table')
            if table:
                # Find the second td which contains the user's note
                tds = table.find_all('td')
                if len(tds) >= 2:
                    note_text = tds[1].get_text().strip()
                    # Only include non-default notes (not "Underline notes")
                    if note_text and note_text != "Underline notes":
                        note = note_text
            
            # Create the highlight entry
            highlight_entry = {
                'Highlight': highlight_text,
                'Title': title,
                'Author': author,
                'URL': '',  # No URL for books
                'Note': note,
                'Location': str(location_counter),
                'Location Type': 'order',
                'Date': date_str
            }
            
            highlights.append(highlight_entry)
            location_counter += 1
        
        # Reverse order: HTML has newest/later chapters first, we want chronological order
        highlights.reverse()
        for i, h in enumerate(highlights, 1):
            h['Location'] = str(i)
        
        return highlights
    
    def convert_html_file(self, html_file_path: str) -> List[Dict[str, str]]:
        """Convert a single HTML file to highlight data"""
        try:
            with open(html_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract title and author
            title, author = self.extract_title_author(soup)
            
            # Extract highlights
            highlights = self.extract_highlights(soup, title, author)
            
            return highlights
            
        except Exception as e:
            print(f"Error processing {html_file_path}: {str(e)}")
            return []
    
    def convert_to_csv(self, html_files: List[str], output_csv: str):
        """Convert multiple HTML files to a single CSV file"""
        all_highlights = []
        
        for html_file in html_files:
            print(f"Processing: {html_file}")
            highlights = self.convert_html_file(html_file)
            all_highlights.extend(highlights)
            print(f"  Found {len(highlights)} highlights")
        
        # Write to CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
            writer.writeheader()
            writer.writerows(all_highlights)
        
        print(f"\nConversion complete!")
        print(f"Total highlights: {len(all_highlights)}")
        print(f"Output file: {output_csv}")
        
        return all_highlights
    
    def batch_process_folder(self, html_folder: str = "html-files", output_folder: str = "output"):
        """
        Batch process all HTML files in the html-files folder.
        Creates individual CSV files for each book and a combined CSV file.
        """
        html_folder_path = Path(html_folder)
        output_folder_path = Path(output_folder)
        
        # Create output folder if it doesn't exist
        output_folder_path.mkdir(exist_ok=True)
        
        # Find all HTML files
        html_files = list(html_folder_path.glob('*.html'))
        
        if not html_files:
            print(f"No HTML files found in '{html_folder}' folder.")
            print(f"Please place your HTML book note files in the '{html_folder}' folder and run again.")
            return
        
        print(f"Found {len(html_files)} HTML files to process:")
        for file in html_files:
            print(f"  - {file.name}")
        print()
        
        all_combined_highlights = []
        individual_files_created = []
        
        # Process each file individually
        for html_file in html_files:
            # Create a safe filename for the CSV
            book_name = html_file.stem
            # Remove timestamp and clean up filename
            if '_202' in book_name:  # Remove timestamp like _20251026_083943
                book_name = re.sub(r'_\d{8}_\d{6}$', '', book_name)
            
            # Replace problematic characters for filename
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', book_name)
            csv_filename = f"{safe_filename}.csv"
            csv_path = output_folder_path / csv_filename
            
            print(f"Processing: {html_file.name}")
            highlights = self.convert_html_file(str(html_file))
            
            if highlights:
                # Write individual CSV file
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                    writer.writeheader()
                    writer.writerows(highlights)
                
                all_combined_highlights.extend(highlights)
                individual_files_created.append(csv_path)
                print(f"  ✓ Created: {csv_path}")
                print(f"  ✓ Found {len(highlights)} highlights")
            else:
                print(f"  ✗ No highlights found in {html_file.name}")
            print()
        
        # Create combined CSV file
        if all_combined_highlights:
            combined_csv_path = output_folder_path / "all_books_combined.csv"
            with open(combined_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                writer.writeheader()
                writer.writerows(all_combined_highlights)
            
            print("="*60)
            print("BATCH PROCESSING COMPLETE!")
            print("="*60)
            print(f"Individual CSV files created: {len(individual_files_created)}")
            for file in individual_files_created:
                print(f"  - {file}")
            print(f"\nCombined CSV file: {combined_csv_path}")
            print(f"Total highlights across all books: {len(all_combined_highlights)}")
            print(f"\nAll files saved in: {output_folder_path.absolute()}")
        else:
            print("No highlights were found in any of the HTML files.")


def main():
    parser = argparse.ArgumentParser(
        description='Convert HTML book notes to CSV format for Readwise import',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Easy batch processing (recommended):
  python html_to_csv_converter.py --batch
  
  # Process a single file:
  python html_to_csv_converter.py book.html
  
  # Process all files in a directory:
  python html_to_csv_converter.py /path/to/html/files/
        """
    )
    parser.add_argument('input_path', nargs='?', help='Path to HTML file or directory containing HTML files')
    parser.add_argument('-o', '--output', help='Output CSV file path (default: highlights.csv)', default='highlights.csv')
    parser.add_argument('--batch', action='store_true', 
                       help='Batch process all HTML files in the "html-files" folder (recommended)')
    
    args = parser.parse_args()
    
    converter = BookNotesConverter()
    
    # Batch processing mode (recommended)
    if args.batch:
        converter.batch_process_folder()
        return
    
    # Manual processing mode
    if not args.input_path:
        print("Error: input_path is required when not using --batch mode")
        print("Use --batch for easy processing, or provide an input path")
        parser.print_help()
        return
    
    input_path = Path(args.input_path)
    
    if input_path.is_file():
        # Single file
        if not input_path.suffix.lower() == '.html':
            print("Error: Input file must be an HTML file")
            return
        html_files = [str(input_path)]
    elif input_path.is_dir():
        # Directory - find all HTML files
        html_files = [str(f) for f in input_path.glob('*.html')]
        if not html_files:
            print("Error: No HTML files found in the specified directory")
            return
    else:
        print("Error: Input path does not exist")
        return
    
    # Convert to CSV
    converter.convert_to_csv(html_files, args.output)


if __name__ == "__main__":
    main()
