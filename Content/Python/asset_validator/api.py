"""JSON bridge for the EUW. Every call returns the same result JSON (or a plain string)."""
import json

import unreal

from . import config, report, runner
from .core import Severity


class RawJson(str):
    """ExecutePythonCommandEx (EvaluateStatement) returns repr(); this makes repr() the JSON itself."""
    def __repr__(self):
        return str.__str__(self)


def _result(extra=None):
    State = runner.State
    counts = {s.name.lower(): sum(1 for i in State.issues if i.severity == s) for s in Severity}
    out = {
        "root": State.root,
        "group": State.group,
        "stats": dict(State.stats, **counts, total=len(State.issues),
                      fixable=sum(1 for i in State.issues if i.fixable and not i.is_rename),
                      renames=sum(1 for i in State.issues if i.is_rename),
                      can_revert=len(State.history) > 0),
        "issues": [{"Index": n, "CheckId": i.check_id, "Severity": i.severity.name, "AssetPath": i.asset_path,
                    "AssetName": i.asset_path.rsplit("/", 1)[-1],
                    "Message": i.message, "bFixable": i.fixable, "bIsRename": i.is_rename}
                   for n, i in enumerate(State.issues)],
    }
    out.update(extra or {})
    st = out["stats"]
    out["summary"] = (f"[{State.group}]   {st['error']} errors, {st['warning']} warnings, {st['info']} info   |   "
                      f"{st.get('assets', 0)} assets ({st.get('loaded', 0)} loaded) in {st.get('seconds', 0)}s   |   "
                      f"fixed {st.get('fixed', 0)}, {st['fixable']} fixable, {st['renames']} renames"
                      + ("   |   CANCELLED" if st.get("cancelled") else ""))
    return RawJson(json.dumps(out))


def _indices(s):
    return None if s in (None, "", "all") else [int(x) for x in str(s).split(",") if x.strip()]


def run(path, td_target=""):
    if runner.State.group == "materials":
        _save_masters_from_ui()
    try:
        td = float(td_target)
    except ValueError:
        td = None
    runner.validate(path, td_target=td if td and td > 0 else None)
    return _result()


def td_default():
    return RawJson(str(config.load()["texel_density"]["target_px_per_m"]))


def fix(indices="all", auto_save=False):
    n = runner.fix(_indices(indices), bool(auto_save))
    return _result({"last_fixed": n})


def rename(indices="all"):
    n = runner.rename(_indices(indices))
    return _result({"last_fixed": n})


def revert():
    n = runner.revert_last()
    return _result({"last_fixed": -n})


def last():
    return _result()


def tab(group):
    """Switch the active group (UI tab) and return its last results."""
    runner.set_group(group)
    return _result()


def export(fmt="csv"):
    return RawJson(report.export(fmt))  # exports the active group


def selected_path():
    """Selected content-browser folder, else the folder of the selected asset, else the current folder."""
    folders = unreal.EditorUtilityLibrary.get_selected_folder_paths()
    if folders:
        return RawJson(str(folders[0]).replace("/All/Game", "/Game", 1))
    sel = unreal.EditorUtilityLibrary.get_selected_asset_data()
    if sel:
        return RawJson(str(sel[0].package_path))
    return RawJson(str(unreal.EditorUtilityLibrary.get_current_content_browser_path() or "/Game").replace("/All/Game", "/Game", 1))


def sync(asset_path):
    unreal.EditorAssetLibrary.sync_browser_to_objects([asset_path])
    return RawJson(asset_path)


# --- Approved masters box (Materials tab). Python reads/writes the box itself, so multi-line text
# --- never has to travel through a Python expression string.
EUW_PATH = "/Game/Tools/AssetValidator/EUW_AssetValidator"


def _box():
    eus = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
    w = eus.find_utility_widget_from_blueprint(unreal.load_asset(EUW_PATH))
    return w.get_editor_property("MastersBox") if w else None


def _parse_masters(text):
    """One path per line. Accepts /Game/X/M, /Game/X/M.M and Copy Reference form Material'/Game/X/M.M'."""
    out = []
    for line in str(text).replace(",", "\n").splitlines():
        line = line.strip().strip('"')
        if "'" in line:
            line = line.split("'")[1]
        line = line.split(".")[0]
        if line.startswith("/") and line not in out:
            out.append(line)
    return out


def _save_masters_from_ui():
    box = _box()
    if box:
        config.save_approved_masters(_parse_masters(box.get_text()))


def fill_masters_box():
    box = _box()
    if box:
        box.set_text("\n".join(config.load()["materials"]["approved_masters"]))
    return RawJson("ok")


def add_selected_masters():
    box = _box()
    if not box:
        return RawJson("no widget")
    paths = _parse_masters(box.get_text())
    for ad in unreal.EditorUtilityLibrary.get_selected_asset_data():
        if str(ad.asset_class_path.asset_name) == "Material" and str(ad.package_name) not in paths:
            paths.append(str(ad.package_name))
    box.set_text("\n".join(paths))
    return RawJson("ok")
