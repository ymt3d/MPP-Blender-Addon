'''
MPP -Material Pick and Paste- 2023 3dnchu
Created by Yamato3d
License : GNU General Public License version3 (http://www.gnu.org/licenses/)
'''

bl_info = {
    "name": "MPP -Material Pick and Paste-",
    "author": "Yamato3D-3dnchu.com",
    "version": (0, 5),
    "blender": (3, 40, 0),
    "location": "View3D > Tool Shelf",
    "description": "Pick and paste materials between objects and faces",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Material"
}

import bpy
from . import mpp_main
from bpy.types import Operator, AddonPreferences
from bpy.props import * 
import rna_keymap_ui

class MPP_AddonPreferences(AddonPreferences):
    bl_idname = __name__

    tab_addon_menu : EnumProperty(name="Tab", description="", items=[('OPTION', "Option", "","DOT",0),('KEYMAP', "Keymap", "","KEYINGSET",1), ('LINK', "Link", "","URL",2)], default='KEYMAP')

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.prop(self, "tab_addon_menu",expand=True)


        if self.tab_addon_menu=="KEYMAP":
            box = layout.box()
            col = box.column()
            col.label(text="Keymap List:",icon="KEYINGSET")

            wm = bpy.context.window_manager
            kc = wm.keyconfigs.user
            old_km_name = ""
            old_id_l = []

            for km_add, kmi_add in addon_keymaps:
                for km_con in kc.keymaps:
                    if km_add.name == km_con.name:
                        km = km_con
                        break

                for kmi_con in km.keymap_items:
                    if kmi_add.idname == kmi_con.idname:

                        if not kmi_con.id in old_id_l:
                            kmi = kmi_con
                            old_id_l.append(kmi_con.id)
                            break
                                                
                try:
                    if not km.name == old_km_name: 
                        col.label(text=str(km.name),icon="DOT")
                    col.context_pointer_set("keymap", km)
                    rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)
                    col.separator()
                    old_km_name = km.name
                except: pass

        if self.tab_addon_menu=="LINK":
            row = layout.row()
            row.label(text="Link:")
            row.operator( "wm.url_open", text="3dnchu.com", icon="URL").url = "https://3dnchu.com"



classes = (
    mpp_main.MPP_MT_Menu,
)

addon_keymaps = []

def register():
    mpp_main.register()

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
	
        km = wm.keyconfigs.addon.keymaps.new(name = '3D View', space_type = 'VIEW_3D')
        kmi = km.keymap_items.new("mpp.pick", 'MIDDLEMOUSE', 'PRESS', alt=True,shift=True,ctrl=False)
        addon_keymaps.append((km, kmi))
	
        km = wm.keyconfigs.addon.keymaps.new(name = '3D View', space_type = 'VIEW_3D')
        kmi = km.keymap_items.new("mpp.paste", 'MIDDLEMOUSE', 'PRESS', alt=True,shift=False,ctrl=True)
        addon_keymaps.append((km, kmi))

    bpy.utils.register_class(MPP_AddonPreferences)

def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    mpp_main.unregister()
    bpy.utils.unregister_class(MPP_AddonPreferences)

if __name__ == "__main__":
    register()


