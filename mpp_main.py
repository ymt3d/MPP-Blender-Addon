import bpy
import bmesh
import blf
import bgl
import gpu
from bpy.types import Operator, Menu, Panel
from bpy_extras.view3d_utils import region_2d_to_vector_3d, region_2d_to_origin_3d
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils

picked_material = None
global_display_handle = None
global_display_timer = None

#Text----------------------------

class TextDisplay:
    def __init__(self, x, y, text, offset_x=0, offset_y=0):  
        self.x = x
        self.y = y + 10
        self.text = text
        self.offset_x = offset_x
        self.offset_y = offset_y
        self._handle = None

    def draw(self, context):
        font_id = 0
        dpi = 72
        font_size = 20
        shadow_offset_x = 2
        shadow_offset_y = -2
        shadow_alpha = 0.5

        # Text shadow
        blf.color(font_id, 0, 0, 0, shadow_alpha)
        blf.position(font_id, self.x + shadow_offset_x, self.y + shadow_offset_y, 0)
        blf.size(font_id, font_size, dpi)
        blf.draw(font_id, self.text)

        # Text body
        blf.color(font_id, 1, 1, 1, 1)
        blf.position(font_id, self.x, self.y, 0)
        blf.size(font_id, font_size, dpi)
        blf.draw(font_id, self.text)

        # Draw the outline (black)
        blf.enable(font_id, blf.SHADOW)
        blf.shadow(font_id, 3, 0.0, 0.0, 0.0, 1.0)
        blf.shadow_offset(font_id, 1, -1)
        blf.draw(font_id, self.text)
        blf.disable(font_id, blf.SHADOW)
        
    def remove_handler(self, context):
        if hasattr(self, '_handle') and self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None

    def remove(self, context):
        global global_display_handle
        if hasattr(self, '_handle') and self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
            global_display_handle = None

#MaterialPreview----------------------------
class MPP_OT_MaterialPreview(bpy.types.Operator):
    bl_idname = "mpp.material_preview"
    bl_label = "Material Preview"
    bl_options = {'REGISTER'}

    def check(self, context):
        return True
    
    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=150)  

    def draw(self, context):
        layout = self.layout
        if globals().get('picked_material', None):
            layout.template_preview(globals().get('picked_material'), show_buttons=False)  

#Pick----------------------------
class MPP_OT_Pick(Operator):
    bl_idname = "mpp.pick"
    bl_label = "Material Pick"
    bl_description = "Pick material from object under cursor"

    def __init__(self):
        self._handle = None
        self.display_timer = None

    def modal(self, context, event):
        global global_display_handle
        global global_display_timer

        if event.type == 'TIMER':
            try:
                if self._handle is not None:  
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                    self._handle = None
                    global_display_handle = None  
            except ValueError:
                pass  

            self.text_display.remove_handler(context)
            context.window_manager.event_timer_remove(self.display_timer)
            context.area.tag_redraw()
            global_display_timer = None
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global picked_material
        global global_display_handle
        global global_display_timer

        if global_display_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(global_display_handle, 'WINDOW')
            global_display_handle = None
        if global_display_timer is not None:
            context.window_manager.event_timer_remove(global_display_timer)
            global_display_timer = None

        # Save the current selection and active object
        selected_objects = context.selected_objects.copy()
        active_object = context.view_layer.objects.active

        # Save the current mode if the active object is not a mesh
        current_mode = None
        if active_object:
            current_mode = active_object.mode
            if active_object.type != 'MESH' or active_object.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='OBJECT')

        # Deselect all objects and clear active object
        if current_mode != 'EDIT':
            bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = None

        coord = event.mouse_region_x, event.mouse_region_y
        region = context.region
        rv3d = context.region_data

        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)

        result, location, normal, index, obj, matrix = context.scene.ray_cast(context.view_layer.depsgraph, ray_origin, view_vector)

        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')

        picked_material = None
        
        if obj:
            depsgraph = context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            temp_mesh = eval_obj.to_mesh()

            try:
                face = temp_mesh.polygons[index]
                mat_index = face.material_index

                if len(obj.material_slots) > 0 and obj.material_slots[mat_index].material:
                    picked_material = obj.material_slots[mat_index].material
            except IndexError:
                pass

        # Restore the previous selection and active object
        for obj in selected_objects:
            obj.select_set(True)
        context.view_layer.objects.active = active_object

        # If the active object was in edit mode, restore the mode
        if current_mode:
            bpy.ops.object.mode_set(mode=current_mode)

        if picked_material:
            self.report({'INFO'}, f"Picked Material: {picked_material.name}")

            self.text_display = TextDisplay(event.mouse_region_x, event.mouse_region_y, f"Pick: {picked_material.name}")
            self._handle = bpy.types.SpaceView3D.draw_handler_add(self.text_display.draw, (context,), 'WINDOW', 'POST_PIXEL')
            
            self.display_timer = context.window_manager.event_timer_add(1.0, window=context.window)
            context.window_manager.modal_handler_add(self)

        context.area.tag_redraw()

        if self._handle is not None:
            global_display_handle = self._handle
        if self.display_timer is not None:
            global_display_timer = self.display_timer

        return {'RUNNING_MODAL'}


def paste_material_to_edit_mode_object(obj, picked_material):
    bm = bmesh.from_edit_mesh(obj.data)
    selected_faces = [f for f in bm.faces if f.select]

    if not selected_faces:
        return False

    if picked_material.name not in obj.data.materials:
        obj.data.materials.append(picked_material)

    mat_index = obj.data.materials.find(picked_material.name)

    for face in selected_faces:
        face.material_index = mat_index

    bmesh.update_edit_mesh(obj.data)
    return True

# テキストの表示条件をチェックする関数
def should_display_text(selected_objects, mouse_x, mouse_y):
    # マウス直下にオブジェクトが存在する場合は表示する
    region = bpy.context.region
    rv3d = bpy.context.region_data
    mouse_coord = (mouse_x, mouse_y)
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse_coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse_coord)
    
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()  # Depsgraphオブジェクトを取得
    hit, location, normal, index, object, matrix = scene.ray_cast(depsgraph, ray_origin, view_vector)

    if hit:
        return True

    # 選択されたオブジェクトがない場合は表示しない
    if not selected_objects:
        return False

    return True

#Paste----------------------------
class MPP_OT_Paste(Operator):
    bl_idname = "mpp.paste"
    bl_label = "Material Paste"
    bl_description = "Paste material to object under cursor or selected objects/faces"

    def __init__(self):
        self._handle = None
        self.display_timer = None

    def modal(self, context, event):
        global global_display_handle

        context.area.tag_redraw()

        if event.type == 'TIMER':
            try:
                if self._handle is not None:
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                    self._handle = None
                    global_display_handle = None
            except ValueError:
                pass  
            context.window_manager.event_timer_remove(self.display_timer)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global picked_material
        global global_display_handle
        global global_display_timer

        if global_display_handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(global_display_handle, 'WINDOW')
            except ValueError:
                pass  
            global_display_handle = None

        if global_display_timer is not None:
            context.window_manager.event_timer_remove(global_display_timer)
            global_display_timer = None

        if not picked_material:
            self.report({'WARNING'}, "No material picked")
            return {'CANCELLED'}

        # 現在の選択状態とアクティブオブジェクトを保存
        selected_objects = context.selected_objects.copy()
        active_object = context.view_layer.objects.active

        # アクティブオブジェクトがメッシュでない場合は、現在のモードを保存
        current_mode = None
        if active_object:
            current_mode = active_object.mode
            if active_object.type != 'MESH' or active_object.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='OBJECT')

        # 全オブジェクトの選択を解除し、アクティブオブジェクトをクリア
        if current_mode != 'EDIT':
            bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = None

        coord = event.mouse_region_x, event.mouse_region_y
        region = context.region
        rv3d = context.region_data

        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)

        # カーソル位置のオブジェクトと面の情報を取得
        result, location, normal, index, obj, matrix = context.scene.ray_cast(context.view_layer.depsgraph, ray_origin, view_vector)

        if obj and index != -1:
            if obj.type == 'MESH':
                if obj.mode == 'EDIT':
                    # メッシュオブジェクトの編集モードにマテリアルを貼り付ける
                    if paste_material_to_edit_mode_object(obj, picked_material):
                        self.report({'INFO'}, f"Pasted Material: {picked_material.name} to selected faces")
                    else:
                        bm = bmesh.from_edit_mesh(obj.data)
                        face = bm.faces[index]
                        mat_index = face.material_index

                        if len(obj.material_slots) > 1:
                            obj.material_slots[mat_index].material = picked_material
                        else:
                            if len(obj.material_slots) == 0:
                                obj.data.materials.append(None)
                            obj.material_slots[0].material = picked_material

                        self.report({'INFO'}, f"Pasted Material: {picked_material.name}")
                else:
                    # メッシュオブジェクトの編集モードでない場合にマテリアルを貼り付ける
                    obj.update_from_editmode()
                    obj_eval = obj.evaluated_get(context.view_layer.depsgraph)
                    face = obj_eval.data.polygons[index]
                    mat_index = face.material_index

                    if len(obj.material_slots) > 1:
                        obj.material_slots[mat_index].material = picked_material
                    else:
                        if len(obj.material_slots) == 0:
                            obj.data.materials.append(None)
                        obj.material_slots[0].material = picked_material

                    self.report({'INFO'}, f"Pasted Material: {picked_material.name}")

            elif obj.type in ['CURVE', 'FONT', 'SURFACE', 'META']:
                # メッシュ以外のオブジェクトにマテリアルを貼り付けるため一時的にメッシュに変換
                depsgraph = context.evaluated_depsgraph_get()
                temp_obj = obj.evaluated_get(depsgraph)
                temp_mesh = temp_obj.to_mesh()

                face = temp_mesh.polygons[index]
                mat_index = face.material_index

                temp_obj.to_mesh_clear()

                if len(obj.material_slots) > mat_index:
                    obj.material_slots[mat_index].material = picked_material
                else:
                    obj.data.materials.append(picked_material)
                self.report({'INFO'}, f"Pasted Material: {picked_material.name}")

            bpy.ops.ed.undo_push(message="Paste Material")
        else:
            # カーソル位置にオブジェクトがない場合、選択された全オブジェクトにマテリアルを貼り付ける
            for obj in selected_objects:
                if obj.type in ['MESH', 'CURVE', 'FONT', 'SURFACE', 'META']:
                    if obj.type == 'MESH' and obj.mode == 'EDIT':
                        # メッシュオブジェクトの編集モードにマテリアルを貼り付ける
                        if paste_material_to_edit_mode_object(obj, picked_material):
                            self.report({'INFO'}, f"Pasted Material: {picked_material.name} to selected faces")
                        else:
                            self.report({'WARNING'}, "No faces selected")
                            return {'CANCELLED'}
                    else:
                        # メッシュオブジェクトの編集モードでない場合にマテリアルを貼り付ける
                        if len(obj.material_slots) > 0:
                            obj.material_slots[0].material = picked_material
                        else:
                            obj.data.materials.append(picked_material)

                        self.report({'INFO'}, f"Pasted Material: {picked_material.name} to {obj.name}")

            bpy.ops.ed.undo_push(message="Paste Material")

        # 選択状態とアクティブオブジェクトを復元
        for obj in selected_objects:
            obj.select_set(True)
        context.view_layer.objects.active = active_object

        # アクティブオブジェクトが編集モードだった場合、モードを復元
        if current_mode:
            bpy.ops.object.mode_set(mode=current_mode)
        
        if should_display_text(selected_objects, event.mouse_region_x, event.mouse_region_y):
            # テキストの表示
            self.text_display = TextDisplay(event.mouse_region_x, event.mouse_region_y, f"Paste: {picked_material.name}")
            self._handle = bpy.types.SpaceView3D.draw_handler_add(self.text_display.draw, (context,), 'WINDOW', 'POST_PIXEL')
            self.display_timer = context.window_manager.event_timer_add(1, window=context.window)
            context.window_manager.modal_handler_add(self)

        if self._handle is not None:
            global_display_handle = self._handle
        if self.display_timer is not None:
            global_display_timer = self.display_timer

        return {'RUNNING_MODAL'}


class MPP_MT_Menu(Menu):
    bl_idname = "MPP_MT_Menu"
    bl_label = "Material Pick and Paste"

    def draw(self, context):
        layout = self.layout
        layout.operator(MPP_OT_Pick.bl_idname)
        layout.operator(MPP_OT_Paste.bl_idname) 

classes = [
    MPP_OT_MaterialPreview,
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
