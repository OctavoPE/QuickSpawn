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
            {
                "name": category.name,
                "is_expanded": category.is_expanded,
                "generate_override": category.generate_override
            }
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
def update_generate_override(self, context):
    CacheService().cache_category_list(context.scene.category_list)
    context.area.tag_redraw()

class CATEGORY_PG_category(PropertyGroup):
    name: StringProperty(name="Category Name")
    is_expanded: BoolProperty(default=True)
    generate_override: BoolProperty(
        name="Library Override on Link",
        description="Leave this on for rigged characters. Disable if you're spawning unrigged meshes in this category.",
        default=True,
        update=update_generate_override
    )

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
    index: IntProperty()

    # only called when user confirms; blender logic handles this. (based on invoke's return value)
    def execute(self, context):
        category_name = context.scene.category_list[self.index].name

        # Remove the category
        context.scene.category_list.remove(self.index)
        
        # Remove characters in this category
        characters_to_remove = [char for char in context.scene.character_list if char.category == category_name]
        for char in characters_to_remove:
            context.scene.character_list.remove(context.scene.character_list.find(char.name))
        
        # Update the cache
        cache_service = CacheService()
        
        # Update category list in cache
        cache_service.cache_category_list(context.scene.category_list)
        
        # Update character list in cache
        cache_service.cache_character_list(context.scene.character_list)
        
        context.area.tag_redraw()
        
        self.report({'INFO'}, f"Removed category '{category_name}' and its associated collections.")
        return {'FINISHED'}

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

        if self.filename in bpy.data.filepath and ".blend" in self.filename:
            self.report({'ERROR'}, "Blender Limitation: Cannot add the current file as a library. It has to be done outside of the file.") # this appears to be a blender limitation
            return {'CANCELLED'}

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
 
    
    def execute(self, context):
        character = context.scene.character_list[self.index]
        category = next((cat for cat in context.scene.category_list if cat.name == character.category), None)
        
        initial_colls = set(bpy.data.collections)
        initial_texts = set(bpy.data.texts)
        initial_armatures = set(bpy.data.armatures)
        
        if context.scene.quickspawn_import_mode == 'APPEND':
            # User is appending given collection
            try:
                bpy.ops.wm.append(filename=character.collection, directory=character.filepath)   
                action = "Appended"
            except Exception as e:
                self.report({'ERROR'}, f"Could not append collection: {str(e)}")
                return {'CANCELLED'}
        else:
            # User is linking given collection. Additionally, it's made a library override.
            try:
                bpy.ops.wm.link(filename=character.collection, directory=character.filepath)
            except Exception as e:
                self.report({'ERROR'}, f"Error linking collection. It may contain datablocks that are not overridable and thus duplicate. Output: {str(e)}")
                return {'CANCELLED'}
            
            try:
                if category and category.generate_override:
                    bpy.ops.object.make_override_library()
            except Exception as e:
                self.report({'ERROR'}, f"Error making override: {str(e)}")
                return {'CANCELLED'}

            action = "Linked"
            if category and category.generate_override:
                action += " and overridden"
        
        new_colls = set(bpy.data.collections) - initial_colls
        new_texts = set(bpy.data.texts) - initial_texts
        new_armatures = set(bpy.data.armatures) - initial_armatures       
        
        is_character = False
        rig_object = None
        
        # identify if the collection we just added is a character
        for new_collection in new_colls:
            for obj in new_collection.objects:
                if obj.type == 'ARMATURE' and "metarig" not in obj.name.lower():
                    is_character = True
                    # we only care about armatures that are not named metarig
                    print(f"Found rig object: {obj.name}. Is Character.")
                    rig_object = obj
                    
                    break
            if is_character:
                break

        if is_character:
            self.report({'INFO'}, f"{action} character: {character.name}.")
            # Perform character-specific operations here
            self.process_character(rig_object, new_collection, new_texts, new_armatures, action, initial_texts)
        else:
            self.report({'INFO'}, f"{action} collection: {character.name}")
        
        return {'FINISHED'}
    
    # lel same code from setup addon
    def searchForLayerCollection(self, layerColl, coll_name):
        found = None
        if (layerColl.name == coll_name):
            return layerColl
        for layer in layerColl.children:
            found = self.searchForLayerCollection(layer, coll_name)
            if found:
                return found

    def disable_collection(self, collection_name):
        view_layer_collection = bpy.context.view_layer.layer_collection

        layer_collection_to_disable = self.searchForLayerCollection(view_layer_collection, collection_name)
        if layer_collection_to_disable:
            layer_collection_to_disable.exclude = True
            return True
        return False

    # after we identify the character, we can do some processing
    def process_character(self, rig_object, collection, texts, armatures, action_name, initial_texts):
        # if existing, close the wgt collection
        # within the collection, there is a COLLECTION possibly named wgt or wgts we need to disable it
        for obj in collection.children:
            if "wgt" in obj.name.lower() or "wgts" in obj.name.lower():
                print(f"Disabling collection: {obj.name}")
                self.disable_collection(obj.name)

        # identify the armature
        char_armature = None
        for armature in armatures:
            # if armature name doesn't have metarig in it, we can assume it's the character
            if "metarig" not in armature.name.lower():
                char_armature = armature
                break

        script_file = None
        # if we have an armature, we can identify the rig script.
        if char_armature:
            for text in texts:
                if "_ui.py" in text.name:
                    if action_name == "Appended":
                        script_file = text
                    elif "overridden" in action_name:
                        new_text = bpy.data.texts.new(char_armature.name+"_ui.py")
                        new_text.write(text.as_string())
                        script_file = new_text
                        script_file.use_module = True

                    break

        # If linking duplicate characters, this is the case below. 
        if len(texts) == 0 and "overridden" in action_name and char_armature:
            try:
                original_file = bpy.data.texts.get(char_armature.name.split(".")[0]+"_ui.py")
                original_text = original_file.as_string()
                
                new_text = bpy.data.texts.new(char_armature.name+"_ui.py") 
                new_text.write(original_text)
                script_file = new_text
                script_file.use_module = True # enables the text to be treated as a script - to be ran at .blend startup
            except:
                pass # if we get here, it's likely a rig with no corresponding rig script, in which case, just ignore.
        
        if script_file:
            try:
                # this allows us to handle duplicate armature names, that way, the rig layers can be present for duplicated characters
                # every char should just have a unique id; this needs to especially be true for duplicate characters.
                random_id = str(hash(char_armature.name.lower().replace(" ", ""))).replace("-", "")
                
                bpy.data.armatures[char_armature.name]["rig_id"] = random_id
                
                print(f"Generated new rig_id: {bpy.data.armatures[char_armature.name]['rig_id']}")

                script_text = script_file.as_string()
                script_text = script_text.replace(char_armature.name.split(".")[0], char_armature.name)

                rig_char_id = script_text.split("rig_id = \"")[1].split("\"")[0]
                script_text = script_text.replace(rig_char_id, random_id)


                script_file.clear()
                script_file.write(script_text)

                ctx = bpy.context.copy()
                ctx['edit_text'] = script_file
                with bpy.context.temp_override(**ctx):
                    bpy.ops.text.run_script()

            except:
                pass

        
        self.report({'INFO'}, "Setup successful")




# drop down control thx cgpt
class CATEGORY_OT_toggle_expand(Operator):
    bl_idname = "category.toggle_expand"
    bl_label = "Toggle Category Expand"
    
    index: IntProperty()

    def execute(self, context):
        category = context.scene.category_list[self.index]
        category.is_expanded = not category.is_expanded

        # Update the cache
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
       
        row = layout.row()
        row.label(text="Import Mode")
        row.prop(scene, "quickspawn_import_mode", expand=True, text="Import Mode")

        row = layout.row()
        row.operator("category.add_category", text="Add Category", icon='ADD')

        layout.separator()
        
        for catNum, category in enumerate(scene.category_list):
            box = layout.box()
            row = box.row()
            expand_ico = 'TRIA_DOWN' if category.is_expanded else 'TRIA_RIGHT'
            row.operator("category.toggle_expand", text="", icon=expand_ico, emboss=False).index = catNum
            row.label(text=category.name)
            row.operator("category.settings", text="", icon='SETTINGS').index = catNum
            row.operator("category.remove_category", text="", icon='X').index = catNum
            
            if category.is_expanded:
                row = box.row()
                op = row.operator("character.add_character", text="Add Collection", icon='COLLECTION_NEW')
                op.category = category.name
                
                sorted_characters = sorted(
                    [char for char in scene.character_list if char.category == category.name],
                    key=lambda x: x.collection.lower()
                )
                
                for character in sorted_characters:
                    row = box.row()
                    op = row.operator("character.import_character", text=character.collection)
                    op.index = scene.character_list.find(character.name)
                    row.operator("character.remove_character", text="", icon='TRASH').index = scene.character_list.find(character.name)

        layout.separator()
        layout.operator("quickspawn.clear_everything", text="Clear Everything", icon='TRASH')

class QUICKSPAWN_OT_clear_everything(Operator):
    bl_idname = "quickspawn.clear_everything"
    bl_label = "Clear Everything"
    bl_description = "Remove all categories and collections."

    def execute(self, context):
        # Clear all categories and characters from the scene
        context.scene.category_list.clear()
        context.scene.character_list.clear()

        # Clear the cache file
        CacheService().write_to_blender_cache({QUICKSPAWN_CATEGORYLIST: [], QUICKSPAWN_CHARACTERLIST: []})

        # Force UI update
        context.area.tag_redraw()

        self.report({'INFO'}, "All categories and collections have been cleared.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class CATEGORY_OT_settings(Operator):
    bl_idname = "category.settings"
    bl_label = "Category Settings"
    bl_options = {'INTERNAL'}
    bl_description = "Settings for this category."

    index: IntProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        category = context.scene.category_list[self.index]
        layout.prop(category, "generate_override")

    def execute(self, context):
        return {'FINISHED'}

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
    CATEGORY_OT_settings,
    QUICKSPAWN_OT_clear_everything,
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
        print("Cache created")

    # Register load handler (only if not already registered)
    if load_quickspawn_data not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_quickspawn_data)
        print("Load handler registered")

    print("QuickSpawn addon registered")
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
    for cat_data in cached_categories:
        category = bpy.context.scene.category_list.add()
        category.name = cat_data["name"]
        category.is_expanded = cat_data["is_expanded"]
        category.generate_override = cat_data.get("generate_override", True)  # Default to True if not found
    
    # Load characters
    cached_characters = cache_service.get_cached_character_list()
    for char_data in cached_characters:
        character = bpy.context.scene.character_list.add()
        character.name = char_data["name"]
        character.filepath = char_data["filepath"]
        character.collection = char_data["collection"]
        character.category = char_data["category"]

    print(f"Final counts - Categories: {len(bpy.context.scene.category_list)}, Characters: {len(bpy.context.scene.character_list)}")