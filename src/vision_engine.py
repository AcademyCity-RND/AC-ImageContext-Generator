import os
import json
from pathlib import Path
from typing import List, Dict, Any
import google.generativeai as genai
from rich.console import Console
from rich.table import Table

console = Console()

class VisionEngine:
    def __init__(self, api_key: str = None, model_name: str = "gemini-1.5-flash"):
        """Initialize Gemini Vision engine"""
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            console.print("[red]❌ Error: GOOGLE_API_KEY not found![/red]")
            raise ValueError("Google API key is required")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
    
    def analyze_image(self, image_path: str, context_prompt: str = "") -> str:
        """Analyze a single image using Gemini Vision"""
        try:
            img = genai.upload_file(image_path)
            
            prompt = f"""
{context_prompt}

Berdasarkan gambar ini, buat satu baris format inisiasi:
{index}.png | {label} | Konteks: {context} | Arah: {direction}

Aturan:
- label: Judul singkat gambar (maksimal 50 karakter)
- Konteks: Penjelasan teknis apa yang ditampilkan (paling penting, singkat, teknis)
- Arah: Arah pembahasan/pelajaran (mis: implementasi CI/CD, pengaturan docker, dll)
- Bahasa Indonesia, teknis tapi ringkas, langsung esens
"""
            
            response = self.model.generate_content([
                img,
                prompt
            ])
            
            genai.delete_file(img.name)
            return response.text.strip() if response.text else ""
            
        except Exception as e:
            console.print(f"[yellow]⚠️ Error analyzing {image_path}: {e}[/yellow]")
            return ""
    
    def generate_course_inisiasi(self, 
                                 course_id: str,
                                   screenshots_dir: str,
                                   knowledge_manager: "KnowledgeManager",
                                   output_file: str) -> Dict[str, Any]:
        """Generate inisiasi.txt for all screenshots in a course folder"""
        console.print(f"\n[bold blue]🔍 Processing {course_id} screenshots...[/bold blue]")
        
        # Get all numbered PNG files, sorted
        img_dir = Path(screenshots_dir)
        image_files = []
        
        for f in img_dir.glob("*.png"):
            stem = f.stem
            if stem.isdigit():
                image_files.append((int(stem), f))
        
        image_files.sort(key=lambda x: x[0])
        
        if not image_files:
            console.print(f"[yellow]⚠️ No PNG images found in {screenshots_dir}[/yellow]")
            return {"total": 0, "generated": 0, "errors": 0}
        
        # Build context from knowledge base
        course_context = knowledge_manager.build_course_context(
            course_id, 
            os.path.join(screenshots_dir, "..", "_reference")
        )
        
        generated_lines = []
        total = len(image_files)
        generated = 0
        errors = 0
        
        console.print(f"   Memproses {total} gambar...")
        
        for idx, (num, path) in enumerate(image_files, 1):
            # Build per-image context with index
            image_prompt = f"""
{course_context}

---
GAMBAR {idx} dari {total}: {path.name}

TASK: Analisis gambar ini dan berikan output dalam format berikut:
{idx}.png | Label | Konteks | Arah

- Label: Judul visi singkat dari gambar
- Konteks: Apa yang terjadi teknis (bug CI, docker config, Laravel routing, dll)
- Arah: Apa yang perlu dibahas/implementasi berikutnya

Jawab hanya dengan satu baris format, tanpa pemaparan panjang.
"""
            
            result = self.analyze_image(str(path), image_prompt)
            
            if result:
                generated_lines.append(result)
                generated += 1
            else:
                # Fallback manual format
                fallback = f"{idx}.png | Gambar {idx} | Konteks: Analisis visual Gambar {idx} | Arah: Review manual"
                generated_lines.append(fallback)
                errors += 1
            
            # Progress bar
            if idx % 5 == 0 or idx == total:
                console.print(f"   Progress: {idx}/{total} ({100*idx//total}%)")
        
        # Write output file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Header/footer format
        header = "# ========================================================"
        footer = "# ========================================================"
        generated_content = "\n".join([header] + generated_lines + [footer])
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(generated_content)
        
        console.print(f"\n[green]✅ Selesai! Dioutputkan ke: {output_path}[/green]")
        console.print(f"   Total: {total} gambar, Digen: {generated}, Error: {errors}")
        
        return {
            "total": total,
            "generated": generated,
            "errors": errors,
            "output_file": str(output_path)
        }