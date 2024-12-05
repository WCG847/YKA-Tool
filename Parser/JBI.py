import struct
import math
from typing import List, Tuple
import bpy
from mathutils import Vector, Quaternion

class JBIParser:
    def __init__(self, data: bytes):
        """
        Initialise the parser with binary animation data.
        
        :param data: Binary data of the JBI animation.
        """
        self.data = data
        self.offset = 0

    def read_uint8(self) -> int:
        """Read an unsigned 8-bit integer."""
        value = self.data[self.offset]
        self.offset += 1
        return value

    def read_uint16(self) -> int:
        """Read an unsigned 16-bit integer."""
        value = struct.unpack_from('<H', self.data, self.offset)[0]
        self.offset += 2
        return value

    def read_int16(self) -> int:
        """Read an signed 16-bit integer."""
        value = struct.unpack_from('<h', self.data, self.offset)[0]
        self.offset += 2
        return value

    def read_float(self) -> float:
        """Read a single-precision floating-point number."""
        value = struct.unpack_from('<f', self.data, self.offset)[0]
        self.offset += 4
        return value

    def parse_frame(self) -> Tuple[int, bool]:
        """
        Parse the frame indicator to determine frame size and flags.

        :return: A tuple containing frame size and a boolean for pre-frame flags.
        """
        frame_indicator = self.read_uint8()
        frame_size = (frame_indicator - 0x80) & 0xFF << 1
        is_pre_frame_flags = (frame_indicator & 0x20) != 0  # Second bit of the nibble
        return frame_size, is_pre_frame_flags

    def extract_positional_data(self) -> Vector:
        """
        Extract positional data (X, Y, Z) from the binary structure.

        :return: A mathutils.Vector representing position.
        """
        x = self.read_int16()
        y = self.read_int16()
        z = self.read_int16()
        
        return Vector([self.convert_to_float(x), 
                       self.convert_to_float(y), 
                       self.convert_to_float(z)])

    def extract_rotational_data(self) -> Quaternion:
        """
        Extract rotational data (Quaternion: X, Y, Z, W) from the binary structure.

        :return: A mathutils.Quaternion representing rotation.
        """
        qx = self.read_int16()
        qy = self.read_int16()
        qz = self.read_int16()
        qw = self.read_int16()
        
        return Quaternion([self.convert_to_float(qw), 
                           self.convert_to_float(qx), 
                           self.convert_to_float(qy), 
                           self.convert_to_float(qz)])

    def convert_to_float(self, value: int) -> float:
        """
        Convert an integer to a normalized floating-point value.

        :param value: Raw integer value.
        :return: Normalised float value.
        """
        float_value = float(value)
        scaling_factor = 0.01
        return float_value * scaling_factor

    def normalise_value(self, value: float, normalisation_constant: float = 0x3C23D70A):
        """
        Normalise a float value with a specific constant.

        :param value: Input float value.
        :param normalization_constant: Normalization constant (converted to float).
        :return: Normalized float value.
        """
        normalisation_float = struct.unpack('f', struct.pack('I', normalisation_constant))[0]
        return value * normalisation_float

    def parse(self) -> List[Tuple[Vector, Quaternion]]:
        """
        Parse the full JBI file and extract frame data.

        :return: List of tuples containing position and rotation for each frame.
        """
        frames = []

        while self.offset < len(self.data):
            frame_size, is_pre_frame_flags = self.parse_frame()

            if is_pre_frame_flags:
                # Handle pre-frame flags
                self.offset += 9 
            
            position = self.extract_positional_data()
            rotation = self.extract_rotational_data()
            
            # Store parsed position and rotation
            frames.append((position, rotation))

            # Skip padding bytes or unused data
            self.offset += frame_size - 12 

        return frames


def import_jbi(filepath: str):
    """
    Import JBI animation file and apply to Blender armature.

    :param filepath: Path to the JBI file.
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    parser = JBIParser(data)
    frames = parser.parse()

    # Assuming a Blender Armature exists
    armature = bpy.data.objects.get('Armature')
    if not armature or armature.type != 'ARMATURE':
        raise RuntimeError("No Armature found in the scene.")

    for frame_number, (position, rotation) in enumerate(frames, start=1):
        bpy.context.scene.frame_set(frame_number)

        for bone_name, pos, rot in zip(["Root", "Spine", "Neck", "LeftArm", "RightArm", "LeftLeg", "RightLeg"],
                                       [position] * 7,  # For simplicity
                                       [rotation] * 7):  # For simplicity
            bone = armature.pose.bones.get(bone_name)
            if bone:
                bone.location = pos
                bone.rotation_quaternion = rot

        armature.keyframe_insert(data_path="pose.bones[\"Root\"].location", frame=frame_number)
        armature.keyframe_insert(data_path="pose.bones[\"Root\"].rotation_quaternion", frame=frame_number)


# Blender Operator for importing JBI
class ImportJBI(bpy.types.Operator):
    """Import JBI Animation"""
    bl_idname = "import_anim.jbi"
    bl_label = "Import JBI Animation"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        import_jbi(self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# Register the operator
def menu_func_import(self, context):
    self.layout.operator(ImportJBI.bl_idname, text="JBI Animation (.jbi)")


def register():
    bpy.utils.register_class(ImportJBI)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportJBI)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
