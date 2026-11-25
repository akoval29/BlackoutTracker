from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys

dest = Path('dist/BlackoutTracker/licenses')
dest.mkdir(parents=True, exist_ok=True)
shutil.copytree('licenses', dest, dirs_exist_ok=True)
for package in ('PySide6_Essentials', 'shiboken6', 'tzdata', 'pyinstaller'):
    dist = distribution(package)
    for file in dist.files or []:
        if any(s in str(file).lower() for s in ('license', 'copying')) and dist.locate_file(file).is_file():
            target = dest / package / str(file)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dist.locate_file(file), target)
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.exists():
    shutil.copy2(python_license, dest / 'Python-LICENSE.txt')
