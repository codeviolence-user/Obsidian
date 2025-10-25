import os
import shutil
import google.generativeai as genai
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv
import json
import argparse

load_dotenv()

class AIFileSorter:
    def __init__(self, api_key: str, source_dir: str, target_dir: str):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.supported_extensions = {
            '.txt', '.md', '.pdf', '.doc', '.docx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp',
            '.mp3', '.wav', '.mp4', '.avi', '.mov',
            '.py', '.js', '.html', '.css', '.java', '.cpp',
            '.xls', '.xlsx', '.csv', '.json', '.xml'
        }

    def read_file_content(self, file_path: Path, max_chars: int = 5000) -> str:
        try:
            if file_path.suffix.lower() in {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv'}:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(max_chars)
                    return content
            else:
                return f"File: {file_path.name}\nExtension: {file_path.suffix}\nSize: {file_path.stat().st_size} bytes"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def get_category_from_ai(self, file_path: Path) -> Dict[str, str]:
        file_content = self.read_file_content(file_path)
        file_name = file_path.name
        file_ext = file_path.suffix
        prompt = f"""Analyze this file and suggest the BEST category folder name for organizing it.
File name: {file_name}
File extension: {file_ext}
Content preview:
{file_content[:2000]}
Based on the file content and context, suggest ONE specific category folder name.
The category should be:
- Descriptive and clear (e.g., "Work Documents", "Personal Photos", "Python Projects", "Research Papers")
- In English or Russian (choose the most appropriate)
- Concise (1-3 words)
- Useful for organizing files
Respond ONLY with a JSON object in this exact format:
{{
    "category": "folder_name",
    "reason": "brief explanation why this category fits"
}}
Do not include any other text, markdown formatting, or code blocks."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

            result = json.loads(response_text)
            return result
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse AI response for {file_name}, using default category")
            return {"category": "Uncategorized", "reason": "AI response parsing error"}
        except Exception as e:
            print(f"Error processing {file_name}: {str(e)}")
            return {"category": "Uncategorized", "reason": str(e)}

    def create_category_folder(self, category_name: str) -> Path:
        safe_name = "".join(c for c in category_name if c.isalnum() or c in (' ', '-', '_')).strip()
        category_path = self.target_dir / safe_name
        category_path.mkdir(parents=True, exist_ok=True)
        return category_path

    def move_file(self, file_path: Path, category_path: Path) -> bool:
        try:
            destination = category_path / file_path.name
            counter = 1
            while destination.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                destination = category_path / f"{stem}_{counter}{suffix}"
                counter += 1

            shutil.move(str(file_path), str(destination))
            return True
        except Exception as e:
            print(f"Error moving file {file_path.name}: {str(e)}")
            return False

    def sort_files(self) -> Dict[str, List[str]]:
        if not self.source_dir.exists():
            raise ValueError(f"Source directory does not exist: {self.source_dir}")

        self.target_dir.mkdir(parents=True, exist_ok=True)
        files = [f for f in self.source_dir.iterdir() if f.is_file()]

        if not files:
            print("No files found in source directory")
            return {}

        results = {}

        print(f"Processing {len(files)} files...")

        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] Analyzing: {file_path.name}")

            ai_result = self.get_category_from_ai(file_path)
            category = ai_result['category']
            reason = ai_result['reason']

            print(f"  Category: {category}")
            print(f"  Reason: {reason}")

            if category not in results:
                results[category] = []
            results[category].append(file_path.name)

            category_path = self.create_category_folder(category)
            if self.move_file(file_path, category_path):
                print(f"  Moved to: {category_path}")
            else:
                print(f"  Failed to move")

            print()
        return results

    def print_summary(self, results: Dict[str, List[str]]):
        print("SORTING SUMMARY")

        for category, files in sorted(results.items()):
            print(f"{category} ({len(files)} files):")
            for file in files:
                print(f"  - {file}")
            print()

def main():
    parser = argparse.ArgumentParser(
        description='Sort files into categorized folders using AI'
    )
    parser.add_argument(
        'source_dir',
        nargs='?',
        default='.',
        help='Source directory containing files to sort (default: current directory)'
    )
    parser.add_argument(
        '--target',
        '-t',
        default='./sorted_files',
        help='Target directory for sorted files (default: ./sorted_files)'
    )
    parser.add_argument(
        '--api-key',
        '-k',
        help='Google Gemini API key (can also be set via GEMINI_API_KEY env variable)'
    )

    args = parser.parse_args()

    api_key = args.api_key or os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("Error: Gemini API key not found!")
        print("Please provide it via --api-key argument or GEMINI_API_KEY environment variable")
        print("\nTo get an API key:")
        print("1. Visit https://makersuite.google.com/app/apikey")
        print("2. Create a new API key")
        print("3. Set it in .env file: GEMINI_API_KEY=your_key_here")
        return

    try:
        sorter = AIFileSorter(
            api_key=api_key,
            source_dir=args.source_dir,
            target_dir=args.target
        )

        results = sorter.sort_files()

        sorter.print_summary(results)

        print(f"Files successfully sorted into: {args.target}")

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()