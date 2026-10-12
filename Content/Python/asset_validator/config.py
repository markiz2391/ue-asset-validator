"""Load Config/AssetValidator/rules.json on top of the built-in defaults."""
import json
import os

import unreal

DEFAULTS = {
    "prefixes": {
        "StaticMesh": "SM_", "SkeletalMesh": "SK_", "Texture2D": "T_",
        "Material": "M_", "MaterialInstanceConstant": "MI_", "MaterialFunction": "MF_",
        "Blueprint": "BP_", "NiagaraSystem": "NS_",
    },
    "naming": {"allowed_chars": "^[A-Za-z0-9_]+$", "max_length": 64},
    "folders": {},  # class -> list of allowed folder names somewhere in the path
    "texture_suffixes": {},
    "meshes": {
        "nanite_min_triangles": 5000,
        "nanite_exceptions": [],
        "min_lods_non_nanite": 3,
        "require_collision": True,
        "allow_complex_as_simple": True,
        "collision_fix_shape": "BOX",
        "use_baked_lighting": False,
        "min_bounds_cm": 1.0,
        "max_bounds_cm": 50000.0,
        "max_pivot_offset_cm": 100.0,
    },
    "materials": {
        "max_pixel_instructions": 300,
        "max_samplers": 12,
        "master_roots": [],
        "approved_masters": [],
    },
    "texel_density": {"target_px_per_m": 512, "tolerance": 0.25},
    "ignore_paths": [],
}


def rules_path():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_config_dir()),
                        "AssetValidator", "rules.json")


def load(path=None):
    path = path or rules_path()
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        unknown = set(user) - set(DEFAULTS)
        if unknown:
            unreal.log_warning(f"AssetValidator: unknown keys in rules.json ignored: {sorted(unknown)}")
        for key, value in user.items():
            if key not in DEFAULTS:
                continue
            # dict sections merge one level deep, everything else replaces
            if isinstance(DEFAULTS[key], dict) and key not in ("prefixes", "folders", "texture_suffixes"):
                cfg[key].update(value)
            else:
                cfg[key] = value
    else:
        unreal.log_warning(f"AssetValidator: {path} not found, using defaults")
    return cfg


def save_approved_masters(paths, path=None):
    """Write materials.approved_masters back into rules.json (the rest of the file is kept)."""
    path = path or rules_path()
    data = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("materials", {})["approved_masters"] = paths
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
