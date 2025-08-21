import unreal
unreal.log(">>> MayaImporter: Python script executed successfully! <<<")

############################
# Unreal side importer (UE 5.6) — preserves Maya material/texture names, imports textures first,
# then imports the mesh with materials (no new material creation), and imports animations
# only if an *_anim.fbx exists AND a matching Skeleton is found (so no stray Animations folder).
############################

import unreal
import os
import datetime
import traceback

# === CONFIG ===
BASE_IMPORT_DIR = "/Game/Assets"
TEXTURE_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".exr", ".bmp", ".hdr")

# === LOGGING ===
LOG_FILE = os.path.join(
    unreal.SystemLibrary.get_project_saved_directory(), "Logs", "UnrealImportAssets.log"
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
    """
    Finds exports laid out as:
        Content/.../Meshes/<AssetName>.fbx
        Content/.../Textures/<AssetName>/...   (optional)
        Content/.../Animations/<AssetName>_anim.fbx  (optional)
    """
    content_dir = project_content_dir()
    results = []  # (asset_name, fbx_path, textures_dir, anim_fbx_path_or_None)

    for root, _, files in os.walk(content_dir):
        if os.path.basename(root).lower() != "meshes":
            continue
        for f in files:
            if not f.lower().endswith(".fbx"):
                continue
            fbx_path = os.path.join(root, f)
            asset_name = os.path.splitext(f)[0]

            root_dir = os.path.normpath(os.path.join(root, ".."))
            textures_dir = os.path.normpath(os.path.join(root_dir, "Textures", asset_name))
            anim_fbx = os.path.normpath(os.path.join(root_dir, "Animations", f"{asset_name}_anim.fbx"))
            if not os.path.isfile(anim_fbx):
                anim_fbx = None

            results.append((asset_name, fbx_path, textures_dir, anim_fbx))
    return results

# === IMPORT HELPERS ===
def import_textures(textures_dir_disk: str, textures_dir_ue: str):
    """Import textures first so material import can reuse them by original file names."""
    imported = {}
    if not os.path.isdir(textures_dir_disk):
        return imported

    tasks = []
    for fname in os.listdir(textures_dir_disk):
        if not is_texture_file(fname):
            continue
        src = os.path.join(textures_dir_disk, fname)
        t = unreal.AssetImportTask()
        t.filename = src
        t.destination_path = textures_dir_ue
        t.automated = True
        t.replace_identical = True
        t.save = True
        tasks.append(t)

    if tasks:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
        for t in tasks:
            if getattr(t, "imported_object_paths", None):
                tex_asset = unreal.load_asset(t.imported_object_paths[0])
                if tex_asset:
                    basename = os.path.basename(t.filename).lower()
                    imported[basename] = tex_asset
                    log_msg(f"✔ Imported texture: {tex_asset.get_path_name()}")
    return imported

def import_static_mesh_with_materials(asset_name: str, fbx_disk_path: str, meshes_dir: str, reuse_textures=True):
    """Import Static Mesh; import materials from FBX; optionally skip importing textures (reuse already-imported)."""
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
    fbx_ui.import_materials = True
    fbx_ui.import_textures = not reuse_textures  # if textures already imported, avoid duplicates
    # Preserve mesh parts and normals/tangents from FBX (works with Maya-baked smoothing)
    sm = unreal.FbxStaticMeshImportData()
    sm.combine_meshes = False
    try:
        sm.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_ImportNormalsAndTangents
    except Exception:
        pass  # property name varies across minor versions; safe to skip
    fbx_ui.static_mesh_import_data = sm

    task.options = fbx_ui
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    # Try to load the mesh (by canonical name or by returned path)
    mesh_asset_path = f"{meshes_dir}/{asset_name}"
    mesh_asset = unreal.EditorAssetLibrary.load_asset(mesh_asset_path)
    if not mesh_asset:
        imported_paths = getattr(task, "imported_object_paths", None) or []
        for p in imported_paths:
            obj = unreal.EditorAssetLibrary.load_asset(p)
            if isinstance(obj, unreal.StaticMesh):
                mesh_asset = obj
                break
    if not mesh_asset:
        raise RuntimeError(f"Failed to load imported mesh for '{asset_name}'.")
    log_msg(f"✔ Imported Static Mesh: {mesh_asset.get_path_name()}")
    return mesh_asset

def find_skeleton_for_asset(dest_root: str):
    """Look for a Skeleton under the asset bucket to bind animations; return None if not found."""
    try:
        for p in unreal.EditorAssetLibrary.list_assets(dest_root, recursive=True):
            obj = unreal.EditorAssetLibrary.load_asset(p)
            if isinstance(obj, unreal.SkeletalMesh):
                return obj.get_editor_property("skeleton")
            if isinstance(obj, unreal.Skeleton):
                return obj
    except Exception:
        pass
    return None

def import_animation_if_available(asset_name: str, anim_fbx_path: str, dest_root: str):
    """Import animation only if anim FBX exists and a Skeleton is found. Avoids creating an Animations folder otherwise."""
    if not anim_fbx_path or not os.path.isfile(anim_fbx_path):
        return False

    skeleton = find_skeleton_for_asset(dest_root)
    if not skeleton:
        log_warn(f"No Skeleton found for '{asset_name}'. Skipping animation import.")
        return False

    anim_dir = f"{dest_root}/Animations"
    ensure_directory(anim_dir)

    task = unreal.AssetImportTask()
    task.filename = anim_fbx_path
    task.destination_path = anim_dir
    task.automated = True
    task.replace_identical = True
    task.save = True

    fbx_ui = unreal.FbxImportUI()
    fbx_ui.import_mesh = False
    fbx_ui.import_as_skeletal = True
    fbx_ui.import_animations = True
    fbx_ui.skeleton = skeleton

    task.options = fbx_ui
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    imported_any = bool(getattr(task, "imported_object_paths", None))
    if imported_any:
        log_msg(f"✔ Imported Animation(s) for '{asset_name}' into {anim_dir}")
    return imported_any

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

    for asset_name, fbx_disk_path, textures_dir_disk, anim_fbx_disk in exports:
        try:
            dest_root     = f"{BASE_IMPORT_DIR}/{asset_name}"
            meshes_dir    = f"{dest_root}/Meshes"
            textures_dir  = f"{dest_root}/Textures"
            # Only create /Animations if we actually import an anim (handled in function)

            for d in (meshes_dir, textures_dir):
                ensure_directory(d)

            log_msg(f"=== Importing '{asset_name}' ===")

            # 1) Import textures first so FBX material import can reuse them by name
            imported_textures = import_textures(textures_dir_disk, textures_dir)

            # 2) Import the mesh + materials (do NOT import textures again)
            _ = import_static_mesh_with_materials(asset_name, fbx_disk_path, meshes_dir, reuse_textures=bool(imported_textures))

            # 3) Import animation only if *_anim.fbx exists AND a Skeleton is present
            if anim_fbx_disk:
                imported_anim = import_animation_if_available(asset_name, anim_fbx_disk, dest_root)
                if not imported_anim:
                    log_warn(f"No animation imported for '{asset_name}' (no Skeleton or empty file).")

            log_msg(f"=== Finished '{asset_name}' ===\n")

        except Exception as e:
            log_error(f"Import failed for '{asset_name}': {e}\n{traceback.format_exc()}")

    log_msg("All asset imports complete.")

# Run immediately when triggered by the plugin
main()
