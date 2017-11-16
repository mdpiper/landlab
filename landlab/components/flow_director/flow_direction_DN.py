#! /usr/env/python

"""
flow_direction_DN.py: calculates single-direction flow directions.

Works on both a regular or irregular grid.

GT Nov 2013
Modified Feb 2014
"""
import numpy as np

from landlab import BAD_INDEX_VALUE
from landlab.grid.raster_steepest_descent import (
    _calc_steepest_descent_across_cell_faces)
from landlab.core.utils import as_id_array

from .cfuncs import adjust_flow_receivers


UNDEFINED_INDEX = BAD_INDEX_VALUE


def grid_flow_directions(grid, elevations):

    """Flow directions on raster grid.

    Calculate flow directions for node elevations on a raster grid.
    Each node is assigned a single direction, toward one of its neighboring
    nodes (or itself, if none of its neighbors are lower). There is only
    flow from one node to another if there is a negative gradient. If a
    node's steepest gradient is >= 0., then its slope is set to zero and
    its receiver node is listed as itself.

    Parameters
    ----------
    grid : RasterModelGrid
        a raster grid.
    elevations: ndarray
        Node elevations.

    Returns
    -------
    receiver : (ncells, ) ndarray
        For each cell, the node in the direction of steepest descent, or
        itself if no downstream nodes.
    steepest_slope : (ncells, ) ndarray
        The slope value in the steepest direction of flow.

    Notes
    -----
    This function considers only nodes that have four neighbors. Thus, only
    calculate flow directions and slopes for nodes that have associated
    cells.

    Examples
    --------
    This example calculates flow routing on a (4,5) raster grid with the
    following node elevations::

        5 - 5 - 5 - 5 - 5
        |   |   |   |   |
        5 - 3 - 4 - 3 - 5
        |   |   |   |   |
        5 - 1 - 2 - 2 - 5
        |   |   |   |   |
        5 - 0 - 5 - 5 - 5

    >>> import numpy as np
    >>> from landlab import RasterModelGrid
    >>> from landlab.components.flow_routing import grid_flow_directions
    >>> mg = RasterModelGrid(4,5)
    >>> z = np.array([5., 0., 5., 5., 5.,
    ...               5., 1., 2., 2., 5.,
    ...               5., 3., 4., 3., 5.,
    ...               5., 5., 5., 5., 5.])
    >>> recv_nodes, slope = grid_flow_directions(mg, z)

    Each node with a cell has a receiving node (although that node may be
    itself).

    >>> recv_nodes
    array([1, 6, 8, 6, 7, 8])

    All positive gradients are clipped to zero.

    >>> slope
    array([-1., -1.,  0., -2., -2., -1.])

    If a cell has no surrounding neighbors lower than itself, it is a sink.
    Use :attr:`~landlab.grid.base.ModelGrid.node_at_cell` to get the
    nodes associated with the cells.

    >>> sink_cells = np.where(slope >= 0)[0]
    >>> list(sink_cells)
    [2]
    >>> mg.node_at_cell[sink_cells] # Sink nodes
    array([8])

    The source/destination node pairs for the flow.

    >>> list(zip(mg.node_at_cell, recv_nodes))
    [(6, 1), (7, 6), (8, 8), (11, 6), (12, 7), (13, 8)]
    """
    slope, receiver = _calc_steepest_descent_across_cell_faces(
        grid, elevations, return_node=True)

    (sink_cell, ) = np.where(slope >= 0.)
    receiver[sink_cell] = grid.node_at_cell[sink_cell]
    slope[sink_cell] = 0.

    return receiver, slope


def flow_directions(elev, active_links, tail_node, head_node, link_slope,
                    grid=None, baselevel_nodes=None):
    """Find flow directions on a grid.

    Finds and returns flow directions for a given elevation grid. Each node is
    assigned a single direction, toward one of its N neighboring nodes (or
    itself, if none of its neighbors are lower).

    Parameters
    ----------
    elev : array_like
        Elevations at nodes.
    active_links : array_like
        IDs of active links.
    tail_node : array_like
        IDs of the tail node for each link.
    head_node : array_like
        IDs of the head node for each link.
    link_slope : array_like
        slope of each link, defined POSITIVE DOWNHILL (i.e., a negative value
        means the link runs uphill from the fromnode to the tonode).
    baselevel_nodes : array_like, optional
        IDs of open boundary (baselevel) nodes.

    Returns
    -------
    receiver : ndarray
        For each node, the ID of the node that receives its flow. Defaults to
        the node itself if no other receiver is assigned.
    steepest_slope : ndarray
        The slope value (positive downhill) in the direction of flow
    sink : ndarray
        IDs of nodes that are flow sinks (they are their own receivers)
    receiver_link : ndarray
        ID of link that leads from each node to its receiver, or
        UNDEFINED_INDEX if none.

    Examples
    --------
    The example below assigns elevations to the 10-node example network in
    Braun and Willett (2012), so that their original flow pattern should be
    re-created.

    >>> import numpy as np
    >>> from landlab.components.flow_routing import flow_directions
    >>> z = np.array([2.4, 1.0, 2.2, 3.0, 0.0, 1.1, 2.0, 2.3, 3.1, 3.2])
    >>> fn = np.array([1,4,4,0,1,2,5,1,5,6,7,7,8,6,3,3,2,0])
    >>> tn = np.array([4,5,7,1,2,5,6,5,7,7,8,9,9,8,8,6,3,3])
    >>> s = z[fn] - z[tn]  # slope with unit link length, positive downhill
    >>> active_links = np.arange(len(fn))
    >>> r, ss, snk, rl = flow_directions(z, active_links, fn, tn, s)
    >>> r
    array([1, 4, 1, 6, 4, 4, 5, 4, 6, 7])
    >>> ss
    array([ 1.4,  1. ,  1.2,  1. ,  0. ,  1.1,  0.9,  2.3,  1.1,  0.9])
    >>> snk
    array([4])
    >>> rl[3:8]
    array([15, -1,  1,  6,  2])
    """
    # OK, the following are rough notes on design: we want to work with just
    # the active links. Ways to do this:
    # *  Pass active_links in as argument
    # *  In calling code, only refer to receiver_links for active nodes

    # Setup
    num_nodes = len(elev)
    steepest_slope = np.zeros(num_nodes)
    receiver = np.arange(num_nodes)
    receiver_link = UNDEFINED_INDEX + np.zeros(num_nodes, dtype=np.int)

    # For each link, find the higher of the two nodes. The higher is the
    # potential donor, and the lower is the potential receiver. If the slope
    # from donor to receiver is steeper than the steepest one found so far for
    # the donor, then assign the receiver to the donor and record the new slope.
    # (Note the minus sign when looking at slope from "t" to "f").
    #
    # NOTE: MAKE SURE WE ARE ONLY LOOKING AT ACTIVE LINKS
    #THIS REMAINS A PROBLEM AS OF DEJH'S EFFORTS, MID MARCH 14.
    #overridden as part of fastscape_stream_power

    adjust_flow_receivers(tail_node, head_node, elev, link_slope,
                          active_links, receiver, receiver_link,
                          steepest_slope)

    node_id = np.arange(num_nodes)

    # Optionally, handle baselevel nodes: they are their own receivers
    if baselevel_nodes is not None:
        receiver[baselevel_nodes] = node_id[baselevel_nodes]
        receiver_link[baselevel_nodes] = UNDEFINED_INDEX
        steepest_slope[baselevel_nodes] = 0.

    # The sink nodes are those that are their own receivers (this will normally
    # include boundary nodes as well as interior ones; "pits" would be sink
    # nodes that are also interior nodes).
    (sink, ) = np.where(node_id==receiver)
    sink = as_id_array(sink)

    return receiver, steepest_slope, sink, receiver_link
