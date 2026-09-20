from dataclasses import dataclass,field
from datetime import datetime,timezone
@dataclass
class QueuedCommand:
    command_id:str; payload:dict; created_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc)); status:str='PENDING'
class CommandQueue:
    def __init__(self): self.items={}
    def enqueue(self,c):
        if c.command_id in self.items: return self.items[c.command_id]
        self.items[c.command_id]=c; return c
    def pending(self): return [x for x in self.items.values() if x.status=='PENDING']
    def conflict(self,command_id): self.items[command_id].status='CONFLICT'
