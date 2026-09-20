from threading import RLock
class Repository:
    def __init__(self): self._data={}; self._lock=RLock()
    def get(self,k): return self._data.get(k)
    def create(self,k,v):
        with self._lock:
            if k in self._data: raise ValueError('ALREADY_EXISTS')
            self._data[k]=v; return v
    def update(self,k,v):
        with self._lock:
            if k not in self._data: raise KeyError('NOT_FOUND')
            self._data[k]=v; return v
    def all(self): return list(self._data.values())
