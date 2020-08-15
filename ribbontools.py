import maya.cmds as mc
import matrixconstrainttools as mt
reload(mt)

RIB = "_ribbon"
RIG = "_rig"
RIV = "_riv"
GRP = "_grp"

POS_ATTR = ".translate"
ROT_ATTR = ".rotate"
SCL_ATTR = ".scale"
VECTORS = ["X", "Y", "Z"]
ATTRS = [POS_ATTR, ROT_ATTR, SCL_ATTR]


class Ribbon(mt.Rivet):
    def __init__(self, name, jointNum=3, driverJointNum=2, primaryAxis="X"):
        mt.Rivet.__init__(self, mo=True)
        self.name = name
        self.jointNum = jointNum
        self.driverJointNum = driverJointNum
        self.primaryAxis = primaryAxis
        self.spans = ((jointNum - 1) * (driverJointNum - 1))
        self.ribbon = []
        self.lenCurves = []
        self.joints = []
        self.driverJoints = []
        self.deformers = []
        self.proxies = []

        if jointNum < 3 or driverJointNum < 2:
            return mc.error("Rig needs a minimum of 2 drivers and 3 joints")

        ptPosList = []
        attrs = [POS_ATTR, SCL_ATTR]
        prxyGrp = mc.createNode("transform", n="{}_prxy{}".format(name, GRP))
        prevPrxy = "{}_base_prxy".format(name)
        for i in range(driverJointNum):
            # Create a set of locators to be used as proxies for your ribbon's driver joints
            # Set position based on rig's primary axis
            if primaryAxis == "Z":
                ptPos = (0, 0, i * 10)
            elif primaryAxis == "Y":
                ptPos = (0, i * 10, 0)
            else:
                ptPos = (i * 10, 0, 0)
            ptPosList.append(ptPos)

            # Name the proxy based on its order in the chain
            if i == 0:
                prxy = "{}_base_prxy".format(name)
            elif i == driverJointNum - 1:
                prxy = "{}_tip_prxy".format(name)
            elif i >= 1 and driverJointNum >= 4:
                prxy = "{}_mid{}_prxy".format(name, str(i).zfill(2))
            else:
                prxy = "{}_mid_prxy".format(name)

            # Create the locator
            mc.spaceLocator(n=prxy)
            mc.setAttr("{}.translate{}".format(prxy, primaryAxis), i * 10)

            # Lock attributes you don't want to be changed so the rig is buit properly
            if i == 0:
                # As the root, the first proxy will have the freest range of motion
                for v in VECTORS:
                    mc.setAttr("{}.scale{}".format(prxy, v),
                               lock=True, keyable=False, channelBox=False)
                # Parent to the appropriate group
                mc.parent(prxy, prxyGrp)

            if i > 0:
                # Child proxies will have a more limited range of movement
                for attr in attrs:
                    for v in VECTORS:
                        if attr == SCL_ATTR or v != primaryAxis:
                            mc.setAttr("{}{}{}".format(prxy, attr, v),
                                       lock=True, keyable=False, channelBox=False)
                # Parent to the appropriate group
                mc.parent(prxy, prevPrxy)

            self.proxies.append(prxy)
            prevPrxy = prxy

        # We also want to create a curve whose arclen will create the width of your ribbon
        self.proxieCrv = mc.curve(
            d=1, p=ptPosList, n="{}_prxyCrv".format(name))
        mc.parent(self.proxieCrv, prxyGrp)
        mc.setAttr("{}.inheritsTransform".format(self.proxieCrv))
        for i, prxy in enumerate(self.proxies):
            clstr = mc.cluster("{}.cv[{}]".format(self.proxieCrv, i))[1]
            mc.setAttr("{}.visibility".format(clstr), 0)
            mc.parent(clstr, prxy)

    def mk_ribbon(self):
        """
        Create the ribbon that will be the base for your rig
        """
        width = mc.arclen(self.proxieCrv)
        ratio = 1.0 / width
        ribbon = "{}{}".format(self.name, RIB)
        grp = "{}{}".format(ribbon, GRP)

        if not mc.objExists(ribbon):
            ribbon = mc.nurbsPlane(p=(0, 0, 0), ax=(0, 1, 0), w=width, lr=ratio,
                                   d=3, u=self.spans, v=1, name=ribbon, ch=True)[0]

        if not mc.listRelatives(ribbon, p=True) == grp:
            self.mk_parent_grp(ribbon)

        mc.setAttr("{}.rotateOrder".format(grp), 1)
        mc.xform(ribbon, piv=[-(width * .5), 0, 0])

        self.ribbon = ribbon

        return ribbon

    def mk_len_crv(self):
        """
        Create a curve skinned along with ribbon that provides you with
        your ribbon's length data for volume preservation
        """
        crv = mc.duplicateCurve("{}.v[0.5]".format(
            self.ribbon), ch=False, rn=False, l=False, n=self.ribbon.replace("ribbon", "crv"))[0]
        mc.setAttr("{}.visibility".format(crv), 0)
        mc.parent(crv, "{}{}".format(self.ribbon, GRP))

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

    def mk_driver_joints(self):
        """
        Create the joints that will drive your ribbon
        """
        for i in range(self.driverJointNum):
            # Define rotation order based on riibbon's primary axis
            if self.primaryAxis == "X":
                ro = "xyz"
            elif self.primaryAxis == "Y":
                ro = "yzx"
            else:
                ro = "zxy"

            if i == 0:
                jnt = mc.joint(n="{}_base_driver_jnt".format(
                    self.name), rad=3, roo=ro)
            elif i == self.driverJointNum - 1:
                jnt = mc.joint(n="{}_tip_driver_jnt".format(
                    self.name), rad=3, roo=ro)
                mc.setAttr("{}.translate{}".format(
                    jnt, self.primaryAxis), mc.arclen(self.proxieCrv) / (self.driverJointNum - 1))
            elif i == 1 and self.driverJointNum == 3:
                jnt = mc.joint(n="{}_mid_driver_jnt".format(
                    self.name), rad=3, roo=ro)
                mc.setAttr("{}.translate{}".format(
                    jnt, self.primaryAxis), mc.arclen(self.proxieCrv) / (self.driverJointNum - 1))
            else:
                jnt = mc.joint(
                    n="{}_mid{}_driver_jnt".format(self.name, str(i).zfill(2)), rad=3, roo=ro)
                mc.setAttr("{}.translate{}".format(jnt, self.primaryAxis), mc.arclen(
                    self.proxieCrv) / (self.driverJointNum - 1))

            self.driverJoints.append(jnt)

        # Group your driver joints and parent it to your rig group
        driverGrp = mc.createNode(
            "transform", n="{}_driver_jnt_grp".format(self.name))
        mc.parent(self.driverJoints[0], driverGrp)
        mc.parent(driverGrp, "{}{}".format(self.name, RIG))
        mc.reorder(driverGrp, r=-1)

        return self.driverJoints

    def mv_ribbon(self):
        """
        Move the Rig group into position with the bottom driver
        """
        btDriver = self.driverJoints[0]
        pos = mc.getAttr("{}.translate".format(btDriver))[0]
        rot = mc.getAttr("{}.rotate".format(btDriver))[0]
        for i, v in enumerate(VECTORS):
            mc.setAttr("{}_rig.translate{}".format(self.name, v), pos[i])
            mc.setAttr("{}_rig.rotate{}".format(self.name, v), rot[i])
        mc.setAttr("{}.translateX".format(self.ribbon),
                   mc.arclen(self.lenCurves[0]) * .5)

    def orient_to_axis(self):
        """
        Aligns the ribbon to the primary axis
        """
        mc.setAttr("{}.translateX".format(self.ribbon),
                   mc.arclen(self.lenCurves[0]) * .5)
        mc.setAttr("{}.translate{}".format(
            self.lenCurves[0], self.primaryAxis), mc.arclen(self.lenCurves[0]) * .5)

        if self.primaryAxis == "Z":
            mc.setAttr("{}.rotateY".format(self.ribbon), -90)
            mc.setAttr("{}.rotateY".format(self.lenCurves[0]), -90)

        if self.primaryAxis == "Y":
            mc.setAttr("{}.rotateZ".format(self.ribbon), 90)
            mc.setAttr("{}.rotateX".format(self.ribbon), 90)
            mc.setAttr("{}.rotateZ".format(self.lenCurves[0]), 90)

    def skin_duo_drivers(self):
        """
        Creates a pair of driver joints at either end of your ribbon
        """
        btDriver = self.driverJoints[0]
        tpDriver = self.driverJoints[1]
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
        scCrv = mc.skinCluster(btDriver, tpDriver, crv,
                               n="{}_sc".format(crv))[0]
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
            mc.skinPercent(scCrv, "{}.cv[{}]".format(
                crv, i), tv=[(btDriver, btwt), (tpDriver, tpwt)])

        # turn off ribbon's inherit transform to prevent double transforms
        mc.setAttr("{}.inheritsTransform".format(ribbon), 0)
        # turn off curve's inherit transform to prevent double transforms
        mc.setAttr("{}.inheritsTransform".format(crv), 0)

        # Group your driver joints and parent it to your rig group
        driverGrp = mc.createNode(
            "transform", n="{}_driver_jnt_grp".format(self.name))
        mc.parent(tpDriver, driverGrp)
        mc.parent(btDriver, driverGrp)
        mc.parent(driverGrp, "{}_rig".format(self.name))
        mc.reorder(driverGrp, r=-1)

    def skin_to_drivers(self):
        """
        Skin the ribbon to the driver joints
        """
        ribbon = self.ribbon
        crv = self.lenCurves[0]
        spansPer = self.jointNum - 1
        frac = 1.0 / self.spans
        thrdFrac = .333 * frac

        # Freeze transformation of the base driver joint
        mc.makeIdentity(self.driverJoints[0], a=True)

        # Apply skincluster to ribbon and lenCrv
        scRib = mc.skinCluster(self.driverJoints[0], ribbon,
                               n="{}_sc".format(ribbon))[0]
        scCrv = mc.skinCluster(self.driverJoints[0], crv,
                               n="{}_sc".format(crv))[0]

        for n in range(self.driverJointNum - 1):
            # Determine the number of cvrows between each pair of driver joints
            if n == 0 and self.driverJointNum == 2:
                cvrows = spansPer + 3
            elif n == 0 and self.driverJointNum >= 3 or n == self.driverJointNum and self.driverJointNum >= 3:
                cvrows = spansPer + 2
            else:
                cvrows = spansPer + 1

            for i in range(cvrows):
                # Calculate the weighting for each cvrow
                btDriver = self.driverJoints[n]
                tpDriver = self.driverJoints[n + 1]

                if i == 0:
                    btwt = 1
                    tpwt = 0
                elif i == 1 and n == 0:
                    btwt = 1 - thrdFrac
                    tpwt = thrdFrac
                elif i == cvrows - 2 and n == self.driverJointNum - 2:
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
                mc.skinPercent(scCrv, "{}.cv[{}]".format(
                    crv, i), tv=[(btDriver, btwt), (tpDriver, tpwt)])

        # turn off ribbon's inherit transform to prevent double transforms
        mc.setAttr("{}.inheritsTransform".format(ribbon), 0)
        # turn off curve's inherit transform to prevent double transforms
        mc.setAttr("{}.inheritsTransform".format(crv), 0)

    def align_to_proxies(self):
        """
        Move the driver joints into place and remove the proxies
        """
        for i, jnt in enumerate(self.driverJoints):
            # Move each driver joint
            prxy = jnt.replace("driver_jnt", "prxy")
            if i == 0:
                mc.matchTransform("{}{}".format(self.name, RIG), prxy)
            else:
                mc.matchTransform(jnt, prxy)

        # Delete the proxy group
        mc.delete("{}_prxy{}".format(self.name, GRP))

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
        scl = mc.shadingNode("multiplyDivide", asUtility=True,
                             n="{}_len_scl".format(self.name))
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
        mc.connectAttr("{}.outputScale".format(decM), "{}.input2".format(scl))
        mc.connectAttr("{}.outputX".format(scl), "{}.input2X".format(nml))
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
        mc.setAttr("{}.input1X".format(scl), crvLen)
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

    def build_ribbon_rig(self):
        """
        Goes through all the steps to build your ribbon rig
        """
        self.mk_ribbon()
        self.mk_len_crv()
        self.mk_rig()
        self.mk_driver_joints()
        self.mv_ribbon()
        self.orient_to_axis()
        self.skin_to_drivers()
        self.align_to_proxies()
        self.set_preserve_vol()
