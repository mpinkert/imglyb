import numpy as np

import imglyb
from .accesses import *
from .types import for_np_dtype
from jnius import autoclass, PythonJavaClass, java_method

Cell                        = autoclass('net.imglib2.img.cell.Cell')
CellGrid                    = autoclass('net.imglib2.img.cell.CellGrid')
SoftRefLoaderCache          = autoclass('net.imglib2.cache.ref.SoftRefLoaderCache')
CachedCellImg               = autoclass('net.imglib2.cache.img.CachedCellImg')
GuardedStrongRefLoaderCache = autoclass('net.imglib2.cache.ref.GuardedStrongRefLoaderCache')
PythonHelpers               = autoclass('net.imglib2.python.Helpers')


def as_cached_cell_img(func, cell_grid, dtype, cache_generator=SoftRefLoaderCache, volatile=False):
    loader      = CacheLoaderFromFunction(func, cell_grid)
    cache       = cache_generator().withLoader(loader)
    t           = for_np_dtype(dtype, volatile=False)
    img         = CachedCellImg(cell_grid, t.getEntitiesPerPixel(), cache, as_array_access(np.zeros((0,), dtype=dtype)))
    linked_type = t.getNativeTypeFactory().createLinkedType(img)
    img.setLinkedType(linked_type)
    return img


class CacheLoaderFromFunction(PythonJavaClass):
    __javainterfaces__ = ['net/imglib2/cache/CacheLoader']

    def __init__(self, func, cell_grid, volatile=False):
        super(CacheLoaderFromFunction, self).__init__()
        self.func      = func
        self.cell_grid = cell_grid
        self.volatile  = volatile

    @java_method('(Ljava/lang/Object;)Ljava/lang/Object;', name='get')
    def get(self, index):
        chunk      = self.func(index)
        refGuard   = imglyb.util.ReferenceGuard(chunk)
        address    = chunk.ctypes.data

        try:
            pos    = PythonHelpers.cellMin(self.cell_grid, index)
            target = as_array_access(chunk, volatile=self.volatile)
            cell   = Cell(chunk.shape[::-1], pos, target)
        except JavaException as e:
            print('Name    --', e.classname)
            print('Message --', e.innermessage)
            print('Stack trace --', e.stacktrace)
            raise e
        return cell

try:
    import dask
    import dask.array
    def dask_array_as_cached_cell_img(
            dask_array,
            chunk_size=None,
            cache_generator=SoftRefLoaderCache,
            volatile=False):
        slices     = dask.array.core.slices_from_chunks(dask_array.chunks)
        dims       = dask_array.shape
        block_size = chunk_size if chunk_size else tuple(c[0] for c in dask_array.chunks)
        return as_cached_cell_img(
            func            = lambda index : dask_array[slices[index]].compute(),
            cell_grid       = PythonHelpers.makeGrid(dims, block_size),
            dtype           = dask_array.dtype,
            cache_generator = cache_generator,
            volatile        = volatile
        )

except ImportError as e:
    print("[WARN] Unable to import dask -- dask to imglib2 wrappers not available!")