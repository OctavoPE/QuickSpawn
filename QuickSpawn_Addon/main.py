bl_info = {
    "name": "QuickSpawn",
    "author": "OctavoPE",
    "version": (0, 0, 1),
    "blender": (3, 3, 0),
    "category": "3D View",
    "description": "Add Collections to quickly spawn them (Append/Link) when needed."
}

import bpy
from bpy.app.handlers import persistent

from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import StringProperty, CollectionProperty, BoolProperty, IntProperty, EnumProperty
import os
import json

# Thanks to mken for helping me with persisting data across sessions
BLENDER_ADDON_CONFIG_FILENAME = f'quickspawn.json'
BLENDER_ADDON_CONFIG_FILEPATH = os.path.join(bpy.utils.user_resource('CONFIG'), BLENDER_ADDON_CONFIG_FILENAME)

QUICKSPAWN_CATEGORYLIST = "quickspawn_categorylist"
QUICKSPAWN_CHARACTERLIST = "quickspawn_characterlist"

class CacheService:
    # read from cache
    def read_from_blender_cache(self):
        try:
            with open(BLENDER_ADDON_CONFIG_FILEPATH, 'r') as file:
                print(f"Reading from {BLENDER_ADDON_CONFIG_FILEPATH}")
                config = json.load(file)
                print(f"Config: {config}")
                return config
        except Exception as e:
            print(f"Error reading from {BLENDER_ADDON_CONFIG_FILEPATH}: {e}")
            return {}
    # attempt to find out if cachce exists
    def get_cache(self, cache_enabled=True):
        if not cache_enabled:
            return {}
        return self.read_from_blender_cache()
    # if it doesnt lets make it
    def write_to_blender_cache(self, config):
        with open(BLENDER_ADDON_CONFIG_FILEPATH, 'w') as file:
            print(f"Writing to {BLENDER_ADDON_CONFIG_FILEPATH}")
            json_str = json.dumps(config, indent=4)
            file.write(json_str)
            print(f"Wrote to {BLENDER_ADDON_CONFIG_FILEPATH}")
    # fired whenever category list is updated - added, removed, etc
    def cache_category_list(self, category_list):
        cache = self.get_cache()
        cache[QUICKSPAWN_CATEGORYLIST] = [
            {"name": category.name, "is_expanded": category.is_expanded}
            for category in category_list
        ]
        self.write_to_blender_cache(cache)
    # fired whenever character list is updated - added, removed, etc
    def cache_character_list(self, character_list):
        cache = self.get_cache()
        cache[QUICKSPAWN_CHARACTERLIST] = [
            {
                "name": character.name,
                "filepath": character.filepath,
                "collection": character.collection,
                "category": character.category
            }
            for character in character_list
        ]
        self.write_to_blender_cache(cache)
    # get the cached category list
    def get_cached_category_list(self):
        cache = self.get_cache()
        return cache.get(QUICKSPAWN_CATEGORYLIST, [])
    # get the cached character list
    def get_cached_character_list(self):
        cache = self.get_cache()
        return cache.get(QUICKSPAWN_CHARACTERLIST, [])
    
    # also we should save the import mode
    def cache_quickspawn_settings(self, import_mode):
        cache = self.get_cache()
        cache['quickspawn_import_mode'] = import_mode
        self.write_to_blender_cache(cache)
    
    # get the cached import mode
    def get_cached_quickspawn_settings(self):
        cache = self.get_cache()
        return cache.get('quickspawn_import_mode', 'APPEND')  # append default

# class containing relevant details for storing the category
class CATEGORY_PG_category(PropertyGroup):
    name: StringProperty(name="Category Name")
    is_expanded: BoolProperty(default=True)

# class containing relevant details for the character
class CHARACTER_PG_character(PropertyGroup):
    name: StringProperty(name="Name")
    filepath: StringProperty(name="File Path", subtype='FILE_PATH')
    collection: StringProperty(name="Collection Name")
    category: StringProperty(name="Category")

# add category - characters go into these
class CATEGORY_OT_add_category(Operator):
    bl_idname = "category.add_category"
    bl_label = "Add Category"
    bl_description = "Add a category"
    
    # name of the category
    name: StringProperty(name="Category Name")

    # presents the pop up to add category
    # use invoke if we need user input first
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    # draws the pop up with the name input
    # use draw if we need to display smthng before executing
    # if we need to show a custom dialog, we'll need to draw
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")

    # main functionality of operator. called after any user confirmations. ALL operators need execute. it returns FINISHED
    def execute(self, context):
        # note do we want to allow dupe categories?
        if any(category.name.lower() == self.name.lower() for category in context.scene.category_list):
            self.report({'ERROR'}, f"Category '{self.name}' already exists.")
            return {'CANCELLED'}
        
        category = context.scene.category_list.add()
        category.name = self.name
        context.area.tag_redraw()
        
        # Cache updated category list with new category
        CacheService().cache_category_list(context.scene.category_list)
        
        self.report({'INFO'}, f"Added category: {self.name}")
        return {'FINISHED'}

# are you sure you want to remove category (and characters)?
class CATEGORY_OT_remove_category(Operator):
    bl_idname = "category.remove_category"
    bl_label = "Remove Category"
    bl_description = "Remove a category and all its collections"
    # index of category to remove, passed in by the ui
    index: IntProperty()

    # only called when user confirms; blender logic handles this. (based on invoke's return value)
    def execute(self, context):
        category_name = context.scene.category_list[self.index].name

        context.scene.category_list.remove(self.index)
        context.area.tag_redraw()
        
        # Cache updated category list
        CacheService().cache_category_list(context.scene.category_list)
        
        # Remove characters in this category using the stored name
        characters_to_remove = [char for char in context.scene.character_list if char.category == category_name]
        for char in characters_to_remove:
            context.scene.character_list.remove(context.scene.character_list.find(char.name))
        
        # Cache updated character list with removed category
        CacheService().cache_character_list(context.scene.character_list)
        
        return {'FINISHED'}

    # asks user for confirmation
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

# adding character
class CHARACTER_OT_add_character(Operator):
    bl_idname = "character.add_character"
    bl_label = "Add Character"
    bl_description = "Add a collection to this category"
    
    filepath: bpy.props.StringProperty()
    directory: bpy.props.StringProperty()
    filename: bpy.props.StringProperty()
    
    # https://blenderartists.org/t/fileselect-add-that-goes-inside-blendfiles/1464061/2
    # not sure why but this is needed
    link: bpy.props.BoolProperty()
    autoselect: bpy.props.BoolProperty()
    active_collection: bpy.props.BoolProperty()
    filemode: bpy.props.IntProperty(default = 1)
    
    category: StringProperty(name="Category")

    def execute(self, context):
        # note do we want to allow dupe characters? assume characters coll names are unique
        if any(char.collection.lower() == self.filename.lower() and char.category == self.category 
               for char in context.scene.character_list):
            self.report({'ERROR'}, f"Collection '{self.filename}' already exists in category '{self.category}'.")
            return {'CANCELLED'}

        character = context.scene.character_list.add()
        character.name = os.path.basename(self.filepath)
        character.filepath = self.directory
        character.collection = self.filename
        character.category = self.category
        # forces ui update: WITHOUT THIS, UI DOESNT UPDATE UNTIL YOU MOVE YOUR MOUSE
        context.area.tag_redraw()
        
        # Cache updated character list with new character
        CacheService().cache_character_list(context.scene.character_list)
        self.report({'INFO'}, f"Added {self.filename} to {self.category}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "category")
        layout.prop(self, "collection")
    
    def check(self, context):
        return True

# are you sure you want to remove character?
class CHARACTER_OT_remove_character(Operator):
    bl_idname = "character.remove_character"
    bl_label = "Remove Collection"
    bl_description = "Remove a collection from this category"
    index: IntProperty()

    def execute(self, context):
        context.scene.character_list.remove(self.index)
        context.area.tag_redraw()
        
        # Cache updated character list with deleted character
        CacheService().cache_character_list(context.scene.character_list)
        
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

# handles importing; one press importing
class CHARACTER_OT_import_character(Operator):
    bl_idname = "character.import_character"
    bl_label = "Import Character"
    bl_options = {'INTERNAL'}
    bl_description = "Import this collection"

    index: bpy.props.IntProperty()

    # prompts the user if they want append or link, then does action
    def execute(self, context):
        character = context.scene.character_list[self.index]
        
        if context.scene.quickspawn_import_mode == 'APPEND':
            # APPEND THE CHARACTER
            bpy.ops.wm.append(filename=character.collection, directory=character.filepath)   
            self.report({'INFO'}, f"Appended collection: {character.name}")
        else:
            # LINK THE CHARACTER
            bpy.ops.wm.link(filename=character.collection, directory=character.filepath)
            self.report({'INFO'}, f"Linked collection: {character.name}")
        
        return {'FINISHED'}


# drop down control thx cgpt
class CATEGORY_OT_toggle_expand(Operator):
    bl_idname = "category.toggle_expand"
    bl_label = "Toggle Category Expand"
    
    index: IntProperty()

    def execute(self, context):
        category = context.scene.category_list[self.index]
        category.is_expanded = not category.is_expanded

        # forgot to cache this, stays collapsed on blender relaunch
        CacheService().cache_category_list(context.scene.category_list)
        return {'FINISHED'}

# The main panel
class CHARACTER_PT_panel(Panel):
    bl_label = "QuickSpawn"
    bl_idname = "CHARACTER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "QuickSpawn"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        print(f"Drawing panel. Category count: {len(scene.category_list)}, Character count: {len(scene.character_list)}")

        
        row = layout.row()
        row.label(text="Import Mode")
        row.prop(scene, "quickspawn_import_mode", expand=True, text="Import Mode")

        row = layout.row()
        row.operator("category.add_category", text="Add Category", icon='ADD')

        layout.separator()
        
        for catNum, category in enumerate(scene.category_list):
            print(f"Drawing category: {category.name}")
            box = layout.box()
            row = box.row()
            expand_ico = 'TRIA_DOWN' if category.is_expanded else 'TRIA_RIGHT'
            row.operator("category.toggle_expand", text="", icon=expand_ico, emboss=False).index = catNum
            row.label(text=category.name)
            row.operator("category.remove_category", text="", icon='X').index = catNum
            
            if category.is_expanded:
                row = box.row()
                op = row.operator("character.add_character", text="Add Collection", icon='COLLECTION_NEW')
                op.category = category.name
                
                sorted_characters = sorted(
                    [char for char in scene.character_list if char.category == category.name],
                    key=lambda x: x.collection.lower()
                )
                print(f"Characters in {category.name}: {[char.name for char in sorted_characters]}")
                
                for character in sorted_characters:
                    row = box.row()
                    op = row.operator("character.import_character", text=character.collection)
                    op.index = scene.character_list.find(character.name)
                    row.operator("character.remove_character", text="", icon='TRASH').index = scene.character_list.find(character.name)

        print("Finished drawing panel")


# list of the classes to register
classes = (
    CATEGORY_PG_category,
    CHARACTER_PG_character,
    CATEGORY_OT_add_category,
    CATEGORY_OT_remove_category,
    CHARACTER_OT_add_character,
    CHARACTER_OT_remove_character,
    CHARACTER_OT_import_character,
    CHARACTER_PT_panel,
    CATEGORY_OT_toggle_expand,
)
# change between append and link
def import_mode_update(self, context):
    CacheService().cache_quickspawn_settings(self.quickspawn_import_mode)

# done whenever add on is installed
def register():
    print("Registering QuickSpawn addon")
    for clas in classes:
        bpy.utils.register_class(clas)

    bpy.types.Scene.character_list = CollectionProperty(type=CHARACTER_PG_character)
    bpy.types.Scene.category_list = CollectionProperty(type=CATEGORY_PG_category)

    bpy.types.Scene.quickspawn_import_mode = EnumProperty(
        name="Import Mode",
        items=[
            ('APPEND', "Append", "Append the collection to the scene"),
            ('LINK', "Link", "Link the collection to the scene")
        ],
        default=CacheService().get_cached_quickspawn_settings(),
        update=import_mode_update
    )

    # check for cache, if not found, create it
    cache_service = CacheService()
    if not cache_service.get_cache():
        # default empty stuff
        cache_service.write_to_blender_cache({QUICKSPAWN_CATEGORYLIST: [], QUICKSPAWN_CHARACTERLIST: []})

    # Register load handler (only if not already registered)
    if load_quickspawn_data not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_quickspawn_data)

def unregister():
    print("Unregistering QuickSpawn addon")
    # Unregister load handler
    if load_quickspawn_data in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_quickspawn_data)

    del bpy.types.Scene.character_list
    del bpy.types.Scene.category_list
    del bpy.types.Scene.quickspawn_import_mode

    for clas in reversed(classes):
        bpy.utils.unregister_class(clas)


if __name__ == "__main__":
    register()

# this is called when the file is loaded: from the cache, write the data to the scene's lists
@persistent
def load_quickspawn_data(dummy):
    print("Starting load_quickspawn_data")
    cache_service = CacheService()
    
    # Clear OLD!
    bpy.context.scene.category_list.clear()
    bpy.context.scene.character_list.clear()
    print(f"Cleared lists. Category count: {len(bpy.context.scene.category_list)}, Character count: {len(bpy.context.scene.character_list)}")
    
    # Load categories
    cached_categories = cache_service.get_cached_category_list()
    print(f"Cached categories: {cached_categories}")
    for cat_data in cached_categories:
        category = bpy.context.scene.category_list.add()
        category.name = cat_data["name"]
        category.is_expanded = cat_data["is_expanded"]
        print(f"Added category: {category.name}")
    
    # Load characters
    cached_characters = cache_service.get_cached_character_list()
    print(f"Cached characters: {cached_characters}")
    for char_data in cached_characters:
        character = bpy.context.scene.character_list.add()
        character.name = char_data["name"]
        character.filepath = char_data["filepath"]
        character.collection = char_data["collection"]
        character.category = char_data["category"]
        print(f"Added character: {character.name} in category {character.category}")

    print(f"Final counts - Categories: {len(bpy.context.scene.category_list)}, Characters: {len(bpy.context.scene.character_list)}")
    print("Finished load_quickspawn_data")

