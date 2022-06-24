from pydeation.materials import FillMaterial, SketchMaterial
from pydeation.tags import FillTag, SketchTag, XPressoTag
from pydeation.constants import WHITE, SVG_PATH
from pydeation.animation.object_animators import Show, Hide
from abc import ABC, abstractmethod
import c4d
import os


class ProtoObject(ABC):

    def __init__(self, name=None, x=0, y=0, z=0, h=0, p=0, b=0, scale=1, scale_x=1, scale_y=1, scale_z=1):
        self.document = c4d.documents.GetActiveDocument()  # get document
        self.specify_object()
        self.insert_to_document()
        self.set_name(name=name)
        self.set_position(x=x, y=y, z=z)
        self.set_rotation(h=h, p=p, b=b)
        self.set_scale(uniform_scale=scale, x=scale_x, y=scale_y, z=scale_z)
        self.xpressions = {}  # keeps track of animators, composers etc.
        self.accessed_parameters = {}  # keeps track which parameters have AccessControl
        self.helper_objects = {}  # keeps track of helper objects created by Animators

    def __repr__(self):
        """sets the string representation for printing"""
        return self.name

    @abstractmethod
    def specify_object(self):
        pass

    def set_name(self, name=None):
        if name is None:
            self.name = self.__class__.__name__
        else:
            self.name = name
        self.obj.SetName(self.name)

    def set_position(self, x=0, y=0, z=0, position=None):
        if position is None:
            position = c4d.Vector(x, y, z)
        self.obj[c4d.ID_BASEOBJECT_POSITION] = position

    def set_rotation(self, h=0, p=0, b=0, rotation=None):
        if rotation is None:
            rotation = c4d.Vector(h, p, b)
        self.obj[c4d.ID_BASEOBJECT_ROTATION] = rotation

    def set_scale(self, uniform_scale=1, x=1, y=1, z=1):
        if x != 1 or y != 1 or z != 1:
            scale = c4d.Vector(x, y, z)
        else:
            scale = c4d.Vector(uniform_scale, uniform_scale, uniform_scale)
        self.obj[c4d.ID_BASEOBJECT_SCALE] = scale

    def move(self, x=None, y=None, z=None):
        if x is not None:
            self.obj[c4d.ID_BASEOBJECT_POSITION, c4d.VECTOR_X] += x
        if y is not None:
            self.obj[c4d.ID_BASEOBJECT_POSITION, c4d.VECTOR_Y] += y
        if z is not None:
            self.obj[c4d.ID_BASEOBJECT_POSITION, c4d.VECTOR_Z] += z

    def rotate(self, h=None, p=None, b=None):
        if h is not None:
            self.obj[c4d.ID_BASEOBJECT_ROTATION, c4d.VECTOR_X] += h
        if p is not None:
            self.obj[c4d.ID_BASEOBJECT_ROTATION, c4d.VECTOR_Y] += p
        if b is not None:
            self.obj[c4d.ID_BASEOBJECT_ROTATION, c4d.VECTOR_Z] += b

    def scale(self, uniform_scale=None, x=None, y=None, z=None):
        if x is not None:
            self.obj[c4d.ID_BASEOBJECT_SCALE, c4d.VECTOR_X] += x
        if y is not None:
            self.obj[c4d.ID_BASEOBJECT_SCALE, c4d.VECTOR_Y] += y
        if z is not None:
            self.obj[c4d.ID_BASEOBJECT_SCALE, c4d.VECTOR_Z] += z

        if uniform_scale is not None:
            scale = c4d.Vector(uniform_scale, uniform_scale, uniform_scale)
        self.obj[c4d.ID_BASEOBJECT_SCALE] = scale

    def insert_to_document(self):
        self.document.InsertObject(self.obj)


class HelperObject(ProtoObject):  # invisible helper objects

    @abstractmethod
    def set_object_properties(self):
        pass


class VisibleObject(ProtoObject):  # visible objects

    def __init__(self, visible=False, **kwargs):
        super().__init__(**kwargs)
        self.set_visibility(visible=visible)
        self.set_xpresso_tags()

    def set_visibility(self, visible=False):
        if visible:
            show_animation = Show(self)
            show_animation.execute()
        else:
            hide_animation = Hide(self)
            hide_animation.execute()

    def set_sketch_material(self, color=WHITE, arrow_start=False, arrow_end=False):
        self.sketch_material = SketchMaterial()
        self.sketch_material.set_name(self.name)
        self.sketch_material.set_material_properties(
            color=color, arrow_start=arrow_start, arrow_end=arrow_end)

    def set_sketch_tag(self):
        self.sketch_tag = SketchTag(self.sketch_material)
        self.sketch_tag.set_tag_properties()
        self.sketch_tag.apply_to_object(self)

    def set_fill_material(self, filling=0, fill_color=None):
        if fill_color is None:
            fill_color = self.sketch_material.color  # use sketch as fill
        self.fill_material = FillMaterial()
        self.fill_material.set_name(self.name)
        self.fill_material.set_material_properties(
            filling=filling, color=fill_color)

    def set_fill_tag(self):
        self.fill_tag = FillTag(self.fill_material)
        self.fill_tag.set_tag_properties()
        self.fill_tag.apply_to_object(self)

    def set_xpresso_tags(self):
        """initializes the necessary xpresso tags on the object"""
        # the composition tags hold the hierarchy of compositions and ensure execution from highest to lowest
        self.composition_tags = []
        # the animator tag holds the acting of the animators on the actual parameters
        self.animator_tag = XPressoTag()
        self.animator_tag.set_name("AnimatorTag")
        # set priority to be executed last
        self.animator_tag.set_priority(1, mode="expression")
        self.animator_tag.apply_to_object(self)
        # the freeze tag holds the freezing xpressions that are executed before the animators
        self.freeze_tag = XPressoTag()
        self.freeze_tag.set_name("FreezeTag")
        # set priority to be executed after compositions and before animators
        self.freeze_tag.set_priority(0, mode="animation")
        self.freeze_tag.apply_to_object(self)

    def add_composition_tag(self):
        """adds another layer to the composition hierarchy"""
        composition_tag = XPressoTag()
        self.composition_tags.append(composition_tag)
        composition_tag.set_name(
            "CompositionTag" + str(len(self.composition_tags)))
        # set priority according to position in composition hierarchy
        composition_tag.set_priority(-len(self.composition_tags),
                                     mode="initial")
        composition_tag.apply_to_object(self)
        return composition_tag.obj

    def clone(self):
        """clones an object and inserts it into the scene"""
        clone = self.obj.GetClone()
        self.document.InsertObject(clone)
        return clone

    def get_editable(self):
        """returns an editable clone of the object"""
        clone = self.clone()
        editable_clone = c4d.utils.SendModelingCommand(command=c4d.MCOMMAND_MAKEEDITABLE, list=[
            clone], mode=c4d.MODELINGCOMMANDMODE_ALL, doc=self.document)[0]
        return editable_clone

    def attach_to(self, target, direction="top"):
        """places the object such that the bounding boxes touch along a given direction and makes object child of target"""
        bounding_box = self.obj.GetRad()
        bounding_box_position = self.obj.GetMp()
        bounding_box_target = target.obj.GetRad()
        bounding_box_position_target = target.obj.GetMp()
        new_position = bounding_box_position_target - bounding_box_position
        if direction == "top":
            new_position.y += bounding_box_target.y + bounding_box.y
        if direction == "bottom":
            new_position.y -= bounding_box_target.y + bounding_box.y
        if direction == "left":
            new_position.x -= bounding_box_target.x + bounding_box.x
        if direction == "right":
            new_position.x += bounding_box_target.x + bounding_box.x
        if direction == "front":
            new_position.z -= bounding_box_target.z + bounding_box.z
        if direction == "back":
            new_position.z += bounding_box_target.z + bounding_box.z

        self.obj.InsertUnder(target.obj)
        self.set_position(position=new_position)


class LineObject(VisibleObject):  # line objects only require sketch material

    def __init__(self, color=WHITE, plane="xy", fill_color=None, solid=False, arrow_start=False, arrow_end=False, **kwargs):
        super().__init__(**kwargs)
        self.set_general_properties(plane=plane)
        if solid or fill_color is not None:
            self.create_loft(color=color, fill_color=fill_color,
                             arrow_start=arrow_start, arrow_end=arrow_end)
        else:
            self.set_sketch_material(
                color=color, arrow_start=arrow_start, arrow_end=arrow_end)
            self.set_sketch_tag()

    def set_general_properties(self, plane="xy"):
        # set plane
        planes = {"xy": 0, "zy": 1, "xz": 2}
        self.obj[c4d.PRIM_PLANE] = planes[plane]

    @abstractmethod
    def set_object_properties(self):
        pass

    def create_loft(self, color=WHITE, fill_color=None, arrow_start=False, arrow_end=False):
        self.loft = Loft(color=color, fill_color=fill_color,
                         arrow_start=arrow_start, arrow_end=arrow_end)
        self.obj.InsertUnder(self.loft.obj)


class SolidObject(LineObject):  # solid objects also require fill material

    def __init__(self, filling=0, fill_color=None, **kwargs):
        super().__init__(**kwargs)
        self.set_fill_material(filling=filling, fill_color=fill_color)
        self.set_fill_tag()

    @abstractmethod
    def set_object_properties(self):
        pass


class Loft(SolidObject):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def specify_object(self):
        self.obj = c4d.BaseObject(c4d.Oloft)

    def set_object_properties(self):
        pass


class SVG(LineObject):  # takes care of importing svgs

    def __init__(self, file_name, **kwargs):
        self.load_svg_in_separate_document(file_name)
        super().__init__(**kwargs)
        self.kill_separate_document()
        self.fix_axes()

    def load_svg_in_separate_document(self, file_name):
        file_path = os.path.join(SVG_PATH, file_name + ".svg")
        self.svg_doc = c4d.documents.LoadDocument(
            file_path, c4d.SCENEFILTER_NONE)
        if self.svg_doc is None:
            raise RuntimeError("Failed to load svg file.")

    def kill_separate_document(self):
        c4d.documents.KillDocument(self.svg_doc)

    def fix_axes(self):
        self.document.SetSelection(self.obj)  # select svg
        c4d.CallCommand(1011982)  # moves svg axes to center
        self.obj[c4d.ID_BASEOBJECT_REL_POSITION] = c4d.Vector(
            0, 0, 0)  # move svg to origin

    def specify_object(self):
        self.obj = self.svg_doc.GetFirstObject().GetDown()

    def set_object_properties(self, spline_type="bezier", closed=True):
        # implicit propertiesd
        spline_types = {"bezier": 4, "linear": 0}
        # set properties
        self.obj[c4d.SPLINEOBJECT_TYPE] = spline_types[spline_type]
        self.obj[c4d.SPLINEOBJECT_CLOSED] = closed
