# pylint: disable=too-many-boolean-expressions, too-many-lines, no-name-in-module, import-error
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import Any, Union, Optional, Tuple, List, Callable, Generator, IO, Dict
from io import DEFAULT_BUFFER_SIZE
from time import time
from functools import reduce, lru_cache
from collections import defaultdict, OrderedDict
from re import findall as re_findall
from datetime import date as dt_date, datetime, timedelta
from pickle import loads as pickle_loads, dumps as pickle_dumps, PicklingError # nosec B403
from marshal import loads as marshal_loads, dumps as marshal_dumps
from bz2 import compress as bz2_compress, decompress as bz2_decompress
from lzma import compress as lzma_compress, decompress as lzma_decompress, LZMAError as XZ_Error
try:
    from gzip import compress as _gzip_compress, decompress as gzip_decompress, BadGzipFile as GZ_Error

except ImportError:
    from gzip import compress as _gzip_compress, decompress as gzip_decompress
    GZ_Error = OSError

gzip_compress = lambda _bytes : _gzip_compress(_bytes, compresslevel=1)
#-----------------------------------------------------------------------------
from .utils import Style, JIoBase, bitarray, JValueError

try:
    import yaml

    def frozenset_representer(dumper, data):
        return dumper.represent_set(set(data))

    yaml.SafeDumper.add_representer(frozenset, frozenset_representer)
    # bytes is natively dumped as !!binary by SafeRepresenter; register the same
    # representer for bytearray so dumps_with_zip() fully supports bytearray payloads.
    yaml.SafeDumper.add_representer(bytearray, yaml.SafeDumper.represent_binary)

except ImportError:
    yaml = None

try:
    from brotli import compress as brotli_compress, decompress as brotli_decompress, error as BR_Error
    # Some brotli bindings (e.g. brotlipy / brotlicffi, "brotli/brotli.py") only
    # accept bytes and raise ``TypeError: expected new array length or
    # list/tuple/str, not bytearray`` on bytearray/memoryview inputs, so convert
    # bytes-like inputs here (brotli is the only codec that needs this copy).
    br_compress = lambda _bytes : brotli_compress(_bytes if isinstance(_bytes, bytes) else bytes(_bytes), quality=6)
    br_decompress = lambda _bytes : brotli_decompress(_bytes if isinstance(_bytes, bytes) else bytes(_bytes))
except ModuleNotFoundError:
    br_compress = br_decompress = None
    BR_Error = OSError  # keep except-clauses in zip()/unzip() resolvable

try:
    from lz4.frame import compress as _lz4_compress, decompress as _lz4_decompress, COMPRESSIONLEVEL_MIN, BLOCKSIZE_MAX256KB
    lz4_compress = lambda _bytes : _lz4_compress(_bytes, compression_level=COMPRESSIONLEVEL_MIN, block_size=BLOCKSIZE_MAX256KB)
    lz4_decompress = _lz4_decompress
except ModuleNotFoundError:
    lz4_compress = lz4_decompress = None

def _json_default(obj):
    """JSON encoder fallback for types JSON cannot handle natively.

    Sets become lists; bytes/bytearrays become a hex string prefixed with a
    marker (with a checksum byte) so :meth:`JIoVAL_J.loads` can restore them.

    Args:
        obj (Any): The value that plain JSON could not serialize.

    Returns:
        Any: A JSON-serializable stand-in.

    Raises:
        TypeError: If the type is still not supported.
    """
    if isinstance(obj, (set, frozenset)):
        return list(obj)

    if isinstance(obj, (bytes, bytearray)):
        chk_code = reduce(lambda x,y: (x+y) & 0xff, obj)
        return '\0\1\0\1'+obj.hex()+bytearray([(256-chk_code) & 0xff]).hex()

    raise TypeError(f"Unknown type: {type(obj)}")

try:
    from orjson import loads as _json_loads, dumps as _json_dumps, JSONDecodeError
    # don't support bigger than 64bit integer
    json_dumps = lambda obj : _json_dumps(obj, default=_json_default)
    # 17.25% faster than json_loads = lambda data : _json_loads(data)
    json_loads = _json_loads

except ModuleNotFoundError:
    from json import loads as __json_loads, dumps as __json_dumps, JSONDecodeError

    def _json_loads(data:bytes) -> Any:
        if isinstance(data, memoryview):
            data = bytes(data)

        return __json_loads(data)

    def _json_dumps(obj:Any, default:Optional[Callable[[Any], bytes]]=None) -> bytes:
        """Internal JSON string dump utility function acting as alternative to orjson.

        Args:
            obj (Any): Target object structure payload to serialize.
            default (Optional[Callable[[Any], bytes]], optional): Fallback serialization routing encoder. Defaults to None.

        Returns:
            bytes: UTF-8 encoded byte representation of the serialized JSON payload.
        """
        return __json_dumps(obj, default=default, ensure_ascii=False, separators=(',',':')).encode('utf8')

    def json_dumps(obj:Any) -> bytes:
        """Standard JSON dump abstraction routing parameters through custom default fallback logic layers.

        Args:
            obj (Any): Python data structure or primitive payload to process.

        Returns:
            bytes: Compact UTF-8 raw encoded JSON byte sequence array.
        """
        return __json_dumps(obj, default=_json_default, ensure_ascii=False, separators=(',',':')).encode('utf8')

    json_loads = _json_loads

try:
    from ormsgpack import packb as _msg_dumps, Ext
    from msgpack import unpackb as _msg_loads, Unpacker

except (ModuleNotFoundError, ImportError):
    from msgpack import packb as _msg_dumps, unpackb as _msg_loads, Unpacker, ExtType as Ext

def _msg_encode(obj) -> bytes:
    """Pack non-primitive objects into MsgPack ExtType objects.

    Args:
        obj (Any): The non-primitive input object (e.g., a set).

    Returns:
        ExtType: A wrapped serialization object extension mapping to type ID 123.
        
    Raises:
        TypeError: If the object type is not supported.
    """
    if isinstance(obj, set):
        return Ext(123, _msg_dumps(list(obj)))

    if isinstance(obj, frozenset):
        return Ext(124, _msg_dumps(list(obj)))

    raise TypeError

def _msg_decode(code:int, data:bytes):
    """Decode custom MsgPack extensions.

    Args:
        code (int): The extension type code. Expects type ID 123.
        data (bytes): The raw binary payload associated with the extension.

    Returns:
        Any: The unpacked Python object (e.g., a set).

    Raises:
        TypeError: If the extension type code is unregistered.
    """
    if code == 123:
        try:
            return set(_msg_loads(data))

        except ValueError: # pragma: no cover
            # nosemgrep
            return marshal_loads(data) # nosec B302

    if code == 124:
        try:
            return frozenset(_msg_loads(data))

        except ValueError: # pragma: no cover
            pass

    raise TypeError(f'code={code} data={data}')

msg_dumps = lambda obj : _msg_dumps(obj, default=_msg_encode)
msg_loads = lambda _bytes : _msg_loads(_bytes, ext_hook=_msg_decode, strict_map_key=False)

# don't use zstd.ZstdCompressor and zstd.ZstdDecompressor due to thread issue
try:
    from zstandard import compress as zs_compress, decompress as zs_decompress, ZstdError as ZS_Error
    zstd_compress = lambda _bytes : zs_compress(_bytes, level=22)
    zs1_compress = lambda _bytes : zs_compress(_bytes, level=6)
    zs2_compress = lambda _bytes : zs_compress(_bytes, level=11)
    zstd_decompress = zs_decompress

except ModuleNotFoundError:
    zstd_compress = zs1_compress = zs2_compress = zstd_decompress = None
    ZS_Error = OSError  # keep except-clauses in zip()/unzip() resolvable

except ImportError:
    # Python 3.7 does not support compress() and decompress()
    from zstandard import ZstdCompressor, ZstdDecompressor, ZstdError as ZS_Error
    zstd_compress = ZstdCompressor(level=22).compress
    zs1_compress = ZstdCompressor(level=6).compress
    zs2_compress = ZstdCompressor(level=11).compress
    zstd_decompress = ZstdDecompressor().decompress

BZ_Error = OSError
LZ_Error = RuntimeError

#-----------------------------------------------------------------------------
from .jdb_file import JFilesBase

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
MAX_FILE_ID     = 0x8000
DEF_FILE_SIZE   = (2**32) - 1  # 4GB
MIN_FILE_SIZE   = 1024
MAX_FILE_SIZE   = (2**50) * 1  # 1024TB

DEF_INDEX_SIZE  = 128
MIN_INDEX_SIZE  = 16 + 8 * 6  # key(16), (file_id, offset, row_size, val_size, ver, date)
MAX_INDEX_SIZE  = 2**13       # 8192
MAX_KEY_SIZE    = MAX_INDEX_SIZE - DEF_INDEX_SIZE

DEF_VALUE_SIZE  = 16 # 1-15 bytes can store in KEY file
MIN_VALUE_SIZE  = 1
MAX_VALUE_SIZE  = (2**30) * 4 - 1 # 4GB (32bit)

DEF_FLAG_MASK   = 2**20 - 1 # bitarray size for key search

DEF_RATIO       = 0.001
MAX_RATIO       = 256.
DEF_KEY_LIMIT   = 0 # 0=DictKeyTable(dict)
HEADER_SIZE     = 128

TOTAL_KEY_ROWS  = 8
TOTAL_DEAD_ROWS = 16

MIN_KEY_STRUCT_V0 = 8 + 8 * 5  # n_pad, (file_id, offset, size, ver, date)
MIN_KEY_STRUCT_V1 = 8 + 8 * 6  # n_pad, (file_id, offset, row_size, val_size, ver, date)

THE_1ST_DATE    = dt_date(1, 1, 1)
THE_1ST_SEC     = 59400         # 1970-1-2
NUM_1970_DAYS   = 719163        # date(1970, 1, 2) - date(1,1,1)
NUM_1996_DAYS   = 728689        # date(1996, 2, 1) - date(1,1,1)
NUM_2000_DAYS   = 730119        # date(2000, 1, 1) - date(1,1,1)
DAY_SEC         = 24*60*60
NEW_DAY_SHIFT   = 26            # 0x400_0000
OLD_DAY_MASK    = 0x3FF_FFFF    # 9999 years
NEW_DAY_MASK    = OLD_DAY_MASK << NEW_DAY_SHIFT   # 9999 years (52 bits)
CHG_DAY_FLAG    = 1 << (NEW_DAY_SHIFT*2)

# -1 = DEFAULT_BUFFER_SIZE (8192)
# 0 = no buffering
# 65536 > 8192[default] improve loading key table 7.69%
KEY_FILE_BUF_SIZE = DEFAULT_BUFFER_SIZE * 8
VAL_FILE_BUF_SIZE = DEFAULT_BUFFER_SIZE

DEF_TYPE = 0  # default data type
L_J_TYPE = 1  # split+Json                  | readable
M_M_TYPE = 2  # Marshal+Marshal             | unreadable, full type
J_J_TYPE = 3  # Json+Json                   | readable
J_M_TYPE = 4  # Json+Marshal                | half-readable, full type
J_P_TYPE = 5  # Json+Pickle                 | half-readable, full type
S_S_TYPE = 6  # Msgpack+Msgpack             | smallest size
J_S_TYPE = 7  # Json+Msgpack                | readable, small size
S_M_TYPE = 8  # Msgpack+Marshal             | unreadable, full type
S_J_TYPE = 9  # Msgpack+Json                | half-readable
S_P_TYPE = 10 # Msgpack+Pickle              | unreadable, full type
J_Y_TYPE = 11 # Json+Yaml                   | readable, full type
S_Y_TYPE = 12 # Msgpack+Yaml                | half-readable
J_U_TYPE = 13 # Json+User                   | KEY=readable, VAL=developer-defined codec (e.g. encryption)
S_U_TYPE = 14 # Msgpack+User                | KEY=small,    VAL=developer-defined codec (e.g. encryption)
U_U_TYPE = 15 # User+User                   | KEY and VAL both developer-defined codecs
LAST_DATA_TYPE = U_U_TYPE

DEF_ZIP = -1 # default zip type
NO_ZIP = 0 # no zip mode                    | fastest
GZ_ZIP = 1 # gzip mode(9)                   | random bit, poor ratio
BZ_ZIP = 2 # bz2 mode(9)                    | slow decompress
XZ_ZIP = 3 # lzma mode                      | slow compress
ZS_ZIP = 4 # zstandard mode(22)             | slow compress
BR_ZIP = 5 # brotli mode(6)                 | slow compress, padding issue
Z1_ZIP = 6 # zstandard mode(6)              | better than gz
Z2_ZIP = 7 # zstandard mode(11)             | better than gz, br
LZ_ZIP = 8 # lz4 mode(0)                    | fastest compress+decompress but worst size
LAST_ZIP_TYPE = LZ_ZIP

API_V0 = 0 # header=8           key=6
API_V1 = 1 # header=9(+api_ver) key=7 (+val_size)
API_LATEST = API_V1

ZIP_lut = (
    lambda data: data,
    gzip_compress,
    bz2_compress,
    lzma_compress,
    zstd_compress,
    br_compress,
    zs1_compress,
    zs2_compress,
    lz4_compress,
)

UNZIP_lut = (
    lambda pad,data : data.strip(pad),
    lambda pad,data : gzip_decompress(data.rstrip(pad) + b'\0\0\0'),
    lambda pad,data : bz2_decompress(data.rstrip(pad) + b'\0\0\0'),
    lambda pad,data : lzma_decompress(data.rstrip(pad)),
    lambda pad,data : zstd_decompress(data.rstrip(pad) + b'\0\0\0\0'),
    lambda pad,data : br_decompress(data.rstrip(pad)),
    lambda pad,data : zstd_decompress(data.rstrip(pad) + b'\0\0\0\0'),
    lambda pad,data : zstd_decompress(data.rstrip(pad) + b'\0\0\0\0'),
    lambda pad,data : lz4_decompress(data.rstrip(pad) + b'\0\0\0\0'),
)

UNZIP_lut0 = (
    lambda data: data,
    gzip_decompress,
    bz2_decompress,
    lzma_decompress,
    zstd_decompress,
    br_decompress,
    zstd_decompress,
    zstd_decompress,
    lz4_decompress,
)

def _pad_byte_v0(mode:int) -> bytes:
    """Select the NO_ZIP padding byte for a given data_type.

    Msgpack-only combos use ``0xc1`` (msgpack's unused "never occurs" byte).
    User-defined VAL codecs (J+U / S+U / U+U) use whatever pad byte the
    developer registered via ``register_user_val_codec()`` (defaults to
    ``b'\\n'``), since the library cannot know the byte distribution of a
    developer-supplied encoding (e.g. encrypted payloads).
    """
    if mode in (S_S_TYPE, J_S_TYPE):
        return b'\xc1'
    if mode in (J_U_TYPE, S_U_TYPE, U_U_TYPE):
        return g_VAL_U.pad_byte
    return b'\n'

PAD_lut = (
    _pad_byte_v0,
    lambda mode : b'\0',
    lambda mode : b'\0',
    lambda mode : b'\xff',
    lambda mode : b'\0',
    lambda mode : b'\xff',
    lambda mode : b'\0',
    lambda mode : b'\0',
    lambda mode : b'\0',
)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JDbGroupDict(dict):
    """Custom dictionary implementation returning None instead of throwing KeyError on missing elements."""
    __slots__ = ()
    def __missing__(self, key:str) -> None:
        """Return ``None`` for absent group names instead of raising ``KeyError``.

        Args:
            key (str): The missing group name.

        Returns:
            None: Always ``None``.
        """
        return None

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
xhash = hash # hash() is not deterministic, can export PYTHONHASHSEED=0
class KeyTable:
    """Standard indexing schema for tracking key-to-row mappings in the database."""
    __slots__ = ('io', 'cache', 'files_obj', 'groups', 'size', 'mask', 'flags', 'flags_mask', 'found_flags', 'with_cache')

    def __init__(self, jio:JIo, groups_mask:int, flags_mask:int, with_cache:bool=False):
        """Initialize the storage partitions and bloom filters for key tracking.

        Args:
            jio (JIo): The active I/O transaction driver.
            groups_mask (int): The size mask for the key_array groups.
            flags_mask (int): The size mask for the flags bitarray.
            with_cache (bool, optional): If ``True``, enables the key and row_id cache. Defaults to ``False``.

        Raises:
            ValueError: If an invalid mask is provided.
        """
        if (flags_mask & 0xFFFF_FFFF_FFFF_FFFF) != flags_mask: # pragma: no cover
            raise ValueError('invalid flag mask')
        if (groups_mask & 0xFFFF_FFFF_FFFF_FFFF) != groups_mask: # pragma: no cover
            raise ValueError('invalid group mask')

        self.io = jio
        self.files_obj = jio.files_obj.copy()
        self.mask = groups_mask
        self.flags_mask = flags_mask
        self.flags = bitarray(flags_mask+1)
        self.groups:List[bytearray] = [bytearray() for _ in range(groups_mask+1)]
        self.size = -1
        self.found_flags = bitarray()
        self.with_cache = with_cache
        self.cache:Dict[str,int] = OrderedDict()

    def get_mode(self) -> int:
        """Get the current classification mode configuration.

        Returns:
            int: The constant indicating the current mode, defaults to -1.
        """
        return -1

    def __repr__(self) -> str:
        """Return a string summary of the table's memory usage and density metrics."""
        return f'<{type(self).__name__} '\
            f'cache:{len(self.cache) if self.with_cache else "-"} '\
            f'mask:{self.mask:x} '\
            f'used:{(self.flags.nbytes+self.found_flags.nbytes+sum(len(ka) for ka in self.groups))/1024/1024:.2f}MB+{self.flags.count(1)*100./len(self.flags):.2f}% '\
            f'done:{self.size}/{self.io.n_records}+{self.found_flags.count(1)*100./max(1,len(self.found_flags)):.2f}% '\
            f'at {hex(id(self))}>'

    def set(self, key:str, row_id:int):
        """Associate a key with its row id in the key table.

        Args:
            key (str): The record key.
            row_id (int): The key's row id in the KEY file.
        """
        if self.size < 0: #pragma: no cover
            self.clear()

        cache = self.cache
        if self.with_cache and cache.get(key, None) == row_id: # pragma: no cover
            cache.move_to_end(key, last=True)
            return

        key_hash = xhash(key)
        key_array = self.groups[key_hash & self.mask]
        old_row_id, s_idx, e_idx = self._find_key(key_array, key)
        if old_row_id >= 0: # old key
            if old_row_id != row_id:
                key_array[s_idx:e_idx] = _msg_dumps((key, row_id)) or b''
                if cache: cache.pop(key, None)

        else: # new key
            self.size += 1
            self.flags[key_hash & self.flags_mask] = True
            key_array.extend(_msg_dumps((key, row_id)) or b'')

        self._set_found_flag(row_id, True)

        if self.with_cache:
            while len(cache) >= self.io._key_limit:
                cache.popitem(last=False)

            cache[key] = row_id
            cache.move_to_end(key, last=True)

    def pop(self, key:str, default_row_id:int=-1, fp:IO=None) -> int:
        """Remove a key mapping from the index table.

        Args:
            key (str): The string identifier to remove.
            default_row_id (int, optional): The value to return if the key is not found. Defaults to -1.
            fp (IO, optional): The open KEY file pointer. None=use internal

        Returns:
            int: The row ID that was unlinked, or ``default_row_id`` if not found.
        """
        if self.size < 0: #pragma: no cover
            self.clear()

        self.cache.pop(key, None)
        jio = self.io
        is_sync = self.size == jio.n_records
        key_hash = xhash(key)
        flag_idx = key_hash & self.flags_mask
        if is_sync and not self.flags[flag_idx]:
            return default_row_id

        mask = self.mask
        groups = self.groups
        find_key = self._find_key
        set_found_flag = self._set_found_flag
        key_array = groups[key_hash & mask]
        row_id, s_idx, e_idx = find_key(key_array, key)
        if row_id >= 0:
            if is_sync:
                del key_array[s_idx:e_idx]
                self.size -= 1
                set_found_flag(row_id, False)
                return row_id

            KEY_loads = jio.KEY_loads
            index_size = jio.index_size
            key_fp = None if fp is None else fp
            try:
                key_fp = self.files_obj.KEY_open('rb') if key_fp is None else key_fp
                key_fp.seek(HEADER_SIZE + row_id * index_size)
                _key, _f, _o, _r, _v, _s, _d = KEY_loads(key_fp.read(index_size))
                if _key == key:
                    del key_array[s_idx:e_idx]
                    self.size -= 1
                    set_found_flag(row_id, False)
                    return row_id

                else: # pragma: no cover
                    is_sync = False
                    del key_array[s_idx:e_idx]
                    self.size -= 1
                    set_found_flag(row_id, False)

            except FileNotFoundError: # pragma: no cover
                self.clear()

            finally:
                if key_fp is not None and fp is None:
                    key_fp.close()

        if not is_sync:
            for _key, row_id in self._item_iter(fp):
                if key == _key:
                    old_row_id, s_idx, e_idx = find_key(key_array, key)
                    if old_row_id == row_id:
                        del key_array[s_idx:e_idx]
                        self.size -= 1

                    set_found_flag(row_id, False)
                    return row_id

        return default_row_id

    def get(self, key:str, default_row_id:int=-1, fp:IO=None) -> int:
        """Retrieve the row index mapped to a specific key.

        Args:
            key (str): The string identifier to look up.
            default_row_id (int, optional): The value to return if the key is not found. Defaults to -1.
            fp (IO, optional): The open KEY file pointer. None=use internal

        Returns:
            int: The mapped row index, or ``default_row_id`` if not found.
        """
        if self.size < 0: #pragma: no cover
            self.clear()

        jio = self.io
        is_sync = self.size == jio.n_records
        key_hash = xhash(key)
        flag_idx = key_hash & self.flags_mask
        if is_sync and not self.flags[flag_idx]:
            return default_row_id

        cache = self.cache
        if self.with_cache:
            row_id = cache.get(key, -1)
            if row_id >= 0:
                return row_id

        mask = self.mask
        groups = self.groups
        find_key = self._find_key
        key_array = groups[key_hash & mask]
        row_id, _s_idx, _e_idx = find_key(key_array, key)
        if row_id >= 0:
            if self.with_cache:
                while len(cache) >= jio._key_limit:
                    cache.popitem(last=False)

                cache[key] = row_id
                cache.move_to_end(key, last=True)

            return row_id

        if not is_sync:
            for _key, row_id in self._item_iter(fp):
                if _key == key:
                    # clean up extra buffer
                    if self.with_cache:
                        while len(cache) >= jio._key_limit:
                            cache.popitem(last=False)

                        cache[key] = row_id
                        cache.move_to_end(key, last=True)

                    return row_id

        return default_row_id

    def items(self, fp:IO=None) -> Generator[Tuple[str,int], None, None]:
        """Yield all key and row_id pairs from the table.
        
        Args:
            fp (IO, optional): The open KEY file pointer. None=use internal
        
        Yields:
            (str, int): A tuple containing the key and its corresponding row index.
        """
        if self.size < 0: #pragma: no cover
            self.clear()

        is_sync = self.size == self.io.n_records
        if is_sync:
            if self.size > 0:
                unpacker = Unpacker()
                for key_array in self.groups:
                    if not key_array: continue
                    unpacker.feed(key_array)
                    yield from unpacker
            return

        # not sync
        yield from self._item_iter(fp)

    def values(self, fp:IO=None) -> Generator[int, None, None]:
        """Yield all active row indices in the table.

        Args:
            fp (IO, optional): The open KEY file pointer. None=use internal

        Yields:
            int: An active row index.
        """
        if self.size < 0: #pragma: no cover
            self.clear()

        is_sync = self.size == self.io.n_records
        if is_sync:
            if self.size > 0:
                unpacker = Unpacker()
                for key_array in self.groups:
                    if not key_array: continue
                    unpacker.feed(key_array)
                    for _key,row in unpacker:
                        yield row
            return

        # not sync
        for _key,row_id in self._item_iter(fp):
            yield row_id

    def keys(self, fp:IO=None) -> Generator[str, None, None]:
        """Yield all keys registered in the table.

        Args:
            fp (IO, optional): The open KEY file pointer. None=use internal

        Yields:
            str: A registered key string.
        """
        if self.size < 0: #pragma: no cover
            self.clear()

        is_sync = self.size == self.io.n_records
        if is_sync:
            if self.size > 0:
                unpacker = Unpacker()
                for key_array in self.groups:
                    if not key_array: continue
                    unpacker.feed(key_array)
                    for key,_row in unpacker:
                        yield key
            return

        # not sync
        for key,_row_id in self._item_iter(fp):
            yield key

    def copy(self) -> KeyTable: # pragma: no cover
        """Create a duplicate instance of the KeyTable.

        Returns:
            KeyTable: A new KeyTable instance with the same configurations.
        """
        return KeyTable(self.io, self.mask, self.flags_mask, self.with_cache)

    def clear(self):
        """Purge all memory configurations and reset trackers/bloom filters to zero."""
        if self.size != 0:
            for key_array in self.groups:
                key_array.clear()
            self.cache.clear()
            self.found_flags.clear()
            self.flags.setall(0)
            self.size = 0

    def __len__(self) -> int:
        """Return the total number of registered data records.

        Returns:
            int: The record count.
        """
        return self.io.n_records

    def __setitem__(self, key:str, row_id:int):
        """Map a key to a row ID using item assignment (e.g., ``table[key] = row_id``)."""
        self.set(key, row_id)

    def __getitem__(self, key:str) -> int:
        """Retrieve a row ID using item access (e.g., ``table[key]``)."""
        return self.get(key, -1)

    def __delitem__(self, key:str):
        """Delete a key mapping using the `del` keyword.

        Raises:
            KeyError: If the key does not exist.
        """
        if self.pop(key, -1) < 0:
            raise KeyError(f'{key}')

    def __contains__(self, key:str) -> bool:
        """Check if a key exists in the table using the `in` keyword."""
        return self.get(key, -1) != -1

    def __iter__(self) -> Generator[str, None, None]:
        """Iterate over the keys in the table."""
        yield from self.keys()

    def __eq__(self, obj:Union[KeyTable,Dict[str,int]]) -> bool:
        """Check if this table contains the exact same key-row mappings as another object."""
        if self is obj:
            return True

        if len(self) != len(obj):
            return False

        if isinstance(obj, KeyTable):
            if self.files_obj == obj.files_obj:
                return True

        for key,val in self.items():
            if key not in obj:
                return False

            if val != obj.get(key, -1):
                return False

        return True

    def _item_iter(self, fp:IO=None) -> Generator[Tuple[str,int], None, None]:
        """Iterate over every ``(key, row_id)`` pair by scanning the KEY file,
        reading the index in large blocks for speed. Rows not yet registered
        in the hash table are added on the fly.

        Args:
            fp (IO, optional): The open KEY file pointer. None=use internal

        Yields:
            (str, int): Each record's key and its row id.
        """
        jio = self.io
        is_empty = self.size == 0
        flags = self.flags
        mask = self.mask
        flags_mask = self.flags_mask
        get_found_flag = self._get_found_flag
        set_found_flag = self._set_found_flag
        groups = self.groups
        key_fp = None if fp is None else fp
        try:
            key_fp = self.files_obj.KEY_open('rb') if key_fp is None else key_fp
            row_id = 0
            for (_key, _f, _o, _r, _v, _s, _d) in jio.KEY_iter(key_fp, row_id, jio.n_records):
                if is_empty or not get_found_flag(row_id):
                    key_hash = xhash(_key)
                    flags[key_hash & flags_mask] = True
                    groups[key_hash & mask].extend(_msg_dumps((_key, row_id)) or b'')
                    set_found_flag(row_id, True)
                    self.size += 1

                yield _key, row_id
                row_id += 1

        except FileNotFoundError: # pragma: no cover
            self.clear()

        finally:
            if key_fp is not None and fp is None:
                key_fp.close()

    def _find_key(self, key_array:bytearray, key:str) -> Tuple[int, int, int]:
        """Find key msgpack pattern in bytearray.

        Args:
            key_array (bytearray): bytearray to store key+row
            key (str): key in bytearray.

        Returns:
            Tuple[int, int, int]: key's row ID, bytearray start index, bytearry end index
        """
        n_bytes = len(key_array)
        if n_bytes > 0:
            search_prefix = b'\x92' + (_msg_dumps(key) or b'')
            prefix_len = len(search_prefix)
            idx = key_array.find(search_prefix)
            while idx >= 0:
                val_idx = idx + prefix_len
                val_type = key_array[val_idx]
                val_len = 1 if val_type <= 0x7f or val_type >= 0xe0 else \
                        2 if val_type == 0xcc or val_type == 0xd0 else \
                        3 if val_type == 0xcd or val_type == 0xd1 else \
                        5 if val_type == 0xce or val_type == 0xd2 else \
                        9 if val_type == 0xcf or val_type == 0xd3 else 0

                val_idx_e = val_idx + val_len
                if val_len > 0 and val_idx_e <= n_bytes:
                    if val_idx_e == n_bytes or key_array[val_idx_e] == 0x92:
                        row_id = val_type if val_type <= 0x7f else \
                            int.from_bytes(key_array[val_idx+1:val_idx_e], 'big') if 0xcf >= val_type >= 0xcc else \
                            int.from_bytes(key_array[val_idx+1:val_idx_e], 'big', signed=True) if 0xd3 >= val_type >= 0xd0 else \
                            val_type - 256 if val_type >= 0xe0 else -1

                        if row_id >= 0:
                            return row_id, idx, val_idx_e

                idx = key_array.find(search_prefix, idx+1) # pragma: no cover

        return -1, -1, -1

    def _set_found_flag(self, row_id:int, is_found:bool=True):
        """Mark whether the row at ``row_id`` has already been scanned into the table, extending the flag array as needed."""
        found_flags = self.found_flags
        ext_size = row_id + 1 - len(found_flags)
        if ext_size > 0:
            found_flags.extend('0' * ext_size)
        found_flags[row_id] = is_found

    def _get_found_flag(self, row_id:int) -> bool:
        """Return whether the row at ``row_id`` has already been scanned into the table."""
        found_flags = self.found_flags
        ext_size = row_id + 1 - len(found_flags)
        if ext_size > 0:
            found_flags.extend('0' * ext_size)
            return False

        return found_flags[row_id]

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class DictKeyTable(dict):
    """Key table backed by a plain Python ``dict`` (the default)."""
    __slots__ = ()
    def __missing__(self, key:str) -> int:
        """Handle missing keys safely by returning default error indicator value -1.

        Args:
            key (str): Target lookup indicator.

        Returns:
            int: Error code indicating unallocated item references.
        """
        return -1

    def get_mode(self) -> int:
        """Return the key-table mode code (``0`` for a plain dict).

        Returns:
            int: The mode code.
        """
        return -1

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class PartialKeyTable(KeyTable):
    """Key table that keeps only a bounded set of keys in memory, resolving
    misses by scanning the KEY file on demand instead of loading every key.
    """
    __slots__ = ()

    def __init__(self, jio:JIo):
        """Initialize partial tracking layers parsing data indices boundaries criteria metrics models.

        Args:
            jio (JIo): Active pipeline transaction driver routing local configuration properties.
        """
        super().__init__(jio, groups_mask=0xFFF, flags_mask=DEF_FLAG_MASK, with_cache=True)

    def copy(self) -> PartialKeyTable:
        """Return a copy of this table with the same configuration and duplicated
        hash buckets and flags.

        Returns:
            PartialKeyTable: The copy.
        """
        return PartialKeyTable(self.io)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class LiteKeyTable(KeyTable):
    """Key table that stores ``(key, row_id)`` pairs as packed bytes in hash
    buckets instead of Python dict entries, for a much smaller memory footprint.
    """
    __slots__ = ('mode', )

    def __init__(self, jio:JIo, mode:int=0):
        """Initialize the table with a bucket-count size profile.

        Args:
            jio (JIo): The owning IO engine.
            mode (int, optional): Size profile 0-5 (``'l0'``-``'l5'``); larger
                modes use more buckets. Defaults to 0.

        Raises:
            ValueError: If ``mode`` is out of range.
        """
        _mode = mode & 0xfff
        if _mode == 0:
            groups_mask = 0
            flags_mask = DEF_FLAG_MASK
        elif _mode == 1:
            groups_mask = 0xF
            flags_mask = DEF_FLAG_MASK
        elif _mode == 2:
            groups_mask = 0xff
            flags_mask = max(DEF_FLAG_MASK, 8*(2**18)-1)
        elif _mode == 3:
            groups_mask = 0xfff
            flags_mask = max(DEF_FLAG_MASK, 8*(2**19)-1)
        elif _mode == 4:
            groups_mask = 0xffff
            flags_mask = max(DEF_FLAG_MASK, 8*(2**20)-1)
        elif _mode == 5:
            groups_mask = 0xf_ffff
            flags_mask = max(DEF_FLAG_MASK, 8*(2**21)-1)
        else:
            raise ValueError(f'invalid mode {mode}!')

        super().__init__(jio, groups_mask, flags_mask, with_cache=False)
        self.mode = mode

    def get_mode(self) -> int:
        """Extract the exact active masking operational mode code index number integer.

        Returns:
            int: Tracking classification setting variable.
        """
        return self.mode

    def copy(self) -> LiteKeyTable:
        """Construct replica instances duplication frameworks copying binary data tracking targets indicators context.

        Returns:
            LiteKeyTable: Cloned alternative index workspace data object manager framework handle.
        """
        return LiteKeyTable(self.io, self.mode)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
try:
    from BTrees.OLBTree import OLBTree as BTree

    class BTreeKeyTable(BTree):
        """Key table backed by a B-tree (``BTrees.OLBTree``), for large sorted key sets."""
        def __repr__(self) -> str:
            return f'<{type(self).__name__} at {hex(id(self))}>'

        def __eq__(self, obj) -> bool:
            if self is obj:
                return True

            if len(self) != len(obj):
                return False

            for key,val in self.items():
                if key not in obj:
                    return False

                if val != obj.get(key, -1):
                    return False

            return True

        def copy(self) -> BTreeKeyTable:
            """Return a copy of this B-tree key table.

            Returns:
                BTreeKeyTable: The copy.
            """
            return BTreeKeyTable(self)

        def __getitem__(self, key:str) -> int:
            return self.get(key, -1)

        def get_mode(self) -> int:
            """Return the key-table mode code (``-1`` for the B-tree table).

            Returns:
                int: The mode code.
            """
            return -1

except ModuleNotFoundError:
    BTreeKeyTable = None

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoHEAD:
    """Codec module for packing and unpacking the database layout header."""
    def dumps_v0(self, sync_id:int, n_records:int, n_lines:int, index_size:int, zip_type:int, data_type:int, swap_id:int, remv_id:int, api_ver:int) -> bytes:
        """Serialize the database header (V0 layout) as a fixed-size JSON line.

        Args:
            sync_id (int): Write-session counter.
            n_records (int): Number of active records.
            n_lines (int): Total rows including dead/history rows.
            index_size (int): Byte size of one KEY index row.
            zip_type (int): Compression code:

                - 0 = no compression for VAL
                - 1 = gzip compression(9) for VAL
                - 2 = bz2 compression(9) for VAL
                - 3 = lzma compression for VAL
                - 4 = zstandard compression(22) for VAL
                - 5 = brotli compression(6) for VAL
                - 6 = zstandard compression(6) for VAL
                - 7 = zstandard compression(11) for VAL
                - 8 = lz4 compression(0) for VAL

            data_type (int): Serialization format code:

                - 1  = KEY=split    | VAL=Json
                - 2  = KEY=Marshal  | VAL=Marshal
                - 3  = KEY=Json     | VAL=Json
                - 4  = KEY=Json     | VAL=Marshal
                - 5  = KEY=Json     | VAL=Pickle
                - 6  = KEY=msgpack  | VAL=msgpack
                - 7  = KEY=Json     | VAL=msgpack
                - 8  = KEY=msgpack  | VAL=Marshal
                - 9  = KEY=msgpack  | VAL=Json
                - 10 = KEY=msgpack  | VAL=Pickle
                - 11 = KEY=Json     | VAL=YAML
                - 12 = KEY=msgpack  | VAL=YAML

            swap_id (int): Compaction counter.
            remv_id (int): Deletion counter.
            api_ver (int): On-disk format version.

        Returns:
            bytes: The header line bytes.
        """
        return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver))

    def loads_v0(self, header:bytes) -> Tuple[int,int,int,int,int,int,int,int,int]:
        """Parse a V0 header line back into its fields.

        Args:
            header (bytes): The raw header bytes.

        Returns:
            Tuple[int, int, int, int, int, int, int, int, int]:
            ``(sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver)``.
        """
        try:
            if header[0] == 91: # '['
                info = _json_loads(header)
            else: # pragma: no cover
                # deprecated
                info = [int(v) for v in header.decode('utf8').split(',')]

            nn = len(info)
            if nn >= 9:
                sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver = info[:9]

            else: # pragma: no cover
                if nn >= 8:
                    sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id = info[:8]
                    api_ver = API_V0

                elif nn >= 7:
                    sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id = info[:7]
                    remv_id = sync_id % 10
                    api_ver = API_V0

                elif nn >= 4:
                    sync_id, n_records, n_lines, index_size = info[:4]
                    zip_type = info[4] if nn >= 5 else 0
                    data_type = info[5] if nn >= 6 else 1
                    swap_id = info[6] if nn >= 7 else (sync_id % 10)
                    remv_id = info[7] if nn >= 8 else (sync_id % 10)
                    api_ver = API_V0

                else:
                    raise ValueError(f'cannot decode header (n={nn})')

            return sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise ValueError from e

    def dumps_v1(self, sync_id:int, n_records:int, n_lines:int, index_size:int, zip_type:int, data_type:int, swap_id:int, remv_id:int, api_ver:int) -> bytes:
        """Serialize the database header (V1 layout) as a fixed-size JSON line.

        Args:
            sync_id (int): Write-session counter.
            n_records (int): Number of active records.
            n_lines (int): Total rows including dead/history rows.
            index_size (int): Byte size of one KEY index row.
            zip_type (int): Compression code:

                - 0 = no compression for VAL
                - 1 = gzip compression(9) for VAL
                - 2 = bz2 compression(9) for VAL
                - 3 = lzma compression for VAL
                - 4 = zstandard compression(22) for VAL
                - 5 = brotli compression(6) for VAL
                - 6 = zstandard compression(6) for VAL
                - 7 = zstandard compression(11) for VAL
                - 8 = lz4 compression(0) for VAL

            data_type (int): Serialization format code:

                - 1  = KEY=split    | VAL=Json
                - 2  = KEY=Marshal  | VAL=Marshal
                - 3  = KEY=Json     | VAL=Json
                - 4  = KEY=Json     | VAL=Marshal
                - 5  = KEY=Json     | VAL=Pickle
                - 6  = KEY=msgpack  | VAL=msgpack
                - 7  = KEY=Json     | VAL=msgpack
                - 8  = KEY=msgpack  | VAL=Marshal
                - 9  = KEY=msgpack  | VAL=Json
                - 10 = KEY=msgpack  | VAL=Pickle
                - 11 = KEY=Json     | VAL=YAML
                - 12 = KEY=msgpack  | VAL=YAML
            
            swap_id (int): Compaction counter.
            remv_id (int): Deletion counter.
            api_ver (int): On-disk format version.

        Returns:
            bytes: The header line bytes.
        """
        try:
            return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v1(self, header:bytes) -> Tuple[int,int,int,int,int,int,int,int,int]:
        """Parse a V1 header line back into its fields.

        Args:
            header (bytes): The raw header bytes.

        Returns:
            Tuple[int, int, int, int, int, int, int, int, int]:
            ``(sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver)``.
        """
        try:
            return _json_loads(header)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError): # pragma: no cover
            return self.loads_v0(header)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class UserCodecNotRegisteredError(RuntimeError):
    """Raised when a 'U' (developer-defined) data_type is used before its codec was registered."""

class JIoKEY(metaclass=ABCMeta): # pragma: no cover
    """Abstract codec for one KEY index row.

    A KEY row holds the fixed-width metadata for one record:
    ``(key, file_id, offset, row_size, val_size, ver, days)``. The ``_v0``
    methods use the older layout that packs ``val_size`` into the high 32 bits
    of ``row_size``; the ``_v1`` methods store every field separately.
    """
    @abstractmethod
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row in the v0 layout (``val_size`` packed into ``row_size``)."""
    @abstractmethod
    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v0 KEY row into ``(key, file_id, offset, row_size, val_size, ver, days)``."""
    @abstractmethod
    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row in the v1 layout (all fields stored separately)."""
    @abstractmethod
    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v1 KEY row into ``(key, file_id, offset, row_size, val_size, ver, days)``."""

class JIoKEY_J(JIoKEY):
    """KEY row codec using JSON (one JSON array per row)."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row as a JSON array (v0 layout)."""
        try:
            return _json_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v0 JSON KEY row, unpacking val_size from the high bits of row_size."""
        try:
            args = _json_loads(data)
            if len(args) != 6: # pragma: no cover
                args.append(0)

            key, file_id, offset, row_size, ver, days = args[:6]
            val_size = row_size >> 32
            row_size &= 0X_FFFF_FFFF
            return key, file_id, offset, row_size, val_size, ver, days

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise JValueError from e

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row as a JSON array (v1 layout)."""
        try:
            return _json_dumps((key, file_id, offset, row_size, val_size, ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v1 JSON KEY row."""
        try:
            return _json_loads(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise JValueError from e

class JIoKEY_S(JIoKEY):
    """KEY row codec using msgpack, prefixed with a 3-byte length header."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row with msgpack behind a 3-byte length prefix (v0 layout)."""
        try:
            info_b = _msg_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days)) or b''
            info_len = len(info_b)
            return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v0 msgpack KEY row, unpacking val_size from the high bits of row_size."""
        try:
            prefix0, prefix1, prefix2, info0 = data[:4]
            if prefix0 == 0xcd and info0 == 0x96:
                info_len = (prefix1 << 8)| prefix2
                end_idx = info_len + 3
                key, file_id, offset, row_size, ver, days = _msg_loads(data[3:end_idx])
                return key, file_id, offset, row_size & 0X_FFFF_FFFF, row_size >> 32, ver, days

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row with msgpack behind a 3-byte length prefix (v1 layout)."""
        try:
            info_b = _msg_dumps((key, file_id, offset, row_size, val_size, ver, days)) or b''
            info_len = len(info_b)
            return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v1 msgpack KEY row."""
        try:
            prefix0, prefix1, prefix2, info0 = data[:4]
            if prefix0 == 0xcd and info0 == 0x97:
                info_len = (prefix1 << 8)| prefix2
                end_idx = info_len + 3
                return _msg_loads(data[3:end_idx])

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

class JIoKEY_M(JIoKEY):
    """KEY row codec using Python ``marshal`` (fast, CPython-specific)."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row with marshal (v0 layout)."""
        try:
            # nosemgrep
            return marshal_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days)) # tuple smaller than list

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v0 marshal KEY row, unpacking val_size from the high bits of row_size."""
        try:
            # nosemgrep
            args = marshal_loads(data) # nosec B302
            if isinstance(args, (list, tuple)):
                if len(args) != 6: # pragma: no cover
                    args.append(0)

                key, file_id, offset, row_size, ver, days = args[:6]
                val_size = row_size >> 32
                row_size &= 0X_FFFF_FFFF
                return key, file_id, offset, row_size, val_size, ver, days

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row with marshal (v1 layout)."""
        try:
            # nosemgrep
            return marshal_dumps((key, file_id, offset, row_size, val_size, ver, days)) # tuple smaller than list

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v1 marshal KEY row."""
        try:
            # nosemgrep
            args = marshal_loads(data) # nosec B302
            if isinstance(args, (list, tuple)):
                return args

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

class JIoKEY_L(JIoKEY):
    """KEY row codec using a plain comma-separated text line."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row as comma-separated text (v0 layout)."""
        try:
            data = f'{key},{file_id},{offset},{row_size | (val_size << 32)}|{ver}|{days}'
            return data.encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v0 comma-separated KEY row (keys may contain commas)."""
        try:
            if isinstance(data, memoryview):
                data = bytes(data)

            data_s = data.decode('utf8').rstrip()
            fields = data_s.split(',')
            file_id = int(fields[-3])
            offset = int(fields[-2])
            n_fields = len(fields)
            key = ','.join(fields[:-3]) if n_fields > 4 else fields[0]
            extra = fields[-1].split('|')
            n_extra = len(extra)
            if n_extra > 2:
                row_size = int(extra[0])
                ver = int(extra[1])
                days = int(extra[2])
            else: # pragma: no cover
                if n_extra > 1:
                    row_size = int(extra[0])
                    ver = int(extra[1])
                    days = 0
                else:
                    row_size = int(extra[0])
                    ver = 0
                    days = 0

            return key, file_id, offset, row_size & 0X_FFFF_FFFF, row_size >> 32, ver, days

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row as comma-separated text (v1 layout)."""
        try:
            data = f'{key},{file_id},{offset},{row_size},{val_size},{ver},{days}'
            return data.encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a v1 comma-separated KEY row (keys may contain commas)."""
        try:
            if isinstance(data, memoryview):
                data = bytes(data)

            data_s = data.decode('utf8').rstrip()
            fields = data_s.split(',')
            n_fields = len(fields)
            key = ','.join(fields[:-6]) if n_fields > 7 else fields[0]
            file_id, offset, row_size, val_size, ver, days = (int(field) for field in fields[-6:])
            return key, file_id, offset, row_size, val_size, ver, days

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError) as e: # pragma: no cover
            raise JValueError from e

class JIoKEY_U(JIoKEY):
    """Pluggable KEY (row index) codec ("U+U" data_type).

    Like :class:`JIoVAL_U`, but for the KEY row metadata
    ``(key, file_id, offset, row_size, val_size, ver, days)``. Most developers
    only need to customize the VAL codec (``J+U`` / ``S+U``); this exists for
    the rarer case where the KEY row itself must be transformed too (e.g. to
    obfuscate record keys on disk).

    If only ``dumps``/``loads`` are registered, they are reused for both the
    legacy (v0) and current (v1) on-disk layouts. Register ``dumps_v0``/
    ``loads_v0`` separately only if v0-file compatibility with a different
    wire layout is required.
    """
    __slots__ = ('_dumps', '_loads', '_dumps_v0', '_loads_v0')

    def __init__(self):
        self._dumps: Optional[Callable[..., bytes]] = None
        self._loads: Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int]]] = None
        self._dumps_v0: Optional[Callable[..., bytes]] = None
        self._loads_v0: Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int]]] = None

    def register(self, dumps:Callable[..., bytes], loads:Callable[[bytes], Tuple[str,int,int,int,int,int,int]],
                 dumps_v0:Optional[Callable[..., bytes]]=None, loads_v0:Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int]]]=None) -> None:
        """Register the developer-defined KEY codec.

        Args:
            dumps (Callable): Receives a single packed row tuple
                ``(key, file_id, offset, row_size, val_size, ver, days)`` (API v1 layout)
                and returns ``bytes``. Called with *one* tuple argument, not 7 separate
                positional arguments.
            loads (Callable[[bytes], Tuple]): ``bytes -> (key, file_id, offset, row_size, val_size, ver, days)``.
            dumps_v0 (Callable, optional): Same as ``dumps`` but for the legacy v0 layout (no separate val_size).
                Defaults to reusing ``dumps``.
            loads_v0 (Callable, optional): Same as ``loads`` but for the legacy v0 layout. Defaults to ``loads``.

        Raises:
            TypeError: If any provided argument is not callable, or if the dumps/loads
                round-trip self-test fails.
        """
        for fn in (dumps, loads) + tuple(f for f in (dumps_v0, loads_v0) if f is not None):
            if not callable(fn):
                raise TypeError('dumps/loads must be callable')

        # test_val mirrors the real call convention: dumps() always receives ONE
        # packed 7-tuple (key, file_id, offset, row_size, val_size, ver, days).
        test_val = ('key', 1, 2, 3, 4, 5, 6)
        try:
            if tuple(loads(dumps(test_val))) != test_val:
                raise TypeError
        except Exception as e:
            raise TypeError('dumps/loads cannot work correctly') from e

        self._dumps = dumps
        self._loads = loads
        self._dumps_v0 = dumps_v0 or dumps
        self._loads_v0 = loads_v0 or loads

    def unregister(self) -> None:
        """Clear a previously registered codec, e.g. between tests."""
        self._dumps = self._loads = self._dumps_v0 = self._loads_v0 = None

    @property
    def is_registered(self) -> bool:
        """bool: Whether a developer codec has been registered yet."""
        return self._dumps is not None and self._loads is not None

    def _missing(self):
        raise UserCodecNotRegisteredError(
            "data_type 'U+U' (KEY) is selected but no codec is registered. "
            "Call register_user_key_codec(dumps, loads) before opening the JDb.")

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row (v1 layout) using the registered developer codec."""
        if self._dumps is None:
            self._missing()
        try:
            return self._dumps((key, file_id, offset, row_size, val_size, ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a KEY row (v1 layout) using the registered developer codec."""
        if self._loads is None:
            self._missing()
        try:
            args = self._loads(data)
            if isinstance(args, (list, tuple)):
                return args

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        """Serialize a KEY row (v0 layout) using the registered developer codec."""
        if self._dumps_v0 is None:
            self._missing()
        try:
            return self._dumps_v0((key, file_id, offset, row_size, val_size, ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        """Parse a KEY row (v0 layout) using the registered developer codec."""
        if self._loads_v0 is None:
            self._missing()
        try:
            args = self._loads_v0(data)
            if isinstance(args, (list, tuple)):
                return args

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoVAL(metaclass=ABCMeta): # pragma: no cover
    """Abstract codec for a stored record value."""
    @abstractmethod
    def dumps(self, data:Any) -> bytes:
        """Serialize a Python value to bytes."""
    @abstractmethod
    def loads(self, data:bytes) -> Any:
        """Deserialize bytes back into a Python value."""

class JIoVAL_J(JIoVAL):
    """Value codec using JSON (human-readable; bytes are hex-encoded)."""
    def dumps(self, data:Any) -> bytes:
        """Serialize a value as JSON (bytes are hex-encoded with a marker prefix)."""
        try:
            return _json_dumps(data, default=_json_default)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads(self, data:bytes) -> Any:
        """Deserialize a JSON value, decoding the hex-encoded bytes marker back to bytes."""
        try:
            val = json_loads(data)
            if isinstance(val, str) and val[:4] == '\0\1\0\1':
                try:
                    _bytes = bytes.fromhex(val[4:])
                    if reduce(lambda x,y: (x+y) & 0xff, _bytes) == 0:
                        return _bytes[:-1]

                except ValueError: # pragma: no cover
                    return val

            return val

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise JValueError from e

class JIoVAL_S(JIoVAL):
    """Value codec using msgpack (compact binary)."""
    def dumps(self, data:Any) -> bytes:
        """Serialize a value with msgpack."""
        try:
            return _msg_dumps(data, default=_msg_encode) or b''

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads(self, data:bytes) -> Any:
        """Deserialize a msgpack value (retries with padding to tolerate reserved-row slack)."""
        for _ in range(9):
            try:
                return _msg_loads(data, ext_hook=_msg_decode, strict_map_key=False)

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError): # pragma: no cover
                data = data + b'\xc1'

        raise JValueError

class JIoVAL_M(JIoVAL):
    """Value codec using Python ``marshal`` (fast, CPython-specific)."""
    def dumps(self, data:Any) -> bytes:
        """Serialize a value with marshal."""
        try:
            # nosemgrep
            return marshal_dumps(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads(self, data:bytes) -> Any:
        """Deserialize a marshal value (retries with padding to tolerate reserved-row slack)."""
        for _ in range(9):
            try:
                # nosemgrep
                return marshal_loads(data) # nosec B302

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError): # pragma: no cover
                data = data + b'\n'

        raise JValueError

class JIoVAL_P(JIoVAL):
    """Value codec using pickle (supports arbitrary Python objects)."""
    def dumps(self, data:Any) -> bytes:
        """Serialize a value with pickle."""
        try:
            # nosemgrep
            return pickle_dumps(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, PicklingError) as e: # pragma: no cover
            raise JValueError from e

    def loads(self, data:bytes) -> Any:
        """Deserialize a pickle value (retries with padding to tolerate reserved-row slack)."""
        for _ in range(9):
            try:
                # nosemgrep
                return pickle_loads(data) # nosec B301

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, PicklingError): # pragma: no cover
                data = data + b'\n'

        raise JValueError

class JIoVAL_Y(JIoVAL):
    """Value codec using YAML (human-readable; requires PyYAML)."""
    def dumps(self, data:Any) -> bytes:
        """Serialize a value as YAML."""
        if yaml is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

        try:
            return yaml.safe_dump(data, allow_unicode=True).encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, yaml.YAMLError) as e: # pragma: no cover
            raise JValueError from e

    def loads(self, data:bytes) -> Any:
        """Deserialize a YAML value (retries with padding to tolerate reserved-row slack)."""
        if yaml is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

        if isinstance(data, (bytearray, memoryview)): # pragma: no cover
            # PyYAML only accepts str/bytes; any other object is treated as a
            # file-like stream (and fails with AttributeError: no 'read').
            data = bytes(data)

        for _ in range(9):
            try:
                return yaml.safe_load(data)

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, yaml.YAMLError): # pragma: no cover
                data = data + b'\n'

        raise JValueError

class JIoVAL_U(JIoVAL):
    """Pluggable VAL codec ("U+..." / "...+U" data types).

    Ships with no encoding logic of its own. A developer registers a
    ``dumps``/``loads`` pair once (typically at application start-up) via
    :meth:`register` or the module-level :func:`register_user_val_codec`
    helper, and every ``JDb`` opened with a 'U' VAL data_type (``J+U``,
    ``S+U``, ``U+U``) routes every value through that pair. This is the
    extension point for encryption, custom compression, protobuf, etc.,
    without needing to fork the library.
    """
    __slots__ = ('_dumps', '_loads', 'pad_byte')

    def __init__(self):
        self._dumps: Optional[Callable[[Any], bytes]] = None
        self._loads: Optional[Callable[[bytes], Any]] = None
        self.pad_byte: bytes = b'\n'

    def register(self, dumps:Callable[[Any], bytes], loads:Callable[[bytes], Any], pad_byte:bytes=b'\n') -> None:
        """Register the developer-defined VAL codec.

        Args:
            dumps (Callable[[Any], bytes]): Encode a Python value into bytes.
            loads (Callable[[bytes], Any]): Decode bytes back into the Python value.
            pad_byte (bytes, optional): Single byte guaranteed to never occur as the
                first/last byte of ``dumps()`` output; used only when zip_type=NO_ZIP
                to pad small values inline in the KEY row. Defaults to ``b'\\n'``.

        Raises:
            TypeError: If dumps/loads are not callable, pad_byte is not a single byte,
                or the dumps/loads round-trip self-test fails.
        """
        if not callable(dumps) or not callable(loads):
            raise TypeError('dumps and loads must be callable')
        if not (isinstance(pad_byte, bytes) and len(pad_byte) == 1):
            raise TypeError('pad_byte must be a single byte, e.g. b"\\n"')

        test_val = {'key1':0, 'key2':[True,2.,'3']}
        try:
            if loads(dumps(test_val)) != test_val:
                raise TypeError

        except Exception as e:
            raise TypeError('dumps/loads cannot work correctly') from e

        self._dumps = dumps
        self._loads = loads
        self.pad_byte = pad_byte

    def unregister(self) -> None:
        """Clear a previously registered codec, e.g. between tests."""
        self._dumps = self._loads = None
        self.pad_byte = b'\n'

    @property
    def is_registered(self) -> bool:
        """bool: Whether a developer codec has been registered yet."""
        return self._dumps is not None and self._loads is not None

    def dumps(self, data:Any) -> bytes:
        """Serialize a value using the registered developer codec."""
        if self._dumps is None:
            raise UserCodecNotRegisteredError(
                "data_type 'U' (VAL) is selected but no codec is registered. "
                "Call register_user_val_codec(dumps, loads) before opening the JDb.")
        try:
            return self._dumps(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads(self, data:bytes) -> Any:
        """Deserialize a value using the registered developer codec."""
        if self._loads is None:
            raise UserCodecNotRegisteredError(
                "data_type 'U' (VAL) is selected but no codec is registered. "
                "Call register_user_val_codec(dumps, loads) before opening the JDb.")
        try:
            return self._loads(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
g_KEY_J = JIoKEY_J()
g_KEY_S = JIoKEY_S()
g_KEY_M = JIoKEY_M()
g_KEY_L = JIoKEY_L()
g_VAL_J = JIoVAL_J()
g_VAL_S = JIoVAL_S()
g_VAL_M = JIoVAL_M()
g_VAL_P = JIoVAL_P()
g_VAL_Y = JIoVAL_Y()
g_VAL_U = JIoVAL_U()
g_KEY_U = JIoKEY_U()
g_HEAD = JIoHEAD()

def register_user_val_codec(dumps:Callable[[Any], bytes], loads:Callable[[bytes], Any], pad_byte:bytes=b'\n') -> None:
    """Register the developer-defined VAL codec used by the 'U' VAL data types (J+U, S+U, U+U).

    Call this once, before opening any JDb with a 'U' data_type. Typical use case
    is layering encryption on top of the existing JSON/msgpack encoders:

    Example:
        >>> from cryptography.fernet import Fernet
        >>> from omni_json_db.jdb_io import register_user_val_codec, json_dumps, json_loads
        >>> fernet = Fernet(Fernet.generate_key())
        >>> register_user_val_codec(
        ...     dumps=lambda data: fernet.encrypt(json_dumps(data)),
        ...     loads=lambda raw: json_loads(fernet.decrypt(raw)),
        ... )
        >>> jdb = JDb('secure.jdb', data_type='J+U')  # readable KEY, encrypted VAL

    Args:
        dumps (Callable[[Any], bytes]): Encode a Python value into bytes.
        loads (Callable[[bytes], Any]): Decode bytes back into the Python value.
        pad_byte (bytes, optional): Single byte guaranteed to never occur as the
            first/last byte of ``dumps()`` output. Defaults to ``b'\\n'``.
    """
    g_VAL_U.register(dumps, loads, pad_byte)

def unregister_user_val_codec():
    """Clear the process-wide VAL codec registered via ``register_user_val_codec()``.

    After this, opening a JDb with a 'U' VAL data_type (J+U, S+U, U+U) will raise
    :class:`UserCodecNotRegisteredError` again unless a per-instance ``val_codec=``
    is supplied instead. Mainly useful for tests.
    """
    g_VAL_U.unregister()

def register_user_key_codec(dumps:Callable[..., bytes], loads:Callable[[bytes], Tuple[str,int,int,int,int,int,int]],
                             dumps_v0:Optional[Callable[..., bytes]]=None, loads_v0:Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int]]]=None) -> None:
    """Register the developer-defined KEY (row index) codec used by data_type 'U+U'.

    Only needed if the KEY row itself (key string + file offsets) must also be
    transformed. Most developers only need :func:`register_user_val_codec`.

    Args:
        dumps (Callable): Receives a single packed row tuple
            ``(key, file_id, offset, row_size, val_size, ver, days)`` and returns ``bytes``.
            (Note: unlike the KEY row's field names might suggest, this is called with
            *one* tuple argument, not 7 separate positional arguments.)
        loads (Callable[[bytes], Tuple]): ``bytes -> (key, file_id, offset, row_size, val_size, ver, days)``.
        dumps_v0 (Callable, optional): Legacy v0-layout variant of ``dumps``. Defaults to ``dumps``.
        loads_v0 (Callable, optional): Legacy v0-layout variant of ``loads``. Defaults to ``loads``.
    """
    g_KEY_U.register(dumps, loads, dumps_v0, loads_v0)

def unregister_user_key_codec():
    """Clear the process-wide KEY codec registered via ``register_user_key_codec()``.

    After this, opening a JDb with data_type 'U+U' will raise
    :class:`UserCodecNotRegisteredError` again unless a per-instance ``key_codec=``
    is supplied instead. Mainly useful for tests.
    """
    g_KEY_U.unregister()

class JIo(JIoBase):
    """Core processing engine linking pipeline translation modules and file handles."""

    # reduce memory usage --> __dict__, but child class cannot have member
    __slots__ = ('days', 'sync_id', 'swap_id', 'remv_id', 'min_days',\
            '_sync_id', '_swap_id', '_remv_id', '_n_records',\
            '_n_lines', 'file_size', 'n_records', 'n_lines', 'groups',\
            '_data_type', '_zip_type', '_key_limit', 'index_size',\
            'max_file_size', 'reserved_rate', 'api_ver', 'file_table',\
            'files_obj', 'key_table', 'window_size', 'min_value_size',\
            '_KEY_rows', '_DEAD_rows', 'row_bytes', 'pad_byte', 'pad0_byte',\
            'KEY_dumps', 'KEY_loads', 'VAL_dumps', 'VAL_loads',\
            'HEAD_dumps', 'HEAD_loads','VAL_zip', 'VAL_unzip', 'VAL_unzip0',\
            '_val_codec', '_key_codec')

    @staticmethod
    def z_zip_type_str(zip_type:int) -> str:
        """Convert a compression code number to its short name.

        Args:
            zip_type (int): The compression code.

        Returns:
            str: The short name (e.g., ``'zs'``, ``'gz'``, ``'no'``).

        Raises:
            ValueError: If the code is unknown.
        """
        if zip_type == NO_ZIP: return 'no'
        if zip_type == GZ_ZIP: return 'gz'
        if zip_type == BZ_ZIP: return 'bz'
        if zip_type == XZ_ZIP: return 'xz'
        if zip_type == ZS_ZIP: return 'zs'
        if zip_type == BR_ZIP: return 'br'
        if zip_type == Z1_ZIP: return 'z1'
        if zip_type == Z2_ZIP: return 'z2'
        if zip_type == LZ_ZIP: return 'lz'

        raise ValueError(f'unknown zip type {zip_type}')

    @staticmethod
    def z_data_type_str(data_type:int) -> str:
        """Convert a serialization format code to its ``'<KEY>+<VAL>'`` string.

        Args:
            data_type (int): The format code.

        Returns:
            str: The format string (e.g., ``'J+S'``).

        Raises:
            ValueError: If the code is unknown.
        """
        if data_type == DEF_TYPE: return 'J+S'
        if data_type == L_J_TYPE: return 'L+J'
        if data_type == M_M_TYPE: return 'M+M'
        if data_type == J_J_TYPE: return 'J+J'
        if data_type == J_M_TYPE: return 'J+M'
        if data_type == J_P_TYPE: return 'J+P'
        if data_type == S_S_TYPE: return 'S+S'
        if data_type == J_S_TYPE: return 'J+S'
        if data_type == S_M_TYPE: return 'S+M'
        if data_type == S_J_TYPE: return 'S+J'
        if data_type == S_P_TYPE: return 'S+P'
        if data_type == J_Y_TYPE: return 'J+Y'
        if data_type == S_Y_TYPE: return 'S+Y'
        if data_type == J_U_TYPE: return 'J+U'
        if data_type == S_U_TYPE: return 'S+U'
        if data_type == U_U_TYPE: return 'U+U'

        raise ValueError(f'unknown data type {data_type}')

    @staticmethod
    def z_key_limit_str(key_limit:int) -> str:
        """Convert a key-table code to its readable string form.

        Args:
            key_limit (int): The key-table code.

        Returns:
            str: The readable form (e.g., ``'no'``, ``'bt'``, ``'l0'``, ``'<100'``).
        """
        if key_limit == 0:      return 'no'
        if key_limit == -0x100: return 'bt'
        if key_limit > 0:       return f'<{key_limit+1}'
        return f'l{-key_limit-1}'

    @staticmethod
    def z_conv_days(timestamp:Union[int,float,datetime,dt_date]) -> int:
        """Compute the relative day integer offset from the baseline date.

        Args:
            timestamp (int | float | datetime | dt_date): The target timestamp.

        Returns:
            int: The absolute day index number.
        """
        if isinstance(timestamp, datetime): # before dt_date
            timestamp = timestamp.date()

        if isinstance(timestamp, dt_date):
            if timestamp < THE_1ST_DATE:
                return 0

            return (timestamp - THE_1ST_DATE).days

        return NUM_1970_DAYS + max(0, int(timestamp) - THE_1ST_SEC) // DAY_SEC

    @staticmethod
    def z_conv_date(days:int) -> Tuple[dt_date, dt_date]:
        """Convert relative day integers back into structured standard timezone-agnostic calendar object dates.

        Args:
            days (int): Compact relative timeline offset value tracking variable inside index row.

        Returns:
            Tuple[dt_date, dt_date]: Pair processing baseline baseline dates and updated adaptation tracking timeline pointers.
        """
        old_days = days & OLD_DAY_MASK
        new_days = (days & NEW_DAY_MASK) >> NEW_DAY_SHIFT

        # NOTES: remove after API v3
        if old_days < NUM_1970_DAYS and old_days+new_days < NUM_1996_DAYS:  # pragma: no cover
            old_days += NUM_2000_DAYS
            old_date = THE_1ST_DATE + timedelta(days=old_days)
            if old_date > dt_date.today():
                old_date -= timedelta(days=NUM_2000_DAYS)
        else:
            old_date = THE_1ST_DATE + timedelta(days=old_days)

        new_date = old_date + timedelta(days=new_days)
        return old_date, new_date

    @staticmethod
    @lru_cache(maxsize=256)
    def z_conv_str_to_days(val:str) -> int:
        """Parse raw textual timestamp representation parameters expressions converting fields directly to unified day numbers integers.

        Args:
            val (str): Human readable raw calendar date text sequence string (e.g., 'YYYY-MM-DD').

        Returns:
            int: Compact integer measurement mapping day metrics boundaries positions indices numbers parameters logs.

        Raises:
            ValueError: If alphanumeric parsing patterns break constraint definitions templates format specifications.
        """
        _vals = re_findall(r'(\d+)(?=\W|$)', val)
        if len(_vals) == 3:
            return JIo.z_conv_days(dt_date(*[int(v) for v in _vals[0:3]]))

        if len(_vals) == 6:
            _date_0 = JIo.z_conv_days(dt_date(*[int(v) for v in _vals[0:3]]))
            _date_1 = JIo.z_conv_days(dt_date(*[int(v) for v in _vals[3:6]]))
            if _date_0 >= _date_1:
                val = _date_1 & OLD_DAY_MASK
                val |= ((_date_0 - _date_1) << NEW_DAY_SHIFT ) & NEW_DAY_MASK
            else:
                val = _date_0 & OLD_DAY_MASK
                val |= ((_date_1 - _date_0) << NEW_DAY_SHIFT ) & NEW_DAY_MASK

            return val
        else:
            raise ValueError

    def __init__(self, files_obj:JFilesBase, \
            data_type:Union[str,int,None]=None, \
            zip_type:Union[str,int,None]=None, \
            key_limit:Union[str,int,None]=None, \
            api_ver:Optional[int]=None, \
            min_value_size:Optional[int]=None, \
            index_size:Optional[int]=None, \
            max_file_size:Optional[int]=None, \
            reserved_rate:Optional[float]=None, \
            sync_id:int=0, swap_id:int=0, remv_id:int=0, \
            val_codec:Optional['JIoVAL_U']=None, \
            key_codec:Optional['JIoKEY_U']=None):

        """Initialize the IO engine that reads and writes the KEY/VAL files.

        Args:
            files_obj (JFilesBase): File management abstraction driver context.
            data_type (str | int, optional): Codec serialization scheme categorization flag.

                - 'L+J' | 1  = KEY=split    | VAL=Json
                - 'M+M' | 2  = KEY=Marshal  | VAL=Marshal
                - 'J+J' | 3  = KEY=Json     | VAL=Json
                - 'J+M' | 4  = KEY=Json     | VAL=Marshal
                - 'J+P' | 5  = KEY=Json     | VAL=Pickle
                - 'S+S' | 6  = KEY=msgpack  | VAL=msgpack
                - 'J+S' | 7  = KEY=Json     | VAL=msgpack
                - 'S+M' | 8  = KEY=msgpack  | VAL=Marshal
                - 'S+J' | 9  = KEY=msgpack  | VAL=Json
                - 'S+P' | 10 = KEY=msgpack  | VAL=Pickle
                - 'J+Y' | 11 = KEY=msgpack  | VAL=YAML
                - 'S+Y' | 12 = KEY=msgpack  | VAL=YAML
                - 'J+U' | 13 = KEY=msgpack  | VAL=User
                - 'S+U' | 14 = KEY=msgpack  | VAL=User
                - 'U+U' | 15 = KEY=User     | VAL=User

            zip_type (str | int, optional): Target row data level compression profile.
                
                - 'no' | 0 = no compression for VAL
                - 'gz' | 1 = gzip compression(9) for VAL
                - 'bz' | 2 = bz2 compression(9) for VAL
                - 'xz' | 3 = lzma compression for VAL
                - 'zs' | 4 = zstandard compression(22) for VAL
                - 'br' | 5 = brotli compression(6) for VAL
                - 'z1' | 6 = zstandard compression(6) for VAL
                - 'z2' | 7 = zstandard compression(11) for VAL
                - 'lz' | 8 = lz4 compression(0) for VAL

            key_limit (str | int, optional): Sizing constraint boundary for index memory.

                - "no" | 0 = use DictKeyTable (dict). (default). 
                - "bt" | -0x100 = use BTreeKeyTable.
                - "l0"-"l5" | -ve = use LiteKeyTable (fast load_keys()). 
                - "<{n}" | +ve = use PartialKeyTable (fast load_keys()).

            api_ver (int, optional): Logical structural schema edition index. Defaults to latest.

                - 0 = oldest version.
                - None = latest version. (default)

            min_value_size (int, optional): Minimal alignment constraint width.
            index_size (int, optional): Fixed byte width defining row segmentation sizes.
            max_file_size (int, optional): Constraint limiting data partitions allocation sizes.
            reserved_rate (float, optional): Expansion reserve factor allocated for updates.
            sync_id (int, optional): Synchronization sequence generation tracker. Defaults to 0.
            swap_id (int, optional): Rearrangement transaction milestone tracking index. Defaults to 0.
            remv_id (int, optional): Accumulative deletions sequence tracker. Defaults to 0.
            val_codec (Optional[JIoVAL_U], optional): Per-instance VAL codec override for 'U' VAL
                data types (J+U, S+U, U+U). Lets different JDb instances use different developer
                codecs (e.g. per-tenant encryption keys) instead of sharing the process-wide
                ``g_VAL_U`` registered via ``register_user_val_codec()``. Must already have a
                codec registered (``JIoVAL_U().register(dumps, loads)``) before being passed in.
            key_codec (Optional[JIoKEY_U], optional): Per-instance KEY codec override for the
                'U+U' data type, analogous to ``val_codec`` but for the row index. Defaults to
                the process-wide ``g_KEY_U``.

        Raises:
            TypeError: If input structural variables violate driver specifications.
        """
        if not isinstance(files_obj, JFilesBase):
            raise TypeError

        if val_codec is not None:
            if not isinstance(val_codec, JIoVAL_U) or not val_codec.is_registered:
                raise TypeError('val_codec must be a registered JIoVAL_U instance')

        if key_codec is not None:
            if not isinstance(key_codec, JIoKEY_U) or not key_codec.is_registered:
                raise TypeError('key_codec must be a registered JIoKEY_U instance')

        if index_size is None or index_size == 0:
            index_size = DEF_INDEX_SIZE

        if reserved_rate is None:
            reserved_rate = DEF_RATIO

        if max_file_size is None or max_file_size == 0:
            max_file_size = DEF_FILE_SIZE

        if min_value_size is None or min_value_size == 0:
            min_value_size = DEF_VALUE_SIZE # key file allow to store below 15 bytes

        if key_limit is None:
            key_limit = DEF_KEY_LIMIT

        if data_type is None: # pragma: no cover
            data_type = DEF_TYPE

        if zip_type is None: # pragma: no cover
            zip_type = DEF_ZIP

        if api_ver is None:
            api_ver = API_LATEST

        self._KEY_rows      = OrderedDict()
        self._DEAD_rows     = {}
        self._val_codec     = val_codec
        self._key_codec     = key_codec
        self._data_type     = self._zip_type = self._key_limit = -1
        self.key_table      = DictKeyTable() # must before self.key_limit = key_limit
        self.sync_id        = sync_id
        self.swap_id        = swap_id
        self.remv_id        = remv_id
        self.index_size     = index_size
        self.min_value_size = min_value_size
        self.max_file_size  = max_file_size
        self.reserved_rate  = reserved_rate
        self.files_obj      = files_obj
        self.data_type      = data_type
        if self._zip_type < 0:
            self.zip_type = zip_type
        self.key_limit      = key_limit
        self.file_table     = defaultdict(int)
        self.groups         = JDbGroupDict()
        self.key_table      = PartialKeyTable(self) if self._key_limit > 0 else \
                                DictKeyTable() if self._key_limit == 0 else \
                                BTreeKeyTable() if self._key_limit == -0x100 else \
                                LiteKeyTable(self, (-self._key_limit-1) | 0x1000)

        self.days = self.min_days = self._swap_id = self._remv_id = -1
        self._sync_id = self._n_records = self._n_lines = self.file_size = self.n_records = self.n_lines = 0

        self.api_ver        = api_ver
        self.HEAD_dumps     = g_HEAD.dumps_v1
        self.HEAD_loads     = g_HEAD.loads_v1
        self.KEY_dumps      = g_KEY_J.dumps_v1
        self.KEY_loads      = g_KEY_J.loads_v1
        self.VAL_dumps      = g_VAL_J.dumps
        self.VAL_loads      = g_VAL_J.loads
        self.VAL_zip        = ZIP_lut[0]
        self.VAL_unzip      = UNZIP_lut[0]
        self.VAL_unzip0     = UNZIP_lut0[0]
        self.pad_byte       = b'\x00'
        self.pad0_byte      = b'\x00'
        self.window_size = max(1, int(KEY_FILE_BUF_SIZE / index_size))
        self.row_bytes = index_size - min_value_size * (1 + reserved_rate)

        self.update_days()
        self.init_APIs(api_ver)

        if not (isinstance(self._data_type, int) and LAST_DATA_TYPE >= self._data_type >= 0):
            raise TypeError
        if not (isinstance(self._zip_type, int) and LAST_ZIP_TYPE >= self._zip_type >= 0):
            raise TypeError
        if not isinstance(self._key_limit, int):
            raise TypeError
        if not isinstance(self.key_table, (KeyTable, DictKeyTable, BTreeKeyTable)):
            raise TypeError
        if not (isinstance(self.pad_byte, bytes) and len(self.pad_byte) == 1):
            raise TypeError
        if not (isinstance(self.pad0_byte, bytes) and len(self.pad0_byte) == 1):
            raise TypeError

    def __repr__(self) -> str:
        """Generate structured string summary reports outlining operational engine states parameters configurations specs.

        Returns:
            str: Identity presentation string block details tracks logs metrics layout context text.
        """
        return f'<{type(self).__name__}[v{self.api_ver}|{self.data_type_str}|{self.zip_type_str}|{self.key_limit_str}|{self.index_size}|{self.n_records}+{self.n_lines-self.n_records}|k:{self.file_size:,}|s:{self.sync_id}/{self.swap_id}/{self.remv_id}] at {hex(id(self))}>'

    def init_APIs(self, api_ver:Optional[int], reset:bool=False):
        """Bind the header/KEY/VAL codec methods for the given format version.

        Args:
            api_ver (Optional[int]): The on-disk format version; ``None`` uses the latest.
            reset (bool, optional): Also reset the in-memory state first. Defaults to False.
        """
        files_obj = self.files_obj
        if self.min_days < 0:
            self.min_days = self.z_conv_days(files_obj.KEY_date())

        fp = None
        data_type = self._data_type
        zip_type = self._zip_type
        try:
            fp = files_obj.KEY_open('rb')
            header = bytearray(HEADER_SIZE)
            if fp.readinto(header) == HEADER_SIZE:
                if header[0] == 91: # = '['
                    info = json_loads(header)
                else: # pragma: no cover
                    # deprecated
                    info = [int(v) for v in header.decode('utf8').split(',')]
                nn = len(info)
                if nn >= 9: # pragma: no cover
                    api_ver = info[8]
                    if data_type == DEF_TYPE:
                        data_type = info[5]

                    if zip_type == DEF_ZIP:
                        zip_type = info[4]
                else: # pragma: no cover
                    if nn >= 6:
                        api_ver = API_V0
                        if data_type == DEF_TYPE:
                            data_type = info[5]

                        if zip_type == DEF_ZIP:
                            zip_type = info[4]
                    else:
                        api_ver = API_V0

        # may throw FileNotFoundError
        except Exception: # pragma: no cover
            if api_ver is None:
                api_ver = API_LATEST

        finally:
            if fp is not None:
                fp.close()

        self.change_APIs(api_ver, data_type, zip_type, reset=reset)

    @property
    def zip_type_str(self) -> str:
        """Get the current compression code as a short string (e.g. ``'zs'``, ``'no'``).

        Returns:
            str: The compression short name.
        """
        return self.z_zip_type_str(self._zip_type)

    @property
    def zip_type(self) -> int:
        """Get the current compression code.

        Returns:
            int: The compression code.
        """
        return self._zip_type

    @zip_type.setter
    def zip_type(self, value:Union[int,str]):
        """Set the active algorithmic code rule string or integer bounding dataset row level serialization compression properties.

        Args:
            value (Union[int, str]): Target format indicator selection option parameter string or integer index.
        """
        if isinstance(value, str):
            value = value.lower()
            if not value or value in {'no', '-', '--'}:
                value = NO_ZIP
            elif value in {'gz', 'gzip'}:
                value = GZ_ZIP
            elif value in {'bz', 'bzip', 'bz2'}:
                value = BZ_ZIP
            elif value in {'xz', 'lzma', 'xzip'}:
                value = XZ_ZIP
            elif value in {'z0', 'zs0', 'zstd0', 'zs', 'zstd'}:
                value = ZS_ZIP
            elif value in {'br', 'brotli'}:
                value = BR_ZIP
            elif value in {'z1', 'zs1', 'zstd1'}:
                value = Z1_ZIP
            elif value in {'z2', 'zs2', 'zstd2'}:
                value = Z2_ZIP
            elif value in {'lz', 'lz4'}:
                value = LZ_ZIP
            else:
                raise ValueError(f'invalid zip string {value}')

        if not isinstance(value, int):
            raise TypeError(f'invalid data type {value}')

        if not LAST_ZIP_TYPE >= value >= 0:
            raise ValueError(f'invalid data type {value}')

        if value in {ZS_ZIP, Z1_ZIP, Z2_ZIP} and zstd_decompress is None: # pragma: no cover
            raise ModuleNotFoundError("zstandard is not installed. Please pip install zstandard.")

        if value == LZ_ZIP and lz4_decompress is None: # pragma: no cover
            raise ModuleNotFoundError("lz4 is not installed. Please pip install lz4.")

        if value == BR_ZIP and br_decompress is None: # pragma: no cover
            raise ModuleNotFoundError("brotli is not installed. Please pip install brotli.")

        if ZIP_lut[value] is None:
            raise ValueError(f'cannot use this zip type, please pip install. {value}')

        self._zip_type = value

    @property
    def data_type_str(self) -> str:
        """Get the serialization format as a ``'<KEY>+<VAL>'`` string (e.g. ``'J+S'``).

        Returns:
            str: The format string.
        """
        return self.z_data_type_str(self._data_type)

    @property
    def data_type(self) -> int:
        """Get operational database layout coding formats parameters targets.

        Returns:
            int: Operational mapping category tracking specification number integer.
        """
        return self._data_type

    @data_type.setter
    def data_type(self, value:Union[int,str]):
        """Set the serialization format.

        Args:
            value (Union[int, str]): The new format, as a ``'<KEY>+<VAL>'`` string or its code.
        """
        if isinstance(value, str):
            value = value.upper()
            if not value: # pragma: no cover
                value = J_S_TYPE
            else:
                if value.find('(') > 0 and value[-1] == ')':
                    value, zip_type = value.split('(')
                    self.zip_type = zip_type[:-1]

                if value in {'J+S', 'J:S', 'JSON+MSGPACK'}:
                    value = J_S_TYPE
                elif value in {'J+J', 'J:J', 'JSON+JSON'}:
                    value = J_J_TYPE
                elif value in {'S+S', 'S:S', 'MSGPACK+MSGPACK'}:
                    value = S_S_TYPE
                elif value in {'S+J', 'S:J', 'MSGPACK+JSON'}:
                    value = S_J_TYPE
                elif value in {'J+M', 'J:M', 'JSON+MARSHAL'}:
                    value = J_M_TYPE
                elif value in {'S+M', 'S:M', 'MSGPACK+MARSHAL'}:
                    value = S_M_TYPE
                elif value in {'J+P', 'J:P', 'JSON+PICKLE'}:
                    value = J_P_TYPE
                elif value in {'S+P', 'S:P', 'MSGPACK+PICKLE'}:
                    value = S_P_TYPE
                elif value in {'J+Y', 'J:Y', 'JSON+YAML'}:
                    value = J_Y_TYPE
                elif value in {'S+Y', 'S:Y', 'MSGPACK+YAML'}:
                    value = S_Y_TYPE
                elif value in {'M+M', 'M:M', 'MARSHAL+MARSHAL'}:
                    value = M_M_TYPE
                elif value in {'L+J', 'L:J', 'SPLIT+JSON'}:
                    value = L_J_TYPE
                elif value in {'J+U', 'J:U', 'JSON+USER'}:
                    value = J_U_TYPE
                elif value in {'S+U', 'S:U', 'MSGPACK+USER'}:
                    value = S_U_TYPE
                elif value in {'U+U', 'U:U', 'USER+USER'}:
                    value = U_U_TYPE
                else:
                    raise ValueError(f'invalid data string {value}')

        if not isinstance(value, int):
            raise TypeError(f'invalid data type {value}')

        if not LAST_DATA_TYPE >= value >= 0:
            raise ValueError(f'invalid data type {value}')

        if value in {J_Y_TYPE, S_Y_TYPE} and yaml is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

        if value in {J_U_TYPE, S_U_TYPE, U_U_TYPE} and self._val_codec is None and not g_VAL_U.is_registered:
            raise UserCodecNotRegisteredError(
                "data_type requires a VAL codec. Pass val_codec=... to JDb()/JIo(), "
                "or call register_user_val_codec(dumps, loads) to set a process-wide default.")

        if value == U_U_TYPE and self._key_codec is None and not g_KEY_U.is_registered:
            raise UserCodecNotRegisteredError(
                "data_type 'U+U' requires a KEY codec too. Pass key_codec=... to JDb()/JIo(), "
                "or call register_user_key_codec(dumps, loads) to set a process-wide default.")

        self._data_type = value

    @property
    def key_limit(self) -> int:
        """Get memory cache restriction constraint rules selection variables indices numbers.

        Returns:
            int: Operational limitations tracking threshold index value integer number.
        """
        return self._key_limit

    @key_limit.setter
    def key_limit(self, value:Union[int,str]):
        """Set the key-table implementation.

        Args:
            value (Union[int, str]): The new key-table type — a code string
                (``'no'``, ``'bt'``, ``'l0'``-``'l5'``) or an int size for a partial table.
        """
        if isinstance(value, str):
            value = value.lower()
            if not value or value in {'no', '-', '--'}:
                value = 0
            elif value.startswith('l'):
                value = -(int(value[1:]) + 1)
            elif value in {'tr', 'bt', 'btree', 'tree'}:
                value = -0x100
            elif value.startswith('<'):
                value = max(1, int(value[2:]) if value[1] == '=' else (int(value[1:])-1))
            else:
                raise ValueError(f'invalid key limit string {value}')

        if not isinstance(value, int):
            raise TypeError(f'invalid key limit type {value}')

        if value == -0x100 and BTreeKeyTable is None: # pragma: no cover
            raise ModuleNotFoundError("BTrees is not installed. Please pip install BTrees.")

        if self._key_limit != value and (self.key_table is not None):
            if value == 0:
                if self._key_limit != 0:
                    self.key_table.clear()
                    self.key_table = DictKeyTable()
                    self._n_records = self._n_lines = self.file_size = 0

            elif value == -0x100:
                if self._key_limit != -0x100:
                    self.key_table.clear()
                    self.key_table = BTreeKeyTable()
                    self._n_records = self._n_lines = self.file_size = 0

            elif value < 0:
                _mode = (-value-1) | 0x1000
                if self._key_limit >= 0 or -self._key_limit >= 0x10 or self.key_table.get_mode() != _mode:
                    self.key_table.clear()
                    self.key_table = LiteKeyTable(self, _mode)
                    self._n_records = self._n_lines = self.file_size = 0

            elif value > 0:
                if self._key_limit <= 0:
                    self.key_table.clear()
                    self.key_table = PartialKeyTable(self)
                    self._n_records = self._n_lines = self.file_size = 0

        self._key_limit = value

    @property
    def key_limit_str(self) -> str:
        """Get the key-table type as a readable string (e.g. ``'no'``, ``'l0'``).

        Returns:
            str: The key-table type.
        """
        return self.z_key_limit_str(self._key_limit)

    def change_APIs(self, version:Optional[int]=None, data_type:int=DEF_TYPE, zip_type:int=DEF_ZIP, reset:bool=False):
        """Switch the format version, serialization, and compression, re-binding the codec methods.

        Args:
            version (Optional[int], optional): Target on-disk format version. Defaults to None.
            data_type (int, optional): New serialization format code. Defaults to DEF_TYPE.
            zip_type (int, optional): New compression code. Defaults to DEF_ZIP.
            reset (bool, optional): Reset the in-memory state first. Defaults to False.

        Raises:
            TypeError: If an argument has an unsupported type.
            ValueError: If the version or format code is invalid.
        """
        if reset:
            if self.index_size is None: # pragma: no cover
                self.index_size = DEF_INDEX_SIZE

            if self.reserved_rate is None:
                self.reserved_rate = DEF_RATIO

            if self.max_file_size is None:
                self.max_file_size = DEF_FILE_SIZE

            if self.min_value_size is None: # pragma: no cover
                self.min_value_size = DEF_VALUE_SIZE

            self.file_table.clear()
            self.key_table.clear()
            self.groups.clear()
            self._KEY_rows.clear()
            self._DEAD_rows.clear()
            self._swap_id = self._remv_id = -1
            self._sync_id = self._n_records = self._n_lines = self.file_size = self.n_records = self.n_lines = 0
            self.update_days()

        if version is None: # pragma: no cover
            version = API_LATEST

        if data_type == DEF_TYPE: # pragma: no cover
            data_type = J_S_TYPE

        if zip_type == DEF_ZIP: # pragma: no cover
            zip_type = NO_ZIP

        if not isinstance(data_type, int):
            raise TypeError
        if not isinstance(zip_type, int):
            raise TypeError
        if not isinstance(version, int):
            raise TypeError

        if data_type in {J_Y_TYPE, S_Y_TYPE} and yaml is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

        if data_type in {J_U_TYPE, S_U_TYPE, U_U_TYPE} and self._val_codec is None and not g_VAL_U.is_registered:
            raise UserCodecNotRegisteredError(
                "data_type requires a VAL codec. Pass val_codec=... to JDb()/JIo(), "
                "or call register_user_val_codec(dumps, loads) to set a process-wide default.")

        if data_type == U_U_TYPE and self._key_codec is None and not g_KEY_U.is_registered:
            raise UserCodecNotRegisteredError(
                "data_type 'U+U' requires a KEY codec too. Pass key_codec=... to JDb()/JIo(), "
                "or call register_user_key_codec(dumps, loads) to set a process-wide default.")

        if zip_type in {ZS_ZIP, Z1_ZIP, Z2_ZIP} and zstd_decompress is None: # pragma: no cover
            raise ModuleNotFoundError("zstandard is not installed. Please pip install zstandard.")

        if zip_type == LZ_ZIP and lz4_decompress is None: # pragma: no cover
            raise ModuleNotFoundError("lz4 is not installed. Please pip install lz4.")

        if zip_type == BR_ZIP and br_decompress is None: # pragma: no cover
            raise ModuleNotFoundError("brotli is not installed. Please pip install brotli.")

        if version == API_V0:
            self._data_type     = data_type
            self._zip_type      = zip_type
            self.api_ver        = version
            self.VAL_zip        = ZIP_lut[zip_type]
            self.VAL_unzip      = UNZIP_lut[zip_type]
            self.VAL_unzip0     = UNZIP_lut0[zip_type]
            self.pad_byte       = PAD_lut[zip_type](data_type)
            self.pad0_byte      = PAD_lut[NO_ZIP](data_type)
            if data_type in (J_U_TYPE, S_U_TYPE, U_U_TYPE) and self._val_codec is not None:
                # per-instance codec may declare its own safe NO_ZIP pad byte
                self.pad_byte  = self._val_codec.pad_byte if zip_type == NO_ZIP else self.pad_byte
                self.pad0_byte = self._val_codec.pad_byte
            self.HEAD_dumps     = g_HEAD.dumps_v0
            self.HEAD_loads     = g_HEAD.loads_v0
            if data_type == L_J_TYPE:
                self.KEY_loads = g_KEY_L.loads_v0
                self.KEY_dumps = g_KEY_L.dumps_v0
                self.VAL_loads = g_VAL_J.loads
                self.VAL_dumps = g_VAL_J.dumps
            elif data_type == M_M_TYPE:
                self.KEY_loads = g_KEY_M.loads_v0
                self.KEY_dumps = g_KEY_M.dumps_v0
                self.VAL_loads = g_VAL_M.loads
                self.VAL_dumps = g_VAL_M.dumps
            elif data_type == J_J_TYPE:
                self.KEY_loads = g_KEY_J.loads_v0
                self.KEY_dumps = g_KEY_J.dumps_v0
                self.VAL_loads = g_VAL_J.loads
                self.VAL_dumps = g_VAL_J.dumps
            elif data_type == J_M_TYPE:
                self.KEY_loads = g_KEY_J.loads_v0
                self.KEY_dumps = g_KEY_J.dumps_v0
                self.VAL_loads = g_VAL_M.loads
                self.VAL_dumps = g_VAL_M.dumps
            elif data_type == J_P_TYPE:
                self.KEY_loads = g_KEY_J.loads_v0
                self.KEY_dumps = g_KEY_J.dumps_v0
                self.VAL_loads = g_VAL_P.loads
                self.VAL_dumps = g_VAL_P.dumps
            elif data_type == S_S_TYPE:
                self.KEY_loads = g_KEY_S.loads_v0
                self.KEY_dumps = g_KEY_S.dumps_v0
                self.VAL_loads = g_VAL_S.loads
                self.VAL_dumps = g_VAL_S.dumps
            elif data_type == J_S_TYPE:
                self.KEY_loads = g_KEY_J.loads_v0
                self.KEY_dumps = g_KEY_J.dumps_v0
                self.VAL_loads = g_VAL_S.loads
                self.VAL_dumps = g_VAL_S.dumps
            elif data_type == S_M_TYPE:
                self.KEY_loads = g_KEY_S.loads_v0
                self.KEY_dumps = g_KEY_S.dumps_v0
                self.VAL_loads = g_VAL_M.loads
                self.VAL_dumps = g_VAL_M.dumps
            elif data_type == S_J_TYPE:
                self.KEY_loads = g_KEY_S.loads_v0
                self.KEY_dumps = g_KEY_S.dumps_v0
                self.VAL_loads = g_VAL_J.loads
                self.VAL_dumps = g_VAL_J.dumps
            elif data_type == S_P_TYPE:
                self.KEY_loads = g_KEY_S.loads_v0
                self.KEY_dumps = g_KEY_S.dumps_v0
                self.VAL_loads = g_VAL_P.loads
                self.VAL_dumps = g_VAL_P.dumps
            elif data_type == J_Y_TYPE:
                self.KEY_loads = g_KEY_J.loads_v0
                self.KEY_dumps = g_KEY_J.dumps_v0
                self.VAL_loads = g_VAL_Y.loads
                self.VAL_dumps = g_VAL_Y.dumps
            elif data_type == S_Y_TYPE:
                self.KEY_loads = g_KEY_S.loads_v0
                self.KEY_dumps = g_KEY_S.dumps_v0
                self.VAL_loads = g_VAL_Y.loads
                self.VAL_dumps = g_VAL_Y.dumps
            elif data_type == J_U_TYPE:
                self.KEY_loads = g_KEY_J.loads_v0
                self.KEY_dumps = g_KEY_J.dumps_v0
                _val = self._val_codec or g_VAL_U
                self.VAL_loads = _val.loads
                self.VAL_dumps = _val.dumps
            elif data_type == S_U_TYPE:
                self.KEY_loads = g_KEY_S.loads_v0
                self.KEY_dumps = g_KEY_S.dumps_v0
                _val = self._val_codec or g_VAL_U
                self.VAL_loads = _val.loads
                self.VAL_dumps = _val.dumps
            elif data_type == U_U_TYPE:
                _key = self._key_codec or g_KEY_U
                self.KEY_loads = _key.loads_v0
                self.KEY_dumps = _key.dumps_v0
                _val = self._val_codec or g_VAL_U
                self.VAL_loads = _val.loads
                self.VAL_dumps = _val.dumps
            else:
                raise ValueError(f'invalid data type {self.api_ver}->{version} type:{data_type}')

        elif version == API_V1:
            self._data_type     = data_type
            self._zip_type      = zip_type
            self.api_ver        = version
            self.VAL_zip        = ZIP_lut[zip_type]
            self.VAL_unzip      = UNZIP_lut[zip_type]
            self.VAL_unzip0     = UNZIP_lut0[zip_type]
            self.pad_byte       = PAD_lut[zip_type](data_type)
            self.pad0_byte      = PAD_lut[NO_ZIP](data_type)
            if data_type in (J_U_TYPE, S_U_TYPE, U_U_TYPE) and self._val_codec is not None:
                # per-instance codec may declare its own safe NO_ZIP pad byte
                self.pad_byte  = self._val_codec.pad_byte if zip_type == NO_ZIP else self.pad_byte
                self.pad0_byte = self._val_codec.pad_byte
            self.HEAD_dumps     = g_HEAD.dumps_v1
            self.HEAD_loads     = g_HEAD.loads_v1
            if data_type == L_J_TYPE:
                self.KEY_loads = g_KEY_L.loads_v1
                self.KEY_dumps = g_KEY_L.dumps_v1
                self.VAL_loads = g_VAL_J.loads
                self.VAL_dumps = g_VAL_J.dumps
            elif data_type == M_M_TYPE:
                self.KEY_loads = g_KEY_M.loads_v1
                self.KEY_dumps = g_KEY_M.dumps_v1
                self.VAL_loads = g_VAL_M.loads
                self.VAL_dumps = g_VAL_M.dumps
            elif data_type == J_J_TYPE:
                self.KEY_loads = g_KEY_J.loads_v1
                self.KEY_dumps = g_KEY_J.dumps_v1
                self.VAL_loads = g_VAL_J.loads
                self.VAL_dumps = g_VAL_J.dumps
            elif data_type == J_M_TYPE:
                self.KEY_loads = g_KEY_J.loads_v1
                self.KEY_dumps = g_KEY_J.dumps_v1
                self.VAL_loads = g_VAL_M.loads
                self.VAL_dumps = g_VAL_M.dumps
            elif data_type == J_P_TYPE:
                self.KEY_loads = g_KEY_J.loads_v1
                self.KEY_dumps = g_KEY_J.dumps_v1
                self.VAL_loads = g_VAL_P.loads
                self.VAL_dumps = g_VAL_P.dumps
            elif data_type == S_S_TYPE:
                self.KEY_loads = g_KEY_S.loads_v1
                self.KEY_dumps = g_KEY_S.dumps_v1
                self.VAL_loads = g_VAL_S.loads
                self.VAL_dumps = g_VAL_S.dumps
            elif data_type == J_S_TYPE:
                self.KEY_loads = g_KEY_J.loads_v1
                self.KEY_dumps = g_KEY_J.dumps_v1
                self.VAL_loads = g_VAL_S.loads
                self.VAL_dumps = g_VAL_S.dumps
            elif data_type == S_M_TYPE:
                self.KEY_loads = g_KEY_S.loads_v1
                self.KEY_dumps = g_KEY_S.dumps_v1
                self.VAL_loads = g_VAL_M.loads
                self.VAL_dumps = g_VAL_M.dumps
            elif data_type == S_J_TYPE:
                self.KEY_loads = g_KEY_S.loads_v1
                self.KEY_dumps = g_KEY_S.dumps_v1
                self.VAL_loads = g_VAL_J.loads
                self.VAL_dumps = g_VAL_J.dumps
            elif data_type == S_P_TYPE:
                self.KEY_loads = g_KEY_S.loads_v1
                self.KEY_dumps = g_KEY_S.dumps_v1
                self.VAL_loads = g_VAL_P.loads
                self.VAL_dumps = g_VAL_P.dumps
            elif data_type == J_Y_TYPE:
                self.KEY_loads = g_KEY_J.loads_v1
                self.KEY_dumps = g_KEY_J.dumps_v1
                self.VAL_loads = g_VAL_Y.loads
                self.VAL_dumps = g_VAL_Y.dumps
            elif data_type == S_Y_TYPE:
                self.KEY_loads = g_KEY_S.loads_v1
                self.KEY_dumps = g_KEY_S.dumps_v1
                self.VAL_loads = g_VAL_Y.loads
                self.VAL_dumps = g_VAL_Y.dumps
            elif data_type == J_U_TYPE:
                self.KEY_loads = g_KEY_J.loads_v1
                self.KEY_dumps = g_KEY_J.dumps_v1
                _val = self._val_codec or g_VAL_U
                self.VAL_loads = _val.loads
                self.VAL_dumps = _val.dumps
            elif data_type == S_U_TYPE:
                self.KEY_loads = g_KEY_S.loads_v1
                self.KEY_dumps = g_KEY_S.dumps_v1
                _val = self._val_codec or g_VAL_U
                self.VAL_loads = _val.loads
                self.VAL_dumps = _val.dumps
            elif data_type == U_U_TYPE:
                _key = self._key_codec or g_KEY_U
                self.KEY_loads = _key.loads_v1
                self.KEY_dumps = _key.dumps_v1
                _val = self._val_codec or g_VAL_U
                self.VAL_loads = _val.loads
                self.VAL_dumps = _val.dumps
            else:
                raise ValueError(f'invalid data type {self.api_ver}->{version} type:{data_type}')

        else:
            raise ValueError(f'invalid version {self.api_ver}->{version} type:{data_type}')

        try:
            if tuple(self.KEY_loads(self.KEY_dumps('1',2,3,4,5,6,7))) != ('1',2,3,4,5,6,7): # pragma: no cover
                raise TypeError
        except Exception as e: # pragma: no cover
            raise TypeError('invalid KEY_loads/KEY_dumps') from e

        try:
            test_val = {'key1':0, 'key2':[True,2.,'3']}
            if self.VAL_loads(self.VAL_dumps(test_val)) != test_val: # pragma: no cover
                raise TypeError
        except Exception as e:
            raise TypeError('invalid VAL_loads/VAL_dumps') from e

    def sorted_key_table_items(self, start_row:int=0, stop_row:int=-1, copy:bool=False, reverse:bool=False) -> Generator[Tuple[str,int], None, None]:
        """Iterate ``(key, row_id)`` pairs in row order.

        Args:
            start_row (int, optional): First row to include. Defaults to 0.
            stop_row (int, optional): One past the last row; ``-1`` means the
                last active record. Defaults to -1.
            copy (bool, optional): Read directly from the KEY file instead of
                the in-memory table, so the caller may modify the database
                while iterating. Defaults to False.
            reverse (bool, optional): Iterate in descending row order. Defaults to False.

        Yields:
            (str, int): Each record's key and its row id.
        """
        stop_row = self.n_records if stop_row < 0 else min(self.n_records, stop_row)
        start_row = max(0, min(start_row, stop_row-1))
        if copy:
            fp = None
            try:
                files_obj = self.files_obj.copy()
                fp = files_obj.KEY_open('rb')
                row_id = (stop_row-1) if reverse else start_row
                for (_key, _f, _o, _r, _v, _s, _d) in self.KEY_iter(fp, start_row, stop_row, reverse=reverse):
                    yield _key, row_id
                    row_id = (row_id - 1) if reverse else (row_id + 1)

            finally:
                if fp is not None:
                    fp.close()

            return

        lut = {}
        if reverse:
            row = stop_row-1
            for key,_row in self.key_table.items():
                if _row == row:
                    yield key, row
                    row -= 1
                    while lut and row in lut:
                        yield lut.pop(row, ''), row
                        row -= 1
                elif start_row <= _row < stop_row:
                    lut[_row] = key

            for row in sorted(lut, reverse=True): # pragma: no cover
                yield lut.pop(row, ''), row

        else:
            row = start_row
            for key,_row in self.key_table.items():
                if _row == row:
                    yield key, row
                    row += 1
                    while lut and row in lut:
                        yield lut.pop(row, ''), row
                        row += 1
                elif start_row <= _row < stop_row:
                    lut[_row] = key

            for row in sorted(lut): # pragma: no cover
                yield lut.pop(row, ''), row

    def zip(self, data:Union[bytes,bytearray], zip_type:Optional[int]=None) -> bytes:
        """Compress raw binary block sequence elements utilizing active chosen format algorithms drivers factories.

        Args:
            data (bytes): Target binary payload block array string input context.
            zip_type (Optional[int], optional): Overriding specification targeting alternative compress parameters rules. Defaults to None.

        Returns:
            bytes: Compressed block sequence output data.

        Raises:
            ValueError: If compressor engine throws system level error conditions.
        """
        zip_type_i = self._zip_type if zip_type is None else zip_type
        if zip_type_i == NO_ZIP:
            return data

        try:
            return self.VAL_zip(data)

        except (GZ_Error, BZ_Error, XZ_Error, ZS_Error, BR_Error, LZ_Error, \
                ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, MemoryError, OSError) as e: # pragma: no cover
            print(Style(f'!!!!!!!!!!! [{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!zip(bytes[{len(data)}]={data[-512:]}, zip_type={zip_type_i})\nexception:{e}', red=1))
            raise JValueError from e

    def unzip(self, data:Union[bytes,bytearray], zip_type:Optional[int]=None) -> Union[bytes,bytearray]:
        """Decompress value bytes previously compressed by :meth:`zip`.

        Args:
            data (bytes): The compressed bytes.
            zip_type (Optional[int], optional): Compression code to use; ``None`` uses the database default. Defaults to None.

        Returns:
            bytes: The decompressed bytes.

        Raises:
            ValueError: If the data cannot be decompressed.
        """
        zip_type_i = self._zip_type if zip_type is None else zip_type
        try:
            if zip_type_i < 0:
                zip_type_i = -zip_type_i-1
                return data if zip_type_i == NO_ZIP else self.VAL_unzip0(data)

            return self.VAL_unzip(self.pad_byte, data)

        except (GZ_Error, BZ_Error, XZ_Error, ZS_Error, BR_Error, LZ_Error, \
                ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, MemoryError, OSError) as e: # pragma: no cover
            pad = self.pad_byte
            data = data.rstrip(pad) + pad
            for ii in range(8):
                try:
                    print(Style(f'!!!!!!!!!!! [{ii}|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!unzip(bytes[{len(data)}]={data[-512:]}, zip_type={zip_type})', yellow=1))
                    return self.VAL_unzip0(data)

                except (GZ_Error, BZ_Error, XZ_Error, ZS_Error, BR_Error, LZ_Error, \
                        ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, MemoryError, OSError):
                    data += pad

            raise JValueError from e

    def seek(self, fp:IO, row_id:int):
        """Reposition system storage stream pointer coordinates directly targeting selected index row boundaries blocks fields.

        Args:
            fp (IO): Target active open file object interface streaming channel handle.
            row_id (int): Absolute or negative index tracking row target selector integer position number.

        Returns:
            int: The newly repositioned file navigation pointer absolute byte index address location.
        """
        row_id = (self.n_lines + row_id) if row_id < 0 else row_id
        return fp.seek(HEADER_SIZE + row_id * self.index_size)

    def get_dead_row(self, min_row_id:int, req_size:int) -> Tuple[int, int, int, int]:
        """Get the matched dead row from DEAD_rows cache.

        Args:
            min_row_id (int): start row ID
            req_size (int): requested row size

        Returns:
            Tuple[int, int, int, int]: row_id, file_id, offset, row_size
        """
        del_list = []
        match_list = []
        _DEAD_rows = self._DEAD_rows
        n_records = self.n_records
        for _row_id, (_file_id, _offset, _row_size) in _DEAD_rows.items():
            if _row_id >= min_row_id:
                if req_size == _row_size == 0 or _row_size >= req_size > 0:
                    match_list.append((_row_size, _file_id, _offset, _row_id))
                    if req_size == _row_size:
                        break

            elif _row_id < n_records: # pragma: no cover
                del_list.append(_row_id)

        for del_id in del_list: # pragma: no cover
            _DEAD_rows.pop(del_id, None)

        if match_list:
            match_list.sort()
            row_size, file_id, offset, row_id = match_list[0]
            _DEAD_rows.pop(row_id, None)
        else:
            row_id = file_id = offset = row_size = -1

        return row_id, file_id, offset, row_size

    def write_key(self, fp:IO, row_id:int, key:str, file_id:int, offset:int, row_size:int, val_size:int=0, ver:Optional[int]=None, days:int=-1) -> int:
        """Write one KEY index row at ``row_id``, growing the index row size if the key does not fit.

        Args:
            fp (IO): The open KEY file pointer.
            row_id (int): The row to write.
            key (str): The record key.
            file_id (int): The VAL file id holding the value.
            offset (int): The value's byte offset within the VAL file.
            row_size (int): The reserved byte length of the value row.
            val_size (int, optional): The actual value byte length. Defaults to 0.
            ver (Optional[int], optional): The version (write-session id); ``None`` uses the current ``sync_id``. Defaults to None.
            days (int, optional): The stored date in days; ``-1`` keeps the current date. Defaults to -1.

        Returns:
            int: The number of bytes written.
        """
        if days < 0:
            days = self.days
        elif days & CHG_DAY_FLAG:
            days &= OLD_DAY_MASK
            days |= (max(0, self.days-days) << NEW_DAY_SHIFT) & NEW_DAY_MASK
        else:
            days &= (NEW_DAY_MASK | OLD_DAY_MASK)

        ver_i = ver if ver is not None else self.sync_id
        data = self.KEY_dumps(key, file_id, offset, row_size, val_size, ver_i, days)
        data_size = len(data)
        index_size = self.index_size
        pad_size = index_size - data_size - 1
        if pad_size < 0:
            if data_size+1 > MAX_INDEX_SIZE: # pragma: no cover
                # strip the key length to match max index size
                while True:
                    key = key[:pad_size]
                    data = self.KEY_dumps(key, file_id, offset, row_size, val_size, ver_i, days)
                    data_size = len(data)
                    if data_size+1 <= MAX_INDEX_SIZE and key not in self.key_table or not key:
                        break

                    pad_size = 1

                pad_size = index_size - data_size - 1

        if pad_size < 0:
            if row_id+1 >= self.n_lines:
                _data = self.KEY_dumps('', 0, 0, 0, 0, 0, 0)
                fp.seek(HEADER_SIZE + row_id * index_size)
                fp.write(_data + b' ' * (index_size - len(_data) - 1) + b'\n')

            self.resize_keys(fp, data_size + 1)
            index_size = self.index_size # after resize_key
            pad_size = index_size - data_size - 1

        pos = HEADER_SIZE + row_id * index_size
        if fp.tell() != pos:
            fp.seek(pos)

        _DEAD_rows = self._DEAD_rows
        _DEAD_rows.pop(row_id, None)
        _KEY_rows = self._KEY_rows
        _KEY_rows.pop(row_id, None)
        if row_id < self.n_records:
            _KEY_rows[row_id] = (key, file_id, offset, row_size, val_size, ver_i, days)
            while len(_KEY_rows) > TOTAL_KEY_ROWS: # pragma: no cover
                _KEY_rows.popitem(last=False) # 1st item

        elif row_id >= self.n_records+1:
            _DEAD_rows[row_id] = (file_id, offset, row_size)
            while len(_DEAD_rows) > TOTAL_DEAD_ROWS:
                _DEAD_rows.pop(next(iter(_DEAD_rows)), None)

        wr_size = fp.write(data + b' ' * pad_size + b'\n') if pad_size > 0 else fp.write(data + b'\n')
        return wr_size

    def read_key(self, fp:IO, row_id:int) -> Tuple[str, int, int, int, int, int, int]:
        """Read and decode one KEY index row.

        Args:
            fp (IO): The open KEY file pointer.
            row_id (int): The row to read.

        Returns:
            Tuple[str,int,int,int,int,int,int]:
            ``(key, file_id, offset, row_size, val_size, ver, days)``.
        """
        _DEAD_rows = self._DEAD_rows
        _DEAD_rows.pop(row_id, None)
        _KEY_rows = self._KEY_rows
        _info = _KEY_rows.pop(row_id, None)
        if _info is not None:
            _KEY_rows[row_id] = _info
            return _info

        index_size = self.index_size
        pos = HEADER_SIZE + row_id * index_size
        if fp.tell() != pos:
            fp.seek(pos)

        buf = bytearray(index_size)
        n_read = fp.readinto(buf) or 0
        info = self.KEY_loads(buf if n_read > 0 else b'')
        if row_id < self.n_records:
            _KEY_rows[row_id] = info
            while len(_KEY_rows) > TOTAL_KEY_ROWS:
                _KEY_rows.popitem(last=False) # 1st item

        else:
            _DEAD_rows[row_id] = info[1:4]
            while len(_DEAD_rows) > TOTAL_DEAD_ROWS:
                _DEAD_rows.pop(next(iter(_DEAD_rows)))

        return info

    def update_days(self) -> int:
        """Refresh and return today's date as a day count (days since the epoch date).

        Returns:
            int: Today's day number.
        """
        timestamp = int(time())
        self.days = NUM_1970_DAYS + max(0, timestamp - THE_1ST_SEC) // DAY_SEC
        return self.days

    def is_updated(self) -> bool:
        """Check whether the in-memory counters match the KEY file on disk.

        Returns:
            bool: ``True`` if in sync with the file.
        """
        if self.file_size <= 0 or self.sync_id != self._sync_id:
            self._KEY_rows.clear()
            self._DEAD_rows.clear()
            return False

        return True

    def reset(self, **kwargs):
        """Reset all in-memory counters, caches, and settings to defaults.

        Args:
            **kwargs: Configuration overrides (e.g. ``index_size``, ``reserved_rate``).
        """
        self.data_type  = kwargs.get('data_type', self._data_type)
        self.zip_type   = kwargs.get('zip_type', self._zip_type)
        self.index_size = max(kwargs.get('index_size', self.index_size), MIN_INDEX_SIZE)
        self.min_value_size = max(kwargs.get('min_value_size', self.min_value_size), MIN_VALUE_SIZE)
        self.max_file_size = max(kwargs.get('max_file_size', self.max_file_size), MIN_FILE_SIZE)
        self.reserved_rate = max(kwargs.get('reserved_rate', self.reserved_rate), DEF_RATIO)
        self.sync_id = self.swap_id = self.remv_id = self._sync_id = self.n_records = self.n_lines  = self.file_size = 0
        self.days = self._swap_id = self.min_days = self._remv_id = self._n_records = self._n_lines = -1
        self.key_table.clear()
        self.file_table.clear()
        self._KEY_rows.clear()
        self._DEAD_rows.clear()
        self.update_days()
        self.row_bytes = self.index_size - self.min_value_size * (1 + self.reserved_rate)
        self.window_size = max(1, int(KEY_FILE_BUF_SIZE / self.index_size))

    def write_header(self, fp:IO, truncate:bool=False) -> int:
        """Write the database header (counters and format) to the start of the KEY file. header schemas directly into metadata boundaries fields.

        Args:
            fp (IO): Destination active streaming interface pipeline driver handle context.
            truncate (bool, optional): Force physical truncation pruning obsolete residual data rows block remnants away. Defaults to False.

        Returns:
            int: Calculated total byte storage width capacity logged after header updates execution completes.
        """
        sync_id = self.sync_id
        n_records = self.n_records
        n_lines = self.n_lines
        remv_id = self.remv_id
        swap_id = self.swap_id

        is_chg = self._sync_id != sync_id \
            or self._n_records != n_records \
            or self._n_lines != n_lines \
            or self._remv_id != remv_id \
            or self._swap_id != swap_id

        index_size = self.index_size
        data = self.HEAD_dumps(sync_id, n_records, n_lines, index_size, self._zip_type, self._data_type, swap_id, remv_id, self.api_ver)
        pad_size = HEADER_SIZE - len(data) - 1
        if pad_size > 0:
            pad_bytes = b' ' * pad_size
            data += pad_bytes
        data += b'\n'
        old_file_size = self.file_size
        if fp.tell() != 0: fp.seek(0)
        fp.write(data)
        if truncate:
            file_size = fp.seek(HEADER_SIZE + n_lines * index_size)
            fp.truncate()
            self.update_days()
        else:
            file_size = fp.seek(0,2)

        if is_chg:
            self._sync_id = sync_id
            self._swap_id = swap_id
            self._remv_id = remv_id
            self._n_records = n_records
            self._n_lines = n_lines

            if file_size == old_file_size:
                file_size += 1
                fp.write(b'\n')

        self.file_size = file_size
        return file_size

    def read_header(self, fp:IO) -> JIo:
        """Read the header from the KEY file and load its counters/format into this engine.

        Args:
            fp (IO): The open KEY file pointer.

        Returns:
            JIo: ``self``, updated from the header.
        """
        if fp.tell() != 0: fp.seek(0)
        header = bytearray(HEADER_SIZE)
        if fp.readinto(header) == HEADER_SIZE:
            sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver = self.HEAD_loads(header)
        else:
            n_records = n_lines = sync_id = swap_id = remv_id = 0
            index_size  = self.index_size
            zip_type    = self.zip_type
            data_type   = self.data_type
            api_ver     = self.api_ver

        if self.file_size > 0:
            if index_size != self.index_size \
                    or n_records != self.n_records \
                    or n_lines != self.n_lines \
                    or sync_id != self.sync_id \
                    or remv_id != self.remv_id \
                    or swap_id != self.swap_id:

                self.file_size = 0

        if data_type != self._data_type or zip_type != self._zip_type:
            self.index_size = index_size
            self.zip_type   = zip_type
            self.data_type  = data_type
            self.change_APIs(api_ver, data_type, zip_type, reset=True)
        else:
            self.index_size = index_size
            self.zip_type   = zip_type
            self.data_type  = data_type
            if api_ver != self.api_ver: # pragma: no cover
                self.change_APIs(api_ver, data_type, zip_type)

        self.window_size = max(1, int(KEY_FILE_BUF_SIZE / self.index_size))
        self.row_bytes   = self.index_size - self.min_value_size * (1 + self.reserved_rate)
        self.sync_id     = sync_id
        self.swap_id     = swap_id
        self.remv_id     = remv_id
        self.n_records   = n_records
        self.n_lines     = n_lines
        return self

    def pad(self, data:bytes, max_size:int=0, no_zip:bool=False) -> bytes:
        """Prune out padding byte array trailing margins restoring raw compressed string context array.

        Args:
            data (bytes): Aligned padded binary stream data blocks array.

        Returns:
            bytes: Clean trimmed binary data payload block.
        """
        data_size = len(data)
        if max_size == 0:
            if self.reserved_rate > 0.:
                size = max(self.min_value_size, int(data_size * (1. + self.reserved_rate)))
            else:
                size = max(self.min_value_size, data_size)

        else:
            size = max_size

        n_pad = size - data_size
        if n_pad < 0:
            return data

        pad_byte = self.pad0_byte if no_zip else self.pad_byte
        return data + pad_byte * n_pad

    def unpad(self, data:bytes) -> bytes: # pragma: no cover
        """Prune out padding byte array trailing margins restoring raw compressed string context array.

        Args:
            data (bytes): Aligned padded binary stream data blocks array.

        Returns:
            bytes: Clean trimmed binary data payload block.
        """
        pad_byte = self.pad_byte
        if pad_byte == b'\n' or pad_byte == b'\xc1':
            return data.rstrip(pad_byte)

        return data.rstrip(pad_byte) + pad_byte

    def read_bytes(self, fp:IO, pos:int, row_size:int, val_size:int) -> bytes:
        """Read a value's raw (still-serialized) bytes from a VAL file.

        Args:
            fp (IO): The open VAL file pointer.
            pos (int): The byte offset of the value.
            row_size (int): The reserved row length.
            val_size (int): The actual value length (``0`` means the value fills ``row_size``).

        Returns:
            bytes: The raw value bytes.
        """
        fp.seek(pos)
        return fp.read(val_size if val_size > 0 else row_size)

    def read_value(self, fp:IO, pos:int, row_size:int, val_size:int) -> Any:
        """Read and deserialize a stored value from a VAL file.

        Args:
            fp (IO): The open VAL file pointer.
            pos (int): The byte offset of the value.
            row_size (int): The reserved row length.
            val_size (int): The actual value length (``0`` means the value fills ``row_size``).

        Returns:
            Any: The deserialized value.
        """
        fp.seek(pos)
        zip_type = self.zip_type
        if val_size > 0:
            val_bytes = fp.read(val_size)
            if zip_type == NO_ZIP:
                try:
                    return self.VAL_loads(val_bytes)

                except ValueError as e: # pragma: no cover
                    # print(Style(f'!!!!!!!!!!! [???|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!loads_with_unzip(val_bytes[{len(val_bytes)}]={val_bytes[-512:]}, zip_type={zip_type})\nexception:{e}', red=1))
                    raise JValueError from e

            zip_type = -(self.zip_type+1)
        else: # pragma: no cover
            val_bytes = fp.read(row_size)

        if not val_bytes:
            return None

        return self.loads_with_unzip(val_bytes, zip_type=zip_type)

    def dumps_with_zip(self, data:Any, zip_type:Optional[int]=None) -> bytes:
        """Serialize a value and compress it in one step.

        Args:
            data (Any): The value to store.
            zip_type (Optional[int], optional): Compression code; ``None`` uses the database default. Defaults to None.

        Returns:
            bytes: The serialized, compressed bytes.
        """
        try:
            val_bytes = self.VAL_dumps(data)
            return self.zip(val_bytes, zip_type=zip_type)

        except ValueError as e: # pragma: no cover
            print(Style(f'!!!!!!!!!!! [???|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!dumps_with_zip(data={type(data)}, zip_type={zip_type})\nexception:{e}', red=1))
            raise JValueError from e

    def loads_with_unzip(self, val_bytes:Union[bytes,bytearray,memoryview], zip_type:Optional[int]=None) -> Any:
        """Decompress and deserialize a value in one step (reverse of :meth:`dumps_with_zip`).

        Fully supports ``bytearray`` inputs (e.g. buffers filled by
        ``read_bytes()``/``readinto()``): the payload is forwarded to the
        decompressors and decoders as-is, without converting to ``bytes``
        first, preserving the zero-copy read path. ``memoryview`` inputs are
        promoted to ``bytearray`` only because padded decoding requires
        ``rstrip()`` support.

        Args:
            val_bytes (Union[bytes,bytearray,memoryview]): The compressed, serialized bytes.
            zip_type (Optional[int], optional): Compression code; ``None`` uses the database default. Defaults to None.

        Returns:
            Any: The deserialized value.
        """
        try:
            if isinstance(val_bytes, memoryview): # pragma: no cover
                val_bytes = bytearray(val_bytes)

            unzip_bytes = self.unzip(val_bytes, zip_type=zip_type)
            return self.VAL_loads(unzip_bytes)

        except ValueError as e: # pragma: no cover
            print(Style(f'!!!!!!!!!!! [???|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!loads_with_unzip(val_bytes[{len(val_bytes)}]={val_bytes[-512:]}, zip_type={zip_type})\nexception:{e}', red=1))
            raise JValueError from e

    def update_file_table(self) -> None:
        """Scan all VAL files and update the max size for each VAL file.
        """
        file_table = self.file_table
        VAL_size = self.files_obj.VAL_size
        file_id = miss_cnt = 0
        file_table.clear()
        for file_id in range(MAX_FILE_ID):
            size = VAL_size(file_id)
            if size < 0:
                miss_cnt += 1
                if miss_cnt >= 8: break
                continue

            while miss_cnt > 0:
                _file_id = max(0, file_id-miss_cnt)
                file_table[_file_id] = max(file_table.get(_file_id, 0), 0)
                miss_cnt -= 1

            file_table[file_id] = size

    def load_keys(self, fp:IO, force:bool=False):
        """Synchronize the master index tracking dataset by parsing the database index file.

        Args:
            fp (IO): Open index file pointer stream handle.
            force (bool, optional): If ``True``, overrules timeline checks and rebuilds 
                index layouts from zero. Defaults to ``False``.
        """
        n_records       = self.n_records
        n_lines         = self.n_lines
        prev_n_records  = self._n_records
        prev_n_lines    = self._n_lines
        index_size      = self.index_size
        file_table      = self.file_table
        key_table       = self.key_table
        swap_id         = self.swap_id
        remv_id         = self.remv_id
        sync_id         = self.sync_id
        fast_mode       = isinstance(key_table, KeyTable)
        rec_diff  = n_records - prev_n_records          # new/del records
        line_diff = n_lines - prev_n_lines              # new rows
        self.file_size = records = 0
        self.update_days()
        if force or n_lines == 0 or prev_n_lines == 0 or line_diff < 0:
            key_table.clear()
            file_table.clear()
            self._KEY_rows.clear()
            self._DEAD_rows.clear()
        else:
            # swap+1 if swap record A and record B
            prev_swap_id = self._swap_id
            swap_diff = (swap_id - prev_swap_id) if swap_id >= prev_swap_id else (swap_id + 0X_7FF_FFFF_FFFF + 1 - prev_swap_id) & 0X_7FF_FFFF_FFFF

            # remv+1 if change file_table or delete record
            prev_remv_id = self._remv_id
            remv_diff = (remv_id - prev_remv_id) if remv_id >= prev_remv_id else (remv_id + 0X_7FF_FFFF_FFFF + 1 - prev_remv_id) & 0X_7FF_FFFF_FFFF

            # sync+1 if change, add, delete
            prev_sync_id = self._sync_id
            sync_diff = (sync_id - prev_sync_id) if sync_id >= prev_sync_id else (sync_id + 0X_7FF_FFFF_FFFF + 1 - prev_sync_id) & 0X_7FF_FFFF_FFFF

            if sync_diff != 0:
                self._KEY_rows.clear()
                self._DEAD_rows.clear()

            # [A] no swapping
            if swap_diff == 0:
                # swap_diff == rec_diff == remv_diff == 0
                if rec_diff == remv_diff == 0:
                    if n_records <= 0: # pragma: no cover
                        key_table.clear()

                    # swap_diff == rec_diff == remv_diff == line_diff == 0
                    if line_diff == 0:
                        self._n_lines   = n_lines
                        self._n_records = n_records
                        self._sync_id   = sync_id
                        self._swap_id   = swap_id
                        self._remv_id   = remv_id
                        self.file_size  = fp.seek(0, 2)

                    # swap_diff == rec_diff == remv_diff == 0 and line_diff > 0
                    else:
                        self.update_file_table()
                        self._sync_id   = sync_id
                        self._swap_id   = swap_id
                        self._remv_id   = remv_id
                        self._n_records = n_records
                        self._n_lines   = n_lines
                        self.file_size  = fp.seek(0, 2)

                    return

                # swap_diff == remv_diff == 0 and rec_diff > 0
                if remv_diff == 0 and rec_diff > 0:
                    records = max(0, prev_n_records)

                # swap_diff == rec_diff == 0 and remv_diff > 0
                elif rec_diff == 0 and remv_diff > 0: # ADD == DEL
                    records = max(0, n_records-remv_diff)

                # swap_diff == 0 and remv_diff > 0 and rec_diff > 0
                elif rec_diff > 0: # ADD > DEL
                    records = max(0, prev_n_records-remv_diff)

                # swap_diff == 0 and remv_diff > 0 and rec_diff < 0
                else: # ADD < DEL
                    records = max(0, n_records-remv_diff)

                if n_records <= 0 or records == 0 or fast_mode:
                    key_table.clear()

                elif key_table:
                    del_cnt = prev_n_records - records
                    if del_cnt > 0:
                        del_keys = []
                        for key,row in key_table.items():
                            if row < records:
                                continue

                            del_keys.append(key)
                            if len(del_keys) == del_cnt:
                                break

                        for key in del_keys:
                            key_table.pop(key, 0)

                if records < n_records:
                    for (key, file_id, _offset, row_size, _val_size, _ver, _days) in self.KEY_iter(fp, records, n_records):
                        key_table[key] = records
                        if row_size == 0 and file_id == 0x10: # pragma: no cover
                            self.groups.setdefault(key, None)
                        records += 1

                self.update_file_table()
                self._sync_id   = sync_id
                self._swap_id   = swap_id
                self._remv_id   = remv_id
                self._n_records = n_records
                self._n_lines   = n_lines
                self.file_size  = fp.seek(0, 2)
                return

            # [B] with swapping
            # swap_diff > 0 (n_lines >= 2)
            if swap_diff > 0:
                # swap_diff > 0 and sync_diff == remv_diff == -rec_diff and line_diff == 0
                if sync_diff == remv_diff == -rec_diff and line_diff == 0:
                    # [B1-0] only delete records with swap
                    if n_records <= 0:
                        key_table.clear()
                        self._sync_id   = sync_id
                        self._swap_id   = swap_id
                        self._remv_id   = remv_id
                        self._n_records = n_records
                        self._n_lines   = n_lines
                        self.file_size  = fp.seek(0, 2)
                        return

                    # swap_diff > 0 and sync_diff == remv_diff == -rec_diff and line_diff == 0 and n_records > 0
                    if fast_mode:
                        key_table.clear()
                    else:
                        KEY_loads = self.KEY_loads
                        line = bytearray(index_size)
                        for (key, _f, _o, _rs, _vs, _v, _d) in self.KEY_iter(fp, n_records, min(n_lines, n_records+remv_diff)):
                            old_row = key_table.pop(key, -1)
                            if n_records > old_row >= 0:
                                cur_pos = fp.tell()
                                fp.seek(HEADER_SIZE + old_row * index_size)
                                if fp.readinto(line) == index_size:
                                    new_rec = KEY_loads(line)
                                    key_table[new_rec[0]] = old_row
                                fp.seek(cur_pos)

                    self._sync_id   = sync_id
                    self._swap_id   = swap_id
                    self._remv_id   = remv_id
                    self._n_records = n_records
                    self._n_lines   = n_lines
                    self.file_size  = fp.seek(0, 2)
                    return

                key_table.clear()
                file_table.clear()

        if n_lines <= 0:
            self._sync_id   = sync_id
            self._swap_id   = swap_id
            self._remv_id   = remv_id
            self._n_records = self._n_lines = self.n_lines = self.n_records = 0
            self.file_size  = fp.seek(0, 2)
            return

        if fast_mode:
            self.update_file_table()
            self._sync_id   = sync_id
            self._swap_id   = swap_id
            self._remv_id   = remv_id
            self._n_records = n_records
            self._n_lines   = n_lines
            self.file_size  = fp.seek(0, 2)
            return

        for (key, file_id, _offset, row_size, _val_size, _ver, _days) in self.KEY_iter(fp, records, n_records):
            key_table[key] = records
            if row_size == 0 and file_id == 0x10: # pragma: no cover
                self.groups.setdefault(key, None)
            records += 1

        self.update_file_table()
        self._sync_id   = sync_id
        self._swap_id   = swap_id
        self._remv_id   = remv_id
        self._n_records = n_records
        self._n_lines   = n_lines
        self.file_size  = fp.seek(0, 2)

    def copy_key(self, fp:IO, src_row:int, dst_row:int, decode:bool=False) -> Union[bytes,tuple,list]:
        """Duplicate an exact slice of row metadata bytes from one slot address to another slot index line.

        Args:
            fp (IO): Persistent active streaming framework connection file object.
            src_row (int): Original row source index position number.
            dst_row (int): Destination target row index line location mapping parameters.
            decode (bool, optional): De-serialize and unpack raw duplicated lines properties back into tuple parameters objects instead. Defaults to False.

        Returns:
            Union[bytes, tuple, list]: Copied binary stream metadata chunk array, or unpacked items elements tuple.
        """
        self._KEY_rows.pop(dst_row, None)
        self._DEAD_rows.pop(dst_row, None)

        index_size = self.index_size
        src_pos = HEADER_SIZE + src_row * index_size
        dst_pos = HEADER_SIZE + dst_row * index_size
        if fp.tell() != src_pos:
            fp.seek(src_pos)

        line = bytearray(index_size)
        fp.readinto(line)
        if src_pos != dst_pos:
            if fp.tell() != dst_pos:
                fp.seek(dst_pos)
            fp.write(line)

        return line if not decode else self.KEY_loads(line)

    def resize_keys(self, fp:IO, index_size:int, min_ver:bool=False):
        """Rebuild the KEY file with a different index row size.

        Args:
            fp (IO): The open KEY file pointer.
            index_size (int): The new byte size for each KEY index row.
            min_ver (bool, optional): Reset stored versions to a minimal baseline. Defaults to False.
        """

        # make sure n_lines == total rows in KEY file
        index_size = ((index_size >> 3) << 3) + (8 if index_size & 0x7 else 0)  # 64bit alignment
        n_lines = self.n_lines
        sync_id = self.sync_id
        if index_size == self.index_size:
            if not min_ver:
                return

            if n_lines >= sync_id:
                return

        api_ver = API_LATEST if self.api_ver is None else self.api_ver
        dst_io = JIo(files_obj=self.files_obj.copy(), # due to JNetFiles
                    data_type=self._data_type,
                    zip_type=self._zip_type,
                    api_ver=api_ver,
                    index_size=index_size,
                    val_codec=self._val_codec,
                    key_codec=self._key_codec)

        table = {}
        src_row_id = dst_row_id = 0
        size_diff = index_size - self.index_size
        dst_io.n_lines = n_lines
        n_records = self.n_records
        src_read_key = self.read_key
        if size_diff > 0:
            table_size = min(n_lines, int(n_lines * size_diff / self.index_size) + 8)
            fp.seek(HEADER_SIZE)
            while src_row_id < table_size:
                row_info = src_read_key(fp, src_row_id)
                if row_info:
                    table[src_row_id] = row_info

                src_row_id += 1

        print(Style(f'!!! [{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] WAIT until KEY file resize is DONE!!! size:{self.index_size}->{index_size} buffer:{len(table)}/{n_lines}', cyan=1, bold=1, underscore=1))
        dst_write_key = dst_io.write_key
        while dst_row_id < n_lines:
            if src_row_id < n_lines:
                row_info = src_read_key(fp, src_row_id)
                if row_info:
                    table[src_row_id] = row_info

                src_row_id += 1

            key_info = table.pop(dst_row_id, None)
            if not key_info: # pragma: no cover
                break

            if min_ver:
                _key, _file_id, _offset, _row_size, _val_size, _ver, _days = key_info
                _ver = max(1, _ver - sync_id + n_lines)
                _key = '' if dst_row_id >= n_records else _key
                dst_write_key(fp, dst_row_id, _key, _file_id, _offset, _row_size, _val_size, _ver, _days)
            else:
                dst_write_key(fp, dst_row_id, *key_info)

            dst_row_id += 1

        fp.truncate()
        if min_ver:
            self.sync_id = max(1, n_lines)
            self.remv_id = (self.remv_id % 2) + 1
            self.swap_id = (self.swap_id % 2) + 1

        self.index_size = index_size
        self._n_lines = 0
        self.write_header(fp)
        self.window_size = max(1, int(KEY_FILE_BUF_SIZE / index_size))
        self.row_bytes = index_size - self.min_value_size * (1 + self.reserved_rate)

    def KEY_iter(self, fp:IO, start:int, stop:int, reverse:bool=False, n_rows:int=8192) -> Generator[Tuple[str, int, int, int, int, int, int], None, None]:
        """Iterate decoded KEY rows in the half-open row range ``[start, stop)``,
        reading the index file in large blocks for speed.

        The file position is re-seeked before every block, so repositioning
        ``fp`` between yields is safe. However, the rows of the current block
        are served from a snapshot buffer: writing to the KEY file during
        iteration may yield stale rows, and replacing/closing ``fp`` (e.g. a
        read-to-write mode switch) breaks the iterator. Do not modify the
        database while iterating.

        Args:
            fp (IO): The open KEY file pointer.
            start (int): First row id to yield (inclusive).
            stop (int): End row id (exclusive); clamped to ``n_lines``.
            reverse (bool, optional): Yield rows in descending row order.
                Defaults to ``False``.
            n_rows (int, optional): Maximum rows per read block; the effective
                block size is also capped at 4MB and at the range length.
                Defaults to ``8192``.

        Yields:
            Tuple[str, int, int, int, int, int, int]: The decoded row
            ``(key, file_id, offset, row_size, val_size, ver, days)``.
            Iteration stops silently on a short read or a row decode error.
        """
        if stop <= start or stop < 0 or start < 0 or self.n_lines < 0: # pragma: no cover
            return

        n_lines = self.n_lines
        if start >= n_lines: # pragma: no cover
            return

        index_size = self.index_size
        stop = n_lines if stop >= n_lines else stop
        n_keys = stop - start
        n_rows = min(n_rows, (2**22) // index_size, n_keys)
        if n_rows <= 0:
            return

        KEY_loads = self.KEY_loads
        buf = bytearray(index_size * n_rows)
        mv_buf = memoryview(buf)
        row_id = start if not reverse else stop
        cnt = 0
        if not reverse:
            while cnt < n_keys:
                _n_rows = min(n_keys - cnt, n_rows)
                fp.seek(HEADER_SIZE + row_id * index_size)
                n_bytes = fp.readinto(buf if _n_rows == n_rows else mv_buf[:_n_rows * index_size])
                if n_bytes < index_size or n_bytes % index_size != 0: # pragma: no cover
                    break

                for idx in range(0, n_bytes, index_size):
                    try:
                        yield KEY_loads(mv_buf[idx:idx+index_size])
                    except ValueError: # pragma: no cover
                        cnt += n_lines
                        break

                cnt += _n_rows
                row_id += _n_rows
        else:
            while cnt < n_keys:
                _n_rows = min(n_keys - cnt, n_rows)
                row_id -= _n_rows
                fp.seek(HEADER_SIZE + row_id * index_size)
                n_bytes = fp.readinto(buf if _n_rows == n_rows else mv_buf[:_n_rows * index_size])
                if n_bytes < index_size or n_bytes % index_size != 0: # pragma: no cover
                    break

                for idx in range(n_bytes-index_size, -index_size, -index_size):
                    try:
                        yield KEY_loads(mv_buf[idx:idx+index_size])
                    except ValueError: # pragma: no cover
                        cnt += n_lines
                        break

                cnt += _n_rows

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------

#
