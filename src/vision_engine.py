import os
import json
from pathlib import Path
from typing import List, Dict, Any

# Load .env file di direktori root proyek (auto-load)
from dotenv import load_dotenv
dotenv_path = Path(__file__).parent.parent / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
else:
    # fallback: coba direktori saat ini
    load_dotenv()

import google.generativeai as genai
from rich.console import Console
from rich.table import Table

from PIL import Image

console = Console()

class VisionEngine:
    def __init__(self, api_key: str = None, model_name: str = "models/gemini-3.1-flash-lite"):
        """Initialize Gemini Vision engine"""
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            console.print("[red]❌ Error: GOOGLE_API_KEY not found![/red]")
            raise ValueError("Google API key is required")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
    
    def analyze_image_with_context(self, image_path: str, git_context: str, general_context: str = "", planned_index: int = None) -> str:
        """Analyze a single image with specific git commit context"""
        try:
            with Image.open(image_path) as img:
                index_hint = f" (urutan ke-{planned_index} dalam narasi)" if planned_index else ""
                prompt = f"""
Git Commit Context: {git_context}
General Context: {general_context}{index_hint}

Berdasarkan gambar ini, buat satu baris format inisiasi (TANPA nomor indeks di depan):
{{label}} | Konteks: {{context}} | Arah: {{direction}}

Aturan penting:
- Utamakan APA YANG NYATA TERLIHAT DI GAMBAR (GUI/terminal/browser/editor). JANGAN menyimpulkan GHCR jika gambar adalah Docker Desktop lokal. JANGAN menyimpulkan web browser jika gambar adalah Postman!
- Gunakan Git Commit Context hanya sebagai pendukung topik/alur, BUKAN menggantikan fakta gambar.
- label: Judul singkat gambar (maksimal 50 karakter)
- Konteks: Penjelasan teknis apa yang benar-benar tampak di layar (status response, endpoint, output terminal, struktur file)
- Arah: Arah pembahasan/evaluasi teknis (CI/CD, optimasi Docker, autentikasi REST API, dll)
- Bahasa Indonesia, teknis tapi ringkas, langsung esens.
- Output HANYA satu baris format: Label | Konteks: ... | Arah: ... (JANGAN ada awalan "1.png |" atau penomoran).
"""

                response = self.model.generate_content([
                    img,
                    prompt
                ])
                
                return response.text.strip() if response.text else ""
        except Exception as e:
            console.print(f"[yellow]⚠️ Error analyzing {image_path}: {e}[/yellow]")
            return ""
    
    def generate_director_inisiasi(self,
                                   plan_items: List[Dict[str, Any]],
                                   course_id: str,
                                   knowledge_manager: "KnowledgeManager",
                                   output_file: str) -> Dict[str, Any]:
        """Generate inisiasi.txt using Director Mode planned items and git context"""
        console.print(f"\n[bold magenta]🎬 Running Director Mode Generation for {course_id}...[/bold magenta]")
        
        course_context = knowledge_manager.build_course_context(course_id)
        
        generated_lines = []
        total = len(plan_items)
        generated = 0
        errors = 0
        
        console.print(f"   Memproses {total} screenshot terencana...")
        
        for idx, item in enumerate(plan_items, 1):
            path = item["path"]
            git_ctx = item["git_context"]
            
            console.print(f"   [{idx}/{total}] Menganalisis {path.name} (Git: {git_ctx[:30]}...)")
            
            result_line = self.analyze_image_with_context(
                str(path),
                git_context=git_ctx,
                general_context=course_context
            )
            
            if result_line:
                # Strip leading numbering if model outputs "1.png |", "1. |", etc.
                import re
                cleaned = re.sub(r'^(?:(?:\d+\.png|\d+\.|\d+\))\s*\|\s*|\d+\.\s*)', '', result_line.strip())
                clean_line = f"{idx}.png | {cleaned}"
                generated_lines.append(clean_line)
                generated += 1
            else:
                # Fallback jika gagal
                generated_lines.append(f"{idx}.png | Dokumentasi Teknis {idx} | Konteks: {git_ctx} | Arah: Evaluasi UTS")
                errors += 1
                
        # Tulis ke file output
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        header = "# ========================================================\n# FORMAT INISIASI UTS - DIRECTOR MODE\n# ========================================================"
        footer = "# ========================================================"
        
        content = header + "\n" + "\n".join(generated_lines) + "\n" + footer
        out_path.write_text(content, encoding="utf-8")
        
        console.print(f"\n[green]✅ Director Mode generated successfully: {output_file}[/green]")
        return {"total": total, "generated": generated, "errors": errors}