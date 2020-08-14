###########################################################################################
#
#   Title: Matrix Constraint Tools
#   Version 2.1
#   Author: Steve Addeo
#   Created: April 15, 2020
#   Last Updated: August 04, 2020
#
#   Descritpion: Utilizes Maya's matrix nodes to apply various constraint solutions that
#       are faster and lead to less clutter in your outliner
#
#    Instructions: all the constraints have the option to maintain offset or not and default
#       to the more logical option based on what you're trying to do. You can define this
#       function when you initialize the class (mo=True) or (mo=False)
#
#       Constraints - Works like your typical Maya constraint nodes. Select your driver
#           (or dirvers) object(s), initialize the Constraint class (var =
#           Constraint(mo=True)), then run your desited constraint:
#               - var.parent(), var.point(), var.orient(), and var.scale()
#
#       Blend Colors - works similarly to the regular constraints (maintain offset defaults
#           to False) but allows you to control the weighting for one or two drivers. Same
#            approach as constraint class. Initialize the BlendColor class (var =
#            BlendColors(mo=False)), then run your command:
#               - var.parent(), var.point(), var.orient(), and var.scale()
#
#      Rivets - an alternative to using follicles, the Rivet class generates a locator or
#           series of locators that are constrained to a nurbs surface and can act as the
#           parent for an object you want to stick to a given surface. Simply select your
#           nurbsSurface, initialize the Rivet class (var = Rivet()), then run your
#           command:
#               - var.mk_rivet(name, u=0.0, v=0.5) and you can set the u & v values
#               - set_rivets(rivets) set a number of rivets to evenly distribute evenly
#                   along the u values of the nurbs surface
#
###########################################################################################


import maya.cmds as mc
from maya.api.OpenMaya import MMatrix as omm

# Suffix variables
POS = "_pos"
ROT = "_rot"
SCL = "_scale"
GRP = "_grp"
BC = "_bc"
RIV = "_riv"
BIND = "_bind"
FK = "_FK"
IK = "_IK"
FKIK = "_FKIK"

# Attribute variables
POS_ATTR = ".translate"
ROT_ATTR = ".rotate"
SCL_ATTR = ".scale"
OUT = ".output"
MTRXIN = ".inputMatrix"
WM = ".worldMatrix[0]"
NML = ".normal"
TANU = ".tangentU"
TANV = ".tangentV"
VECTORS = ["X", "Y", "Z"]


class Matrix:
    def __init__(self, mo):
        self.mo = mo
        self.drivers = []
        self.driven = []

    def get_driver_driven(self):
        """
        Create parent groups and returns a list of your diven object
        as well as your driver
        """
        objs = mc.ls(sl=True)

        if not len(objs) >= 2 and len(self.driven) == 0:
            # Check to make sure at least two objects are selected
            return mc.error("Please select your driver objects and a driven object")

        for i, obj in enumerate(objs, 1):
            # Sort each selected object so the last object selected is the driven object
            if not mc.objectType(obj) == "transform":
                pass

            driversChk = set(self.drivers)
            drivenChk = set(self.driven)

            if i == len(objs) and len(self.driven) == 0:
                # If the driven list is empty, put the last object selected in that list
                self.driven.append(obj)
            elif obj not in driversChk and obj not in drivenChk:
                # If the object isn't already part of the drivers list, put it there
                self.drivers.append(obj)

        return self.drivers, self.driven[0]

    def mk_parent_grp(self, obj):
        """
        Create a parent_grp and transfer objects transform attributes
        """
        parent = mc.listRelatives(obj, p=True)
        grp = mc.createNode("transform", n="{}{}".format(obj, GRP))
        mc.matchTransform(grp, obj)
        if parent is not None:
            mc.parent(grp, parent[0])
        mc.parent(obj, grp)
        return grp

    def set_offset(self):
        """
        Create a multMatrix that calculates the offset of the driven object to preserve
        its transformation attributes
        """
        multMList = []
        for driver in self.drivers:
            offsetList = []
            offsetAttr = "{}{}.{}Offset".format(self.driven[0], GRP, driver)
            drivenGrpWIM = "{}{}.worldInverseMatrix".format(
                self.driven[0], GRP)
            dOut = "{}{}".format(driver, WM)
            multM = "{}_multM".format(driver)

            # Keep figuring out mult matrix setup
            if not mc.objExists(offsetAttr):
                mc.addAttr("{}{}".format(self.driven[0], GRP), ln="{}Offset".format(
                    driver), nn="{} Offset".format(driver), at="matrix")
            # get the offset matrix value
            drivenWM = omm(mc.getAttr("{}{}".format(self.driven[0], WM)))
            driverWIM = omm(mc.getAttr("{}.worldInverseMatrix".format(driver)))
            # define the offset tramsformation (driver.inverseMatrix * driven.worldMatrix)
            offsetM = driverWIM * drivenWM
            # set offset matrix value
            for item in offsetM:
                offsetList.append(item)
            mc.setAttr(offsetAttr, offsetList[0], offsetList[1], offsetList[2], offsetList[3], offsetList[4], offsetList[5], offsetList[6], offsetList[7],
                       offsetList[8], offsetList[9], offsetList[10], offsetList[11], offsetList[12], offsetList[13], offsetList[14], offsetList[15], type="matrix")

            # Create multMatrix node
            if not mc.objExists(multM):
                mc.shadingNode("multMatrix", asUtility=True, n=multM)
                # Connect multMatrix node
                mc.connectAttr(offsetAttr, "{}.matrixIn[0]".format(multM))
                mc.connectAttr(dOut, "{}.matrixIn[1]".format(multM))
                mc.connectAttr(drivenGrpWIM, "{}.matrixIn[2]".format(multM))

            multMList.append(driver)

        return multMList

    def mk_decomposition(self, obj):
        """
        Create a decompose matrix that will directly drive the driven object
        """
        decMtrx = "{}_decM".format(obj)
        if not mc.objExists(decMtrx):
            # Check to make sure decompose matrix node doesn't already exist
            mc.shadingNode("decomposeMatrix", asUtility=True, n=decMtrx)
        return decMtrx


class Constraint(Matrix):
    def mk_blend(self, decMtrx):
        """
        Create a wtAddMatrix node to combine matrix values of all your driver objects
        that can either be averaged together or create a blend
        """
        blend = "{}_blend".format(self.driven[0])
        if mc.objExists(blend):
            # Check to make sure wtAddMatrix (blend) node doesn't already exist
            return blend

        # Create a wtAddMatrix (blend) node
        mc.shadingNode("wtAddMatrix", asUtility=True, n=blend)

        for i, driver in enumerate(self.drivers):
            # Connect each driver to the wtAddMatrix node
            if self.mo is True:
                # If offset is maintained, driver will need to pass through a multMatrix node first
                dOut = "{}_multM.matrixSum".format(driver)
            else:
                dOut = "{}{}".format(driver, WM)
            mc.connectAttr(
                dOut, "{}.wtMatrix[{}].matrixIn".format(blend, i), f=True)

        # Connct your blended matrix values to the decompose matrix node
        mc.connectAttr("{}.matrixSum".format(blend),
                       "{}{}".format(decMtrx, MTRXIN), f=True)

        return blend

    def mk_switch(self, decMtrx):
        """
        Create a choice node to combine matrix values of all your driver objects that
        will be switched between
        """
        switch = "{}_switch".format(self.driven[0])
        if mc.objExists(switch):
            # Check to make sure choice (switch) node doesn't already exist
            return switch

        # Create a choice (switch) node
        mc.shadingNode("choice", asUtility=True, n=switch)

        for i, driver in enumerate(self.drivers):
            if self.mo is True:
                # If offset is maintained, driver will need to pass through a multMatrix node first
                dOut = "{}_multM.matrixSum".format(driver)
            else:
                dOut = "{}{}".format(driver, WM)
            mc.connectAttr(dOut, "{}.input[{}]".format(switch, i), f=True)

        # Connct your switch to the decompose matrix node
        mc.connectAttr("{}{}".format(switch, OUT),
                       "{}{}".format(decMtrx, MTRXIN), f=True)

        return switch

    def set_avg_blend(self, blender):
        """
        Create a value for evenly applying weighting for each driver object
        """
        if not len(self.drivers) > 1:
            return

        val = "{}_wtVal".format(self.driven[0])
        if mc.objExists(val):
            # Check to make sure object exists
            return val

        # Create a multiply node to generate a blend value
        mc.shadingNode("multDoubleLinear", asUtility=True, n=val)
        # Set the first value to 1/(number of drivers)
        mc.setAttr("{}.input1".format(val), 1.0 / len(self.drivers))
        # Set the second valuse to 1 (so dissapointing Maya doesn't have a simple value node)
        mc.setAttr("{}.input2".format(val), 1)

        for i, driver in enumerate(self.drivers):
            mc.connectAttr("{}{}".format(val, OUT),
                           "{}.wtMatrix[{}].weightIn".format(blender, i))

        return val

    def set_constraint(self, mtrxType, attrs):
        """
        Create your Matrix Constraint network
        """
        self.get_driver_driven()
        dec = self.mk_decomposition(self.driven[0])

        if self.mo is True:
            grp = "{}{}".format(self.driven[0], GRP)
            parent = mc.listRelatives(self.driven[0], p=True)
            if parent is None or parent[0] != grp:
                # Check to see if your driven object has a parent group and, if not, give it one
                self.mk_parent_grp(self.driven[0])
            self.set_offset()

        if len(self.drivers) > 1:
            # If more than one driver is needed, we'll have to combine their world matrices
            if mtrxType == "switch":
                addMtrx = self.mk_switch(dec)
            else:
                addMtrx = self.mk_blend(dec)
        else:
            # Single driver setups can connect directly to the decompose matrix node
            if self.mo is True:
                dOut = "{}_multM.matrixSum".format(self.drivers[0])
            else:
                dOut = "{}{}".format(self.drivers[0], WM)
            mc.connectAttr(dOut, "{}{}".format(dec, MTRXIN))

        for attr in attrs:
            # Connect specified attributes to your driven object
            if attr == POS:
                mtrxAttr = "{}.outputTranslate".format(dec)
                drivenAttr = "{}{}".format(self.driven[0], POS_ATTR)
            if attr == ROT:
                # We first need to make a quatToEuler node to match rotational ordera
                q2e = mc.shadingNode(
                    "quatToEuler", asUtility=True, n="{}_q2e".format(self.driven[0]))
                ro = mc.getAttr("{}.rotateOrder".format(self.driven[0]))
                mc.setAttr("{}.inputRotateOrder".format(q2e), ro)
                mc.connectAttr("{}.outputQuat".format(
                    dec), "{}.inputQuat".format(q2e))
                mtrxAttr = "{}.outputRotate".format(q2e)
                drivenAttr = "{}{}".format(self.driven[0], ROT_ATTR)
            if attr == SCL:
                mtrxAttr = "{}.outputScale".format(dec)
                drivenAttr = "{}{}".format(self.driven[0], SCL_ATTR)

            if not mc.connectionInfo(drivenAttr, id=1):
                # Make sure driven object isn't already receiving a connection...
                mc.connectAttr(mtrxAttr, drivenAttr)
            else:
                # ... or notify the user if it does
                return mc.warning("{} is already receiving an incoming connection.".format(drivenAttr))

        if len(self.drivers) > 1:
            return addMtrx

    def parent(self):
        """
        Create a matrix Parent Constraint
        """
        const = self.set_constraint("blend", [POS, ROT])
        self.set_avg_blend(const)

    def point(self):
        """
        Create a matrix Point Constraint
        """
        const = self.set_constraint("blend", [POS])
        self.set_avg_blend(const)

    def orient(self):
        """
        Create a matrix Orient Constraint
        """
        const = self.set_constraint("blend", [ROT])
        self.set_avg_blend(const)

    def scale(self):
        """
        Create a matrix Scale Constraint
        """
        if len(self.drivers) >= 2:
            return mc.warning("driven objects can only be scale constrained to one driver")
        const = self.set_constraint("blend", [SCL])
        self.set_avg_blend(const)


class BlendColor(Matrix):
    def __init__(self):
        Matrix.__init__(self, mo=False)

    def mk_bc(self, attr):
        """
        Create a blendColor node for each attr driving the driven object
        """
        bc = "{}{}{}".format(self.driven[0], attr, BC)

        if not mc.objExists(bc):
            # Check to make sure blendColor node doesn't exist
            mc.createNode("blendColors", n=bc)

        mc.setAttr(bc + ".color1", 0, 0, 0)
        mc.setAttr(bc + ".color2", 0, 0, 0)

        return bc

    def conn_matrix(self, mtrx, bc):
        """
        Connect the decompose matrix node to blendColor inputs
        """
        for i, m in enumerate(mtrx, 1):
            # For each decomposeMatrix node, connect to blendColor node
            char = bc[len(bc) - 6]

            # Determine the output attribute of the decomposeMatrix node
            if char == "p":
                mAttr = ".outputTranslate"
            if char == "r":
                mAttr = ".outputRotate"
            if char == "s":
                mAttr = ".outputScale"

            # Make the connection
            mc.connectAttr("{}{}".format(m, mAttr),
                           "{}.color{}".format(bc, i))

    def conn_bc(self, bc):
        """
        Connect the blendColor node to the driven attribute
        """
        char = bc[len(bc) - 6]

        # Determine the input attribute of the driven object
        if char == "p":
            dAttr = POS_ATTR
        if char == "r":
            dAttr = ROT_ATTR
        if char == "s":
            dAttr = SCL_ATTR

        # Make the connection
        mc.connectAttr("{}{}".format(bc, OUT),
                       "{}{}".format(self.driven[0], dAttr))

    def set_constraint(self, attrs):
        """
        Create a matrix constraint setup using blendColor nodes
        """
        mtrxList = []
        bcList = []

        self.get_driver_driven()
        if len(self.drivers) > 2:
            # Check to make sure there aren't more than two drivers
            return mc.warning("blendColor constraints can't have mroe than two drivers")

        for driver in self.drivers:
            # Create a decomposeMatrix node for each driver
            dec = "{}_decM".format(driver)
            if not mc.objExists(dec):
                dec = self.mk_decomposition(driver)
                mc.connectAttr("{}{}".format(driver, WM),
                               "{}{}".format(dec, MTRXIN))
            mtrxList.append(dec)

        for attr in attrs:
            # Create a blendColor node for each attribute you want to drive
            bc = "{}{}{}".format(self.driven[0], attr, BC)
            if not mc.objExists(bc):
                bc = self.mk_bc(attr)
            bcList.append(bc)

        for bc in bcList:
            # Connect decomposeMatrix nodes to driven object through blendColor node
            self.conn_matrix(mtrxList, bc)
            self.conn_bc(bc)

        return bcList

    def parent(self):
        """
        Create a matrix-based blendColor Parent Constraint
        """
        bcs = self.set_constraint([POS, ROT])
        return bcs

    def point(self):
        """
        Create a matrix-based blendColor Point Constraint
        """
        bcs = self.set_constraint([POS])
        return bcs

    def orient(self):
        """
        Create a matrix-based blendColor Orient Constraint
        """
        bcs = self.set_constraint([ROT])
        return bcs

    def scale(self):
        """
        Create a matrix-based blendColor Scale Constraint
        """
        bcs = self.set_constraint([SCL])
        return bcs


class Rivet(Matrix):
    def get_driver(self):
        """
        Set selected surface as your driver object
        """
        obj = mc.ls(sl=True)
        if not len(obj) == 1:
            # Can only work with one driver object
            if len(obj) == 0:
                return mc.warning("No objects selected")
            if len(obj) >= 2:
                return mc.warning("Too many objects selected")

        if len(self.drivers) == 0:
            # Object should be the first (or only) object in drivers
            self.drivers.append(obj[0])
        else:
            self.drivers[0] = obj[0]

        for o in obj:
            parent = mc.listRelatives(o, p=True)
            grp = "{}{}".format(o, GRP)
            if parent is None or parent[0] != grp:
                # Check to see if object has a parent group and, if not, give it one
                self.mk_parent_grp(o)

        return obj[0]

    def get_pt_surface(self, riv, u, v):
        """
        Create a pointOnSurface node for your driver surface
        """
        ptSurf = "{}_ptSurf".format(riv)

        shape = mc.listRelatives(self.drivers[0], s=True)[0]
        if not mc.objectType(shape) == "nurbsSurface":
            # Check to make sure incomming geo is a nurbs surface
            return mc.warning("Driver object needs to be a nurbsSurface")

        if not mc.objExists(ptSurf):
            mc.createNode("pointOnSurfaceInfo", n=ptSurf)
        mc.setAttr("{}.parameterU".format(ptSurf), u)
        mc.setAttr("{}.parameterV".format(ptSurf), v)
        mc.connectAttr("{}.worldSpace[0]".format(
            shape), "{}.inputSurface".format(ptSurf))

        return ptSurf

    def mk_4x4_mtrx(self, ptSurf):
        """
        Create a matrix that defines the world space of a rivet
        """
        mtrx = ptSurf.replace("ptSurf", "mtrx")
        attrs = [NML, TANU, TANV, ".position"]

        if not mc.objExists(mtrx):
            mc.shadingNode("fourByFourMatrix", asUtility=True, n=mtrx)

        for i, attr in enumerate(attrs):
            # Make a connection for each matrix attribute...
            for j, v in enumerate(VECTORS):
                # ...and vector directions per attribute
                if attr == TANU or attr == TANV:
                    v = v.lower()

                mc.connectAttr("{}{}{}".format(ptSurf, attr, v),
                               "{}.in{}{}".format(mtrx, i, j))
        return mtrx

    def mk_rivet(self, name, u=0.0, v=0.5):
        """
        Create a rivet based on a defined uValue and vVaule
        """
        if mc.objExists(name):
            return name

        if len(self.drivers) == 0:
            self.get_driver()

        driverDecM = self.mk_decomposition(self.drivers[0])

        if not mc.connectionInfo("{}{}".format(driverDecM, MTRXIN), id=1):
            # Check to make sure decompose matrix is receiving data from driver
            mc.connectAttr("{}{}".format(
                self.drivers[0], WM), "{}{}".format(driverDecM, MTRXIN))

        riv = mc.spaceLocator(n=name)[0]
        mc.setAttr("{}.inheritsTransform".format(riv), 0)

        # Create the nodes
        ptSurf = self.get_pt_surface(riv, u, v)
        mtrx = self.mk_4x4_mtrx(ptSurf)
        decM = self.mk_decomposition(riv)

        # Connect the nodes
        mc.connectAttr("{}{}".format(mtrx, OUT),
                       "{}{}".format(decM, MTRXIN))
        mc.connectAttr("{}.outputTranslate".format(
            decM), "{}{}".format(riv, POS_ATTR))
        mc.connectAttr("{}.outputRotate".format(
            decM), "{}{}".format(riv, ROT_ATTR))
        mc.connectAttr("{}.outputScale".format(
            driverDecM), "{}{}".format(riv, SCL_ATTR))

        return riv

    def set_rivets(self, rivets):
        """
        Create a given number of rivets set eavenly across the Uvalue of a nurbsSurface
        """
        rivList = []
        self.get_driver()
        rivGrp = mc.createNode(
            "transform", n="{}{}{}".format(self.drivers[0], RIV, GRP))

        for rivet, i in enumerate(range(rivets), 1):
            # Create a locator and matrix constraint network
            if rivet == 1:
                uVal = 0
            elif rivet == rivets:
                uVal = 1
            else:
                uVal = i / (rivets - 1.0)

            # Create the rivet
            riv = self.mk_rivet("{}{}{}".format(
                self.drivers[0], RIV, str(rivet).zfill(2)), uVal)
            mc.parent(riv, rivGrp)
            rivList.append(riv)

        # Organize the outliner
        mc.parent(rivGrp, "{}{}".format(self.drivers[0], GRP))
        return rivList
