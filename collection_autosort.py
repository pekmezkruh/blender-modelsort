"""
Collection Auto-Sort by Name Prefix
===================================

Automatically files objects into collections based on their names.

1. PREFIX MATCHING (objects without a leading '#')
   The object is moved into the EXISTING collection whose name is the
   LONGEST prefix of the object's name followed by a separator ('_' or '.').
       engine_metalblue         -> collection 'engine'
       enginedynamic_metalblue  -> collection 'enginedynamic'  (longest wins)
       carburettor_paintred     -> collection 'carburettor'
   Objects whose prefix matches no existing collection are left untouched.

2. EXPLICIT #PATH CREATION (objects whose name starts with '#')
   The '#'-separated segments define a collection path. Missing collections
   are created, existing ones are reused, and the object is renamed with the
   hashtag prefix stripped.
       #vehicle#exterior#engine#enginepart2_object
         -> creates/reuses  vehicle / exterior / engine / enginepart2
         -> links the object into 'enginepart2'
         -> renames the object to 'enginepart2_object'
   The final collection takes the PREFIX of the leaf segment, so later
   prefix-matched objects (enginepart2_*) will also land in it.

OPTIONS (operator dialog)
   Objects          : Selected only, or All in scene.
   Match Against    : Scene collections, or every collection in the .blend.
   Separators       : '_' and/or '.' (at least one required).
   Case Sensitive   : prefix comparison case sensitivity (default off).
   Move (exclusive) : unlink from other collections (default), or also-link.
   Create From #Path: enable '#path' creation (default on).

LIVE AUTO-SORT (react to renames)
   Enable 'Live Auto-Sort (on rename)' in the N-panel to automatically
   re-sort an object the moment its name changes (prefix match or #path).
   Off by default; live-mode defaults live in Add-on Preferences.

WHERE TO RUN
   View3D > Sidebar (N) > 'Auto-Sort' tab, or
   Object menu > Collection > Auto-Sort Into Collections.
"""

bl_info = {
    "name": "Collection Auto-Sort by Name Prefix",
    "author": "pekmez",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar (N) > Auto-Sort  |  Object > Collection",
    "description": (
        "Sort objects into collections by name. A prefix matching an existing "
        "collection (engine_metalblue -> 'engine'; longest match wins for "
        "enginedynamic_*) moves the object there. A name starting with '#' "
        "like #vehicle#exterior#engine#part_object creates/reuses the nested "
        "collections vehicle/exterior/engine/part and moves+renames the "
        "object into it. Optional Live Auto-Sort re-sorts objects the moment "
        "they are renamed. See Add-on Preferences for full usage notes."),
    "doc_url": "",
    "category": "Object",
}

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, StringProperty


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

SEPARATORS = ("_", ".")


def _iter_collections(root):
    """Yield every collection under (and including) root recursively."""
    stack = [root]
    seen = set()
    while stack:
        col = stack.pop()
        if col.name in seen:
            continue
        seen.add(col.name)
        yield col
        stack.extend(col.children)


def find_target_collection(obj_name, collections, separators, case_sensitive):
    """Return the collection whose name is the LONGEST prefix of obj_name
    that is immediately followed by one of the given separators.

    This makes 'enginedynamic_metalblue' match 'enginedynamic' rather than
    'engine', because the longer match wins.
    """
    name = obj_name if case_sensitive else obj_name.lower()
    best = None
    best_len = -1
    for col in collections:
        col_name = col.name if case_sensitive else col.name.lower()
        if not name.startswith(col_name):
            continue
        # character right after the matched prefix must be a separator
        tail = name[len(col_name):]
        if not tail:
            continue  # object name identical to collection name -> skip
        if tail[0] not in separators and separators:
            continue
        if len(col_name) > best_len:
            best = col
            best_len = len(col_name)
    return best


def _unlink_from_all(obj):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)


def _prefix_of(name, separators):
    """Return the part of 'name' before the first separator (or whole name)."""
    idx = min(
        (name.find(s) for s in separators if name.find(s) != -1),
        default=-1)
    return name if idx == -1 else name[:idx]


def parse_hashtag_name(name, separators):
    """Parse an explicit '#a#b#c#leaf_object' name.

    Returns (path_names, object_name) or None if not a hashtag name.
      '#vehicle#exterior#engine#enginepart2_object'
        -> (['vehicle', 'exterior', 'engine', 'enginepart2'],
            'enginepart2_object')
    The final collection takes the prefix of the leaf segment; the object is
    renamed to that leaf segment (hashtag path stripped).
    """
    if not name.startswith("#"):
        return None
    segments = [s for s in name[1:].split("#")]
    # drop empty segments caused by '##' but keep the leaf intact
    segments = [s for s in segments if s != ""]
    if len(segments) < 2:
        return None
    parents = segments[:-1]
    leaf = segments[-1]
    leaf_col = _prefix_of(leaf, separators)
    path_names = parents + [leaf_col]
    return path_names, leaf


def ensure_collection_path(scene, path_names):
    """Create/reuse a nested chain of collections under the scene and
    return the deepest collection."""
    parent = scene.collection
    deepest = parent
    for cname in path_names:
        found = None
        # reuse only a collection that is already a DIRECT child of this parent
        # (so #vehicle#exterior#engine reuses the real existing chain, but we
        # never alias/relink a collection that lives elsewhere)
        for child in parent.children:
            if child.name == cname:
                found = child
                break
        if found is None:
            found = bpy.data.collections.new(cname)
            parent.children.link(found)
        parent = found
        deepest = found
    return deepest


def sort_objects(context, objects, separators, case_sensitive,
                 move_exclusive, search_scope, create_from_hashtag=True):
    scene = context.scene

    if search_scope == 'SCENE':
        root = scene.collection
        collections = list(_iter_collections(root))
    else:  # ALL data collections
        collections = list(bpy.data.collections)

    moved, skipped = 0, 0
    report_lines = []

    for obj in objects:
        # --- explicit hashtag path: create nested collections -------------
        if create_from_hashtag:
            parsed = parse_hashtag_name(obj.name, separators)
            if parsed is not None:
                path_names, new_name = parsed
                target = ensure_collection_path(scene, path_names)
                _unlink_from_all(obj)
                target.objects.link(obj)
                old = obj.name
                obj.name = new_name
                moved += 1
                report_lines.append(
                    f"{old} -> /{'/'.join(path_names)}/  (renamed '{obj.name}')")
                # refresh collection list so later objects can match new cols
                if search_scope == 'SCENE':
                    collections = list(_iter_collections(scene.collection))
                else:
                    collections = list(bpy.data.collections)
                continue

        target = find_target_collection(
            obj.name, collections, separators, case_sensitive)
        if target is None:
            skipped += 1
            continue
        # already correctly placed?
        if target.name in [c.name for c in obj.users_collection] and \
           (not move_exclusive or len(obj.users_collection) == 1):
            continue
        if move_exclusive:
            _unlink_from_all(obj)
        if target.name not in [c.name for c in obj.users_collection]:
            target.objects.link(obj)
        moved += 1
        report_lines.append(f"{obj.name} -> {target.name}")

    return moved, skipped, report_lines


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class OBJECT_OT_collection_autosort(bpy.types.Operator):
    bl_idname = "object.collection_autosort"
    bl_label = "Auto-Sort Into Collections"
    bl_description = ("Move objects into the collection whose name matches "
                      "the object's name prefix")
    bl_options = {'REGISTER', 'UNDO'}

    use_underscore: BoolProperty(
        name="Underscore ( _ )", default=True,
        description="Treat '_' as a prefix separator")
    use_dot: BoolProperty(
        name="Dot ( . )", default=True,
        description="Treat '.' as a prefix separator")
    case_sensitive: BoolProperty(
        name="Case Sensitive", default=False)
    move_exclusive: BoolProperty(
        name="Move (exclusive)", default=True,
        description="Unlink from other collections so the object lives only "
                    "in its matched collection. If off, it is additionally "
                    "linked (kept in current collections)")
    create_from_hashtag: BoolProperty(
        name="Create From #Path", default=True,
        description="Names like '#vehicle#exterior#engine#part_object' create "
                    "the nested collections vehicle/exterior/engine/part and "
                    "move the object there (renaming it to 'part_object')")

    scope: EnumProperty(
        name="Objects",
        items=[
            ('SELECTED', "Selected", "Only sort selected objects"),
            ('ALL', "All in Scene", "Sort every object in the scene"),
        ],
        default='SELECTED')

    search_scope: EnumProperty(
        name="Match Against",
        items=[
            ('SCENE', "Scene Collections", "Only collections linked in the scene"),
            ('DATA', "All Collections", "Every collection in the .blend"),
        ],
        default='SCENE')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scope")
        layout.prop(self, "search_scope")
        box = layout.box()
        box.label(text="Separators:")
        row = box.row()
        row.prop(self, "use_underscore")
        row.prop(self, "use_dot")
        layout.prop(self, "case_sensitive")
        layout.prop(self, "move_exclusive")
        layout.prop(self, "create_from_hashtag")

    def execute(self, context):
        separators = tuple(
            s for s, on in ((("_"), self.use_underscore), (("."), self.use_dot))
            if on)
        if not separators:
            self.report({'ERROR'}, "Select at least one separator.")
            return {'CANCELLED'}

        if self.scope == 'SELECTED':
            objects = list(context.selected_objects)
            if not objects:
                self.report({'WARNING'}, "No objects selected.")
                return {'CANCELLED'}
        else:
            objects = list(context.scene.objects)

        moved, skipped, lines = sort_objects(
            context, objects, separators, self.case_sensitive,
            self.move_exclusive, self.search_scope, self.create_from_hashtag)

        for ln in lines:
            print("[AutoSort]", ln)
        self.report({'INFO'},
                    f"Sorted {moved} object(s); {skipped} unmatched.")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class VIEW3D_PT_collection_autosort(bpy.types.Panel):
    bl_label = "Collection Auto-Sort"
    bl_idname = "VIEW3D_PT_collection_autosort"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Auto-Sort"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        op = col.operator("object.collection_autosort",
                          text="Sort Selected", icon='OUTLINER_COLLECTION')
        op.scope = 'SELECTED'
        op = col.operator("object.collection_autosort",
                          text="Sort All In Scene", icon='SCENE_DATA')
        op.scope = 'ALL'

        box = layout.box()
        box.prop(context.scene, "autosort_live_enabled",
                 text="Live Auto-Sort (on rename)", icon='FILE_REFRESH')
        if context.scene.autosort_live_enabled:
            box.label(text="Objects re-sort when renamed.", icon='INFO')

        header, body = layout.panel("autosort_help", default_closed=True) \
            if hasattr(layout, "panel") else (layout, layout)
        header.label(text="Usage / Help", icon='INFO')
        if body is not None:
            _draw_help(body)


def _menu_func(self, context):
    self.layout.operator("object.collection_autosort",
                         icon='OUTLINER_COLLECTION')


# ---------------------------------------------------------------------------
# Live auto-sort (react to object name changes)
# ---------------------------------------------------------------------------
#
# Blender has no dedicated "name changed" callback, so we watch the depsgraph
# for updated objects, compare each object's current name against a cached
# value, and -- when it differs -- queue the object for sorting. The actual
# collection move is performed from a timer, NOT inside the depsgraph handler,
# because editing data (linking/renaming) during a depsgraph update is unsafe.

_name_cache = {}          # object .as_pointer() -> last seen name
_pending = set()          # names of objects awaiting a live sort
_timer_active = False
_is_sorting = False       # re-entry guard


def _live_settings():
    """Return (separators, case_sensitive, move_exclusive, search_scope,
    create_from_hashtag) for live sorting, from preferences if available."""
    try:
        prefs = bpy.context.preferences.addons[__name__].preferences
        seps = tuple(s for s, on in (("_", prefs.live_use_underscore),
                                     (".", prefs.live_use_dot)) if on)
        if not seps:
            seps = ("_", ".")
        return (seps, prefs.live_case_sensitive, prefs.live_move_exclusive,
                prefs.live_search_scope, prefs.live_create_from_hashtag)
    except Exception:
        return (("_", "."), False, True, 'SCENE', True)


def _rebuild_cache(scene=None):
    # bpy.data is restricted during some callbacks (e.g. load_post); bail out
    # quietly and let the next depsgraph pass seed the cache instead.
    try:
        scenes = [scene] if scene else list(bpy.data.scenes)
        _name_cache.clear()
        for sc in scenes:
            for obj in sc.objects:
                _name_cache[obj.as_pointer()] = obj.name
    except (AttributeError, ReferenceError):
        pass


def _process_pending():
    """Timer callback: sort any queued objects."""
    global _timer_active, _is_sorting
    _timer_active = False
    if not _pending:
        return None
    context = bpy.context
    scene = context.scene
    if scene is None:
        _pending.clear()
        return None

    seps, case_sens, move_excl, scope, from_hash = _live_settings()
    names = list(_pending)
    _pending.clear()
    objects = [scene.objects.get(n) for n in names]
    objects = [o for o in objects if o is not None]
    if not objects:
        return None

    _is_sorting = True
    try:
        moved, skipped, lines = sort_objects(
            context, objects, seps, case_sens, move_excl, scope, from_hash)
        for ln in lines:
            print("[AutoSort/live]", ln)
    except Exception as exc:  # never let the timer die silently
        print("[AutoSort/live] error:", exc)
    finally:
        _is_sorting = False
        # refresh cache so renamed objects aren't reprocessed endlessly
        _rebuild_cache()
    return None


@persistent
def _depsgraph_handler(scene, depsgraph=None):
    """Detect object name changes and queue them for the timer."""
    global _timer_active
    if _is_sorting:
        return
    if not getattr(scene, "autosort_live_enabled", False):
        return

    changed = False
    for obj in scene.objects:
        key = obj.as_pointer()
        prev = _name_cache.get(key)
        if prev is None:
            _name_cache[key] = obj.name
            continue
        if prev != obj.name:
            _name_cache[key] = obj.name
            _pending.add(obj.name)
            changed = True

    if changed and not _timer_active:
        _timer_active = True
        bpy.app.timers.register(_process_pending, first_interval=0.0)


@persistent
def _load_post_handler(dummy):
    _pending.clear()
    _rebuild_cache()


def _enable_live():
    if _depsgraph_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_handler)
    if _load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_handler)
    _rebuild_cache()


def _disable_live():
    if _depsgraph_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_handler)
    if _load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_handler)


def _on_live_toggle(self, context):
    """Scene property update: (re)build cache when live sort is switched on."""
    if self.autosort_live_enabled:
        _rebuild_cache()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

# Usage notes shown in Add-on Preferences and the N-panel 'Help' box.
HELP_LINES = (
    ("PREFIX MATCHING (no '#')", 'OUTLINER_COLLECTION'),
    ("   name prefix must match an EXISTING collection, longest wins:", 'BLANK1'),
    ("      engine_metalblue        -> 'engine'", 'DOT'),
    ("      enginedynamic_metalblue -> 'enginedynamic'", 'DOT'),
    ("      carburettor_paintred    -> 'carburettor'", 'DOT'),
    ("   unmatched objects are left untouched.", 'BLANK1'),
    ("", 'BLANK1'),
    ("EXPLICIT #PATH (name starts with '#')", 'NEWFOLDER'),
    ("   creates/reuses nested collections, then renames the object:", 'BLANK1'),
    ("      #vehicle#exterior#engine#enginepart2_object", 'DOT'),
    ("      -> vehicle/exterior/engine/enginepart2", 'DOT'),
    ("      -> object renamed 'enginepart2_object'", 'DOT'),
    ("", 'BLANK1'),
    ("Separators: '_' and '.'   |   Run: N-panel 'Auto-Sort' or", 'BLANK1'),
    ("Object > Collection > Auto-Sort Into Collections", 'BLANK1'),
    ("", 'BLANK1'),
    ("LIVE AUTO-SORT", 'FILE_REFRESH'),
    ("   enable 'Live Auto-Sort (on rename)' to re-sort objects", 'BLANK1'),
    ("   automatically whenever their name changes.", 'BLANK1'),
)


def _draw_help(layout):
    col = layout.column(align=True)
    for text, icon in HELP_LINES:
        col.label(text=text, icon=icon)


class CollectionAutoSortPrefs(bpy.types.AddonPreferences):
    bl_idname = __name__

    # defaults used by LIVE auto-sort (the operator dialog has its own)
    live_use_underscore: BoolProperty(name="Underscore ( _ )", default=True)
    live_use_dot: BoolProperty(name="Dot ( . )", default=True)
    live_case_sensitive: BoolProperty(name="Case Sensitive", default=False)
    live_move_exclusive: BoolProperty(name="Move (exclusive)", default=True)
    live_create_from_hashtag: BoolProperty(name="Create From #Path",
                                           default=True)
    live_search_scope: EnumProperty(
        name="Match Against",
        items=[('SCENE', "Scene Collections", ""),
               ('DATA', "All Collections", "")],
        default='SCENE')

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Live Auto-Sort defaults", icon='TEMP')
        row = box.row()
        row.prop(self, "live_use_underscore")
        row.prop(self, "live_use_dot")
        box.prop(self, "live_case_sensitive")
        box.prop(self, "live_move_exclusive")
        box.prop(self, "live_create_from_hashtag")
        box.prop(self, "live_search_scope")

        layout.label(text="Usage", icon='INFO')
        box = layout.box()
        _draw_help(box)


classes = (
    OBJECT_OT_collection_autosort,
    VIEW3D_PT_collection_autosort,
    CollectionAutoSortPrefs,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.autosort_live_enabled = BoolProperty(
        name="Live Auto-Sort",
        description="Automatically sort an object into its matching collection "
                    "whenever its name changes",
        default=False,
        update=_on_live_toggle)
    bpy.types.VIEW3D_MT_object_collection.append(_menu_func)
    _enable_live()


def unregister():
    _disable_live()
    bpy.types.VIEW3D_MT_object_collection.remove(_menu_func)
    del bpy.types.Scene.autosort_live_enabled
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
