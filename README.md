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

| Id | What | Fix |
|----|------|-----|
| `naming.prefix` | Prefix by class (`SM_`, `T_`, `MI_`…) | rename (confirm) |
| `naming.chars` | Allowed characters, max length | – |
| `naming.texture_suffix` | Texture has a known suffix | – |
| `path.folder` | Class lives under an allowed folder | – |
| `tex.pow2` | Power-of-two size | – |
| `tex.max_size` | Max resolution per suffix | max texture size |
| `tex.compression` | Compression per suffix | set |
| `tex.srgb` | sRGB per suffix | set |
| `tex.group` | Texture group per suffix (optional) | set |
| `mesh.nanite` | Nanite above N triangles / off for exceptions | toggle |
| `mesh.lods` | LOD count for non-Nanite meshes | – |
| `mesh.collision` | Simple collision present | add box/convex |
| `mesh.lightmap_uv` | Valid lightmap UV index (baked lighting only) | set index |
| `mesh.bounds` | Size limits, pivot far outside bounds | – |
| `mesh.texel_density` | px/m vs target ± tolerance | – |
| `mat.budget` | Pixel instructions / samplers | – |
| `mat.master_folder` | Masters only in allowed roots | – |
| `mat.mi_parent` | MI master is approved | – |
| `mat.direct_master` | Mesh slots use MIs, not masters | – |

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
