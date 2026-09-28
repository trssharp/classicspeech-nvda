"""Run every ClassicSpeech harness in an isolated interpreter, fail closed."""
import compileall
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    for path in (ROOT / "classicSpeech.py", ROOT / "installTasks.py", ROOT / "_speech_core",
                 ROOT / "appModules", ROOT / "scripts", ROOT / "tests"):
        ok = compileall.compile_dir(path, quiet=1) if path.is_dir() else compileall.compile_file(path, quiet=1)
        if not ok:
            return 1
    harnesses = sorted((ROOT / "tests").glob("*harness.py"))
    if not harnesses:
        raise RuntimeError("No harnesses found")
    for test in harnesses:
        print(f"Running {test.name}", flush=True)
        subprocess.run([sys.executable, str(test)], cwd=ROOT, check=True)
    print(f"Passed all {len(harnesses)} harnesses", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
