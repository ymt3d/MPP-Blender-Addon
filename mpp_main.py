import bpy
import bmesh
from bpy.types import Operator, Menu, Panel
from bpy_extras.view3d_utils import region_2d_to_vector_3d, region_2d_to_origin_3d

def menu_draw_face(self, context):
    layout = self.layout
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.menu(MPP_MT_Menu.bl_idname)

def menu_draw_object(self, context):
    layout = self.layout
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.menu(MPP_MT_Menu.bl_idname)

picked_material = None  

class MPP_OT_Pick(Operator):
    bl_idname = "mpp.pick"
    bl_label = "Material Pick"
    bl_description = "Pick material from object under cursor"

    def invoke(self, context, event):
        global picked_material

        coord = event.mouse_region_x, event.mouse_region_y
        region = context.region
        rv3d = context.region_data

        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)

        result, location, normal, index, obj, matrix = context.scene.ray_cast(context.view_layer.depsgraph, ray_origin, view_vector)

        if obj and obj.type == 'MESH' and index != -1:
            depsgraph = context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            temp_mesh = eval_obj.to_mesh()

            try:
                face = temp_mesh.polygons[index]
                mat_index = face.material_index

                if len(obj.material_slots) > 0 and obj.material_slots[mat_index].material:
                    picked_material = obj.material_slots[mat_index].material
                    self.report({'INFO'}, f"Picked Material: {picked_material.name}")
                else:
                    self.report({'WARNING'}, "No material found")

            except IndexError:
                self.report({'WARNING'}, "Unable to pick material from the mirrored part")

            eval_obj.to_mesh_clear()

        else:
            self.report({'WARNING'}, "No valid selection found")

        return {'FINISHED'}




class MPP_OT_Paste(Operator):
    bl_idname = "mpp.paste"
    bl_label = "Material Paste"
    bl_description = "Paste material to object under cursor or selected objects/faces"

    def invoke(self, context, event):
        global picked_material

        if not picked_material:
            self.report({'WARNING'}, "No material picked")
            return {'CANCELLED'}

        coord = event.mouse_region_x, event.mouse_region_y
        region = context.region
        rv3d = context.region_data

        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)

        result, location, normal, index, obj, matrix = context.scene.ray_cast(context.view_layer.depsgraph, ray_origin, view_vector)

        if obj and obj.type == 'MESH' and index != -1:
            obj.update_from_editmode()
            obj_eval = obj.evaluated_get(context.view_layer.depsgraph)
            face = obj_eval.data.polygons[index]
            mat_index = face.material_index

            if len(obj.material_slots) > 1:
                obj.material_slots[mat_index].material = picked_material
            else:
                obj.material_slots[0].material = picked_material

            self.report({'INFO'}, f"Pasted Material: {picked_material.name}")

            # Add undo push after operation
            bpy.ops.ed.undo_push(message="Paste Material")
        else:
            # If no object is found under the cursor, paste the material to all selected objects or faces in edit mode
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    if obj.mode == 'EDIT':
                        bm = bmesh.from_edit_mesh(obj.data)
                        selected_faces = [f for f in bm.faces if f.select]

                        if not selected_faces:
                            self.report({'WARNING'}, "No faces selected")
                            return {'CANCELLED'}

                        if picked_material.name not in obj.data.materials:
                            obj.data.materials.append(picked_material)

                        mat_index = obj.data.materials.find(picked_material.name)

                        for face in selected_faces:
                            face.material_index = mat_index

                        bmesh.update_edit_mesh(obj.data)

                        self.report({'INFO'}, f"Pasted Material: {picked_material.name} to selected faces")
                    else:
                        if len(obj.material_slots) > 0:
                            obj.material_slots[0].material = picked_material
                        else:
                            obj.data.materials.append(picked_material)

                        self.report({'INFO'}, f"Pasted Material: {picked_material.name} to {obj.name}")

            # Add undo push after operation
            bpy.ops.ed.undo_push(message="Paste Material")

        return {'FINISHED'}



class MPP_MT_Menu(Menu):
    bl_idname = "MPP_MT_Menu"
    bl_label = "Material Pick and Paste"

    def draw(self, context):
        layout = self.layout
        layout.operator(MPP_OT_Pick.bl_idname)
        layout.operator(MPP_OT_Paste.bl_idname) 

classes = [
    MPP_OT_Pick,
    MPP_OT_Paste,
    MPP_MT_Menu,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
