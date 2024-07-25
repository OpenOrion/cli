from typing import Optional, Union
import cadquery as cq
from pydantic import BaseModel
from OCP.gp import gp_Ax2
from OCP.BRepLib import BRepLib
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.HLRAlgo import HLRAlgo_Projector
from cadquery.occ_impl.shapes import TOLERANCE
from cadquery.occ_impl.exporters.svg import PATHTEMPLATE, getPaths, guessUnitOfMeasure, AXES_TEMPLATE

SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg
    xmlns:svg="http://www.w3.org/2000/svg"
    xmlns="http://www.w3.org/2000/svg"
    width="%(width)s"
    height="%(height)s"

>
     <style>
          path {
          stroke: black;
          }
          @media (prefers-color-scheme: dark) {
          path {
          stroke: white;
          }
          }
     </style>

     <g transform="scale(%(unitScale)s, -%(unitScale)s)   translate(%(xTranslate)s,%(yTranslate)s)" stroke-width="%(strokeWidth)s"  fill="none">
         <!-- hidden lines -->
         <g  stroke="rgb(%(hiddenColor)s)" fill="none" stroke-dasharray="%(strokeWidth)s,%(strokeWidth)s" >
%(hiddenContent)s
         </g>

         <!-- solid lines -->
         <g  stroke="rgb(%(strokeColor)s)" fill="none">
%(visibleContent)s
         </g>
     </g>
     %(axesIndicator)s
</svg>
"""

class SVGOptions(BaseModel):
     width: int = 800
     height: int = 240
     marginLeft: float = 200
     marginTop: float = 20
     projectionDir: tuple = (-1.75, 1.1, 5)
     showAxes: bool = True
     strokeWidth: float = -1.0
     strokeColor: tuple = (0, 0, 0)
     hiddenColor: tuple = (160, 160, 160)
     showHidden: bool = True
     focus: Optional[float] = None

class AssetHelper:
     @staticmethod
     def getSVG(shape: Union[cq.Shape, cq.Assembly], opts: Optional[SVGOptions] = None):
          """
          Export a shape to SVG text.

          :param shape: A CadQuery shape object to convert to an SVG string.
          :type Shape: Vertex, Edge, Wire, Face, Shell, Solid, or Compound.
          :param opts: An options object that influences the SVG that is output.
          :type opts: SVGOptions
          """
          shape = shape if isinstance(shape, cq.Shape) else shape.toCompound()
          # Default options
          d = SVGOptions()

          if opts:
                d = opts

          # need to guess the scale and the coordinate center
          uom = guessUnitOfMeasure(shape)

          # Handle the case where the height or width are None
          width = d.width if d.width is not None else 800
          height = d.height if d.height is not None else 240
          marginLeft = d.marginLeft
          marginTop = d.marginTop
          projectionDir = tuple(d.projectionDir)
          showAxes = d.showAxes
          strokeWidth = d.strokeWidth
          strokeColor = tuple(d.strokeColor)
          hiddenColor = tuple(d.hiddenColor)
          showHidden = d.showHidden
          focus = d.focus

          hlr = HLRBRep_Algo()
          hlr.Add(shape.wrapped)

          projection_origin = shape.Center()
          projection_dir = cq.Vector((1, -1, 1)).normalized()
          projection_x = cq.Vector((0, 0, 1)).normalized().cross(projection_dir)
          coordinate_system = gp_Ax2(
                projection_origin.toPnt(), projection_dir.toDir(), projection_x.toDir()
          )

          if focus is not None:
                projector = HLRAlgo_Projector(coordinate_system, focus)
          else:
                projector = HLRAlgo_Projector(coordinate_system)

          hlr.Projector(projector)
          hlr.Update()
          hlr.Hide()

          hlr_shapes = HLRBRep_HLRToShape(hlr)

          visible = []

          visible_sharp_edges = hlr_shapes.VCompound()
          if not visible_sharp_edges.IsNull():
                visible.append(visible_sharp_edges)

          visible_smooth_edges = hlr_shapes.Rg1LineVCompound()
          if not visible_smooth_edges.IsNull():
                visible.append(visible_smooth_edges)

          visible_contour_edges = hlr_shapes.OutLineVCompound()
          if not visible_contour_edges.IsNull():
                visible.append(visible_contour_edges)

          hidden = []

          hidden_sharp_edges = hlr_shapes.HCompound()
          if not hidden_sharp_edges.IsNull():
                hidden.append(hidden_sharp_edges)

          hidden_contour_edges = hlr_shapes.OutLineHCompound()
          if not hidden_contour_edges.IsNull():
                hidden.append(hidden_contour_edges)

          # Fix the underlying geometry - otherwise we will get segfaults
          for el in visible:
                BRepLib.BuildCurves3d_s(el, TOLERANCE)
          for el in hidden:
                BRepLib.BuildCurves3d_s(el, TOLERANCE)

          # convert to native CQ objects
          visible = list(map(cq.Shape, visible))
          hidden = list(map(cq.Shape, hidden))
          (hiddenPaths, visiblePaths) = getPaths(visible, hidden)

          # get bounding box -- these are all in 2D space
          bb = cq.Compound.makeCompound(hidden + visible).BoundingBox()

          # Determine whether the user wants to fit the drawing to the bounding box
          if width is None or height is None:
                # Fit image to specified width (or height)
                if width is None:
                     width = (height - (2.0 * marginTop)) * (
                          bb.xlen / bb.ylen
                     ) + 2.0 * marginLeft
                else:
                     height = (width - 2.0 * marginLeft) * (bb.ylen / bb.xlen) + 2.0 * marginTop

                # width pixels for x, height pixels for y
                unitScale = (width - 2.0 * marginLeft) / bb.xlen
          else:
                bb_scale = 0.75
                # width pixels for x, height pixels for y
                unitScale = min(width / bb.xlen * bb_scale, height / bb.ylen * bb_scale)

          # compute amount to translate-- move the top left into view
          (xTranslate, yTranslate) = (
                (0 - bb.xmin) + marginLeft / unitScale,
                (0 - bb.ymax) - marginTop / unitScale,
          )

          # If the user did not specify a stroke width, calculate it based on the unit scale
          if strokeWidth == -1.0:
                strokeWidth = 1.0 / unitScale

          # compute paths
          hiddenContent = ""

          # Prevent hidden paths from being added if the user disabled them
          if showHidden:
                for p in hiddenPaths:
                     hiddenContent += PATHTEMPLATE % p

          visibleContent = ""
          for p in visiblePaths:
                visibleContent += PATHTEMPLATE % p

          # If the caller wants the axes indicator and is using the default direction, add in the indicator
          if showAxes and projectionDir == (-1.75, 1.1, 5):
                axesIndicator = AXES_TEMPLATE % (
                     {"unitScale": str(unitScale), "textboxY": str(height - 30), "uom": str(uom)}
                )
          else:
                axesIndicator = ""

          svg = SVG_TEMPLATE % (
                {
                     "unitScale": str(unitScale),
                     "strokeWidth": str(strokeWidth),
                     "strokeColor": ",".join([str(x) for x in strokeColor]),
                     "hiddenColor": ",".join([str(x) for x in hiddenColor]),
                     "hiddenContent": hiddenContent,
                     "visibleContent": visibleContent,
                     "xTranslate": str(xTranslate),
                     "yTranslate": str(yTranslate),
                     "width": str(width),
                     "height": str(height),
                     "textboxY": str(height - 30),
                     "uom": str(uom),
                     "axesIndicator": axesIndicator,
                }
          )

          return svg
