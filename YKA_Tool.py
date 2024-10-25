bl_info = {
    "name": "YKA Tool",
    "blender": (3, 6, 0),
    "category": "Animation",
    "author": "WCG847",
    "version": (4, 9, 1, 2),  # Major, Minor, Small Fixes, Non-Essential Fixes
    "location": "File > Export > Yuke's Keyframe Animation (.yka)",
    "description": "Export Scene Data to YKA format. Import YKA animations in addition to YMKs containers.",
    "warning": "Pre-Alpha",
    "wiki_url": "http://WCG847.weebly.com",
    "support": "TESTING",
}

import bpy  # type: ignore
import struct

# According to Kendrick. Find out what D1-FF represents. Kendrick claims these are environmental sounds.

sound_id_list = [
    ("195", "C3 = No Sound", "No Sound"),
    ("196", "C4 = Slap", "Slap Sound"),
    ("197", "C5 = Strike Punch", "Strike Punch Sound"),
    ("198", "C6 = Punch/Kick", "Punch/Kick Sound"),
    ("199", "C7 = UNK1", "UNK1"),
    ("200", "C8 = UNK2", "UNK2"),
    ("201", "C9 = UNK3", "UNK3"),
    ("202", "CA = Strong Kick", "Strong Kick Sound"),
    ("203", "CB = Aerial Miss Slam", "Fall or Miss Aerial Move"),
    ("204", "CC = Forceful Slam onto Canvas", "Forceful Slam onto Canvas"),
    ("205", "CD = Same as CC", "Same as CC"),
    ("206", "CE = Same as CB", "Same as CB"),
    ("207", "CF = Same as CB", "Same as CB"),
    ("208", "D0 = Forceful Slam 2", "Forceful Slam 2"),
]
# Hand Gestures, Facial Expressions. Placeholder
sprite_marker_list = [
    ("0", "None", "No Sprite"),
    ("1", "Sprite 1", "Example Sprite 1"),
]


class YKAFrameMarkers(bpy.types.PropertyGroup):
    frame: bpy.props.IntProperty(name="Frame", description="Frame number for this marker")  # type: ignore
    sound_marker: bpy.props.EnumProperty(name="Sound Marker", description="Sound Marker", items=sound_id_list)  # type: ignore
    sprite_marker: bpy.props.EnumProperty(name="Sprite Marker", description="Sprite Marker", items=sprite_marker_list)  # type: ignore


class YKAExporter(bpy.types.Operator):
    bl_idname = "export_scene.yka"
    bl_label = "Export Yuke's Keyframe Animation (.yka)"
    bl_options = {"PRESET"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="")  # type: ignore

    def execute(self, context):
        if not self.filepath or not self.filepath.endswith(".yka"):
            self.report(
                {"ERROR"},
                "Filepath not set or invalid extension, set a valid .yka file path",
            )
            return {"CANCELLED"}

        return self.export_yka(context)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def calculate_global_root_position(self, armature_obj, root_bone):
        # Calculates the global position of the root bone in Blender's world space, ensuring proper scaling for the Yuke's PSX format.
        armature_world_matrix = armature_obj.matrix_world
        root_bone_matrix = root_bone.matrix
        global_root_position = armature_world_matrix @ root_bone_matrix.to_translation()

        # Scaling factor to map Blender's coordinates into Yuke's PSX format.
        # Potentially adjust this based on the expected unit system in the game (WIP).
        scale_factor = (
            100.0  # For now, let's assume Blender uses meters, and PSX uses centimeters
        )

        global_root_position.x *= scale_factor
        global_root_position.y *= scale_factor
        global_root_position.z *= scale_factor

        return global_root_position

    def export_yka(self, context):
        scene = context.scene
        objects = scene.objects

        try:
            with open(self.filepath, "wb") as file:
                current_frame = scene.frame_current

                for obj in objects:
                    if obj.hide_viewport or obj.hide_render:
                        continue

                    if obj.type == "ARMATURE":
                        bones = obj.pose.bones
                        root_bone = self.get_root_bone(bones)

                        if root_bone:
                            for frame in range(scene.frame_start, scene.frame_end + 1):
                                scene.frame_set(frame)
                                root_pos = self.calculate_global_root_position(
                                    obj, root_bone
                                )
                                self.export_frame(obj, root_pos, file, frame, scene)

                    elif obj.type == "CAMERA":
                        # Estimation
                        for frame in range(scene.frame_start, scene.frame_end + 1):
                            scene.frame_set(frame)
                            self.export_frame(obj, None, file, frame, scene)

                    elif obj.type == "LIGHT":
                        # Estimation
                        for frame in range(scene.frame_start, scene.frame_end + 1):
                            scene.frame_set(frame)
                            self.export_frame(obj, None, file, frame, scene)

                scene.frame_set(current_frame)

            self.report(
                {"INFO"}, f"Yuke's Keyframe Animation exported to {self.filepath}"
            )
            return {"FINISHED"}

        except FileNotFoundError:
            self.report(
                {"ERROR"}, "Invalid filepath. Please check if the directory exists."
            )
            return {"CANCELLED"}

    def export_bone_hierarchy(self, bone, file, dynamic_precision):
        rot_data = self.pack_rotational_data(bone, dynamic_precision)
        file.write(rot_data)

        for child_bone in bone.children:
            self.export_bone_hierarchy(child_bone, file, dynamic_precision)

    def get_root_bone(self, bones):
        for bone in bones:
            if bone.parent is None:
                return bone
        return None

    def export_frame(self, obj, root_pos, file, frame, scene):
        # Exports a frame of positional data for the root bone, applying transformations based on Blender's world-space changes and dynamically adjusting Yuke's reference position.
        if obj.type == "ARMATURE":
            bones = obj.pose.bones
            if not bones:
                self.report({"WARNING"}, f"No bones found in armature: {obj.name}")
                return

            num_joints = 0
            dynamic_scale, positional_data_size = self.calculate_dynamic_scale_and_size(
                root_pos
            )

            # Add positional data size to num_joints (to include X, Y, Z)
            num_joints += positional_data_size

            for bone in bones:
                num_joints += (
                    3  # 3 bytes per bone for rotational data (yaw, pitch, roll)
                )

            flag_data, flag_size = self.pack_frame_flags(frame, scene)
            sprite_data, sound_data = self.get_sprite_and_sound_markers(frame, scene)
            additional_data_size = flag_size + len(sprite_data) + len(sound_data)

            num_joints += additional_data_size
            frame_size = num_joints + 1  # Add 1 byte for frame header

            if frame_size > 255:
                self.handle_frame_overflow(
                    frame_size,
                    num_joints,
                    root_pos,
                    bones,
                    file,
                    dynamic_scale,
                    frame,
                    scene,
                )
            else:
                # Write the adjusted frame data
                self.write_frame_data(
                    file,
                    frame_size,
                    num_joints,
                    root_pos,
                    bones,
                    dynamic_scale,
                    frame,
                    scene,
                    flag_data,
                    sprite_data,
                    sound_data,
                )

        # Camera and Lights are placeholders. needs precise logic that the game expects.
        elif obj.type == "CAMERA":
            dynamic_precision = 255
            num_joints = 6 + 6  # 6 bytes for position, 6 bytes for rotation
            flag_data, flag_size = self.pack_frame_flags(frame, scene)
            num_joints += flag_size
            frame_size = num_joints + 1

            camera_data = self.pack_camera_data(obj, frame, scene)
            file.write(
                struct.pack("B", 0x80 + frame_size)
            )  # Yuke's for some reason adds 0x80 to the actual frame length.
            file.write(struct.pack("B", num_joints))
            file.write(camera_data)
            file.write(flag_data)
            file.write(b"\x00" * 2)

        elif obj.type == "LIGHT":
            dynamic_precision = 255
            num_joints = (
                6 + 6 + 4
            )  # 6 bytes for position, 6 bytes for rotation, 4 bytes for intensity. Intensity isnt fully confirmed.
            flag_data, flag_size = self.pack_frame_flags(frame, scene)
            num_joints += flag_size
            frame_size = num_joints + 1

            light_data = self.pack_light_data(obj, frame, scene)
            file.write(struct.pack("B", 0x80 + frame_size))
            file.write(struct.pack("B", num_joints))
            file.write(light_data)
            file.write(flag_data)
            file.write(b"\x00" * 2)

    def calculate_precision(self, frame, scene, root_position):
        # Calculate the range of motion for the root bone
        max_range = max(
            abs(root_position.x), abs(root_position.y), abs(root_position.z)
        )

        # Dynamically adjust precision based on range of motion
        if max_range > 1.0:
            precision = 128  # Larger movements get lower precision to avoid overflow
        elif max_range > 0.01:
            precision = 255 / (
                max_range + 0.001
            )  # Scale precision for smaller movements
        else:
            precision = 512  # Ensure small movements get higher precision

        # Cap precision to 255 to avoid exceeding 0xFF
        precision = min(precision, 255)

        print(
            f"Frame: {frame}, Dynamic Precision (based on root position): {precision}"
        )
        return precision

    # Pack Conditional Flags based on markers set in the frame
    def pack_frame_flags(self, frame, scene):
        # Check if any YKA markers are assigned to the current frame
        markers = [m for m in scene.yka_markers if m.frame == frame]

        if markers:
            # If markers exist, pack a flag byte with a size of 1 byte
            return struct.pack("B", 0x02), 1  # Example: '0x02' could be a flag byte
        else:
            # If no markers are present, return an empty byte and size of 0
            return b"", 0

    def get_sprite_and_sound_markers(self, frame, scene):
        markers = [m for m in scene.yka_markers if m.frame == frame]
        if markers:
            marker = markers[0]
            sound_data = struct.pack("B", int(marker.sound_marker))
            sprite_data = struct.pack("B", int(marker.sprite_marker))
        else:
            sound_data = b""  # No data
            sprite_data = b""  # No Data
        return sprite_data, sound_data

    def calculate_dynamic_scale_and_size(self, location):
        # Dynamically calculates a scale factor and the number of bytes required to representeach positional component (X, Y, Z) individually, resulting in a total size between 6 and 12 bytes.
        max_abs_value = max(abs(location.x), abs(location.y), abs(location.z))

        # If max_abs_value is zero or close to zero, return a scale factor of 1 to avoid division by zero
        if max_abs_value < 0.0001:
            return 1.0, 6  # Default to 6 bytes for small/no motion

        # Calculate scale factor to map values into the range of -255 to 255
        scale_factor = 255 / max_abs_value

        # Determine how many bytes are needed for each axis based on scaled values
        def calculate_bytes_needed(value, scale_factor):
            scaled_value = abs(value * scale_factor)
            if scaled_value > 100:  # Large motion, needs 4 bytes
                return 4
            elif scaled_value > 10:  # Moderate motion, needs 3 bytes
                return 3
            elif scaled_value > 1:  # Small motion, needs 2 bytes
                return 2
            else:  # Very small motion, needs 1 byte
                return 1

        # Calculate bytes needed for X, Y, Z individually
        x_bytes = calculate_bytes_needed(location.x, scale_factor)
        y_bytes = calculate_bytes_needed(location.y, scale_factor)
        z_bytes = calculate_bytes_needed(location.z, scale_factor)

        # Total bytes for positional data is the sum of bytes needed for each axis
        total_positional_bytes = x_bytes + y_bytes + z_bytes

        return scale_factor, total_positional_bytes

    def pack_positional_data(self, location, scale_factor, positional_data_size):
        # Packs positional data for the root bone using reference positional bytes from Yuke's as a baseline, since we do not have precise coordinates thanks to them baking transformations. Dynamically adjusting based on Blender's frame-by-frame transformations.
        # Yuke's Reference
        yuke_reference = [0x66, 0x30, 0xB0, 0xE7, 0x0D, 0x05]

        def quantise_pos(value, reference_value):
            # Quantises positional value based on the scale factor, using Yuke's known reference positional data as a starting point. Applies the transformation based on Blender's frame data.
            # Apply scaling to the positional value
            scaled_value = value * scale_factor

            # Dynamically adjust the reference value based on the scaled transformation
            quantised_value = int(scaled_value) + reference_value

            # Make sure the quantized value is within UINT8 bounds (0-255)
            quantised_value = max(0, min(quantised_value, 255))

            return quantised_value

        # Adjust X, Y, Z positional values based on Yuke's reference bytes
        x_quantised = quantise_pos(location.x, yuke_reference[0])
        y_quantised = quantise_pos(
            location.y, yuke_reference[2]
        )  # Using appropriate Yuke's byte for Y axis
        z_quantised = quantise_pos(
            location.z, yuke_reference[4]
        )  # Using appropriate Yuke's byte for Z axis

        # Pack positional data based on the byte size (6 bytes)
        return struct.pack(
            "BBBBBB",
            x_quantised,
            yuke_reference[1],
            y_quantised,
            yuke_reference[3],
            z_quantised,
            yuke_reference[5],
        )

    def pack_rotational_data(self, pose_bone, precision):
        # Packs rotational data as yaw, pitch, and roll, scaled based on precision.
        euler = pose_bone.rotation_euler
        if pose_bone.rotation_mode == "QUATERNION":  # Converts Quanternions to Euler.
            euler = pose_bone.rotation_quaternion.to_euler()

        # Radians to Degrees
        yaw_deg = euler.z * (180.0 / 3.14159)
        pitch_deg = euler.x * (180.0 / 3.14159)
        roll_deg = euler.y * (180.0 / 3.14159)
        # Normalises degrees from 0-180 to 0-127. Rotations seem to be signed integers, as changing values to 0xFF result in backwards, which is something that happens whem the angle goes '-1'
        yaw = int(((yaw_deg / 180.0) * 127.0))
        pitch = int(((pitch_deg / 180.0) * 127.0))
        roll = int(((roll_deg / 180.0) * 127.0))
        yaw = max(-128, min(127, yaw))
        pitch = max(-128, min(127, pitch))
        roll = max(-128, min(127, roll))
        return struct.pack("bbb", yaw, pitch, roll)  # Packs as signed integers

    def handle_frame_overflow(
        self,
        frame_size,
        num_joints,
        root_pos,
        bones,
        file,
        dynamic_precision,
        frame,
        scene,
    ):
        # Handle frame overflow by splitting it into sub-frames
        remaining_frame_size = frame_size
        while remaining_frame_size > 255:
            sub_frame_size = min(remaining_frame_size, 255)
            self.write_sub_frame(
                file,
                sub_frame_size,
                num_joints,
                root_pos,
                bones,
                dynamic_precision,
                frame,
                scene,
            )
            remaining_frame_size -= sub_frame_size

    def write_sub_frame(
        self,
        file,
        frame_size,
        num_joints,
        root_pos,
        bones,
        dynamic_precision,
        frame,
        scene,
    ):
        # Write the sub-frame data similar to a full frame, but smaller chunks
        file.write(
            struct.pack("B", 0x80 + frame_size)
        )  # Yukes adds 0x80 to frame length for some reason
        file.write(struct.pack("B", 0x10 + num_joints))

        # Write positional data (root position) if applicable
        if root_pos:
            pos_data = self.pack_positional_data(root_pos, dynamic_precision)
            file.write(pos_data)
        else:
            file.write(b"\x00" * 6)

        # Write bone hierarchy
        for bone in bones:
            if bone.parent is None:
                self.export_bone_hierarchy(bone, file, dynamic_precision)

        # Add placeholder byte and any additional marker data (sprite/sound)
        file.write(struct.pack("B", 0x10))  # Placeholder for frame interpolation
        flag_data, flag_size = self.pack_frame_flags(frame, scene)
        file.write(flag_data)
        sprite_data, sound_data = self.get_sprite_and_sound_markers(frame, scene)

        if sprite_data:
            file.write(sprite_data)
        if sound_data:
            file.write(sound_data)

    def write_frame_data(
        self,
        file,
        frame_size,
        num_joints,
        root_pos,
        bones,
        dynamic_precision,
        frame,
        scene,
        flag_data,
        sprite_data,
        sound_data,
    ):
        # Writes frame data to the YKA file, handling sub-frames if the frame size exceeds 255 bytes and packing positional data with dynamically calculated precision.
        file.write(struct.pack("B", 0x80 + frame_size))  # Frame size
        file.write(struct.pack("B", 0x10 + num_joints))  # Number of joints

        # Write positional data (root position) if applicable
        if root_pos:
            # Calculate the dynamic scale and positional data size for the root position
            dynamic_scale, positional_data_size = self.calculate_dynamic_scale_and_size(
                root_pos
            )

            # Now call pack_positional_data with the correct arguments
            pos_data = self.pack_positional_data(
                root_pos, dynamic_scale, positional_data_size
            )
            file.write(pos_data)
        else:
            file.write(b"\x00" * 6)  # Default if no positional data

        # Write bone hierarchy
        for bone in bones:
            if bone.parent is None:
                self.export_bone_hierarchy(bone, file, dynamic_precision)

        # Add placeholder byte and any additional marker data (sprite/sound)
        file.write(struct.pack("B", 0x10))  # Placeholder for frame interpolation
        if flag_data:
            file.write(flag_data)
        if sprite_data:
            file.write(sprite_data)
        if sound_data:
            file.write(sound_data)


class YKA_PT_MarkersPanel(bpy.types.Panel):
    bl_label = "YKA Markers"
    bl_idname = "YKA_PT_markers_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "YKA Markers"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Markers:")

        layout.operator("yka.add_marker", text="Add Marker to Keyframe")
        layout.operator("yka.remove_marker", text="Remove Marker from Keyframe")

        row = layout.row()
        row.template_list(
            "UI_UL_list",
            "yka_markers",
            context.scene,
            "yka_markers",
            context.scene,
            "yka_markers_index",
        )


class YKA_OT_AddMarker(bpy.types.Operator):
    bl_idname = "yka.add_marker"
    bl_label = "Add YKA Marker"

    def execute(self, context):
        scene = context.scene
        frame = scene.frame_current

        existing_marker = next((m for m in scene.yka_markers if m.frame == frame), None)
        if existing_marker:
            self.report({"WARNING"}, f"Marker already exists for frame {frame}")
            return {"CANCELLED"}

        marker = scene.yka_markers.add()
        marker.frame = frame
        marker.sound_marker = "195"
        marker.sprite_marker = "0"

        return {"FINISHED"}


class YKA_OT_RemoveMarker(bpy.types.Operator):
    bl_idname = "yka.remove_marker"
    bl_label = "Remove YKA Marker"

    def execute(self, context):
        scene = context.scene
        frame = scene.frame_current

        for i, marker in enumerate(scene.yka_markers):
            if marker.frame == frame:
                scene.yka_markers.remove(i)
                return {"FINISHED"}

        self.report({"WARNING"}, f"No marker found for frame {frame}")
        return {"CANCELLED"}


class YMK_PT_ImporterPanel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport"""

    bl_label = "YMKs Importer"
    bl_idname = "YMK_PT_importer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "YMKs Importer"

    def draw(self, context):
        layout = self.layout

        layout.label(text="YMKs Import Options:")
        layout.operator("import_scene.kyr_ymks", text="Import WWF SD 2 KYR YMKs")
        layout.operator("import_scene.jbi_ymks", text="Import WWF SD JBI+ YMKs (WIP)")


class IMPORT_OT_KYR_YMKs(bpy.types.Operator):
    """Operator to Import KYR YMKs"""

    bl_idname = "import_scene.kyr_ymks"
    bl_label = "Import WWF SD 2 KYR YMKs"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context):
        return self.read_kyr_file(context)

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def read_kyr_file(self, context):
        try:
            with open(self.filepath, "rb") as f:

                num_animations = struct.unpack("<H", f.read(2))[0]
                print(f"Number of animations: {num_animations}")

                armature_data = []

                for anim_idx in range(num_animations):
                    part_id = struct.unpack("<H", f.read(2))[0]
                    asset_id = struct.unpack("<H", f.read(2))[0]
                    toc_offset = struct.unpack("<H", f.read(2))[0]
                    num_frames = struct.unpack("<H", f.read(2))[0]
                    actual_frame_count = num_frames // 0x10

                    print(
                        f"Animation {anim_idx+1}: Part ID: {part_id}, Asset ID: {asset_id}, Frames: {actual_frame_count}, TOC offset: {toc_offset}"
                    )

                    current_pos = f.tell()
                    frame_data_offset = current_pos + toc_offset
                    f.seek(frame_data_offset)

                    animation_frames = []
                    for frame_idx in range(actual_frame_count):

                        frame_data = f.read(0x10)
                        print(f"Frame {frame_idx+1}: {frame_data.hex()}")

                        pos_x, pos_y, pos_z = struct.unpack("<hhh", frame_data[0:6])
                        rot_y, rot_x, rot_z = struct.unpack("<hhh", frame_data[6:12])

                        frame_info = {
                            "frame_idx": frame_idx,
                            "position": (pos_x / 256.0, pos_y / 256.0, pos_z / 256.0),
                            "rotation": (rot_y / 256.0, rot_x / 256.0, rot_z / 256.0),
                        }
                        animation_frames.append(frame_info)

                    armature_data.append(
                        {
                            "part_id": part_id,
                            "asset_id": asset_id,
                            "frames": animation_frames,
                        }
                    )

                    f.seek(current_pos + 10)

                self.create_armature(context, armature_data)
                self.report({"INFO"}, "KYR File imported successfully")
                return {"FINISHED"}

        except FileNotFoundError:
            self.report({"ERROR"}, "KYR file not found.")
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"Error reading KYR file: {e}")
            return {"CANCELLED"}

    def create_armature(self, context, armature_data):
        bpy.ops.object.armature_add(enter_editmode=True)
        armature = context.object
        armature.name = "Imported_YMK_Armature"
        bpy.ops.object.mode_set(mode="EDIT")

        bones = {}
        root_bone = armature.data.edit_bones.new("Root")
        root_bone.head = (0.0, 0.0, 0.0)
        root_bone.tail = (0.0, 1.0, 0.0)
        bones["Root"] = root_bone

        def create_bone_hierarchy(parent_name, hierarchy):
            for joint, data in hierarchy.items():
                bone = armature.data.edit_bones.new(joint)
                bone.parent = bones[parent_name]
                bone.head = data["offset"]
                bone.tail = (bone.head[0], bone.head[1] + 1.0, bone.head[2])
                bones[joint] = bone
                if "children" in data:
                    create_bone_hierarchy(joint, data["children"])

        bone_hierarchy = {
            "Root": {
                "children": {
                    "L_Thigh": {
                        "offset": (1.142, 0.0, -0.000143),
                        "children": {
                            "L_Knee": {
                                "offset": (1.125347, 4.199849, -0.000002),
                                "children": {
                                    "End_L_Thigh": {
                                        "offset": (1.125349, 4.199849, -0.000001)
                                    }
                                },
                            }
                        },
                    },
                    "R_Thigh": {
                        "offset": (-1.141799, 0.0, -0.000143),
                        "children": {
                            "R_Knee": {
                                "offset": (-1.125217, 4.199882, -0.000000),
                                "children": {
                                    "End_R_Thigh": {
                                        "offset": (-1.125185, 4.199890, 0.000000)
                                    }
                                },
                            }
                        },
                    },
                    "Spine": {
                        "offset": (0.0, -4.100565, 0.0),
                        "children": {
                            "Neck": {
                                "offset": (-0.000078, -2.950110, 0.000097),
                                "children": {
                                    "End_Neck": {
                                        "offset": (0.000826, -2.761086, 0.000000)
                                    }
                                },
                            }
                        },
                    },
                }
            }
        }

        create_bone_hierarchy("Root", bone_hierarchy)

        bpy.ops.object.mode_set(mode="OBJECT")

        for animation in armature_data:
            for frame_data in animation["frames"]:
                context.scene.frame_set(frame_data["frame_idx"])
                for bone_name, bone in bones.items():
                    if bone_name in animation["part_id"]:

                        bone.location = frame_data["position"]
                        bone.rotation_euler = frame_data["rotation"]
                        bone.keyframe_insert(data_path="location")
                        bone.keyframe_insert(data_path="rotation_euler")


class IMPORT_OT_JBI_YMKs(bpy.types.Operator):
    """WIP Operator for importing JBI+ YMKs"""

    bl_idname = "import_scene.jbi_ymks"
    bl_label = "Import WWF SD JBI+ YMKs"

    def execute(self, context):
        self.report({"INFO"}, "JBI+ Import is a WIP")
        return {"FINISHED"}


def menu_func_export(self, context):
    self.layout.operator(YKAExporter.bl_idname, text="Yuke's Keyframe Animation (.yka)")


def register():
    bpy.utils.register_class(YKAExporter)
    bpy.utils.register_class(YKA_PT_MarkersPanel)
    bpy.utils.register_class(YKAFrameMarkers)
    bpy.utils.register_class(YKA_OT_AddMarker)
    bpy.utils.register_class(YKA_OT_RemoveMarker)
    # bpy.utils.register_class(IMPORT_OT_KYR_YMKs)
    # bpy.utils.register_class(IMPORT_OT_JBI_YMKs)
    # bpy.utils.register_class(YMK_PT_ImporterPanel)
    bpy.types.Scene.yka_markers = bpy.props.CollectionProperty(type=YKAFrameMarkers)
    bpy.types.Scene.yka_markers_index = bpy.props.IntProperty()

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(YKAExporter)
    bpy.utils.unregister_class(YKA_PT_MarkersPanel)
    bpy.utils.unregister_class(YKAFrameMarkers)
    bpy.utils.unregister_class(YKA_OT_AddMarker)
    bpy.utils.unregister_class(YKA_OT_RemoveMarker)
    # bpy.utils.unregister_class(IMPORT_OT_KYR_YMKs)
    # bpy.utils.unregister_class(IMPORT_OT_JBI_YMKs)
    # bpy.utils.unregister_class(YMK_PT_ImporterPanel)

    del bpy.types.Scene.yka_markers
    del bpy.types.Scene.yka_markers_index

    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
