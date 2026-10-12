"""Smallest check that the rule logic still holds. Run: import asset_validator.selftest"""
from types import SimpleNamespace as NS

from . import config
from .checks.naming import PrefixCheck
from .checks.textures import norm, texture_suffix

cfg = config.load()


def ad(name, cls, path="/Game/T"):
    return NS(asset_name=name, package_name=f"{path}/{name}", package_path=path,
              asset_class_path=NS(asset_name=cls))


assert texture_suffix("T_Rock_ORM", cfg) == "_ORM"  # longest suffix wins over _M
assert texture_suffix("T_Rock_BC", cfg) == "_BC"
assert texture_suffix("T_Rock_B", cfg) is None
assert norm("TC_Normalmap") == norm("TC_NORMALMAP")
assert PrefixCheck().run(ad("M_Rock", "MaterialInstanceConstant"), None, cfg)[0].fix_data["new_name"] == "MI_Rock"
assert PrefixCheck().run(ad("rock", "StaticMesh"), None, cfg)[0].fix_data["new_name"] == "SM_rock"
assert PrefixCheck().run(ad("SM_rock", "StaticMesh"), None, cfg) == []
print("asset_validator selftest OK")
