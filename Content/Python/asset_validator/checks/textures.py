"""Texture rules. The checks read Asset Registry tags (fast pass); only the fix loads the texture."""
import unreal

from ..core import Check, Severity, register


def texture_suffix(name, cfg):
    """Longest configured suffix the name ends with, or None."""
    hits = [s for s in cfg["texture_suffixes"] if name.endswith(s)]
    return max(hits, key=len) if hits else None


def tag(ad, key):
    v = ad.get_tag_value(key)
    return None if v is None else str(v)


def norm(s):
    """'TC_Normalmap' / 'TC_NORMALMAP' / 'TEXTUREGROUP_World_NormalMap' compare equal."""
    return s.upper().replace("_", "")


def enum_member(enum, name):
    return next(getattr(enum, m) for m in dir(enum) if m.isupper() and norm(m) == norm(name))


def dims(ad):
    d = tag(ad, "Dimensions")
    if not d or "x" not in d:
        return None
    w, h = d.split("x")[:2]
    return int(w), int(h)


class TextureRule(Check):
    applies_to = {"Texture2D"}
    needs_load = False
    rule_key = ""

    def rule(self, ad, cfg):
        sfx = texture_suffix(str(ad.asset_name), cfg)
        return sfx, (cfg["texture_suffixes"][sfx].get(self.rule_key) if sfx else None)


@register
class PowerOfTwoCheck(Check):
    id = "tex.pow2"
    applies_to = {"Texture2D"}

    def run(self, ad, asset, cfg):
        d = dims(ad)
        if not d or all(v > 0 and v & (v - 1) == 0 for v in d):
            return []
        return [self.issue(ad, Severity.WARNING, f"{d[0]}x{d[1]} is not power of two (no mips/streaming)")]


@register
class MaxSizeCheck(TextureRule):
    id = "tex.max_size"
    fix_props = ("max_texture_size",)
    rule_key = "max_size"

    def run(self, ad, asset, cfg):
        sfx, limit = self.rule(ad, cfg)
        d = dims(ad)
        if not limit or not d:
            return []
        cap = int(tag(ad, "MaxTextureSize") or 0)
        size = max(d) if cap <= 0 else min(max(d), cap)
        if size <= limit:
            return []
        return [self.issue(ad, Severity.WARNING, f"{sfx} is {size}px, max {limit}px",
                           fixable=True, fix_data={"max_size": limit})]

    def fix(self, issue, tex, cfg):
        tex.set_editor_property("max_texture_size", issue.fix_data["max_size"])
        return True


@register
class CompressionCheck(TextureRule):
    id = "tex.compression"
    fix_props = ("compression_settings",)
    rule_key = "compression"

    def run(self, ad, asset, cfg):
        sfx, want = self.rule(ad, cfg)
        have = tag(ad, "CompressionSettings")
        if not want or not have or norm(have) == norm(want):
            return []
        return [self.issue(ad, Severity.ERROR, f"{sfx} uses {have}, expected {want}",
                           fixable=True, fix_data={"compression": want})]

    def fix(self, issue, tex, cfg):
        tex.set_editor_property("compression_settings",
                                enum_member(unreal.TextureCompressionSettings, issue.fix_data["compression"]))
        return True


@register
class SRGBCheck(TextureRule):
    id = "tex.srgb"
    fix_props = ("srgb",)
    rule_key = "srgb"

    def run(self, ad, asset, cfg):
        sfx, want = self.rule(ad, cfg)
        have = tag(ad, "SRGB")
        if want is None or have is None or (have == "True") == want:
            return []
        return [self.issue(ad, Severity.ERROR, f"{sfx} has sRGB {'on' if want is False else 'off'}, expected {'on' if want else 'off'}",
                           fixable=True, fix_data={"srgb": want})]

    def fix(self, issue, tex, cfg):
        tex.set_editor_property("srgb", issue.fix_data["srgb"])
        return True


@register
class TextureGroupCheck(TextureRule):
    id = "tex.group"
    fix_props = ("lod_group",)
    rule_key = "texture_group"

    def run(self, ad, asset, cfg):
        sfx, want = self.rule(ad, cfg)
        have = tag(ad, "LODGroup")
        if not want or not have or norm(have) == norm(want):
            return []
        return [self.issue(ad, Severity.WARNING, f"{sfx} is in {have}, expected {want}",
                           fixable=True, fix_data={"group": want})]

    def fix(self, issue, tex, cfg):
        tex.set_editor_property("lod_group", enum_member(unreal.TextureGroup, issue.fix_data["group"]))
        return True
