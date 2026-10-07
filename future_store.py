from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import Any

class FutureStore:
    def __init__(self, path: Path):
        self.path=path
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.data=self._load()
    def _load(self):
        try:
            v=json.loads(self.path.read_text('utf-8'))
            return v if isinstance(v,dict) else {}
        except (OSError,ValueError): return {}
    def save(self):
        fd,tmp=tempfile.mkstemp(dir=self.path.parent,prefix='.tasks-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(self.data,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
