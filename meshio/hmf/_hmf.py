import warnings

import h5py
import meshio

from .._common import cell_data_from_raw, raw_from_cell_data
from .._helpers import register
from ..xdmf.common import meshio_to_xdmf_type, xdmf_to_meshio_type


def read(filename):
    with h5py.File(filename, "r") as f:
        assert f.attrs["type"] == "hmf"
        assert f.attrs["version"] == "0.1-alpha"

        assert len(f) == 1, "only one domain supported for now"
        domain = f["domain"]

        assert len(domain) == 1, "only one grid supported for now"
        grid = domain["grid"]

        points = None
        cells = {}
        point_data = {}
        cell_data_raw = {}

        for key, value in grid.items():
            if key[:8] == "Topology":
                cell_type = value.attrs["TopologyType"]
                cells[xdmf_to_meshio_type[cell_type]] = value[()]

            elif key == "Geometry":
                # TODO is GeometryType really needed?
                assert value.attrs["GeometryType"] in ["XY", "XYZ"]
                points = value[()]

            elif key == "CellAttributes":
                for name, ca in value.items():
                    cell_data_raw[name] = ca[()]

            else:
                assert key == "NodeAttributes"
                for name, na in value.items():
                    point_data[name] = na[()]

        cell_data = cell_data_from_raw(cells, cell_data_raw)

        print(cells)
        print(cell_data)

        return meshio.Mesh(
            points,
            cells,
            point_data=point_data,
            cell_data=cell_data,
        )


def write_points_cells(filename, points, cells, **kwargs):
    write(filename, meshio.Mesh(points, cells), **kwargs)


def write(filename, mesh, compression="gzip", compression_opts=4):
    warnings.warn("Experimental file format. Format can change at any time.")
    with h5py.File(filename, "w") as h5_file:
        h5_file.attrs["type"] = "hmf"
        h5_file.attrs["version"] = "0.1-alpha"
        domain = h5_file.create_group("domain")
        grid = domain.create_group("grid")

        _write_points(grid, mesh.points, compression, compression_opts)
        _write_cells(mesh.cells, grid, compression, compression_opts)
        _write_point_data(mesh.point_data, grid, compression, compression_opts)
        _write_cell_data(mesh.cell_data, grid, compression, compression_opts)


def _write_points(grid, points, compression, compression_opts):
    if points.shape[1] == 1:
        geometry_type = "X"
    elif points.shape[1] == 2:
        geometry_type = "XY"
    else:
        assert points.shape[1] == 3
        geometry_type = "XYZ"

    geo = grid.create_dataset(
        "Geometry",
        data=points,
        compression=compression,
        compression_opts=compression_opts,
    )
    geo.attrs["GeometryType"] = geometry_type


def _write_cells(cell_blocks, grid, compression, compression_opts):
    for k, cell_block in enumerate(cell_blocks):
        xdmf_type = meshio_to_xdmf_type[cell_block.type][0]
        topo = grid.create_dataset(
            f"Topology{k}",
            data=cell_block.data,
            compression=compression,
            compression_opts=compression_opts,
        )
        topo.attrs["TopologyType"] = xdmf_type


# In XDMF, the point/cell data are stored as
#
# <Attribute Name="phi" AttributeType="Scalar" Center="Node">
#   <DataItem DataType="Float" Dimensions="4" Format="HDF" Precision="8">
#     out.h5:/data2
#   </DataItem>
# </Attribute>
#
# We cannot register multiple entries with the same name in HDF, so instead of
# "Attribute", use
#
# NodeAttributes
#   -> name0 + data0
#   -> name1 + data0
#   -> ...
# CellAttributes
#   -> ...
#
def _write_point_data(point_data, grid, compression, compression_opts):
    na = grid.create_group("NodeAttributes")
    for name, data in point_data.items():
        na.create_dataset(
            name,
            data=data,
            compression=compression,
            compression_opts=compression_opts,
        )


def _write_cell_data(cell_data, grid, compression, compression_opts):
    raw = raw_from_cell_data(cell_data)
    ca = grid.create_group("CellAttributes")
    for name, data in raw.items():
        ca.create_dataset(
            name,
            data=data,
            compression=compression,
            compression_opts=compression_opts,
        )


# TODO register all xdmf except hdf outside this try block
register(
    "hmf",
    [".hmf"],
    read,
    {"hmf": write},
)
