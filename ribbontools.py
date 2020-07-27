import maya.cmds as mc
import matrixconstrainttools as mt
reload(mt)

RIB = "_ribbon"
GRP = "_grp"


class Ribbon(mt.Rivet):
    def __init__(self, name, width, spans, mo=True):
        self.name = name
        self.width = width
        self.spans = spans
        self.mo = mo
        self.drivers = []
        self.driven = []
        self.ribbon = []
        self.lenCurves = []
        self.joints = []
        self.deformers = []

    def mk_ribbon(self):
        """
        Create the ribbon that will be the base for your rig
        """
        ratio = 1.0 / self.width
        ribbon = "{}{}".format(self.name, RIB)
        grp = "{}{}".format(ribbon, GRP)

        if not mc.objExists(ribbon):
            ribbon = mc.nurbsPlane(p=(0, 0, 0), ax=(0, 1, 0), w=self.width, lr=ratio,
                                   d=3, u=self.spans, v=1, name=ribbon, ch=True)[0]

        if not mc.listRelatives(ribbon, p=True) == grp:
            self.mk_parent_grp(ribbon)

        mc.xform(ribbon, piv=[-(self.width * .5), 0, 0])

        self.ribbon = ribbon

        return ribbon

    def mk_len_crv(self):
        """
        Create a curve skinned along with ribbon that provides you with
        your ribbon's length data for volume preservation
        """
        crv = mc.duplicateCurve("{}.v[0.5]".format(
            self.ribbon), ch=True, rn=False, l=True, n=self.ribbon.replace("ribbon", "crv"))[0]

        # Add curve to lenCurves cless variable
        self.lenCurves.append(crv)

        return crv

    def split_len_crv(self):
        """
        Create two child curves that are half the primary lenCurve to separate
        the upper and lower segments for use in arms and legs
        """
        curve = self.lenCurves[0]

        # Split the curve at the halfway point
        crvs = mc.detachCurve("{}.u[.5]".format(
            curve), ch=True, n="{}_base".format(curve))

        # Name the new curves and add them to a New Curves list
        mc.rename(crvs[1], "{}_tip".format(curve))
        crvs[1] = "{}_tip".format(curve)
        newCrvs = crvs[0:2]

        for crv in newCrvs:
            # Add each curve to lenCurves cless variable...
            self.lenCurves.append(crv)
            # ...and parent them to the primary curve
            mc.parent(crv, curve)

        return newCrvs

    def mk_rig(self):
        """
        Create the rivets and joints that follow along the surface
        of your ribbon
        """
        ribbon = self.ribbon
        mc.select(ribbon, r=True)

        # set your ribbon as the driver object
        if len(self.drivers) != 0:
            self.drivers[0] = ribbon
        else:
            self.drivers.append(ribbon)

        # Create the rivets that will follow along the ribbon surface
        rivets = self.set_rivets(self.spans + 1)
        jntLst = []

        for rivet in rivets:
            # creat a joint for each rivet
            jnt = mc.joint(radius=0.15, name=rivet.replace(
                "riv", "jnt"), rad=.75, roo="yzx")
            mc.parent(jnt, rivet)
            mc.setAttr("{}.translateY".format(jnt), 0)
            jntLst.append(jnt)

        mc.select(ribbon, r=True)
        self.joints = jntLst
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
            # Make sure deformer doesn't already exist
            return deformer

        # Create a duplicate of your ribbon to apply deformer to
        mc.duplicate(ribbon, name="{}_{}".format(ribbon, defType))
        deform = mc.nonLinear(deformer, type=defType)
        mc.rename(deform[0], "{}Def".format(deformer))
        hndl = mc.rename(deform[1], "{}Hndl".format(deformer))
        mc.setAttr(hndl + ".rotateZ", -90)

        # Connect duplicate to primary ribbon via a blend shape
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

    def mk_twist(self):
        """
        Applies twist functionality to your ribbon rig
        """
        twist = self.mk_deformer(self.ribbon, "twist")

        self.deformers.append(twist)
        return twist

    def mk_sine(self, fixedEnd=True):
        """
        Applies sine functionality to your ribbon rig
        """
        sine = self.mk_deformer(self.ribbon, "sine")
        mc.setAttr("{}Def.dropoff".format(sine), 1)

        if fixedEnd is False:
            # If sine wave is only fixed at one end (not both)
            mc.setAttr("{}Def.highBound".format(sine), 2)
            mc.setAttr("{}Hndl.translateX".format(sine), -(self.width * .5))

        self.deformers.append(sine)
        return sine

    def mk_bend(self):
        """
        Applies bend functionality to your ribbon rig
        """
        bend = self.mk_deformer(self.ribbon, "bend")

        self.deformers.append(bend)
        return bend

    def set_preserve_vol(self):
        """
        Set the squash & stretch ammounts for ribbon joints
        """
        crv = self.lenCurves[0]
        shape = mc.listRelatives(crv, s=True)[0]
        info = mc.shadingNode("curveInfo", asUtility=True,
                              n="{}_info".format(crv))
        div = mc.shadingNode(
            "multiplyDivide", asUtility=True, n="{}_div".format(crv))
        blend = mc.shadingNode(
            "blendTwoAttr", asUtility=True, n="{}_volPreserve_offOn".format(crv))

        # Set attributes for blender node
        mc.setAttr("{}.input[0]".format(blend), 1.0)
        mc.setAttr("{}.attributesBlender".format(blend), 1.0)

        # Connect the attributes
        mc.connectAttr("{}.worldSpace[0]".format(
            shape), "{}.inputCurve".format(info))
        mc.connectAttr("{}.arcLength".format(info), "{}.input2X".format(div))
        mc.connectAttr("{}.outputX".format(div),
                       "{}.input[1]".format(blend))

        # Set ttributes for divide node
        mc.setAttr("{}.operation".format(div), 2)
        crvLen = mc.getAttr("{}.arcLength".format(info))
        mc.setAttr("{}.input1X".format(div), crvLen)

        # Connect network to joints' scales Y and Z
        for joint in self.joints:
            mc.connectAttr("{}.output".format(blend),
                           "{}.scaleY".format(joint))
            mc.connectAttr("{}.output".format(blend),
                           "{}.scaleZ".format(joint))

        """
        # Need to figgure out how to apply to multiple cuves
        if len(self.lenCurves) == 1:
            crvs = self.lenCurves
        else:
            crvs = self.lenCurves[1:len(self.lenCurves)]

        blendList = []
        for crv in crvs:
        """

    def skin_duo_drivers(self, btDriver, tpDriver):
        """
        Creates a pair of driver joints at either end of your ribbon
        """
        ribbon = self.ribbon
        cvrows = self.spans + 3
        frac = 1.0 / self.spans
        thrdFrac = .333 * frac

        # Set the position of the ribbon to the base driver joint
        pos = mc.xform(btDriver, q=True, ws=True, rp=True)
        mc.xform(ribbon, ws=True, t=(
            pos[0] + (self.width * .5), pos[1], pos[2]))

        # Set the rotation of the ribbon to the base driver joint
        mc.parent(ribbon, btDriver)
        # Remember to set driver joint rotation order to yzxx
        mc.xform(ribbon, ro=(90, 0, 90))
        mc.parent(ribbon, "{}_grp".format(ribbon))
        mc.reorder(ribbon, f=True)

        # Group driver joints under ribbon grp
        driverGrp = mc.createNode(
            "transform", n="{}_driverJnts_grp".format(ribbon))
        mc.parent(driverGrp, "{}_grp".format(ribbon))
        mc.matchTransform(driverGrp, btDriver)
        mc.parent(btDriver, driverGrp)

        # turn off ribbon's inherit transform to prevent double transforms
        mc.setAttr("{}.inheritsTransform".format(ribbon), 0)

    # Apply skincluster to ribbon
        sc = mc.skinCluster(btDriver, tpDriver, ribbon, n=ribbon + "_sc")[0]
        for i in range(cvrows):
            if i == 0:
                btwt = 1
                tpwt = 0
            elif i == 1:
                btwt = 1 - thrdFrac
                tpwt = thrdFrac
            elif i == cvrows - 2:
                btwt = thrdFrac
                tpwt = 1 - thrdFrac
            elif i == cvrows - 1:
                btwt = 0
                tpwt = 1
            else:
                btwt = 1 - ((i - 1) * frac)
                tpwt = (i - 1) * frac

            mc.skinPercent(sc, "%s.cv[%s][0:3]" %
                           (ribbon, i), tv=[(btDriver, btwt), (tpDriver, tpwt)])

    def skin_trio_drivers(self):
        """
        Creates a set of driver joints: one in the middle and
        two at either end of your ribbon
        """
        # return driverJnts
        pass
