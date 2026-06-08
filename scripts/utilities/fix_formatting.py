import sys
import subprocess
import os

# Format C/C++ files
INCLUDE_FILE_EXTENSIONS = (".cpp", ".h", ".hpp")

# Ensure stable clang format version
CLANG_FORMAT_VERSION = "clang-format-17"

def _get_platform() -> str:
    """
    Get platform this script is running on.
    """
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("darwin"):
        return "mac"
    else:
        return "linux"

def _get_clang_binary(platform_sys: str) -> str:
    if platform_sys == "windows":
        return "clang-format-17.exe"
    elif platform_sys == "mac":
        return "clang-format"
    else:
        return "clang-format-17"

    
def find_files( path_from_root: str) -> list[str]:
      # Prepare path to recursive traverse
    SOURCE_DIR = os.path.join("..", "..", path_from_root)

    print("Finding files under " + os.path.join(os.getcwd(), SOURCE_DIR) + " 🗂️")

    files = []
    for root, dirnames, filenames in os.walk(SOURCE_DIR):
        files += [
            f"{os.path.join(root, f)}"
            for f in filenames
            if f.endswith(INCLUDE_FILE_EXTENSIONS)
        ]
    return files

def run_clang_format(base_cmd: list[str], source_files: list[str]) -> bool:
    print("Running clang formatting ⚙️")
    try:
        return subprocess.run(base_cmd + source_files).returncode == 0
    except KeyboardInterrupt:
        return False

    
def fix_formatting() -> None:
    PYTHON_EXECUTABLE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    os.chdir(PYTHON_EXECUTABLE_DIRECTORY)

    platform = _get_platform()
    clang = _get_clang_binary(platform)

    files = find_files("src") # main cpp trading logic directory
    if not files:
        print("No files found ❌")
        sys.exit(1)

    if (run_clang_format([clang, "-i", "--style=file"], files)):
        print("SUCCESS: formatted " + platform + " files ✅")
    else:
        print("ERROR: clang format run failed ❌")
     

if __name__ == "__main__":
    fix_formatting() 