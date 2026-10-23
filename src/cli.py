import os
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from src.knowledge_manager import KnowledgeManager
from src.vision_engine import VisionEngine
from src.director import DirectorEngine

app = typer.Typer(help="ImageContext-Generator: Generate inisiasi.txt from lab screenshots")
console = Console()

@app.command()
def scan(
    course: str = typer.Option(..., "--course", "-c", help="Course ID (e.g., kepl, ppg)"),
    pertemuan: str = typer.Option(..., "--pertemuan", "-p", help="Pertemuan folder name (e.g., Per4)"),
    workspace_root: str = typer.Option("workspace", "--workspace", "-w", help="Workspace root directory"),
):
    """Scan and list screenshots in a pertemuan folder"""
    screenshots_dir = Path(workspace_root) / course.upper() / "screenshots" / pertemuan
    
    if not screenshots_dir.exists():
        console.print(f"[red]❌ Directory not found: {screenshots_dir}[/red]")
        raise typer.Exit(1)
    
    images = sorted([f for f in screenshots_dir.glob("*.png") if f.stem.isdigit()], 
                    key=lambda x: int(x.stem))
    
    table = Table(title=f"Screenshots in {course.upper()}/{pertemuan}")
    table.add_column("#", style="cyan")
    table.add_column("Filename", style="green")
    table.add_column("Size", style="yellow")
    
    for img in images:
        stat = img.stat()
        size_mb = stat.st_size / (1024 * 1024)
        table.add_row(img.stem, img.name, f"{size_mb:.2f} MB")
    
    console.print(table)
    console.print(f"\nTotal: {len(images)} images")

@app.command()
def generate(
    course: str = typer.Option(..., "--course", "-c", help="Course ID (e.g., kepl, ppg)"),
    pertemuan: str = typer.Option(..., "--pertemuan", "-p", help="Pertemuan folder name (e.g., Per4)"),
    workspace_root: str = typer.Option("workspace", "--workspace", "-w", help="Workspace root directory"),
    knowledge_dir: str = typer.Option("knowledge/courses", "--knowledge", "-k", help="Knowledge base directory"),
):
    """Generate inisiasi.txt from screenshots using Vision AI + knowledge base"""
    course_clean = course.upper()
    screenshots_dir = Path(workspace_root) / course_clean / "screenshots" / pertemuan
    output_file = Path(workspace_root) / course_clean / "inisiasi" / f"{pertemuan}.txt"
    
    if not screenshots_dir.exists():
        console.print(f"[red]❌ Screenshots directory not found: {screenshots_dir}[/red]")
        raise typer.Exit(1)
    
    km = KnowledgeManager(knowledge_dir)
    ve = VisionEngine()
    
    result = ve.generate_course_inisiasi(
        course_id=course.lower(),
        screenshots_dir=str(screenshots_dir),
        knowledge_manager=km,
        output_file=str(output_file)
    )
    
    if result["errors"] > 0:
        console.print(f"[yellow]⚠️ Completed with {result['errors']} errors[/yellow]")
    else:
        console.print("[green]✅ Generation completed successfully![/green]")

@app.command()
def list_courses(
    knowledge_dir: str = typer.Option("knowledge/courses", "--knowledge", "-k", help="Knowledge base directory"),
):
    """List available course configurations"""
    km = KnowledgeManager(knowledge_dir)
    configs = list(Path(knowledge_dir).glob("*.yaml"))
    
    table = Table(title="Available Courses")
    table.add_column("Course ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Code", style="yellow")
    table.add_column("Semester", style="magenta")
    
    for cfg in configs:
        try:
            course = km.load_course_config(cfg.stem)
            table.add_row(
                cfg.stem,
                course.get("course_name", ""),
                course.get("code", ""),
                str(course.get("semester", ""))
            )
        except:
            table.add_row(cfg.stem, "Error loading", "", "")
    
    console.print(table)

@app.command()
def plan(
    course: str = typer.Option(..., "--course", "-c", help="Course ID (e.g., kepl, ppg)"),
    pertemuan: str = typer.Option(..., "--pertemuan", "-p", help="Pertemuan folder name (e.g., Per4, UTS)"),
    repo_path: str = typer.Option(None, "--repo", "-r", help="Path to project repository for git timeline matching"),
    workspace_root: str = typer.Option("workspace", "--workspace", "-w", help="Workspace root directory"),
):
    """Director Mode: Plan screenshot order and match against Git commits"""
    course_clean = course.upper()
    screenshots_dir = Path(workspace_root) / course_clean / "screenshots" / pertemuan
    
    if not screenshots_dir.exists():
        console.print(f"[red]❌ Directory not found: {screenshots_dir}[/red]")
        raise typer.Exit(1)
        
    director = DirectorEngine(repo_path=repo_path)
    plan_items = director.plan_narrative(str(screenshots_dir))
    
    table = Table(title=f"🎬 Director Plan for {course_clean}/{pertemuan}")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Filename", style="green")
    table.add_column("Mod Time", style="yellow")
    table.add_column("Aligned Git Context", style="magenta")
    
    for item in plan_items[:25]:  # preview first 25
        table.add_row(
            str(item["index"]),
            item["original_name"],
            item["mtime"].strftime("%Y-%m-%d %H:%M:%S"),
            item["git_context"][:60] + "..." if len(item["git_context"]) > 60 else item["git_context"]
        )
        
    console.print(table)
    if len(plan_items) > 25:
        console.print(f"[dim]... and {len(plan_items) - 25} more screenshots[/dim]")
        console.print(f"\n[bold green]Total planned:[/bold green] {len(plan_items)} screenshots.")

@app.command()
def organize(
    course: str = typer.Option(..., "--course", "-c", help="Course ID (e.g., kepl, ppg)"),
    pertemuan: str = typer.Option(..., "--pertemuan", "-p", help="Pertemuan folder name (e.g., UTS)"),
    repo_path: str = typer.Option(None, "--repo", "-r", help="Path to project repository for git timeline matching"),
    workspace_root: str = typer.Option("workspace", "--workspace", "-w", help="Workspace root directory"),
    copy: bool = typer.Option(True, "--copy/--rename", help="Copy files to a new 'organized' folder or rename in place (default: copy)"),
):
    """Director Mode: Organize screenshots into 1.png, 2.png, ... based on narrative plan"""
    course_clean = course.upper()
    screenshots_dir = Path(workspace_root) / course_clean / "screenshots" / pertemuan
    
    if not screenshots_dir.exists():
        console.print(f"[red]❌ Directory not found: {screenshots_dir}[/red]")
        raise typer.Exit(1)
        
    director = DirectorEngine(repo_path=repo_path)
    plan_items = director.plan_narrative(str(screenshots_dir))
    
    target_dir = screenshots_dir if not copy else screenshots_dir.parent / f"{pertemuan}_organized"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"\n[bold yellow]📦 Organizing {len(plan_items)} images to {target_dir.name}...[/bold yellow]")
    
    import shutil
    for item in plan_items:
        src = item["path"]
        ext = src.suffix
        dest = target_dir / f"{item['index']}{ext}"
        
        if copy:
            shutil.copy2(src, dest)
        else:
            # Atomic rename if in same folder
            src.rename(dest)
            
    console.print(f"[green]✅ Successfully organized into {target_dir}[/green]")

@app.command()
def generate_director(
    course: str = typer.Option(..., "--course", "-c", help="Course ID (e.g., kepl, ppg)"),
    pertemuan: str = typer.Option(..., "--pertemuan", "-p", help="Pertemuan folder name (e.g., UTS)"),
    repo_path: str = typer.Option(None, "--repo", "-r", help="Path to project repository for git timeline matching"),
    output: str = typer.Option(None, "--output", "-o", help="Custom output file path"),
    workspace_root: str = typer.Option("workspace", "--workspace", "-w", help="Workspace root directory"),
    knowledge_dir: str = typer.Option("knowledge/courses", "--knowledge", "-k", help="Knowledge base directory"),
):
    """Director Mode: Plan and generate inisiasi.txt using multimodal vision + Git timeline"""
    course_clean = course.upper()
    screenshots_dir = Path(workspace_root) / course_clean / "screenshots" / pertemuan
    output_file = Path(output) if output else Path(workspace_root) / course_clean / "inisiasi" / f"{pertemuan}_director.txt"
    
    if not screenshots_dir.exists():
        console.print(f"[red]❌ Directory not found: {screenshots_dir}[/red]")
        raise typer.Exit(1)
        
    director = DirectorEngine(repo_path=repo_path)
    plan_items = director.plan_narrative(str(screenshots_dir))
    
    km = KnowledgeManager(knowledge_dir)
    ve = VisionEngine()
    
    ve.generate_director_inisiasi(
        plan_items=plan_items,
        course_id=course.lower(),
        knowledge_manager=km,
        output_file=str(output_file)
    )

if __name__ == "__main__":
    app()
