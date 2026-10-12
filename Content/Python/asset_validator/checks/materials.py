"""Material rules. Report only: these stay human decisions."""
import unreal

from ..core import Check, Severity, register


@register
class MaterialStatsCheck(Check):
    id = "mat.budget"
    applies_to = {"Material", "MaterialInstanceConstant"}
    needs_load = True

    def run(self, ad, mat, cfg):
        m = cfg["materials"]
        st = unreal.MaterialEditingLibrary.get_statistics(mat)
        out = []
        if st.num_pixel_shader_instructions > m["max_pixel_instructions"]:
            out.append(self.issue(ad, Severity.WARNING,
                                  f"{st.num_pixel_shader_instructions} pixel instructions, budget {m['max_pixel_instructions']}"))
        if st.num_samplers > m["max_samplers"]:
            out.append(self.issue(ad, Severity.WARNING, f"{st.num_samplers} samplers, budget {m['max_samplers']}"))
        return out


@register
class MasterFolderCheck(Check):
    id = "mat.master_folder"
    applies_to = {"Material"}

    def run(self, ad, asset, cfg):
        roots = cfg["materials"]["master_roots"]
        if not roots or any(str(ad.package_name).startswith(r) for r in roots):
            return []
        return [self.issue(ad, Severity.WARNING, f"Master material outside {', '.join(roots)}")]


@register
class ApprovedParentCheck(Check):
    id = "mat.mi_parent"
    applies_to = {"MaterialInstanceConstant"}
    needs_load = True

    def run(self, ad, mi, cfg):
        approved = cfg["materials"]["approved_masters"]
        if not approved:
            return []
        base = mi.get_base_material()
        path = base.get_outermost().get_name() if base else "None"
        if path in approved:
            return []
        return [self.issue(ad, Severity.WARNING, f"Master {path} is not in approved_masters")]


@register
class DirectMasterOnMeshCheck(Check):
    id = "mat.direct_master"
    applies_to = {"StaticMesh"}
    needs_load = True

    def run(self, ad, mesh, cfg):
        out = []
        for i, slot in enumerate(mesh.get_editor_property("static_materials")):
            mat = slot.get_editor_property("material_interface")
            if isinstance(mat, unreal.Material) and not mat.get_outermost().get_name().startswith("/Engine/"):
                out.append(self.issue(ad, Severity.WARNING,
                                      f"Slot {i} '{slot.material_slot_name}' uses master {mat.get_name()}, use an MI"))
        return out
