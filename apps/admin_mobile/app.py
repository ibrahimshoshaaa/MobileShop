"""Thin admin adapter for the same command boundary used by POS."""
class AdminApp:
    def __init__(self, engine): self.engine=engine
    def dashboard(self, branch_id): return self.engine.reports(branch_id)
    def inventory(self, branch_id): return self.engine.inventory_report(branch_id)
