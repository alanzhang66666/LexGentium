import os
import json
import jsonlines
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseConverter(ABC):
    """
    Base class for data conversion.
    """
    def __init__(self, dialog_dir: str, doc_dir: str):
        self.dialog_dir = dialog_dir
        self.doc_dir = doc_dir

    @abstractmethod
    def parse_dialog(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse dialog history from a text file."""
        pass
    
    @abstractmethod
    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """Parse structured document from a text file."""
        pass

    def convert(self, output_path: str, scenario: str):
        """Convert all files in the directory to JSONL format."""
        
        # Get all dialog files
        dialog_files = [f for f in os.listdir(self.dialog_dir) if f.endswith('.txt')]
        
        results = []
        for d_file in dialog_files:
            dialog_path = os.path.join(self.dialog_dir, d_file)
            
            # Determine document filename based on dialog filename
            # CD dialog: SF-CD-2.txt -> CD doc: 2.txt or SF-CD-2.txt depending on folder structure
            # DD dialog: 1.txt -> DD doc: 1.txt
            # CI dialog: SF-CI-1.txt -> CI doc: SF-CI-1.txt
            
            # Extract ID for matching
            case_id_match = re.search(r'(\d+)', d_file)
            if not case_id_match:
                print(f"Skipping {d_file}, valid ID not found.")
                continue
                
            case_id_num = case_id_match.group(1)
            case_id = f"{scenario}-{case_id_num}"
            
            # Attempt to find corresponding document file
            doc_filename_options = [
                 # Common patterns
                d_file,                     # Same name
                f"{case_id_num}.txt",       # Just number
                d_file.replace("SF-", ""),  # Remove prefix if present
                f"SF-{scenario}-{case_id_num}.txt" # Standard format
            ]
            
            doc_path = None
            for opt in doc_filename_options:
                p = os.path.join(self.doc_dir, opt)
                if os.path.exists(p):
                    doc_path = p
                    break
            
            if not doc_path:
                print(f"Warning: Document not found for {d_file} (tried options: {doc_filename_options})")
                document_content = {}
            else:
                try:
                    document_content = self.parse_document(doc_path)
                except Exception as e:
                    print(f"Error parsing document {doc_path}: {e}")
                    document_content = {}

            # Parse dialog
            try:
                dialog_history = self.parse_dialog(dialog_path)
            except Exception as e:
                print(f"Error parsing dialog {dialog_path}: {e}")
                dialog_history = []
            
            # Construct the final object
            # Matches J1Bench structure
            record = {
                "id": case_id,
                "scenario": scenario,
                "dialog_history": dialog_history,
                # Flatten the document content into top-level fields as expected by Evaluators?
                # Or keep structured? Let's check Evaluators.
                # CD Evaluator expects: 'claims', 'case_details', 'evidence' at top level for ground truth
                # It also expects 'specific_characters' : {'plaintiff': ..., 'defendant': ...}
            }
            
            # Merge document content into record
            record.update(document_content)
            
            results.append(record)
            
        # Write to JSONL
        with jsonlines.open(output_path, mode='w') as writer:
            writer.write_all(results)
            
        print(f"Successfully converted {len(results)} records to {output_path}")

    def _extract_section(self, text: str, start_patterns: List[str], end_patterns: List[str]) -> str:
        """Helper to extract text between patterns."""
        start_idx = -1
        for p in start_patterns:
            match = re.search(p, text)
            if match:
                start_idx = match.end()
                break
        
        if start_idx == -1:
            return ""
            
        text_rest = text[start_idx:]
        
        end_idx = len(text_rest)
        for p in end_patterns:
            match = re.search(p, text_rest)
            if match:
                if match.start() < end_idx:
                    end_idx = match.start()
                    
        return text_rest[:end_idx].strip()




