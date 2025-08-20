import unreal
unreal.log(">>> MayaImporter: Python script executed successfully! <<<")

# import_unreal_V4.0_corrected.py
# Maya/Unreal asset importer: FBX + optional textures + simple material creation.
# Ready for plugin-triggered execution.

import unreal
import os
import datetime
import traceback


# === CONFIGURATION ===

BASE_IMPORT_DIR = "/Game/Assets"
TEXTURE_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".exr", ".bmp", ".hdr")


# === LOGGING ===

LOG_FILE = os.path.join(
    unreal.SystemLibrary.get_project_saved_directory(),
    "Logs",
    "UnrealImportAssets.log"
)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def _log(level_fn, prefix, msg):
    level_fn(msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {prefix}{msg}\n")
    except Exception:
        pass

def log_msg(msg):   _log(unreal.log, "",            msg)
def log_warn(msg):  _log(unreal.log_warning, "W: ", msg)
def log_error(msg): _log(unreal.log_error,   "E: ", msg)


# === UTILITIES ===

def ensure_directory(ue_path: str):
    if not unreal.EditorAssetLibrary.does_directory_exist(ue_path):
        unreal.EditorAssetLibrary.make_directory(ue_path)
        log_msg(f"Created UE directory: {ue_path}")

def project_content_dir() -> str:
    return os.path.normpath(unreal.SystemLibrary.get_project_content_directory())

def is_texture_file(filename: str) -> bool:
    return filename.lower().endswith(TEXTURE_EXTS)


# === DISCOVERY ===

def find_maya_exports():
    content_dir = project_content_dir()
    results = []

    for root, _, files in os.walk(content_dir):
        if os.path.basename(root).lower() != "meshes":
            continue

        for f in files:
            if not f.lower().endswith(".fbx"):
                continue

            fbx_path = os.path.join(root, f)
            asset_name = os.path.splitext(f)[0]
            textures_dir = os.path.normpath(os.path.join(root, "..", "Textures", asset_name))

            results.append((asset_name, fbx_path, textures_dir))

    return results


# === IMPORT WORK ===

def import_mesh(asset_name: str, fbx_disk_path: str, meshes_dir: str):
    task = unreal.AssetImportTask()
    task.filename = fbx_disk_path
    task.destination_path = meshes_dir
    task.automated = True
    task.replace_identical = True
    task.save = True

    fbx_ui = unreal.FbxImportUI()
    fbx_ui.import_mesh = True
    fbx_ui.import_as_skeletal = False
    fbx_ui.import_animations = False

    task.options = fbx_ui

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    # Load imported mesh
    mesh_asset_path = f"{meshes_dir}/{asset_name}"
    mesh_asset = unreal.EditorAssetLibrary.load_asset(mesh_asset_path)
    if not mesh_asset:
        imported_paths = getattr(task, "imported_object_paths", None)
        if imported_paths:
            candidate = imported_paths[0]
            mesh_asset = unreal.EditorAssetLibrary.load_asset(candidate)

    if not mesh_asset:
        raise RuntimeError(f"Failed to load imported mesh for '{asset_name}'.")

    log_msg(f"✔ Imported Static Mesh: {mesh_asset.get_path_name()}")
    return mesh_asset


def import_textures(textures_dir_disk: str, textures_dir_ue: str):
    imported = {}

    if not os.path.isdir(textures_dir_disk):
        log_warn(f"No textures folder found: {textures_dir_disk}")
        return imported

    for fname in os.listdir(textures_dir_disk):
        if not is_texture_file(fname):
            continue
        src = os.path.join(textures_dir_disk, fname)

        ttask = unreal.AssetImportTask()
        ttask.filename = src
        ttask.destination_path = textures_dir_ue
        ttask.automated = True
        ttask.replace_identical = True
        ttask.save = True

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([ttask])

        if getattr(ttask, "imported_object_paths", None):
            tex_asset = unreal.load_asset(ttask.imported_object_paths[0])
            if tex_asset:
                imported[fname.lower()] = tex_asset
                log_msg(f"✔ Imported texture: {tex_asset.get_path_name()}")
        else:
            log_warn(f"Texture import failed: {src}")

    return imported


def choose_basecolor_texture(imported_textures: dict):
    keys = ("basecolor", "base_color", "albedo", "diffuse", "color")
    for name, tex in imported_textures.items():
        if any(k in name.lower() for k in keys):
            return tex
    if len(imported_textures) == 1:
        return next(iter(imported_textures.values()))
    return None


def create_simple_material(asset_name: str, materials_dir: str, basecolor_tex):
    mat_name = f"{asset_name}_M"
    mat_path = f"{materials_dir}/{mat_name}"

    if unreal.EditorAssetLibrary.does_asset_exist(mat_path):
        unreal.EditorAssetLibrary.delete_asset(mat_path)
        log_warn(f"Overwriting existing material: {mat_path}")

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=mat_name,
        package_path=materials_dir,
        asset_class=unreal.Material,
        factory=unreal.MaterialFactoryNew(),
    )
    if not material:
        raise RuntimeError(f"Failed to create material '{mat_name}'.")

    if basecolor_tex:
        sample = unreal.MaterialEditingLibrary.create_texture_sample(material, basecolor_tex)
        unreal.MaterialEditingLibrary.connect_material_property(
            sample, unreal.MaterialProperty.MP_BASE_COLOR
        )

    unreal.EditorAssetLibrary.save_loaded_asset(material)
    log_msg(f"✔ Created material: {material.get_path_name()}")
    return material


def assign_material(mesh_asset, material):
    try:
        slot_count = mesh_asset.get_num_materials()
    except Exception:
        slot_count = 1

    for slot in range(slot_count):
        try:
            mesh_asset.set_material(slot, material)
        except Exception as e:
            log_warn(f"Failed to set material on slot {slot}: {e}")

    mesh_asset.post_edit_change()
    mesh_asset.mark_package_dirty()
    unreal.EditorAssetLibrary.save_loaded_asset(mesh_asset)
    log_msg(f"✔ Assigned material to {slot_count} slot(s) on {mesh_asset.get_path_name()}")


# === MAIN ===

def main():
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write("\n" + "=" * 60 + f"\nRUN START: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
    except Exception:
        pass

    exports = find_maya_exports()
    if not exports:
        log_warn("No FBX files found under Content/*/Meshes/. Nothing to import.")
        return

    for asset_name, fbx_disk_path, textures_dir_disk in exports:
        try:
            dest_root = f"{BASE_IMPORT_DIR}/{asset_name}"
            meshes_dir = f"{dest_root}/Meshes"
            textures_dir = f"{dest_root}/Textures"
            materials_dir = f"{dest_root}/Materials"

            for d in (meshes_dir, textures_dir, materials_dir):
                ensure_directory(d)

            log_msg(f"=== Importing '{asset_name}' ===")
            mesh = import_mesh(asset_name, fbx_disk_path, meshes_dir)

            imported_textures = import_textures(textures_dir_disk, textures_dir)
            base_tex = choose_basecolor_texture(imported_textures)

            material = create_simple_material(asset_name, materials_dir, base_tex)
            assign_material(mesh, material)

            log_msg(f"=== Finished '{asset_name}' ===\n")

        except Exception as e:
            log_error(f"Import failed for '{asset_name}': {e}\n{traceback.format_exc()}")

    log_msg("All asset imports complete.")

# Removed automatic execution: main() will be called by plugin button