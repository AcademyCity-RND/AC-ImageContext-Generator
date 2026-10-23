import yaml
import fitz
import os
from pathlib import Path
from typing import Dict, List, Optional

class KnowledgeManager:
    def __init__(self, knowledge_dir: str = "knowledge/courses"):
        self.knowledge_dir = Path(knowledge_dir)
        self.course_cache = {}
    
    def load_course_config(self, course_id: str) -> Dict:
        """Load YAML config for a course"""
        config_path = self.knowledge_dir / f"{course_id}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Course config not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def extract_pdf_knowledge(self, pdf_path: str) -> Dict:
        """Extract structured knowledge from PDF reference"""
        doc = fitz.open(pdf_path)
        knowledge = {
            "slides": [],
            "key_terms": [],
            "topics": []
        }
        
        for page_num in range(doc.page_count):
            text = doc[page_num].get_text()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if lines:
                knowledge["slides"].append({
                    "page": page_num + 1,
                    "title": lines[0] if lines else "",
                    "content": lines[:5]  # First 5 lines as summary
                })
                # Extract potential key terms (capitalized words, technical terms)
                for line in lines[:3]:
                    words = line.split()
                    for w in words:
                        if len(w) > 3 and (w.isupper() or w[0].isupper()):
                            knowledge["key_terms"].append(w)
        
        # Deduplicate
        knowledge["key_terms"] = list(set(knowledge["key_terms"]))
        return knowledge
    
    def build_course_context(self, course_id: str, reference_dir: str = None) -> str:
        """Build comprehensive context string for vision prompt"""
        config = self.load_course_config(course_id)
        
        context_parts = [
            f"MATA KULIAH: {config.get('course_name', course_id)}",
            f"KODE: {config.get('code', '')}",
            f"DESKRIPSI: {config.get('description', '')}",
            "",
            "PANDUAN ANALISIS:",
        ]
        
        for area in config.get('analysis_guidelines', {}).get('focus_areas', []):
            context_parts.append(f"  - Fokus: {area}")
        
        context_parts.append("\n  Terminologi Teknis Kunci:")
        for term in config.get('analysis_guidelines', {}).get('technical_terms', []):
            context_parts.append(f"    - {term}")
        
        # Add PDF reference knowledge if available
        if reference_dir and Path(reference_dir).exists():
            pdf_files = list(Path(reference_dir).glob("*.pdf"))
            if pdf_files:
                context_parts.append("\n  REFERENSI MATERI PRAKTIKUM (dari slide PDF):")
                for pdf in pdf_files:
                    pdf_knowledge = self.extract_pdf_knowledge(str(pdf))
                    context_parts.append(f"    File: {pdf.name}")
                    for slide in pdf_knowledge["slides"][:3]:
                        context_parts.append(f"      Slide {slide['page']}: {slide['title'][:80]}")
                    if pdf_knowledge["key_terms"]:
                        context_parts.append(f"      Istilah kunci: {', '.join(pdf_knowledge['key_terms'][:15])}")
        
        context_parts.append("\n  FORMAT OUTPUT:")
        context_parts.append(f"  Pola baris: {config.get('output_template', {}).get('line_pattern', '{index}.png | {label} | Konteks: {context} | Arah: {direction}')}")
        context_parts.append("  Bahasa: Indonesia, singkat, teknis, langsung to-the-point")
        context_parts.append("  Gaya: Seperti catatan praktikum mahasiswa (ringkas, berurutan)")
        
        return "\n".join(context_parts)