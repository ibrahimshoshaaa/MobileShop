from dataclasses import replace
from shared.models.foundation import Branch
from backend.functions.repositories.foundation import InMemoryRepository

class BranchService:
    def __init__(self, repo: InMemoryRepository[Branch]):
        self.repo = repo

    def create(self, branch: Branch) -> Branch:
        if not branch.id or not branch.code or not branch.name:
            raise ValueError("INVALID_INPUT")
        if any(b.code == branch.code for b in self.repo.all()):
            raise ValueError("DUPLICATE_BRANCH_CODE")
        return self.repo.create(branch.id, branch)

    def deactivate(self, branch_id: str) -> Branch:
        branch = self.repo.get(branch_id)
        if not branch:
            raise KeyError("NOT_FOUND")
        return self.repo.update(branch_id, replace(branch, status="INACTIVE"))
