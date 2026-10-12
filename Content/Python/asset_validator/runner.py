"""Collect assets, run checks in two passes, apply fixes."""
import time

import unreal

from . import checks  # noqa: F401  (registers checks)
from . import config
from .core import REGISTRY, Severity


GROUPS = ("all", "naming", "textures", "meshes", "materials", "texel_density")  # check module names + "all"


class _State:
    """Results of one group (one UI tab). Each group keeps its own issues, stats and revert history."""
    def __init__(self, group):
        self.group, self.issues, self.cfg, self.root, self.stats = group, [], None, "", {}
        self.history = []  # one batch per fix() call: [(asset_path, check_id, snapshot)]


STATES = {g: _State(g) for g in GROUPS}
State = STATES["naming"]  # the active group; always read it as runner.State


def set_group(group):
    global State
    State = STATES[group]
    return State


def group_of(chk):
    return type(chk).__module__.rsplit(".", 1)[-1]


def _checks():
    return [c for c in REGISTRY.values() if State.group == "all" or group_of(c) == State.group]


def _applies(chk, cls, cfg):
    if chk.applies_to is None:
        return True
    return cls in chk.applies_to


def collect(root, cfg):
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    ads = ar.get_assets(unreal.ARFilter(package_paths=[root], recursive_paths=True))
    if not ads and unreal.EditorAssetLibrary.does_asset_exist(root):  # a single asset path
        ads = [unreal.EditorAssetLibrary.find_asset_data(root)]
    ignore = cfg["ignore_paths"]
    return [ad for ad in ads
            if str(ad.asset_class_path.asset_name) != "ObjectRedirector"
            and "/__External" not in str(ad.package_name)  # World Partition actor/object packages
            and not any(str(ad.package_name).startswith(p) for p in ignore)]


def _run_on(ads, cfg, slow_task_title=None):
    """Pass 1: fast checks on AssetData. Pass 2: load only what deep checks need."""
    fast = [c for c in _checks() if not c.needs_load]
    deep = [c for c in _checks() if c.needs_load]
    issues = []
    for ad in ads:
        cls = str(ad.asset_class_path.asset_name)
        for chk in fast:
            if _applies(chk, cls, cfg):
                issues += chk.run(ad, None, cfg)

    todo = [(ad, [c for c in deep if _applies(c, str(ad.asset_class_path.asset_name), cfg)]) for ad in ads]
    todo = [t for t in todo if t[1]]
    cancelled = False
    with unreal.ScopedSlowTask(len(todo), slow_task_title or "Validating assets") as task:
        task.make_dialog(True)
        for ad, chks in todo:
            if task.should_cancel():
                cancelled = True
                break
            task.enter_progress_frame(1, f"Validating {ad.asset_name}")
            asset = ad.get_asset()
            if not asset:
                continue
            for chk in chks:
                try:
                    issues += chk.run(ad, asset, cfg)
                except Exception as e:  # one broken asset must not stop the run
                    issues.append(chk.issue(ad, Severity.ERROR, f"Check crashed: {e}"))
    return issues, len(todo), cancelled


def _sort(issues):
    issues.sort(key=lambda i: (-i.severity, i.asset_path, i.check_id))


def validate(root, group=None, td_target=None):
    """td_target: px/m for this run only (the UI field); rules.json stays untouched."""
    if group:
        set_group(group)
    cfg = config.load()
    if td_target:
        cfg["texel_density"]["target_px_per_m"] = td_target
    t0 = time.perf_counter()
    ads = collect(root, cfg)
    issues, loaded, cancelled = _run_on(ads, cfg)
    _sort(issues)
    State.issues, State.cfg, State.root = issues, cfg, root
    State.stats = {"assets": len(ads), "loaded": loaded, "seconds": round(time.perf_counter() - t0, 2),
                   "cancelled": cancelled, "fixed": 0}
    return issues


def _revalidate(paths):
    """Re-run all checks for the touched assets and replace their issues in State."""
    ads = [unreal.EditorAssetLibrary.find_asset_data(p) for p in paths if unreal.EditorAssetLibrary.does_asset_exist(p)]
    fresh, _, _ = _run_on(ads, State.cfg, "Re-validating fixed assets")
    State.issues = [i for i in State.issues if i.asset_path not in paths] + fresh
    _sort(State.issues)


def fix(indices=None, auto_save=False):
    """Fix the given issue indices (None = all fixable, non-rename).
    Ctrl+Z works on transactional assets; revert_last() works on all of them."""
    picked = [State.issues[i] for i in (indices if indices is not None else range(len(State.issues)))
              if 0 <= i < len(State.issues)]
    picked = [i for i in picked if i.fixable and not i.is_rename]
    touched, fixed, batch = set(), 0, []
    with unreal.ScopedEditorTransaction("Asset Validator: Fix"):
        for issue in picked:
            asset = unreal.EditorAssetLibrary.load_asset(issue.asset_path)
            if not asset:
                continue
            asset.modify()  # False on Fab/Interchange imports (not RF_Transactional); the snapshot covers those
            chk = REGISTRY[issue.check_id]
            try:
                snap = chk.snapshot(asset)
                ok = chk.fix(issue, asset, State.cfg)
            except Exception as e:
                unreal.log_error(f"AssetValidator: fix {issue.check_id} on {issue.asset_path} failed: {e}")
                ok = False
            if ok:
                fixed += 1
                touched.add(issue.asset_path)
                batch.append((issue.asset_path, issue.check_id, snap))
    if batch:
        State.history.append(batch)
    if auto_save:
        for p in touched:
            unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True)
    if touched:
        _revalidate(touched)
    State.stats["fixed"] = State.stats.get("fixed", 0) + fixed
    return fixed


def revert_last():
    """Restore the values the last fix() batch overwrote. Returns the number of reverted fixes."""
    if not State.history:
        return 0
    batch = State.history.pop()
    with unreal.ScopedEditorTransaction("Asset Validator: Revert"):
        for path, check_id, snap in reversed(batch):
            asset = unreal.EditorAssetLibrary.load_asset(path)
            if asset:
                asset.modify()
                REGISTRY[check_id].restore(asset, snap)
    _revalidate({p for p, _, _ in batch})
    State.stats["fixed"] = max(0, State.stats.get("fixed", 0) - len(batch))
    return len(batch)


def rename(indices=None):
    """Apply naming.prefix renames (NOT undoable), then fix up the redirectors they leave."""
    picked = [State.issues[i] for i in (indices if indices is not None else range(len(State.issues)))
              if 0 <= i < len(State.issues)]
    picked = [i for i in picked if i.is_rename]
    eal = unreal.EditorAssetLibrary
    data, moves = [], []
    for issue in picked:
        asset = eal.load_asset(issue.asset_path)
        folder = issue.asset_path.rsplit("/", 1)[0]
        new_path = f"{folder}/{issue.fix_data['new_name']}"
        if asset and not eal.does_asset_exist(new_path):
            data.append(unreal.AssetRenameData(asset, folder, issue.fix_data["new_name"]))
            moves.append((issue.asset_path, new_path))
    if not data or not unreal.AssetToolsHelpers.get_asset_tools().rename_assets(data):
        return 0
    _fixup_redirectors([old for old, _ in moves])
    renamed = {old for old, _ in moves}
    State.issues = [i for i in State.issues if i.asset_path not in renamed]
    _revalidate({new for _, new in moves})
    State.stats["fixed"] = State.stats.get("fixed", 0) + len(moves)
    return len(moves)


def _fixup_redirectors(old_paths):
    """Resave whatever still references the redirector, then delete the redirector if nothing does."""
    eal = unreal.EditorAssetLibrary
    for old in old_paths:
        if not eal.does_asset_exist(old):
            continue
        refs = [str(r) for r in eal.find_package_referencers_for_asset(old, True)]
        for r in refs:
            eal.save_asset(r, only_if_is_dirty=False)
        if not eal.find_package_referencers_for_asset(old, True):
            eal.delete_asset(old)
