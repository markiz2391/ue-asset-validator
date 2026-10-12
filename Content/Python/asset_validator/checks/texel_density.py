"""Texel density: sqrt(UV area / surface area) * texture resolution, in px/m. Report only."""
import math

import unreal

from ..core import Check, Severity, register


def effective_size(tex):
    size = max(tex.blueprint_get_size_x(), tex.blueprint_get_size_y())
    cap = tex.get_editor_property("max_texture_size")
    return min(size, cap) if cap > 0 else size


def largest_texture(mat):
    """Largest Texture2D used by the material (MI overrides, else the master's textures)."""
    mel = unreal.MaterialEditingLibrary
    texs = []
    if isinstance(mat, unreal.MaterialInstance):
        texs = [mel.get_material_instance_texture_parameter_value(mat, n) for n in mel.get_texture_parameter_names(mat)]
        mat = mat.get_base_material()
    if not any(isinstance(t, unreal.Texture2D) for t in texs) and isinstance(mat, unreal.Material):
        texs = mel.get_used_textures(mat)
    texs = [t for t in texs if isinstance(t, unreal.Texture2D)]
    return max(texs, key=effective_size) if texs else None


@register
class TexelDensityCheck(Check):
    id = "mesh.texel_density"
    applies_to = {"StaticMesh"}
    needs_load = True

    def run(self, ad, mesh, cfg):
        td = cfg["texel_density"]
        mat = mesh.get_material(0)
        tex = largest_texture(mat) if mat else None
        if not tex:
            return [self.issue(ad, Severity.INFO, "Texel density skipped: slot 0 has no texture")]

        dm = unreal.DynamicMesh()
        lod = unreal.GeometryScriptMeshReadLOD()
        lod.lod_type = unreal.GeometryScriptLODType.SOURCE_MODEL
        dm, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
            mesh, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(), lod)
        if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
            return [self.issue(ad, Severity.INFO, "Texel density skipped: could not read mesh")]
        _, mesh_area, uv_area, _, _, valid, _ = unreal.GeometryScript_UVs.get_mesh_uv_size_info(
            dm, 0, unreal.GeometryScriptMeshSelection())
        if not valid or mesh_area <= 0 or uv_area <= 0:
            return [self.issue(ad, Severity.INFO, "Texel density skipped: no valid UV0")]

        res = effective_size(tex)
        density = math.sqrt(uv_area / mesh_area) * res * 100.0  # mesh area is cm^2
        target, tol = td["target_px_per_m"], td["tolerance"]
        if abs(density - target) <= target * tol:
            return []
        return [self.issue(ad, Severity.WARNING,
                           f"{density:.0f} px/m (target {target:g} ±{tol:.0%}, {tex.get_name()} {res}px)")]
