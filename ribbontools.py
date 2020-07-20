import maya.cmds as mc
import matrixconstrainttools as mt

RIB = "_rib"
GRP = "_grp"


class Ribbon(mt.Rivet):
    def __init__(self, name, width, spans, mo=True):
        self.name = name
        self.width = width
        self.spans = spans
        self.mo = mo
        self.drivers = []
        self.driven = []

    def mk_ribbon(self):
        ratio = 1.0 / self.width
        ribbon = "{}{}".format(self.name, RIB)
        grp = "{}{}".format(ribbon, GRP)

        if not mc.objExists(ribbon):
            ribbon = mc.nurbsPlane(p=(0, 0, 0), ax=(0, 1, 0), w=self.width, lr=ratio,
                                   d=3, u=self.spans, v=1, name=ribbon, ch=True)[0]

        if not mc.listRelatives(ribbon, p=True) == grp:
            self.mk_parent_grp(ribbon)

        mc.setAttr("{}.inheritsTransform".format(ribbon), 0)
        mc.xform(ribbon, piv=[(self.width * .5), 0, 0])
        return ribbon

    def mk_rig(self, ribbon):
        mc.select(ribbon, r=True)

        if len(self.drivers) != 0:
            self.drivers[0] = ribbon[0]
        else:
            self.drivers.append(ribbon[0])

        rivets = self.set_rivets(self.spans + 1)
        jntLst = []

        for rivet in rivets:
            jnt = mc.joint(radius=0.15, name=rivet.replace(
                "riv", "jnt"), roo="yzx")
            mc.parent(jnt, rivet)
            mc.setAttr("{}.translateY".format(jnt), 0)
            jntLst.append(jnt)

        mc.select(ribbon, r=True)
        return jntLst

    def mk_deformer(self, ribbon, defType):
        """
        Applies a deformer to your ribbon
        """
        mc.select(ribbon, r=True)
        bs = "{}_bs".format(ribbon)

        # Create duplicate ribbon and apply a twist deformer
        deformer = "{}_{}".format(ribbon, defType)

        if mc.objExists(deformer):
            return deformer

        mc.duplicate(ribbon, name="{}_{}".format(ribbon, defType))
        deform = mc.nonLinear(deformer, type=defType)
        mc.rename(deform[0], "{}Def".format(deformer))
        hndl = mc.rename(deform[1], "{}Hndl".format(deformer))
        mc.setAttr(hndl + ".rotateZ", -90)

        # Connect geometry to primary ribbon via a blend shape
        if not mc.objExists(bs):
            mc.blendShape(deformer, ribbon, n=bs, foc=True, w=(0, 1))

        else:
            bs_targets = mc.blendShape(bs, q=True, target=True)
            mc.blendShape(bs, edit=True, t=(ribbon, len(
                bs_targets), deformer, 1.0), w=[len(bs_targets), 1.0])

        # Group everything together
        grp = mc.group(deformer, hndl, n="{}{}".format(deformer, GRP))
        mc.select(ribbon, r=True)
        mc.parent(grp, "{}{}".format(ribbon, GRP))
        mc.setAttr("{}.visibility".format(grp), 0)

        return deformer

    def mk_twist(self, ribbon):
        """
        Applies twist functionality to your ribbon rig
        """
        twist = self.mk_deformer(ribbon, "twist")
        return twist

    def mk_sine(self, ribbon, fixedEnd=True):
        """
        Applies sine functionality to your ribbon rig
        """
        sine = self.mk_deformer(ribbon, "sine")
        mc.setAttr("{}Def.dropoff".format(sine), 1)

        if fixedEnd is False:
            # If sine wave is only fixed at one end (not both)
            mc.setAttr("{}Def.highBound".format(sine), 2)
            mc.setAttr("{}Hndl.translateX".format(sine), -(self.width * .5))

        return sine

    def set_duo_drivers(self):
        """
        Creates a pair of driver joints at either end of your ribbon
        """
        # return driverJnts
        pass

    def set_trio_drivers(self):
        """
        Creates a set of driver joints: one in the middle and
        two at either end of your ribbon
        """
        # return driverJnts
        pass

    def mk_length_curve(self):
        """
        Create a curve skinned along with ribbon that provides you with
        your ribbon's length data for volume preservation
        """
        pass
