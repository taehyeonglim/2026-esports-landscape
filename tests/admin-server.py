"""Disposable database for browser tests. Never opens the operator database."""
import tempfile
from pathlib import Path
from esports_data.workbench import Workbench
from esports_data.admin import make_server
with tempfile.TemporaryDirectory() as directory:
    bench=Workbench(Path('.'),Path(directory)/'test.sqlite3','test-reviewer')
    server=make_server(bench,4199)
    print(server.review_token,flush=True)
    server.serve_forever()
