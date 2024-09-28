bl_info = {
    "name": "QuickSpawn",
    "author": "OctavoPE",
    "version": (0, 0, 1),
    "blender": (3, 3, 0),
    "category": "3D View",
    "description": "Add Collections to quickly spawn them (Append/Link) when needed."
}

import bpy

from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import StringProperty, CollectionProperty, BoolProperty, IntProperty
import os

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
        category = context.scene.category_list.add()
        category.name = self.name
        context.area.tag_redraw()
        return {'FINISHED'}

# are you sure you want to remove category (and characters)?
class CATEGORY_OT_remove_category(Operator):
    bl_idname = "category.remove_category"
    bl_label = "Remove Category"
    
    # index of category to remove, passed in by the ui
    index: IntProperty()

    # only called when user confirms; blender logic handles this. (based on invoke's return value)
    def execute(self, context):
        context.scene.category_list.remove(self.index)
        context.area.tag_redraw()
        return {'FINISHED'}

    # asks user for confirmation
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

# adding character
class CHARACTER_OT_add_character(Operator):
    bl_idname = "character.add_character"
    bl_label = "Add Character"
    
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
        character = context.scene.character_list.add()
        character.name = os.path.basename(self.filepath)
        character.filepath = self.directory
        character.collection = self.filename
        character.category = self.category
        # forces ui update: WITHOUT THIS, UI DOESNT UPDATE UNTIL YOU MOVE YOUR MOUSE
        context.area.tag_redraw()
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
    bl_label = "Remove Character"
    
    index: IntProperty()

    def execute(self, context):
        context.scene.character_list.remove(self.index)
        context.area.tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self,event)

# handles importing; including pop up to pick action
class CHARACTER_OT_import_character(Operator):
    bl_idname = "character.import_character"
    bl_label = "Import Character"
    bl_options = {'INTERNAL'}

    index: bpy.props.IntProperty()
    action: bpy.props.EnumProperty(
        items=[
            ('APPEND', "Append", "Append the character to the scene"),
            ('LINK', "Link", "Link the character to the scene"),
        ],
        name="Action",
        description="Choose whether to append or link the character",
        default='APPEND'
    )

    # prompts the user if they want append or link, then does action
    def execute(self, context):
        character = context.scene.character_list[self.index]
        
        if self.action == 'APPEND':
        # USER SELECTED TO APPEND THE CHARACTER
            bpy.ops.wm.append(filename=character.collection, directory=character.filepath)   
            self.report({'INFO'}, f"Appended character: {character.name} full path: {character.filepath} collection name: {character.collection}")
        else:
        # USER SELECTED TO LINK THE CHARACTER
            self.report({'WARNING'}, "Link functionality not implemented yet")
        
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "action", expand=True)

# drop down control thx cgpt
class CATEGORY_OT_toggle_expand(Operator):
    bl_idname = "category.toggle_expand"
    bl_label = "Toggle Category Expand"
    
    index: IntProperty()

    def execute(self, context):
        category = context.scene.category_list[self.index]
        category.is_expanded = not category.is_expanded
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
        row.operator("category.add_category", text="Add Category")
        
        for catNum, category in enumerate(scene.category_list):
            box = layout.box()
            row = box.row()
            # do we want different icons for categories?
            expand_ico = 'TRIA_DOWN' if category.is_expanded else 'TRIA_RIGHT'
            row.operator("category.toggle_expand", text="", icon=expand_ico, emboss=False).index = catNum # pass in index of category to toggle to the operator
            row.label(text=category.name)
            row.operator("category.remove_category", text="", icon='X').index = catNum # pass in index of category to remove to the operator
            
            # only when extended?
            if category.is_expanded:
                row = box.row()
                op = row.operator("character.add_character", text="Add Character")
                op.category = category.name
                
                sorted_characters = sorted(
                    [char for char in scene.character_list if char.category == category.name],
                    key=lambda x: x.collection.lower() # put in alphabetical order, thanks cgpt
                )
                
                for character in sorted_characters:
                    row = box.row()
                    op = row.operator("character.import_character", text=character.collection)
                    # find that char and import them
                    op.index = scene.character_list.find(character.name)
                    row.operator("character.remove_character", text="", icon='X').index = scene.character_list.find(character.name) # pass in index of character to remove to the operator


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

# done whenever add on is installed
def register():
    for clas in classes:
        bpy.utils.register_class(clas)

    # list of characters and categories
    bpy.types.Scene.character_list = CollectionProperty(type=CHARACTER_PG_character)
    bpy.types.Scene.category_list = CollectionProperty(type=CATEGORY_PG_category)

# done whenever removing addon
def unregister():
    del bpy.types.Scene.character_list
    del bpy.types.Scene.category_list

    for clas in reversed(classes):
        bpy.utils.unregister_class(clas)

if __name__ == "__main__":
    register()