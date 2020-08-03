import maya.cmds as mc
import matrixconstrainttools as mt
reload(mt)

RIB = "_ribbon"
RIG = "_rig"
RIV = "_riv"
GRP = "_grp"
VECTORS = ["X", "Y", "Z"]


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

        mc.setAttr("{}.rotateOrder".format(grp), 1)
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
        mc.setAttr("{}.visibility".format(crv), 0)

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
            mc.setAttr("{}.visibility".format(crv), 0)
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
        rig = mc.createNode("transform", n="{}{}".format(self.name, RIG))
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

        mc.parent("{}{}{}".format(self.name, RIB, GRP), rig)
        mc.parent("{}{}{}{}".format(self.name, RIB, RIV, GRP), rig)
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
        blend = mc.shadingNode(
            "blendTwoAttr", asUtility=True, n="{}_volPreserve_offOn".format(crv))
        decM = mc.shadingNode("decomposeMatrix", asUtility=True,
                              n="{}{}_decM".format(self.name, RIG))
        nml = mc.shadingNode("multiplyDivide", asUtility=True,
                             n="{}_len_scl_nml".format(self.name))
        pwr = mc.shadingNode(
            "multiplyDivide", asUtility=True, n="{}_len_scl_pwr".format(self.name))
        div = mc.shadingNode(
            "multiplyDivide", asUtility=True, n="{}_len_scl_div".format(self.name))

        # Connect the attributes
        mc.connectAttr("{}.worldSpace[0]".format(
            shape), "{}.inputCurve".format(info))
        mc.connectAttr("{}.arcLength".format(info), "{}.input1X".format(nml))
        mc.connectAttr("{}{}.worldMatrix[0]".format(
            self.name, RIG), "{}.inputMatrix".format(decM))
        mc.connectAttr("{}.outputScale".format(decM), "{}.input2".format(nml))
        mc.connectAttr("{}.outputX".format(nml), "{}.input1X".format(pwr))
        mc.connectAttr("{}.outputX".format(pwr), "{}.input2X".format(div))

        # Set attributes for blender node
        crvLen = mc.getAttr("{}.arcLength".format(info))
        mc.setAttr("{}.input[0]".format(blend), crvLen)
        mc.setAttr("{}.attributesBlender".format(blend), 1.0)

        # Set attributes for multiplyDivide nodes
        mc.setAttr("{}.operation".format(nml), 2)
        mc.setAttr("{}.operation".format(pwr), 3)
        mc.setAttr("{}.operation".format(div), 2)
        mc.setAttr("{}.input2X".format(pwr), 0.5)
        mc.setAttr("{}.input1X".format(div), 1)

        # Connect network to joints' scales Y and Z
        for joint in self.joints:
            riv = joint.replace("jnt", "riv")
            mc.connectAttr("{}.outputX".format(div),
                           "{}.scaleY".format(joint))
            mc.connectAttr("{}.outputX".format(div),
                           "{}.scaleZ".format(joint))
            mc.connectAttr("{}.outputScale".format(decM),
                           "{}.scale".format(riv), f=True)

        """
        # Need to figgure out how to apply to multiple cuves
        if len(self.lenCurves) == 1:
            crvs = self.lenCurves
        else:
            crvs = self.lenCurves[1:len(self.lenCurves)]

        blendList = []
        for crv in crvs:
        """

    def mv_rig(self, btDriver):
        """
        Move the Rig group into position with the bottom driver
        """
        pos = mc.getAttr("{}.translate".format(btDriver))[0]
        rot = mc.getAttr("{}.rotate".format(btDriver))[0]
        for i, v in enumerate(VECTORS):
            mc.setAttr("{}_rig.translate{}".format(self.name, v), pos[i])
            mc.setAttr("{}_rig.rotate{}".format(self.name, v), rot[i])
        mc.setAttr("{}.translateX".format(self.ribbon), self.width * .5)

    def orient_x_to_y(self):
        """
        Ribbons may have to be aligned to their driver joints, this method
        aligns the ribbon to the joint's Y axis
        """
        mc.setAttr("{}.rotateZ".format(self.ribbon), 90)
        mc.setAttr("{}.rotateX".format(self.ribbon), 90)

    def skin_duo_drivers(self, btDriver, tpDriver):
        """
        Creates a pair of driver joints at either end of your ribbon
        """
        ribbon = self.ribbon
        crv = self.lenCurves[0]
        cvrows = self.spans + 3
        frac = 1.0 / self.spans
        thrdFrac = .333 * frac

        # Freeze transformation of the base driver joint
        mc.makeIdentity(btDriver, a=True)

        # Apply skincluster to ribbon and lenCrv
        scRib = mc.skinCluster(btDriver, tpDriver, ribbon,
                               n="{}_sc".format(ribbon))[0]
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
            # Set the weighting of the CVs based on the number of CV rows
            mc.skinPercent(scRib, "{}.cv[{}][0:3]".format(
                ribbon, i), tv=[(btDriver, btwt), (tpDriver, tpwt)])

        # turn off ribbon's inherit transform to prevent double transforms
        mc.setAttr("{}.inheritsTransform".format(ribbon), 0)
        # turn off curve's inherit transform to prevent double transforms
        mc.setAttr("{}.inheritsTransform".format(crv), 0)

        # Group your driver joints and parent it to your rig group
        driverGrp = mc.createNode("transform", n="{}_driver_jnt_grp".format(self.name))
        mc.parent(tpDriver, driverGrp)
        mc.parent(btDriver, driverGrp)
        mc.parent(driverGrp, "{}_rig".format(self.name))

    def skin_trio_drivers(self):
        """
        Creates a set of driver joints: one in the middle and
        two at either end of your ribbon
        """
        # return driverJnts
        pass
