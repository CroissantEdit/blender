# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest

import bpy
from bl_operators import uvcalc_lightmap


class TestLightmapPack(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.objects = []
        for k in range(6):
            n = 3 + k
            size = 1.0 + 0.5 * k
            vertices = [(size * i / n, size * j / n, 0.0)
                        for j in range(n + 1) for i in range(n + 1)]
            faces = [(j * (n + 1) + i, j * (n + 1) + i + 1,
                      (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i)
                     for j in range(n) for i in range(n)]
            mesh = bpy.data.meshes.new("Grid{:d}".format(k))
            mesh.from_pydata(vertices, [], faces)
            mesh.uv_layers.new()
            obj = bpy.data.objects.new(mesh.name, mesh)
            bpy.context.scene.collection.objects.link(obj)
            obj.select_set(True)
            self.objects.append(obj)
        bpy.context.view_layer.objects.active = self.objects[0]

    def tearDown(self):
        if bpy.context.object and bpy.context.object.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

    def uv_coordinates(self):
        return tuple(tuple(tuple(uv.uv) for uv in obj.data.uv_layers.active.data)
                     for obj in self.objects)

    def pack_reference(self, meshes, selected_only=False):
        # Match the operator's binary-exact margin of 0.125 percent.
        uvcalc_lightmap.lightmap_uvpack(
            meshes,
            PREF_SEL_ONLY=selected_only,
            PREF_NEW_UVLAYER=False,
            PREF_PACK_IN_ONE=True,
            PREF_BOX_DIV=12,
            PREF_MARGIN_DIV=800,
        )
        return self.uv_coordinates()

    def test_selection_order(self):
        references = []
        for objects in (self.objects, self.objects[::-1]):
            with self.subTest(order=[obj.name for obj in objects]):
                expected = self.pack_reference([obj.data for obj in objects])
                references.append(expected)
                with bpy.context.temp_override(selected_objects=objects):
                    result = bpy.ops.uv.lightmap_pack(PREF_PACK_IN_ONE=True, PREF_MARGIN_DIV=0.125)
                self.assertEqual(result, {'FINISHED'})
                self.assertEqual(bpy.context.object.mode, 'OBJECT')
                self.assertTrue(self.uv_coordinates() == expected, "UVs differ from ordered packing")
        # Ensure the fixture detects changes to the order of the packed meshes.
        self.assertTrue(references[0] != references[1], "Fixture must detect mesh order changes")

    def test_shared_mesh_data(self):
        shared = bpy.data.objects.new("Shared", self.objects[0].data)
        empty_mesh = bpy.data.meshes.new("EmptyMesh")
        empty_object = bpy.data.objects.new("EmptyMesh", empty_mesh)
        non_mesh = bpy.data.objects.new("Empty", None)
        for obj in (shared, empty_object, non_mesh):
            bpy.context.scene.collection.objects.link(obj)
            obj.select_set(True)

        result = bpy.ops.uv.lightmap_pack(
            PREF_NEW_UVLAYER=True, PREF_PACK_IN_ONE=True, PREF_MARGIN_DIV=0.125,
        )

        self.assertEqual(result, {'FINISHED'})
        for obj in self.objects:
            self.assertEqual(len(obj.data.uv_layers), 2)
        self.assertEqual(len(empty_mesh.uv_layers), 0)

    def test_edit_mode(self):
        import bmesh

        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        for obj in self.objects:
            bm = bmesh.from_edit_mesh(obj.data)
            for i, face in enumerate(bm.faces):
                face.select_set(i % 2 == 0)
            bmesh.update_edit_mesh(obj.data)
        meshes = [obj.data for obj in bpy.context.objects_in_mode_unique_data]
        bpy.ops.object.mode_set(mode='OBJECT')

        for selection in ('SEL_FACES', 'ALL_FACES'):
            with self.subTest(selection=selection):
                expected = self.pack_reference(meshes, selected_only=selection == 'SEL_FACES')
                bpy.ops.object.mode_set(mode='EDIT')
                result = bpy.ops.uv.lightmap_pack(
                    PREF_CONTEXT=selection, PREF_PACK_IN_ONE=True, PREF_MARGIN_DIV=0.125,
                )
                self.assertEqual(result, {'FINISHED'})
                self.assertEqual(bpy.context.object.mode, 'EDIT')
                bpy.ops.object.mode_set(mode='OBJECT')
                self.assertTrue(self.uv_coordinates() == expected, "UVs differ from ordered packing")


if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()
