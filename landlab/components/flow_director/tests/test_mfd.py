
import pytest
import numpy as np
from numpy.testing import assert_array_equal

from landlab import RasterModelGrid
from landlab.components import FlowDirectorMFD
from landlab.components.flow_director import flow_direction_mfd


def test_bad_argument_mfd():
    mg = RasterModelGrid((5, 5), spacing=(1, 1))
    z = mg.add_field("topographic__elevation", mg.node_x + mg.node_y, at="node")

    neighbors_at_node = mg.adjacent_nodes_at_node
    links_at_node = mg.links_at_node
    active_link_dir_at_node = mg.active_link_dirs_at_node
    link_slope = np.arctan(mg.calc_grad_at_link(z))
    slopes_to_neighbors_at_node = link_slope[links_at_node] * active_link_dir_at_node

    with pytest.raises(ValueError):
        flow_direction_mfd.flow_directions_mfd(
            z,
            neighbors_at_node,
            links_at_node,
            active_link_dir_at_node,
            link_slope,
            partition_method="foo",
        )


def test_mfd_on_flat_terrain():
    mg = RasterModelGrid((5, 4), spacing=(1, 1))
    mg.add_zeros("node", "topographic__elevation")

    fd = FlowDirectorMFD(mg)
    fd.run_one_step()

    node_ids = np.arange(mg.number_of_nodes)
    true_recievers = -1 * np.ones(fd.receivers.shape)
    true_recievers[:, 0] = node_ids

    true_proportions = np.zeros(fd.proportions.shape)
    true_proportions[:, 0] = 1

    assert_array_equal(fd.receivers, true_recievers)
    assert_array_equal(
        np.round(fd.proportions, decimals=6), np.round(true_proportions, decimals=6)
    )


def test_mfd_flat_closed_lower():
    mg = RasterModelGrid((5, 4), spacing=(1, 1))
    z = mg.add_zeros("node", "topographic__elevation")
    z[mg.core_nodes] += 1
    mg.set_closed_boundaries_at_grid_edges(
        bottom_is_closed=True,
        left_is_closed=True,
        right_is_closed=True,
        top_is_closed=True,
    )

    fd = FlowDirectorMFD(mg)
    fd.run_one_step()

    node_ids = np.arange(mg.number_of_nodes)
    true_recievers = -1 * np.ones(fd.receivers.shape)
    true_recievers[:, 0] = node_ids

    true_proportions = np.zeros(fd.proportions.shape)
    true_proportions[:, 0] = 1

    assert_array_equal(fd.receivers, true_recievers)
    assert_array_equal(
        np.round(fd.proportions, decimals=6), np.round(true_proportions, decimals=6)
    )


def test_mfd_flat_closed_upper():
    mg = RasterModelGrid((5, 4), spacing=(1, 1))
    z = mg.add_zeros("node", "topographic__elevation")
    z[mg.core_nodes] -= 1
    mg.set_closed_boundaries_at_grid_edges(
        bottom_is_closed=True,
        left_is_closed=True,
        right_is_closed=True,
        top_is_closed=True,
    )

    fd = FlowDirectorMFD(mg)
    fd.run_one_step()

    node_ids = np.arange(mg.number_of_nodes)
    true_recievers = -1 * np.ones(fd.receivers.shape)
    true_recievers[:, 0] = node_ids

    true_proportions = np.zeros(fd.proportions.shape)
    true_proportions[:, 0] = 1

    assert_array_equal(fd.receivers, true_recievers)
    assert_array_equal(
        np.round(fd.proportions, decimals=6), np.round(true_proportions, decimals=6)
    )
