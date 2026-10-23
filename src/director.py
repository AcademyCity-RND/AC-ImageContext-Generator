import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from PIL import Image
from rich.console import Console

console = Console()

class DirectorEngine:
    def __init__(self, repo_path: str = None):
        """Initialize Director Engine with optional repo path for git context matching"""
        self.repo_path = repo_path
        self.git_timeline = []
        if repo_path and Path(repo_path).exists():
            self._load_git_timeline()

    def _load_git_timeline(self):
        """Extract git commit history with timestamps and messages"""
        try:
            cmd = ["git", "-C", self.repo_path, "log", "--pretty=format:%h|%ad|%s", "--date=iso"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 2)
                if len(parts) == 3:
                    commit_hash, date_str, subject = parts
                    try:
                        dt = datetime.fromisoformat(date_str.strip())
                        self.git_timeline.append({
                            "hash": commit_hash,
                            "time": dt,
                            "subject": subject
                        })
                    except ValueError:
                        continue
            console.print(f"[green]✅ Loaded {len(self.git_timeline)} git commits for narrative alignment.[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️ Could not load git timeline: {e}[/yellow]")

    def get_nearest_commit(self, file_mtime: datetime) -> str:
        """Find the most relevant commit matching the screenshot modification time"""
        if not self.git_timeline:
            return "General development progress"
        
        # Find commit closest in time (usually slightly before or during)
        best_match = min(self.git_timeline, key=lambda c: abs((c["time"] - file_mtime).total_seconds()))
        return best_match["subject"]

    def plan_narrative(self, screenshots_dir: str, draft_inisiasi_path: str = None) -> List[Dict[str, Any]]:
        """
        Pass 1: Visual Census & Narrative Planning.
        Analyze all screenshots and draft hints (if any) to create an ordered, grouped execution plan.
        """
        img_dir = Path(screenshots_dir)
        files = []
        
        # Collect all PNG files (both numbered and raw timestamped)
        for f in img_dir.glob("*.png"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime).astimezone()
            files.append({
                "path": f,
                "name": f.name,
                "stem": f.stem,
                "mtime": mtime,
                "is_numeric": f.stem.isdigit(),
                "numeric_val": int(f.stem) if f.stem.isdigit() else 9999
            })

        # Sort files: numeric first by value, then timestamp for non-numeric
        numeric_files = sorted([f for f in files if f["is_numeric"]], key=lambda x: x["numeric_val"])
        timestamp_files = sorted([f for f in files if not f["is_numeric"]], key=lambda x: x["mtime"])
        
        all_ordered = numeric_files + timestamp_files
        
        console.print(f"[bold cyan]🎬 Director Mode: Planning narrative for {len(all_ordered)} screenshots...[/bold cyan]")
        
        planned_items = []
        for idx, item in enumerate(all_ordered, start=1):
            git_ctx = self.get_nearest_commit(item["mtime"])
            planned_items.append({
                "index": idx,
                "original_name": item["name"],
                "path": item["path"],
                "mtime": item["mtime"],
                "git_context": git_ctx
            })
            
        return planned_items
