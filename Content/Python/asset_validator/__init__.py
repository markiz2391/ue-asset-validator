"""UE Asset Validator. Console use:

    import asset_validator as av
    av.validate("/Game/MyFolder")   # prints a summary, returns issues
    av.fix()                        # fix all fixable (undoable)
"""
from . import api, report, runner  # noqa: F401
from .core import REGISTRY, Severity


def validate(path, group="all"):
    """group: "all" or a check module name (naming, textures, meshes, materials, texel_density)."""
    issues = runner.validate(path, group)
    s = runner.State.stats
    print(f"AssetValidator: {s['assets']} assets ({s['loaded']} loaded) in {s['seconds']}s, {len(issues)} issues")
    for n, i in enumerate(issues):
        print(f"  [{n}] {i.severity.name:7} {i.check_id:20} {i.asset_path}  {i.message}{'  (fixable)' if i.fixable else ''}")
    return issues


def fix(indices=None, auto_save=False):
    return runner.fix(indices, auto_save)


def reload():
    """Dev helper: hot-reload every module after editing the .py files."""
    import importlib, sys
    for name in [m for m in sys.modules if m == __name__ or m.startswith(__name__ + ".")]:
        del sys.modules[name]
    return importlib.import_module(__name__)
