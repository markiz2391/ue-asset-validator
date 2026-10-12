# UE Asset Validator

One-click audit of an Unreal Engine 5.8 content folder against project rules: results table, per-issue and bulk Fix, revert, CSV/HTML report.
Editor Utility Widget front end, Python back end, rules in JSON.

## Install

1. Copy `Content/` and `Config/` into your project.
2. Enable the engine plugins **Python Editor Script Plugin**, **Editor Scripting Utilities** and **Json Blueprint Utilities**, then restart the editor.
3. Right-click `Content/Tools/AssetValidator/EUW_AssetValidator` and choose **Run Editor Utility Widget**.

`Content/Python` is on the Python path automatically, so no `init_unreal.py` is needed.

## Use

* Tabs **Naming / Textures / Meshes / Materials / Texel Density** each run only their own checks and keep their own results, fix and revert history.
* **Use Selection** takes the folder selected in the Content Browser. **Validate** runs the checks.
* The Errors / Warnings / Info checkboxes filter the list. **Find** syncs the Content Browser to the asset.
* **Fix** / **Fix All** apply the automatic fixes. **Revert Last Fix** restores the previous values.
* **Rename** asks for confirmation first. Renames can't be reverted. Referencers are resaved and the redirector is removed.
* **Export CSV / HTML** writes to `Saved/AssetValidator/`.

Console, without the UI:

```python
import asset_validator as av
av.validate("/Game/MyFolder")              # all checks, prints the issue list
av.validate("/Game/MyFolder", "meshes")    # one group: naming, textures, meshes, materials, texel_density
av.fix()                        # fix everything fixable
av.runner.revert_last()
```

## Checks

Values below are the defaults from `Config/AssetValidator/rules.json`.

### Naming
- **Prefix by class** (`naming.prefix`): StaticMesh `SM_`, SkeletalMesh `SK_`, Texture2D `T_`, Material `M_`, Material Instance `MI_`, Material Function `MF_`, Blueprint `BP_`, Niagara System `NS_`. *Fix: rename (with confirmation, not undoable). A wrong known prefix is replaced, so `M_` on an MI becomes `MI_`.*
- **Allowed characters** (`naming.chars`): letters, digits and `_` only. No spaces or special characters.
- **Name length** (`naming.chars`): 64 characters max.
- **Texture suffix** (`naming.texture_suffix`): the texture ends with a known suffix (`_D`, `_BC`, `_N`, `_ORM`, `_M`, `_E`, `_H`).
- **Folder** (`path.folder`): static meshes live under a folder named `Meshes`, textures under `Textures`.

### Textures
Rules per suffix. These read Asset Registry tags only, so nothing gets loaded and the pass is fast.

| Suffix | Compression | sRGB | Max size |
|---|---|---|---|
| `_D`, `_BC` | Default | on | 4096 |
| `_N` | Normalmap | off | 4096 |
| `_ORM`, `_M` | Masks | off | 2048 |
| `_E` | Default | on | 1024 |
| `_H` | Grayscale | off | 2048 |

- **Power of two** (`tex.pow2`): width and height are powers of two.
- **Max size** (`tex.max_size`): effective size is within the suffix limit. *Fix: sets Max Texture Size.*
- **Compression** (`tex.compression`): matches the suffix. *Fix: sets it.*
- **sRGB** (`tex.srgb`): matches the suffix. *Fix: sets it.*
- **Texture group** (`tex.group`): matches the suffix. Optional, only when `texture_group` is set for a suffix. *Fix: sets it.*

### Meshes
- **Nanite** (`mesh.nanite`): flags meshes over 5000 triangles with Nanite off, and meshes listed in `nanite_exceptions` with Nanite on. *Fix: toggles Nanite.*
- **LODs** (`mesh.lods`): non-Nanite meshes need at least 3 LODs.
- **Collision** (`mesh.collision`): simple collision is present (Use Complex as Simple is allowed). *Fix: adds box collision.*
- **Lightmap UV** (`mesh.lightmap_uv`): valid lightmap UV index, not channel 0. Only runs when `use_baked_lighting` is true. *Fix: sets it to the last UV channel.*
- **Size** (`mesh.bounds`): largest side between 1 cm and 50,000 cm. Catches cm/m scale mistakes.
- **Pivot** (`mesh.bounds`): pivot no more than 100 cm outside the mesh bounds.

### Materials
Report only.
- **Instruction budget** (`mat.budget`): 300 pixel shader instructions max (Materials and MIs).
- **Sampler budget** (`mat.budget`): 12 samplers max.
- **Master folder** (`mat.master_folder`): master Materials live under `/Game/Materials/Masters`.
- **Approved master** (`mat.mi_parent`): the MI's root master is in the approved list. Edit the list in the box on the Materials tab; it is saved to `rules.json`.
- **No masters on meshes** (`mat.direct_master`): static mesh slots use an MI, never a master Material directly. Engine materials are ignored.

### Texel Density
Report only.
- **Texel density** (`mesh.texel_density`): `sqrt(UV0 area / surface area) × texture resolution` in px/m, computed from LOD0 and the largest texture in the slot-0 material. Must be within ±25% of the target (512 by default, or the value typed into the tab's field).
- A mesh is skipped (Info) when slot 0 has no texture, the mesh can't be read, or UV0 is invalid.

Materials and texel density are report-only on purpose. Those calls stay with a human.

Every rule is in `Config/AssetValidator/rules.json`. Adding a check means adding one class:

```python
@register
class SRGBCheck(TextureRule):
    id = "tex.srgb"
    rule_key = "srgb"
    fix_props = ("srgb",)
    def run(self, ad, asset, cfg): ...
    def fix(self, issue, tex, cfg): ...
```

## How it works

* **Fast pass:** naming, folder and texture checks read only Asset Registry tags, so nothing gets loaded.
* **Deep pass:** only meshes and materials get loaded, inside a cancellable `ScopedSlowTask`.
* **Texel density:** Geometry Script copies LOD0 into a DynamicMesh, and `get_mesh_uv_size_info` gives the 3D and UV areas. Density = `sqrt(uv_area / mesh_area) × resolution`, with the resolution taken from the largest texture in the slot-0 material.
* **Undo:** fixes run inside a `ScopedEditorTransaction`, and each fix also snapshots the values it changes. Assets imported through Fab/Interchange are **not** `RF_Transactional`, so `Modify()` records nothing and Ctrl+Z can't revert them. **Revert Last Fix** covers every asset either way.
* **Bridge:** the widget calls `Execute Python Command (Advanced)` in *EvaluateStatement* mode. The Python side returns a `str` subclass whose `repr()` is the raw JSON, and BP parses it with Json Blueprint Utilities `GetField` straight into an array of a UserDefinedStruct. No Python-defined UCLASS/USTRUCT means no startup-order dependency.

## Layout

```
Content/Python/asset_validator/
  core.py            Severity, Issue, Check base, @register
  config.py          rules.json + defaults
  runner.py          collect, fast/deep pass, fix, revert, rename
  checks/            naming, textures, meshes, materials, texel_density
  report.py          CSV / HTML
  api.py             JSON bridge for the widget
Config/AssetValidator/rules.json
Content/Tools/AssetValidator/   EUW_AssetValidator, EUW_AV_IssueRow, FAV_Issue, FAV_Stats
```

## License

MIT
