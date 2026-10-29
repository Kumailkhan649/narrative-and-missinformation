import ast
import io
import sys
import tokenize
from pathlib import Path

def violations(path):
    source=Path(path).read_text(encoding="utf-8")
    found=[]
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type==tokenize.COMMENT:
            found.append((token.start[0],"comment"))
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and ast.get_docstring(node):
            found.append((getattr(node,"lineno",1),"docstring"))
    return found

failed=False
for file in Path("ai08").rglob("*.py"):
    for line,kind in violations(file):
        print(f"{file}:{line}: {kind}")
        failed=True
for folder in ("tests","tools"):
    for file in Path(folder).rglob("*.py"):
        for line,kind in violations(file):
            print(f"{file}:{line}: {kind}")
            failed=True
sys.exit(1 if failed else 0)
