# ImageContext-Generator Engine (ICG)
# File Inisiasi proyek untuk struktur dasar.

import os

def init_project():
    print("Inisialisasi direktori ImageContext-Generator...")
    folders = [
        "src",
        "knowledge/courses",
        "tests/fixtures"
    ]
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"Created: {folder}")

if __name__ == "__main__":
    init_project()
