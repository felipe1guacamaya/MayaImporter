# MayaImporter texture compression helper (drop under: Content/Python/texture_compression.py)
# Usage:
#   from texture_compression import apply_texture_compression_rules
#   apply_texture_compression_rules(asset_paths=[...], manifest_path=".../import_manifest.json")
#
# If manifest_path is provided, it will be used as the source of truth for usage hints.
# Otherwise, filenames are inspected to decide Normal vs Color.

import os
import json
import unreal

NORMAL_TOKENS = ("_n", "_normal", "_norm", "-nrm", "_nrm", ".n.")

def _is_normal_by_name(name):
    base = os.path.splitext(os.path.basename(name))[0].lower()
    return any(tok in base for tok in NORMAL_TOKENS)

def _load_manifest(manifest_path):
    if not manifest_path or not os.path.isfile(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        result = {}
        for t in data.get("textures", []):
            result[t.get("filename")] = t.get("usage")
        return result
    except Exception:
        return {}

def _apply_to_texture_asset(tex, usage):
    # usage: "normal" or "color"
    if not isinstance(tex, unreal.Texture):
        return False

    if usage == "normal":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
    else:
        # default to BC7 for all non-normal textures
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_BC7)
        tex.set_editor_property("srgb", True)

    tex.post_edit_change()
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    return True

def apply_texture_compression_rules(asset_paths, manifest_path=None):
    hints = _load_manifest(manifest_path)
    for path in asset_paths or []:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if not asset:
            continue
        if isinstance(asset, unreal.Texture):
            # Prefer manifest usage keyed by the original disk filename; fallback to name tokens.
    try:
        src = asset.get_editor_property("asset_import_data").get_first_filename() or ""
    except Exception:
        src = ""
        basename = os.path.basename(src).lower() if src else ""
        usage = hints.get(basename) or ("normal" if _is_normal_by_name(src or path) else "color")
