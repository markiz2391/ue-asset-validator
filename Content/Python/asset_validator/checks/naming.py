"""Naming and folder rules. Asset Registry only, nothing gets loaded."""
import re

from ..core import Check, Severity, register
from .textures import texture_suffix


def asset_class(ad):
    return str(ad.asset_class_path.asset_name)


@register
class PrefixCheck(Check):
    id = "naming.prefix"
    applies_to = None  # any class listed in cfg["prefixes"]

    def run(self, ad, asset, cfg):
        prefixes = cfg["prefixes"]
        cls = asset_class(ad)
        want = prefixes.get(cls)
        name = str(ad.asset_name)
        if not want or name.startswith(want):
            return []
        # strip a wrong known prefix (M_ on an MI -> MI_), longest first
        base = name
        for p in sorted(set(prefixes.values()), key=len, reverse=True):
            if name.startswith(p):
                base = name[len(p):]
                break
        new_name = want + base
        return [self.issue(ad, Severity.ERROR, f"{cls} should start with '{want}' -> {new_name}",
                           fixable=True, is_rename=True, fix_data={"new_name": new_name})]


@register
class CharsCheck(Check):
    id = "naming.chars"
    applies_to = None

    def run(self, ad, asset, cfg):
        rules = cfg["naming"]
        name = str(ad.asset_name)
        out = []
        if not re.match(rules["allowed_chars"], name):
            out.append(self.issue(ad, Severity.ERROR, f"Name has characters outside {rules['allowed_chars']}"))
        if len(name) > rules["max_length"]:
            out.append(self.issue(ad, Severity.WARNING, f"Name is {len(name)} chars, max {rules['max_length']}"))
        return out


@register
class TextureSuffixCheck(Check):
    id = "naming.texture_suffix"
    applies_to = {"Texture2D"}

    def run(self, ad, asset, cfg):
        if not cfg["texture_suffixes"] or texture_suffix(str(ad.asset_name), cfg):
            return []
        allowed = ", ".join(cfg["texture_suffixes"])
        return [self.issue(ad, Severity.WARNING, f"Texture has no known suffix ({allowed})")]


@register
class FolderCheck(Check):
    id = "path.folder"
    applies_to = None

    def run(self, ad, asset, cfg):
        allowed = cfg["folders"].get(asset_class(ad))
        if not allowed:
            return []
        parts = str(ad.package_path).split("/")
        if any(a in parts for a in allowed):
            return []
        return [self.issue(ad, Severity.WARNING,
                           f"{asset_class(ad)} must live under a folder named {' / '.join(allowed)}")]
