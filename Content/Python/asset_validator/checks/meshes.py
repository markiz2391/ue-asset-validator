"""Static mesh rules (deep pass, mesh is loaded)."""
import unreal

from ..core import Check, Severity, register


def sme():
    return unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)


def collision_prims(mesh):
    """Boxes/spheres/capsules + convex hulls. get_simple_collision_count alone ignores convex hulls."""
    return sme().get_simple_collision_count(mesh) + sme().get_convex_collision_count(mesh)


def in_paths(path, prefixes):
    return any(path.startswith(p) for p in prefixes)


class MeshCheck(Check):
    applies_to = {"StaticMesh"}
    needs_load = True


@register
class NaniteCheck(MeshCheck):
    id = "mesh.nanite"

    def run(self, ad, mesh, cfg):
        m = cfg["meshes"]
        path = str(ad.package_name)
        tris = mesh.get_num_triangles(0)
        enabled = sme().get_nanite_settings(mesh).enabled
        if in_paths(path, m["nanite_exceptions"]):
            if enabled:
                return [self.issue(ad, Severity.WARNING, "Nanite is on but the mesh is in nanite_exceptions",
                                   fixable=True, fix_data={"enable": False})]
        elif not enabled and tris > m["nanite_min_triangles"]:
            return [self.issue(ad, Severity.WARNING, f"{tris} triangles with Nanite off (> {m['nanite_min_triangles']})",
                               fixable=True, fix_data={"enable": True})]
        return []

    def fix(self, issue, mesh, cfg):
        ns = sme().get_nanite_settings(mesh)
        ns.enabled = issue.fix_data["enable"]
        sme().set_nanite_settings(mesh, ns, apply_changes=True)
        return True

    def snapshot(self, mesh):
        return {"enable": sme().get_nanite_settings(mesh).enabled}

    def restore(self, mesh, data):
        ns = sme().get_nanite_settings(mesh)
        ns.enabled = data["enable"]
        sme().set_nanite_settings(mesh, ns, apply_changes=True)


@register
class LODCheck(MeshCheck):
    id = "mesh.lods"

    def run(self, ad, mesh, cfg):
        want = cfg["meshes"]["min_lods_non_nanite"]
        if sme().get_nanite_settings(mesh).enabled:
            return []
        lods = sme().get_lod_count(mesh)
        if lods >= want:
            return []
        return [self.issue(ad, Severity.WARNING, f"Non-Nanite mesh has {lods} LOD(s), min {want}")]


@register
class CollisionCheck(MeshCheck):
    id = "mesh.collision"

    def run(self, ad, mesh, cfg):
        m = cfg["meshes"]
        if not m["require_collision"] or collision_prims(mesh) > 0:
            return []
        if m["allow_complex_as_simple"] and \
                sme().get_collision_complexity(mesh) == unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE:
            return []
        return [self.issue(ad, Severity.ERROR, "No simple collision",
                           fixable=True, fix_data={"shape": m["collision_fix_shape"]})]

    def fix(self, issue, mesh, cfg):
        shape = getattr(unreal.ScriptCollisionShapeType, issue.fix_data["shape"].upper())
        return sme().add_simple_collisions(mesh, shape) >= 0 and collision_prims(mesh) > 0

    def snapshot(self, mesh):
        return {}  # the fix only runs when there was no simple collision

    def restore(self, mesh, data):
        sme().remove_collisions(mesh)


@register
class LightmapUVCheck(MeshCheck):
    id = "mesh.lightmap_uv"
    fix_props = ("light_map_coordinate_index",)

    def run(self, ad, mesh, cfg):
        if not cfg["meshes"]["use_baked_lighting"]:
            return []
        channels = sme().get_num_uv_channels(mesh, 0)
        idx = mesh.get_editor_property("light_map_coordinate_index")
        if 0 < idx < channels:
            return []
        if channels > 1:
            return [self.issue(ad, Severity.ERROR, f"Lightmap UV index {idx} invalid ({channels} UV channels)",
                               fixable=True, fix_data={"index": channels - 1})]
        return [self.issue(ad, Severity.ERROR, "Only one UV channel, no lightmap UVs")]

    def fix(self, issue, mesh, cfg):
        mesh.set_editor_property("light_map_coordinate_index", issue.fix_data["index"])
        return True


@register
class BoundsCheck(MeshCheck):
    id = "mesh.bounds"

    def run(self, ad, mesh, cfg):
        m = cfg["meshes"]
        box = mesh.get_bounding_box()
        lo, hi = box.min, box.max
        size = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
        out = []
        if size > m["max_bounds_cm"]:
            out.append(self.issue(ad, Severity.WARNING, f"Largest side {size:.0f}cm > {m['max_bounds_cm']:.0f}cm (scale mistake?)"))
        elif size < m["min_bounds_cm"]:
            out.append(self.issue(ad, Severity.WARNING, f"Largest side {size:.2f}cm < {m['min_bounds_cm']}cm (exported in m?)"))
        # distance from the pivot to the box, 0 when the pivot is inside it
        d = sum(max(l - 0.0, 0.0, 0.0 - h) ** 2 for l, h in ((lo.x, hi.x), (lo.y, hi.y), (lo.z, hi.z))) ** 0.5
        if d > m["max_pivot_offset_cm"]:
            out.append(self.issue(ad, Severity.WARNING, f"Pivot is {d:.0f}cm outside the mesh bounds"))
        return out
