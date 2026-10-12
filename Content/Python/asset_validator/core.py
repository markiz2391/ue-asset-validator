"""Core types: Severity, Issue, Check base class and the check registry."""
from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2


@dataclass
class Issue:
    check_id: str
    severity: Severity
    asset_path: str
    message: str
    fixable: bool = False
    fix_data: dict = field(default_factory=dict)
    is_rename: bool = False  # renames are not undoable, the UI confirms them separately


class Check:
    id = ""
    applies_to = set()   # asset class names, e.g. {"Texture2D"}
    needs_load = False   # False: runs on AssetData only (fast pass)

    def run(self, asset_data, asset, cfg):
        """Return a list of Issues. `asset` is None for fast checks."""
        return []

    fix_props = ()       # editor properties fix() changes; snapshot()/restore() cover them by default

    def fix(self, issue, asset, cfg):
        """Apply the fix inside the caller's transaction. Return True on success."""
        return False

    # Our own revert: Fab/Interchange imports are not RF_Transactional, so Ctrl+Z can't undo them.
    def snapshot(self, asset):
        return {p: asset.get_editor_property(p) for p in self.fix_props}

    def restore(self, asset, data):
        for p, v in data.items():
            asset.set_editor_property(p, v)

    def issue(self, asset_data, severity, message, **kw):
        return Issue(self.id, severity, str(asset_data.package_name), message, **kw)


REGISTRY = {}


def register(cls):
    """Class decorator: adding a check = adding one decorated class."""
    REGISTRY[cls.id] = cls()
    return cls
