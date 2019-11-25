import enum
import struct
from .base import FileFormatError
from .valuetype import vpack1, vpack, vunpack, vunpack1_from, \
    check_type_compat

__all__ = ['PageTypes', 'Page', 'PagingFile', 'create_cell', 'INVALID_OFF']

class PageTypes(enum.IntEnum):
    IndexInterior = 2
    TableInterior = 5
    IndexLeaf = 10
    TableLeaf = 13

s_page_header = struct.Struct('>BxHHIIxx')
s_page_offs = struct.Struct('>H')

INVALID_OFF = 0xffffffff

def require_params(params, *names):
    for n in names:
        if params.get(n, None) == None:
            raise ValueError(f'Require parameter "{n}"')


class DataCell(object):
    ''' Abstract superclass representing a data cell within a page block. This
    contains only the attributes (and perhaps attributes of its subclasss also)
    to allow easy updating of attributes '''

    __slots__ = ['left_child', 'rowid', 'tuple_types']
    def __init__(self, tuple_types, **params):
        if type(self) == DataCell:
            raise ValueError('Instantiation of abstract type')
        self.tuple_types = tuple_types
        self.left_child = None
        self.rowid = None
        for key, val in params.items():
            setattr(self, key, val)

    def display(self, tablevel = 0):
        ''' Displays this data cell as a multiline entity '''
        raise NotImplementedError('Abstract method')

    def load_payload(self, payload):
        ''' Loads the payload part of this cell into the cell '''
        raise NotImplementedError('Abstract method')

    def store_payload(self):
        ''' Packs the payload part of this cell into bytes (if any) '''
        raise NotImplementedError('Abstract method')
        
class IndexLeafCell(DataCell):
    ''' This is a leaf cell of an index b tree '''

    __slots__ = ['rowids', 'key']
    _head = struct.Struct('>0sH0s')
    def __init__(self, *params, **kparams):
        super().__init__(*params **kparams)
        self.rowids = []
        self.key = b''
        if len(self.tuple_types) != 1:
            raise FileFormatError('Mismatch size of tuple length')

    def display(self, tablevel = 0):
        tb = '  ' * tablevel
        return f'{tb}IndexLeafCell {{\n' + \
                f'{tb}  key: {repr(self.key)}\n' + \
                f'{tb}  rowids: {repr(rowids)}\n' + \
                f'{tb}}}'

    def load_payload(self, payload):
        if len(payload) < 2:
            raise FileFormatError('Invalid payload size')

        nids = payload[0]
        check_type_compat(self.tuple_types[0], payload[1])
        self.key, key_size = vunpack1_from(payload, 1)
        if len(payload) != key_size + 1 + 4 * nids:
            raise FileFormatError('Invalid payload size')

        self.rowids = set(struct.iter_unpack('>I', payload[key_size + 1:]))

    def store_payload(self):
        nrows = len(self.rowids)
        if nrows > 255:
            raise FileFormatError('Too many row IDs')
        return bytes([nrows]) + vpack1(self.tuple_types[0], self.key) + \
                struct.pack('>' + 'I' * nrows, *self.rowids)

class TableLeafCell(DataCell):
    ''' This is a leaf cell of a table b+ tree '''

    __slots__ = ['tuples']
    _head = struct.Struct('>0sHI')
    def __init__(self, *params, **kparams):
        require_params(kparams, 'rowid')
        super().__init__(*params, **kparams)

    def display(self, tablevel = 0):
        tb = '  ' * tablevel
        ret = f'{tb}TableLeafCell {{\n' + \
                f'{tb}  rowid: {hex(self.rowid)},\n' + \
                f'{tb}  tuples: {repr(self.tuples)}\n' + \
                f'{tb}}}'
        return ret

    def load_payload(self, payload):
        tuples = vunpack(payload)
        if len(tuples) != len(self.tuple_types):
            raise FileFormatError('Mismatch tuple sizes')
        for exp, act in zip(self.tuple_types, list(payload[1:1 + len(tuples)])):
            check_type_compat(exp, act)
        self.tuples = tuples

    def store_payload(self):
        return vpack(self.tuple_types, *self.tuples)

class IndexInteriorCell(IndexLeafCell):
    ''' This is a interior cell of an index b tree '''

    __slots__ = []
    _head = struct.Struct('>IH0s')
    def __init__(self, *params, **kparams):
        require_params(kparams, 'left_child')
        super().__init__(*params, **kparams)

    def display(self, tablevel = 0):
        tb = '  ' * tablevel
        return f'{tb}IndexInteriorCell {{\n' + \
                f'{tb}  left_child: {hex(self.left_child)}\n' + \
                f'{tb}  key: {repr(self.key)}\n' + \
                f'{tb}  rowids: {repr(rowids)}\n' + \
                f'{tb}}}'

class TableInteriorCell(DataCell):
    ''' This is a interior cell of a table b+ tree '''

    __slots__ = []
    _head = struct.Struct('>I0sI')
    def __init__(self, *params, **kparams):
        require_params(kparams, 'left_child', 'rowid')
        super().__init__(*params, **kparams)

    def load_payload(self, payload):
        raise FileFormatError('No payload needed')

    def store_payload(self):
        return b''

    def display(self, tablevel = 0):
        tb = '  ' * tablevel
        return f'{tb}TableInteriorCell {{ left_child: {hex(self.left_child)} }}'

_cells = {
        PageTypes.TableLeaf: TableLeafCell,
        PageTypes.IndexLeaf: TableLeafCell,
        PageTypes.TableInterior: TableInteriorCell,
        PageTypes.IndexInterior: TableInteriorCell,
    }

def create_cell(ptype, *params, **kparams):
    return _cells[ptype](*params, **kparams)

def null(tup):
    ret = []
    for t in tup:
        if t == b'':
            t = None
        ret.append(t)
    return tuple(ret)

def unnull(tup):
    ret = []
    for t in tup:
        if t == None:
            t = b''
        ret.append(t)
    return tuple(ret)


class Page(object):
    ''' This is a page object that represents a page within an index or table
    file. This contains only the attributes of such a page, and not the actual
    bytes itself (to allow for easy updating). '''

    __slots__ = ['cur_pnum', '_type', 'pnum_right', 'pnum_parent', 'cells',
            'tuple_types']

    

    @staticmethod
    def get_page_header_size(self):
        return s_page_header.size

    def __init__(self, pagenum, ptype, tuple_types, pnum_right,
            pnum_parent, cells = []):
        self.cur_pnum = pagenum
        self.type = ptype
        self.tuple_types = tuple_types
        self.pnum_right = pnum_right
        self.pnum_parent = pnum_parent
        self.cells = list(cells)

    def __str__(self):
        return f'Page({self.type})'

    def __repr__(self):
        return self.display(0)

    def _get_type(self):
        return self._type
    def _set_type(self, newtype):
        self._type = PageTypes(newtype)
    type = property(_get_type, _set_type)

    def display(self, tablevel = 0):
        tb = '  ' * tablevel
        ret = f'{tb}Page({self.cur_pnum}) {{\n' +  \
                f'{tb}  type: {self.type.name},\n' + \
                f'{tb}  pnum_right: {hex(self.pnum_right)},\n' + \
                f'{tb}  pnum_parent: {hex(self.pnum_parent)},\n' + \
                f'{tb}  cells: [\n'
        for c in self.cells:
            ret += c.display(tablevel + 2) + ',\n'
        ret += f'{tb}  ]\n{tb}}}'
        return ret

    def unpack_cell_from(self, buff, offset = 0):
        ''' Unpacks byte data from an offset to a cell object exposing its
        attributes. This page will not automatically add it to itself, but if
        this should be added, the user can simply modify the array field "cells"
        that is exposed from this object. '''

        cell_type = _cells[self.type]
        head = cell_type._head
        left_child, payload_size, rowid = null(head.unpack_from(buff, offset))

        if payload_size == 0:
            raise FileFormatError('Invalid payload size')

        if payload_size:
            poff = offset + head.size
            if payload_size + poff > len(buff):
                raise FileFormatError('Invalid payload size')
            payload = buff[poff:poff + payload_size]
        else:
            payload_size = 0
            payload = None

        cell = cell_type(self.tuple_types, left_child = left_child, 
                rowid = rowid)
        if payload: cell.load_payload(payload)
        return (cell, payload_size + head.size)

    def pack_cell(self, cell):
        ''' This will pack a cell according to the type specs of this page
        object. Note that the correct cell type should be passed, that matches
        our page type. 
        
        A FileFormatError is raised if the cell attributes being packed violates
        the file format expected '''

        cell_type = _cells[self.type]
        if cell_type != type(cell):
            raise FileFormatError(f'Expected a cell type of {cell_type}, ' + \
                    f'got {type(cell)}')
        head = cell_type._head

        payload = cell.store_payload()
        payload_size = None
        if payload:
            payload_size = len(payload)

        return head.pack(*unnull([cell.left_child, payload_size, 
            cell.rowid])) + payload

def readn(file, size):
    read = data = file.read(size)
    while len(data) != size:
        if not read:
            raise FileFormatError('Short read')
        read = file.read(size - len(data))
        data += read

    return data

class PagingFile(object):
    ''' Represents a paginated B-tree like structure that lays out key and
    value pairs within a searchable paging system. '''

    def __init__(self, filename, tuple_types, page_size = 512):
        ''' Create paging DB file from a specific file. '''
        self.__file = open(filename, 'rb+')
        self.__filename = filename
        self.__page_size = page_size
        self.__tuple_types = tuple_types

    def read_page(self, pagenum):
        ''' Reads a page from disk into memory, representing this page as a Page
        object.
        
        This will raise a FileFormatError whenever it detects some violation on
        the predefined file specifications vs what it reads from the actual
        underlying file on disk.'''

        # Seek to the respective page.
        f = self.__file
        f.seek(pagenum * self.__page_size)

        head_sz = s_page_header.size
        
        # Parse page header
        page = readn(f, self.__page_size)
        ptype, ncells, poff_start, pnum_right, pnum_parent = \
                s_page_header.unpack_from(page)
        if poff_start == 0:
            poff_start = 0x10000

        # File-format checking
        if ptype not in _cells:
            raise FileFormatError(f'Invalid page type: 0x{ptype:x}')

        # Make sure our data chunks do not overlap
        cell_off_end = head_sz + ncells * s_page_offs.size
        if cell_off_end >= len(page):
            raise FileFormatError(f'Invalid number of cells (0x{cell_off_end:x})')

        if poff_start < cell_off_end:
            raise FileFormatError(f'Invalid start offset (0x{poff_start:x})')

        page_data = Page(pagenum, ptype, self.__tuple_types, pnum_right,
                pnum_parent)

        # Parse each cell
        cells = []
        offs = s_page_offs.iter_unpack(page[head_sz:cell_off_end])
        prev_off = len(page)
        for off, in offs:
            if off < cell_off_end:
                raise FileFormatError(f'Invalid cell offset (0x{off:x})')
            cell, size = page_data.unpack_cell_from(page, off)
            if off + size > prev_off:
                raise FileFormatError(f'Overlapping cells or bad offset')
            cells.append(cell)

        page_data.cells = cells
        return page_data

    def write_page(self, page):
        ''' Writes a page back onto the backing file storage. 
        
        By default, this will write back to the page number that this page was
        read out from. If that should be changed, the cur_pnum attribute of the
        page can be changed to write back to a diffferent page number. 
        
        This will raise FileFormatError whenenver it detects a violation on the
        predefined file specifications vs the attributes of the page being
        written. '''

        # Pack the cells
        cells = [page.pack_cell(c) for c in page.cells]
        if len(cells) >= 256:
            raise FileFormatError('Too many cells to pack')

        # Determine offsets of cell within page block
        offs = []
        prev_off = self.__page_size
        body = b''
        for cell in cells:
            prev_off -= len(cell)
            body = cell + body
            offs.append(prev_off)

        if prev_off <= 0:
            raise FileFormatError('Overflow of cells')

        # Piece together page data
        page_head = s_page_header.pack(page.type, len(cells), prev_off,
                page.pnum_right, page.pnum_parent)
        page_head += struct.pack('>' + 'H' * len(offs), *offs)
        if prev_off < len(page_head):
            raise FileFormatError('Overflow of cells')

        page_data = page_head + b'\0' * (prev_off - len(page_head)) + body
        assert(len(page_data) == self.__page_size)

        # Seek to the respective page and write
        f = self.__file
        f.seek(page.cur_pnum * self.__page_size)
        f.write(page_data)

