from __future__ import annotations # pylint: disable=too-many-lines
from abc import ABCMeta, abstractmethod
from typing import Any, Union, Optional, Tuple, Callable, Generator, IO, Dict
from io import DEFAULT_BUFFER_SIZE
from time import time
from functools import reduce
from collections import defaultdict
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
from bitarray import bitarray

from .utils import Style
# from .utils import debug_break

try:
    import yaml
except ImportError:
    yaml = None

try:
    from brotli import compress as brotli_compress, decompress as brotli_decompress, error as BR_Error
    br_compress = lambda _bytes : brotli_compress(_bytes, quality=6)
    br_decompress = brotli_decompress
except ModuleNotFoundError:
    br_compress = br_decompress = None

try:
    from lz4.frame import compress as _lz4_compress, decompress as _lz4_decompress, COMPRESSIONLEVEL_MIN, BLOCKSIZE_MAX256KB
    lz4_compress = lambda _bytes : _lz4_compress(_bytes, compression_level=COMPRESSIONLEVEL_MIN, block_size=BLOCKSIZE_MAX256KB)
    lz4_decompress = _lz4_decompress
except ModuleNotFoundError:
    lz4_compress = lz4_decompress = None

def _json_default(obj):
    """Fallback serialization encoder function for unsupported default JSON datatypes.

    Converts iterable sets into native list arrays, and custom-encodes raw binary payloads 
    (bytes/bytearrays) into a hex tracking string prefixed with a unique signature matrix.

    Args:
        obj (Any): Object target candidate that failed standard JSON serialization rules.

    Returns:
        Any: JSON-serializable representation of the source object.

    Raises:
        TypeError: If the object data type remains unrecognized and unsupported.
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
    from json import loads as _json_loads, dumps as __json_dumps, JSONDecodeError
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
    """Pack non-primitive object structures using marshal codecs into legacy MsgPack ExtType objects.

    Args:
        obj (Any): Non-primitive input object.

    Returns:
        ExtType: Wrapped serialization object extension mapping type ID 123.
    """
    if isinstance(obj, set):
        return Ext(123, _msg_dumps(list(obj)))

    raise TypeError

def _msg_decode(code:int, data:bytes):
    """Decode custom MsgPack extensions utilizing marshal deserialization routines.

    Args:
        code (int): The extension type registry code. Expects strictly type ID 123.
        data (bytes): The raw binary payload block associated with the extension tag.

    Returns:
        Any: The unpacked python primitive or object structure.

    Raises:
        TypeError: If an unregistered extension type code token encounters parsing streams.
    """
    if code == 123:
        try:
            return set(_msg_loads(data))

        except ValueError: # pragma: no cover
            # nosemgrep
            return marshal_loads(data) # nosec B302

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

except ImportError:
    # Python 3.7 unsupport compress() and decompress()
    from zstandard import ZstdCompressor, ZstdDecompressor, ZstdError as ZS_Error
    zstd_compress = ZstdCompressor(level=22).compress
    zs1_compress = ZstdCompressor(level=6).compress
    zs2_compress = ZstdCompressor(level=11).compress
    zstd_decompress = ZstdDecompressor().decompress

#-----------------------------------------------------------------------------
from .jdb_file import JFilesBase

BZ_Error = OSError
LZ_Error = RuntimeError
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
MAX_INDEX_SIZE  = 2**15

DEF_VALUE_SIZE  = 16 # 1-15 bytes can store in KEY file
MIN_VALUE_SIZE  = 1
MAX_VALUE_SIZE  = (2**30) * 4 - 1 # 4GB (32bit)

DEF_FLAG_MASK   = 2**20 - 1 # bitarray size for key search

DEF_RATIO       = 0.001
MAX_RATIO       = 256.
DEF_KEY_LIMIT   = 0 # 0=DictKeyTable(dict)
HEADER_SIZE     = 128
TOTAL_KEY_ROWS  = 8

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
KEY_FILE_BUF_SIZE = DEFAULT_BUFFER_SIZE * 8 # 16_777_216
VAL_FILE_BUF_SIZE = DEFAULT_BUFFER_SIZE

DEF_TYPE = 0 # default data type
L_J_TYPE = 1 # split+Json                   | readable
M_M_TYPE = 2 # Marshal+Marshal              | unreadable, full type
J_J_TYPE = 3 # Json+Json                    | readable
J_M_TYPE = 4 # Json+Marshal                 | half-readale, full type
J_P_TYPE = 5 # Json+Pickle                  | half-readale, full type
S_S_TYPE = 6 # Msgpack+Msgpack              | smallest size
J_S_TYPE = 7 # Json+Msgpack                 | readale, small size
S_M_TYPE = 8 # Msgpack+Marshal              | unreadable, full type
S_J_TYPE = 9 # Msgpack+Json                 | half-readable
S_P_TYPE = 10# Msgpack+Pickle               | unreadable, full type
J_Y_TYPE = 11# Json+Yaml                    | readable, full type
S_Y_TYPE = 12# Msgpack+Yaml                 | half-readable
LAST_DATA_TYPE = S_Y_TYPE

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

ZIP_lut = [
    lambda data: data,
    gzip_compress,
    bz2_compress,
    lzma_compress,
    zstd_compress,
    br_compress,
    zs1_compress,
    zs2_compress,
    lz4_compress,
]

UNZIP_lut = [
    lambda pad,data : data.strip(pad),
    lambda pad,data : gzip_decompress(data.rstrip(pad) + b'\0\0\0'),
    lambda pad,data : bz2_decompress(data.rstrip(pad) + b'\0\0\0'),
    lambda pad,data : lzma_decompress(data.rstrip(pad)),
    lambda pad,data : zstd_decompress(data.rstrip(pad) + b'\0\0\0\0'),
    lambda pad,data : br_decompress(data.rstrip(pad)),
    lambda pad,data : zstd_decompress(data.rstrip(pad) + b'\0\0\0\0'),
    lambda pad,data : zstd_decompress(data.rstrip(pad) + b'\0\0\0\0'),
    lambda pad,data : lz4_decompress(data.rstrip(pad) + b'\0\0\0\0'),
]

UNZIP_lut0 = [
    lambda data: data,
    gzip_decompress,
    bz2_decompress,
    lzma_decompress,
    zstd_decompress,
    br_decompress,
    zstd_decompress,
    zstd_decompress,
    lz4_decompress,
]

PAD_lut = [
    lambda mode : b'\n' if mode not in {S_S_TYPE, J_S_TYPE} else b'\xc1',
    lambda mode : b'\0',
    lambda mode : b'\0',
    lambda mode : b'\xff',
    lambda mode : b'\0',
    lambda mode : b'\xff',
    lambda mode : b'\0',
    lambda mode : b'\0',
    lambda mode : b'\0',
]

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JDbGroupDict(dict):
    """Custom dictionary implementation returning None instead of throwing KeyError on missing elements."""
    __slots__ = ()
    def __missing__(self, key:str) -> None:
        """Handle missing keys safely by returning None.

        Args:
            key (Str): Missing key token descriptor.

        Returns:
            None: Fallback placeholder indicator value.
        """
        return None

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
xhash = hash # hash() is not deterministic, can export PYTHONHASHSEED=0
class KeyTable:
    """Protocol Interface layout contract defining standard indexing schemas for tracking index rows keys mappings."""
    __slots__ = ('io', 'cache', 'files_obj', 'groups', 'size', 'mask', 'flags', 'flags_mask', 'found_flags')

    def __init__(self, jio:JIo, groups_mask:int, flags_mask:int, with_cache:bool=False):
        """Initialize compact storage partitions maps arrays based on specialized mask profiling parameters rules.

        Args:
            jio (JIo): Active pipeline transaction driver routing local configuration properties.
            groups_mask (int): The size(groups_mask+1) of key_array groups
            flags_mask (int): The size(flags_mask+1) of flags bitarray
            with_cache (bool): True = with key+row_id cache, False = no cache (default=False)

        Raises:
            ValueError: If an unexpected out-of-bounds mode tier is passed.
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
        self.groups = [bytearray() for _ in range(groups_mask+1)]
        self.size = -1
        self.found_flags = bitarray()
        self.cache = {} if with_cache else None

    def get_mode(self) -> int:
        """Get the classification mode configuration parameter code.

        Returns:
            int: Constant mapping indicator parameters.
        """
        return -1

    def __repr__(self) -> str:
        """Generate telemetry reports indicating density metrics and bitwise allocation accuracy tiers.

        Returns:
            str: Presentation text log summary details parameters strings.
        """
        return f'<{type(self).__name__} '\
            f'cache:{len(self.cache) if isinstance(self.cache, dict) else "-"} '\
            f'mask:{self.mask:x} '\
            f'used:{(self.flags.nbytes+self.found_flags.nbytes+sum(len(ka) for ka in self.groups))/1024/1024:.2f}MB+{self.flags.count(1)*100./len(self.flags):.2f}% '\
            f'done:{self.size}/{self.io.n_records}+{self.found_flags.count(1)*100./max(1,len(self.found_flags)):.2f}% '\
            f'at {hex(id(self))}>'

    def set(self, key:str, row_id:int):
        """Log key coordinates properties configurations fields matching localized index pools blocks frameworks.

        Args:
            key (str): Query selector name string token descriptor context.
            row_id (int): Hardware data sector row index position coordinate value number integer.            
        """
        if self.size < 0: #pragma: no cover
            self.clear()

        cache = self.cache
        if isinstance(cache, dict) and cache.get(key, None) == row_id: # pragma: no cover
            cache.pop(key, None)
            cache[key] = row_id
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

        if isinstance(cache, dict):
            while len(cache) >= self.io._key_limit:
                old_key = next(iter(cache))
                cache.pop(old_key, None)

            cache[key] = row_id

    def pop(self, key:str, default_row_id:int=-1) -> int:
        """Erase entry mappings tracking variables unlinking selected items across database layers maps tracks systems.

        Args:
            key (str): Query identity label selection code text format string token.
            default_row_id (int, optional): Fallback value mapping missing slots boundaries coordinates positions numbers. Defaults to -1.

        Returns:
            int: Numerical measure representing unlinked item row address coordinate positions index numbers parameters logs.
        """
        if self.size < 0: #pragma: no cover
            self.clear()

        cache = self.cache
        if cache: cache.pop(key, None)

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
            fp = None
            try:
                fp = self.files_obj.KEY_open('rb')
                fp.seek(HEADER_SIZE + row_id * index_size)
                _key, _f, _o, _r, _v, _s, _d = KEY_loads(fp.read(index_size))
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
                if fp is not None:
                    fp.close()

        if not is_sync:
            for _key, row_id in self._item_iter():
                if key != _key: continue
                old_row_id, s_idx, e_idx = find_key(key_array, key)
                if old_row_id == row_id:
                    del key_array[s_idx:e_idx]
                    self.size -= 1

                set_found_flag(row_id, False)
                return row_id

        return default_row_id

    def get(self, key:str, default_row_id:int=-1) -> int:
        """Resolve target data identifiers strings parameters checking active tracking filters registers pools levels maps.

        Args:
            key (str): Primary key entry selection string identifier token text layout metrics descriptors properties fields fields.
            default_row_id (int, optional): Target fallbacks options settings values if tracking lookups miss indicators pools context paths. Defaults to -1.

        Returns:
            int: Target integer tracking indices indicating row alignment positions markers arrays sheets metrics data.
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
        if isinstance(cache, dict):
            row_id = cache.get(key, -1)
            if row_id >= 0:
                return row_id

        mask = self.mask
        groups = self.groups
        find_key = self._find_key
        key_array = groups[key_hash & mask]
        row_id, _s_idx, _e_idx = find_key(key_array, key)
        if row_id >= 0:
            if isinstance(cache, dict):
                while len(cache) >= jio._key_limit:
                    old_key = next(iter(cache))
                    cache.pop(old_key, None)

                cache[key] = row_id
            return row_id

        if not is_sync:
            for _key, row_id in self._item_iter():
                if _key == key:
                    # clean up extra buffer
                    if isinstance(cache, dict):
                        while len(cache) >= jio._key_limit:
                            old_key = next(iter(cache))
                            cache.pop(old_key, None)

                        cache[key] = row_id
                    return row_id

        return default_row_id

    def items(self) -> Generator[str,int]:
        """Generate unpacked data pairs mapping query strings onto row slot integers indices coordinates from binary matrices blocks fields.

        Yields:
            Tuple[str, int]: Identity selection descriptor token string coupled along row integer reference value number.
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
        yield from self._item_iter()

    def values(self) -> Generator[int]:
        """Iterate through the absolute range of available active row line index numbers.

        Yields:
            int: Row position coordinate value number integer slot position.
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
        for _key,row_id in self._item_iter():
            yield row_id

    def keys(self) -> Generator[str]:
        """Iterate over the full layout collection sequence tracking active identifier string tokens from the database file index sheet.

        Yields:
            str: Identity selection descriptor label context text formats string tokens variables.
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
        for key,_row_id in self._item_iter():
            yield key

    def copy(self) -> KeyTable: # pragma: no cover
        """Construct replica instances duplication frameworks copying active filter arrays signatures matrices layers.

        Returns:
            KeyTable: Carbon copy replication workspace object context wrapper tracker handle.
        """
        return KeyTable(self.io, self.mask, self.flags_mask, isinstance(self.cache, dict))

    def clear(self):
        """Purge memory configurations reset trackers parameters indicators initializing bloom filters blocks matrices maps grids back onto zero fields."""
        if self.size != 0:
            for key_array in self.groups:
                key_array.clear()
            if isinstance(self.cache, dict):
                self.cache.clear()
            self.found_flags.clear()
            self.flags.setall(0)
            self.size = 0

    def __len__(self) -> int:
        """Calculate total registered data rows records numbers.

        Returns:
            int: Element measure count value.
        """
        return self.io.n_records

    def __setitem__(self, key:str, row_id:int):
        self.set(key, row_id)

    def __getitem__(self, key:str) -> int:
        return self.get(key, -1)

    def __delitem__(self, key:str):
        if self.pop(key, -1) < 0:
            raise KeyError(f'{key}')

    def __contains__(self, key:str) -> bool:
        return self.get(key, -1) != -1

    def __iter__(self) -> Generator[str]:
        yield from self.keys()

    def __eq__(self, obj:Union[KeyTable,Dict[str,int]]) -> bool:
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

    def _item_iter(self) -> Generator[str,int]:
        """Iterate pairs matching target identifiers text tokens straight onto physical rows blocks integers coordinates indices trackers sequences.

        Yields:
            Tuple[str, int]: Associated unique identity string token paired along exact allocation row position line index number value.
        """
        jio = self.io
        is_empty = self.size == 0
        flags = self.flags
        mask = self.mask
        flags_mask = self.flags_mask
        get_found_flag = self._get_found_flag
        set_found_flag = self._set_found_flag
        index_size = jio.index_size
        KEY_loads = jio.KEY_loads
        groups = self.groups
        fp = None
        try:
            fp = self.files_obj.KEY_open('rb')
            fp.seek(HEADER_SIZE)
            for row_id in range(jio.n_records):
                _key, _f, _o, _r, _v, _s, _d = KEY_loads(fp.read(index_size))
                if is_empty or not get_found_flag(row_id):
                    key_hash = xhash(_key)
                    flags[key_hash & flags_mask] = True
                    groups[key_hash & mask].extend(_msg_dumps((_key, row_id)) or b'')
                    set_found_flag(row_id, True)
                    self.size += 1

                yield _key, row_id

        except FileNotFoundError: # pragma: no cover
            self.clear()

        finally:
            if fp is not None:
                fp.close()

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
        found_flags = self.found_flags
        ext_size = row_id + 1 - len(found_flags)
        if ext_size > 0:
            found_flags.extend('0' * ext_size)
        found_flags[row_id] = is_found

    def _get_found_flag(self, row_id:int) -> bool:
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
    """Dictionary-backed implementation of KeyTable protocol optimizing fast in-memory lookups."""
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
        """Get the current dictionary matrix classification mode.

        Returns:
            int: Code indicator mapping baseline processing profiles rules.
        """
        return -1

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class PartialKeyTable(KeyTable):
    """Memory-efficient key indexing proxy utilizing bitarrays and sparse object cache pipelines.

    Postpones loading full keys sets from physical devices disks by maintaining localized bloom filter configurations trackers.
    """

    def __init__(self, jio:JIo):
        """Initialize partial tracking layers parsing data indices boundaries criteria metrics models.

        Args:
            jio (JIo): Active pipeline transaction driver routing local configuration properties.
        """
        super().__init__(jio, groups_mask=0xFFF, flags_mask=DEF_FLAG_MASK, with_cache=True)

    def copy(self) -> PartialKeyTable:
        """Construct replica instances duplication frameworks copying active filter arrays signatures matrices layers.

        Returns:
            PartialKeyTable: Carbon copy replication workspace object context wrapper tracker handle.
        """
        return PartialKeyTable(self.io)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class LiteKeyTable(KeyTable):
    """Ultra compact text index manager replacing standard dictionary spaces models entirely with serialized byte arrays.

    Saves device runtime environments storage footprints overhead inside system execution memory layers grids.
    """
    __slots__ = ('mode', )

    def __init__(self, jio:JIo, mode:int=0):
        """Initialize compact storage partitions maps arrays based on specialized mask profiling parameters rules.

        Args:
            jio (JIo): Active pipeline transaction driver routing local configuration properties.
            mode (int, optional): Sizing constraints profile configuration indicator value. Defaults to 0.

        Raises:
            ValueError: If an unexpected out-of-bounds mode tier is passed.
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
    from BTrees.OLBTree import OLBTree as BTree # pylint: disable=no-name-in-module, import-error

    class BTreeKeyTable(BTree):
        """BTree-backed alternative implementation of KeyTable protocol handling heavy database datasets scalability arrays metrics grids."""
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
            """Construct alternative clones instances duplication wrappers tracking active balanced node tree contexts layouts.

            Returns:
                BTreeKeyTable: Duplicate database indexing driver framework tree environment proxy.
            """
            return BTreeKeyTable(self)

        def __getitem__(self, key:str) -> int:
            return self.get(key, -1)

        def get_mode(self) -> int:
            """Get structural layout matrix tree status classification tracker code number.

            Returns:
                int: Operational mode classification identifier indicator.
            """
            return -1

except ModuleNotFoundError:
    BTreeKeyTable = None

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoHEAD:
    """Serialization schema codec module tracking core physical database configuration layout header parameters specifications sheets metadata."""
    def dumps_v0(self, sync_id:int, n_records:int, n_lines:int, index_size:int, zip_type:int, data_type:int, swap_id:int, remv_id:int, api_ver:int) -> bytes:
        """Pack V0 database file layout configuration header state fields parameters into compact JSON text byte strings arrays layers.

        Args:
            sync_id (int): Transaction sync session identifier reference tracking variable sequence number index value.
            n_records (int): Count of current valid data row elements entries actively indexed inside system frameworks pools.
            n_lines (int): Combined count logging both live unique records rows paired along dead or unlinked database elements slots.
            index_size (int): Allocated byte length spacing individual key entries mapping boundaries across index arrays sheets.
            zip_type (int): Compression configuration blueprint indicator code token selection tracking value number integer.

                - 0 = no compression for VAL
                - 1 = gzip compression(9) for VAL
                - 2 = bz2 compression(9) for VAL
                - 3 = lzma compression for VAL
                - 4 = zstandard compression(22) for VAL
                - 5 = brotli compression(6) for VAL
                - 6 = zstandard compression(6) for VAL
                - 7 = zstandard compression(11) for VAL
                - 8 = lz4 compression(0) for VAL

            data_type (int): Codec scheme indicator tracking format specifications parameters settings (e.g., MsgPack, JSON, Marshal).

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
                - 11 = KEY=msgpack  | VAL=YAML
                - 12 = KEY=msgpack  | VAL=YAML

            swap_id (int): Logical tracking reference incrementing with structural record rearrangement transformations transitions.
            remv_id (int): Cumulative deletions sequence indicator code recording dropped elements.
            api_ver (int): API iteration code parameter track logging framework specifications versions limit boundary layers rules.

        Returns:
            bytes: JSON formatted header sequence binary block array string.
        """
        return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver))

    def loads_v0(self, header:bytes) -> Tuple[int,int,int,int,int,int,int,int,int]:
        """Unpack legacy V0 header arrays profiles extracting structural layout parameters metrics trackers from raw bytes streams contexts.

        Args:
            header (bytes): Target binary payload block containing string logs parameters configurations sheets data metrics.

        Returns:
            Tuple[int,int,int,int,int,int,int,int,int]: Complete state representation parameters tracking database properties registers.
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
        """Pack production V1 dataset schemas configurations header states definitions straight into compact JSON data payloads arrays.

        Args:
            sync_id (int): Transaction generation number tracker.
            n_records (int): Active live record entries measure count.
            n_lines (int): Structural baseline row allocation tracks limit integer.
            index_size (int): Sizing operational constraint width specifying row padding bounds.
            zip_type (int): Compression rule profile designation integer value index selection.

                - 0 = no compression for VAL
                - 1 = gzip compression(9) for VAL
                - 2 = bz2 compression(9) for VAL
                - 3 = lzma compression for VAL
                - 4 = zstandard compression(22) for VAL
                - 5 = brotli compression(6) for VAL
                - 6 = zstandard compression(6) for VAL
                - 7 = zstandard compression(11) for VAL
                - 8 = lz4 compression(0) for VAL

            data_type (int): Operational data scheme classification token indicator.

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
                - 11 = KEY=msgpack  | VAL=YAML
                - 12 = KEY=msgpack  | VAL=YAML
            
            swap_id (int): Internal cleanup sequence metrics reference tracking updates.
            remv_id (int): Deletion counter reference.
            api_ver (int): Logic structural schema edition selector index token code.

        Returns:
            bytes: Encoded JSON sequence representing dataset parameters blocks layouts template.
        """
        try:
            return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v1(self, header:bytes) -> Tuple[int,int,int,int,int,int,int,int,int]:
        """Unpack production V1 data matrices parameters sheets extracting variables settings via core JSON interpretation filters.

        Args:
            header (bytes): Source configuration block byte array.

        Returns:
            Tuple[int,int,int,int,int,int,int,int,int]: Parsed state tracking elements.

        Raises:
            ValueError: If transaction stream parsing rules encounter structural corruption across datasets boundaries contexts.
        """
        try:
            return _json_loads(header)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError): # pragma: no cover
            return self.loads_v0(header)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoKEY(metaclass=ABCMeta): # pragma: no cover
    """Abstract codec class defining low-level byte serialization blueprints for single row index items metadata structures."""
    @abstractmethod
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes: ...
    @abstractmethod
    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]: ...
    @abstractmethod
    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes: ...
    @abstractmethod
    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]: ...

class JIoKEY_J(JIoKEY):
    """JSON serialization codec subclass managing row metadata translation models arrays fields."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        try:
            return _json_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        try:
            args = _json_loads(data)
            if len(args) != 6: # pragma: no cover
                args.append(0)

            key, file_id, offset, row_size, ver, days = args[:6]
            val_size = row_size >> 32
            row_size &= 0X_FFFF_FFFF
            return key, file_id, offset, row_size, val_size, ver, days

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise ValueError from e

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        try:
            return _json_dumps((key, file_id, offset, row_size, val_size, ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        try:
            return _json_loads(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise ValueError from e

class JIoKEY_S(JIoKEY):
    """MsgPack compression serialization codec subclass handling high density row index mapping metadata packing rows blocks fields parameters."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        try:
            info_b = _msg_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days)) or b''
            info_len = len(info_b)
            return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        try:
            prefix0, prefix1, prefix2, info0 = data[:4]
            if prefix0 == 0xcd and info0 == 0x96:
                info_len = (prefix1 << 8)| prefix2
                end_idx = info_len + 3
                key, file_id, offset, row_size, ver, days = _msg_loads(data[3:end_idx])
                return key, file_id, offset, row_size & 0X_FFFF_FFFF, row_size >> 32, ver, days

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

        raise ValueError

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        try:
            info_b = _msg_dumps((key, file_id, offset, row_size, val_size, ver, days)) or b''
            info_len = len(info_b)
            return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        try:
            prefix0, prefix1, prefix2, info0 = data[:4]
            if prefix0 == 0xcd and info0 == 0x97:
                info_len = (prefix1 << 8)| prefix2
                end_idx = info_len + 3
                return _msg_loads(data[3:end_idx])

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

        raise ValueError

class JIoKEY_M(JIoKEY):
    """Marshal binary compilation speed codec subclass handling raw system variables mapping optimization layouts structures."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        try:
            # nosemgrep
            return marshal_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days)) # tuple smaller than list

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
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
            raise ValueError from e

        raise ValueError

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        try:
            # nosemgrep
            return marshal_dumps((key, file_id, offset, row_size, val_size, ver, days)) # tuple smaller than list

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        # nosemgrep
        try:
            args = marshal_loads(data) # nosec B302
            if isinstance(args, (list, tuple)):
                return args

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

        raise ValueError

class JIoKEY_L(JIoKEY):
    """Legacy text string comma-separated encoder subclass generating human-readable tracking line rows entries records segments maps paths."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        try:
            data = f'{key},{file_id},{offset},{row_size | (val_size << 32)}|{ver}|{days}'
            return data.encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        try:
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
            raise ValueError from e

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        try:
            data = f'{key},{file_id},{offset},{row_size},{val_size},{ver},{days}'
            return data.encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        try:
            data_s = data.decode('utf8').rstrip()
            fields = data_s.split(',')
            n_fields = len(fields)
            key = ','.join(fields[:-6]) if n_fields > 7 else fields[0]
            file_id, offset, row_size, val_size, ver, days = (int(field) for field in fields[-6:])
            return key, file_id, offset, row_size, val_size, ver, days

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError) as e: # pragma: no cover
            raise ValueError from e

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoVAL(metaclass=ABCMeta): # pragma: no cover
    """Abstract Base Class (ABC) defining data serialization codecs interfaces wrappers for actual target values records."""
    @abstractmethod
    def dumps(self, data:Any) -> bytes: ...
    @abstractmethod
    def loads(self, data:bytes) -> Any: ...

class JIoVAL_J(JIoVAL):
    """JSON values payload formatting subsystem driver handling readable text matrices generation."""
    def dumps(self, data:Any) -> bytes:
        try:
            return _json_dumps(data, default=_json_default)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads(self, data:bytes) -> Any:
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
            raise ValueError from e

class JIoVAL_S(JIoVAL):
    """MsgPack value payload compiler handling high density binary records packaging."""
    def dumps(self, data:Any) -> bytes:
        try:
            return _msg_dumps(data, default=_msg_encode) or b''

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads(self, data:bytes) -> Any:
        for _ in range(9):
            try:
                return _msg_loads(data, ext_hook=_msg_decode, strict_map_key=False)

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError): # pragma: no cover
                data = data + b'\xc1'

        raise ValueError

class JIoVAL_M(JIoVAL):
    """Marshal payload value processing interface utilizing rapid low-level internal runtime hooks."""
    def dumps(self, data:Any) -> bytes:
        try:
            # nosemgrep
            return marshal_dumps(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads(self, data:bytes) -> Any:
        for _ in range(9):
            try:
                # nosemgrep
                return marshal_loads(data) # nosec B302

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError): # pragma: no cover
                data = data + b'\n'

        raise ValueError

class JIoVAL_P(JIoVAL):
    """Pickle value payload subsystem driver supporting deep preservation of native Python objects graphs layouts."""
    def dumps(self, data:Any) -> bytes:
        try:
            # nosemgrep
            return pickle_dumps(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, PicklingError) as e: # pragma: no cover
            raise ValueError from e

    def loads(self, data:bytes) -> Any:
        for _ in range(9):
            try:
                # nosemgrep
                return pickle_loads(data) # nosec B301

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, PicklingError): # pragma: no cover
                data = data + b'\n'

        raise ValueError

class JIoVAL_Y(JIoVAL):
    """YAML values encoder subsystem driver generating multi-line clean configuration trees structures formats documents rows fields."""
    def dumps(self, data:Any) -> bytes:
        if yaml is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

        try:
            return yaml.safe_dump(data, allow_unicode=True).encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, yaml.YAMLError) as e: # pragma: no cover
            raise ValueError from e

    def loads(self, data:bytes) -> Any:
        if yaml is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

        for _ in range(9):
            try:
                return yaml.safe_load(data)

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, yaml.YAMLError): # pragma: no cover
                data = data + b'\n'

        raise ValueError

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
g_HEAD = JIoHEAD()

class JIo:
    # reduce memory usage --> __dict__, but child class cannot have member
    __slots__ = ('days', 'sync_id', 'swap_id', 'remv_id', 'min_days',\
            '_sync_id', '_swap_id', '_remv_id', '_n_records',\
            '_n_lines', 'file_size', 'n_records', 'n_lines', 'groups',\
            '_data_type', '_zip_type', '_key_limit', 'index_size',\
            'max_file_size', 'reserved_rate', 'api_ver', 'file_table',\
            'files_obj', 'key_table', 'window_size', 'min_value_size',\
            '_KEY_rows', 'row_bytes', 'pad_byte', 'pad0_byte',\
            'KEY_dumps', 'KEY_loads', 'VAL_dumps', 'VAL_loads',\
            'HEAD_dumps', 'HEAD_loads','VAL_zip', 'VAL_unzip', 'VAL_unzip0')

    @staticmethod
    def z_zip_type_str(zip_type:int) -> str:
        """Convert a numerical compression classification token into its canonical format name token text string.

        Args:
            zip_type (int): Compression indicator number value index.

        Returns:
            str: Target nomenclature identity label (e.g., 'zs', 'gz', 'no').

        Raises:
            ValueError: If an unknown compression type integer is evaluated.
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
        """Convert serialization schema format integer targets into layout identification token code strings.

        Args:
            data_type (int): Type index value number.

        Returns:
            str: Operational configuration layout nomenclature label text (e.g., 'J+S').

        Raises:
            ValueError: If an unrecognized layout configuration category code is matched.
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

        raise ValueError(f'unknown data type {data_type}')

    @staticmethod
    def z_key_limit_str(key_limit:int) -> str:
        """Translate structural cache constraint parameters integers into readable indicator codes text specifications.

        Args:
            key_limit (int): Underlying memory limitation capacity bounds code index number integer.

        Returns:
            str: Readable constraint description format string token.
        """
        if key_limit == 0:      return 'no'
        if key_limit == -0x100: return 'bt'
        if key_limit > 0:       return f'<{key_limit+1}'
        return f'l{-key_limit-1}'

    @staticmethod
    def z_conv_days(timestamp:Union[int,float,datetime,dt_date]) -> int:
        """Compute relative integer day counters starting from baseline anchor configurations sheets.

        Args:
            timestamp (Union[int, float, datetime, dt_date]): Target timeline marker element candidate.

        Returns:
            int: Calculated absolute day index spacing number integer.
        """
        if isinstance(timestamp, datetime):
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
            sync_id:int=0, swap_id:int=0, remv_id:int=0):

        """Initialize core engine parameters linking pipeline translation modules layers across active devices driver handles.

        Args:
            files_obj (JFilesBase): File management abstraction driver context interface handle instance proxy.
            data_type (Union[str, int, None], optional): Codec serialization scheme categorization flag indicator.
                
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
                - 'J+Y' | 11 =  KEY=msgpack | VAL=YAML
                - 'S+Y' | 12 = KEY=msgpack  | VAL=YAML

            zip_type (Union[str, int, None], optional): Target row data level compression profile rules configuration.
                
                - 'no' | 0 = no compression for VAL
                - 'gz' | 1 = gzip compression(9) for VAL
                - 'bz' | 2 = bz2 compression(9) for VAL
                - 'xz' | 3 = lzma compression for VAL
                - 'zs' | 4 = zstandard compression(22) for VAL
                - 'br' | 5 = brotli compression(6) for VAL
                - 'z1' | 6 = zstandard compression(6) for VAL
                - 'z2' | 7 = zstandard compression(11) for VAL
                - 'lz' | 8 = lz4 compression(0) for VAL

            key_limit (Union[str, int, None], optional): Sizing operational constraint boundary parameters regulating index memory.
                
                - "no" | 0 = use DictKeyTable. (default). 
                - "bt" | 0x100 = use BTreeKeyTable.
                - "l0"-"l5" | -ve = use LiteKeyTable.
                - "<{n}" | +ve = use PartialKeyTable.

            api_ver (Optional[int], optional): Logical physical structural schema edition categorization sequence index token.

                - 0 = oldest version.
                - None = latest version. (default)
                
            min_value_size (Optional[int], optional): Minimal alignment constraint width bounding row expansions.
            index_size (Optional[int], optional): Fixed byte width defining row segmentation sizes boundaries parameters tracking grids.
            max_file_size (Optional[int], optional): Physical storage capacity metrics constraint limiting data partitions files allocation sizes.
            reserved_rate (Optional[float], optional): Expansion reserve factor allocated for updating records drift fields properties.
            sync_id (int, optional): Synchronization sequence generation tracker value index number. Defaults to 0.
            swap_id (int, optional): Rearrangement transaction milestone tracking index code integer number. Defaults to 0.
            remv_id (int, optional): Accumulative deletions sequence tracker reference number code index value. Defaults to 0.

        Raises:
            TypeError: If input structural variables violate driver blueprint specifications classes.
        """

        if not isinstance(files_obj, JFilesBase):
            raise TypeError

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

        self._KEY_rows = {}
        self._data_type = self._zip_type = self._key_limit = -1
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
        """Scan physical descriptor headers logs dynamically setting baseline codecs pipelines matching verified database states blueprints.

        Args:
            api_ver (Optional[int]): Logical iteration category indicator target index selection token code text format.
            reset (bool, optional): Obliterate operational structures resetting metrics back onto standard initialization defaults. Defaults to False.
        """
        files_obj = self.files_obj
        if self.min_days < 0:
            self.min_days = self.z_conv_days(files_obj.KEY_date())

        fp = None
        data_type = self._data_type
        zip_type = self._zip_type
        try:
            fp = files_obj.KEY_open('rb')
            header = fp.read(HEADER_SIZE)
            if len(header) == HEADER_SIZE:
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
        """Get the compression configuration format profile nomenclature string.

        Returns:
            str: Identity code string token mapping algorithmic targets (e.g., 'zs', 'no').
        """
        return self.z_zip_type_str(self._zip_type)

    @property
    def zip_type(self) -> int:
        """Get or set compression rules profiles specifications integers indices tokens.

        Returns:
            int: Structural algorithmic classification identifier number.
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
        """Get format encoding specification layout code tokens indicator naming blueprints.

        Returns:
            str: Structural layout identifier code string token (e.g., 'J+S').
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
        """Set structural serialization layouts formats schemas selecting indicators tokens strings parameters values.

        Args:
            value (Union[int, str]): Format setting classification assignment label string or integer value index.
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
                else:
                    raise ValueError(f'invalid data string {value}')

        if not isinstance(value, int):
            raise TypeError(f'invalid data type {value}')

        if not LAST_DATA_TYPE >= value >= 0:
            raise ValueError(f'invalid data type {value}')

        if value in {J_Y_TYPE, S_Y_TYPE} and yaml is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

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
        """Set cache mapping limitations constraints bounds rules updating operational modules configurations fields dynamically.

        Args:
            value (Union[int, str]): New tracking limit constraint specifications parameters token code format selection options.
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
        """Get structural cache limitation description code tokens.

        Returns:
            str: Parsed context representation parameters string layout text format.
        """
        return self.z_key_limit_str(self._key_limit)

    def change_APIs(self, version:Optional[int]=None, data_type:int=DEF_TYPE, zip_type:int=DEF_ZIP, reset:bool=False):
        """Re-bind serialization codec abstraction routing pointers across chosen logical engine configuration profiles models.

        Args:
            version (Optional[int], optional): Target API schema iteration index token code value number. Defaults to None.
            data_type (int, optional): Coding matrix categorization specification number index value. Defaults to DEF_TYPE.
            zip_type (int, optional): Data row compression profiling rule classification identifier. Defaults to DEF_ZIP.
            reset (bool, optional): Obliterate internal state layouts prior to polling system state logs. Defaults to False.

        Raises:
            TypeError: If input structural identifiers break validation configurations parameters.
            ValueError: If an unexpected out-of-bounds format version token encounters tracking pipelines.
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
            else:
                raise ValueError(f'invalid data type {self.api_ver}->{version} type:{data_type}')

        else:
            raise ValueError(f'invalid version {self.api_ver}->{version} type:{data_type}')

    def sorted_key_table_items(self, copy:bool=False, reverse:bool=False) -> Generator[str,int]:
        """Generate chronologically ordered or reverse ordered key index entries pairs collections sequences.

        Args:
            copy (bool, optional): Force safe execution isolation boundaries by duplicating indices structures tracks first. Defaults to False.
            reverse (bool, optional): Flip direction output forcing descending trajectory parsing flows instead. Defaults to False.

        Yields:
            Tuple[str, int]: Entry identity string descriptor paired along active logical index row line identifier number.
        """
        if copy:
            fp = None
            try:
                files_obj = self.files_obj.copy()
                KEY_loads = self.KEY_loads
                index_size = self.index_size
                fp = files_obj.KEY_open('rb')
                if reverse:
                    for row_id in range(self.n_records-1, -1, -1):
                        fp.seek(HEADER_SIZE + row_id * index_size)
                        _key, _f, _o, _r, _v, _s, _d = KEY_loads(fp.read(index_size))
                        yield _key, row_id
                else:
                    fp.seek(HEADER_SIZE)
                    for row_id in range(self.n_records):
                        _key, _f, _o, _r, _v, _s, _d = KEY_loads(fp.read(index_size))
                        yield _key, row_id

            finally:
                if fp is not None:
                    fp.close()

            return

        lut = {}
        if reverse:
            row = self.n_records-1
            for key,_row in self.key_table.items():
                if _row == row:
                    yield key, row
                    row -= 1
                    while lut and row in lut:
                        yield lut.pop(row, ''), row
                        row -= 1
                else:
                    lut[_row] = key

            for row in sorted(lut, reverse=True): # pragma: no cover
                yield lut.pop(row, ''), row

        else:
            row = 0
            for key,_row in self.key_table.items():
                if _row == row:
                    yield key, row
                    row += 1
                    while lut and row in lut:
                        yield lut.pop(row, ''), row
                        row += 1
                else:
                    lut[_row] = key

            for row in sorted(lut): # pragma: no cover
                yield lut.pop(row, ''), row

    def zip(self, data:bytes, zip_type:Optional[int]=None) -> bytes:
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
            raise ValueError from e

    def unzip(self, data:bytes, zip_type:Optional[int]=None) -> bytes:
        """Decompress data blocks sequences backward returning baseline raw serialization strings contents arrays.

        Args:
            data (bytes): Input compressed binary payload segment array block.
            zip_type (Optional[int], optional): Overriding codec rule selector index option parameter integer. Defaults to None.

        Returns:
            bytes: Decompressed raw byte block string.

        Raises:
            ValueError: If decompression routines hit unrecoverable stream corruptions parameters markers fields.
        """
        zip_type_i = self._zip_type if zip_type is None else zip_type
        try:
            if zip_type_i < 0:
                zip_type_i = -zip_type_i-1
                return data if zip_type_i == NO_ZIP else self.VAL_unzip0(data)

            return self.VAL_unzip(self.pad0_byte, data)

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

            raise ValueError from e

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

    def write_key(self, fp:IO, row_id:int, key:str, file_id:int, offset:int, row_size:int, val_size:int=0, ver:Optional[int]=None, days:int=-1) -> int:
        """Commit structured individual key mapping elements definitions metadata straight into active tracking index slots.

        Args:
            fp (IO): Destination open file descriptor stream handler context.
            row_id (int): Hardware space line allocation alignment position coordinate number integer value.
            key (str): Unique data reference lookup descriptor name string token formatting layout context.
            file_id (int): Segment data section classification index identifier value number code.
            offset (int): Absolute hardware capacity cursor position displacement indicator.
            row_size (int): Allocated byte length ceiling constraining row segment storage space tracks.
            val_size (int, optional): True byte length occupied by payload content items strings. Defaults to 0.
            ver (Optional[int], optional): Synchronization transaction generation code index tracker. Defaults to None.
            days (int, optional): Relative calendar sequence tracking day mapping metrics value number integer. Defaults to -1.

        Returns:
            int: Total absolute verification measurement count bytes committed into physical files.
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
        need_flush = False
        if pad_size < 0:
            need_flush = True
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

        _KEY_rows = self._KEY_rows
        _KEY_rows.pop(row_id, None)
        if row_id < self.n_records:
            _KEY_rows[row_id] = (key, file_id, offset, row_size, val_size, ver_i, days)
            while len(_KEY_rows) > TOTAL_KEY_ROWS:
                _pop_id = next(iter(_KEY_rows))
                _KEY_rows.pop(_pop_id, None)

        wr_size = fp.write(data + b' ' * pad_size + b'\n') if pad_size > 0 else fp.write(data + b'\n')
        if need_flush and wr_size > 0:
            fp.flush()

        return wr_size

    def read_key(self, fp:IO, row_id:int) -> Tuple[str, int, int, int, int, int, int]:
        """Extract individual item schema parameters matrices fields reading indices configurations records rows.

        Args:
            fp (IO): Open file pointer registration stream controller instance proxy handle.
            row_id (int): Targeted hardware data space line allocation position slot integer number.            

        Returns:
            Tuple[str,int,int,int,int,int,int]: Complete row structural metadata metrics (key, file_id, offset, row_size, val_size, ver, days).
        """
        _KEY_rows = self._KEY_rows
        _info = _KEY_rows.pop(row_id, None)
        if _info is not None:
            _KEY_rows[row_id] = _info
            return _info

        index_size = self.index_size
        pos = HEADER_SIZE + row_id * index_size
        if fp.tell() != pos:
            fp.seek(pos)

        data = fp.read(index_size)
        info = self.KEY_loads(data)
        if row_id < self.n_records:
            _KEY_rows[row_id] = info
            while len(_KEY_rows) > TOTAL_KEY_ROWS:
                _pop_id = next(iter(_KEY_rows))
                _KEY_rows.pop(_pop_id, None)

        return info

    def update_days(self) -> int:
        """Query host clock registers re-aligning tracking timestamp offset integer representations variables.

        Returns:
            int: Updated sequence number indicator mapping active relative day metrics thresholds.
        """
        timestamp = int(time())
        self.days = NUM_1970_DAYS + max(0, timestamp - THE_1ST_SEC) // DAY_SEC
        return self.days

    def is_updated(self) -> bool:
        """Validate transactional chronology alignment verifying if memory arrays match disk headers footprints.

        Returns:
            bool: True if alignment indicators match active storage timeline parameters perfectly, False otherwise.
        """
        if self.file_size <= 0 or self.sync_id != self._sync_id:
            self._KEY_rows.clear()
            return False

        return True

    def reset(self, **kwargs):
        """Obliterate runtime trackers dropping state variables clearing memory pools tables configurations allocations fields.

        Args:
            **kwargs: Configuration overrides for baseline engine constants (e.g., index_size, reserved_rate).
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
        self.update_days()
        self.row_bytes = self.index_size - self.min_value_size * (1 + self.reserved_rate)
        self.window_size = max(1, int(KEY_FILE_BUF_SIZE / self.index_size))

    def write_header(self, fp:IO, truncate:bool=False) -> int:
        """Commit production database status configuration descriptors templates header schemas directly into metadata boundaries fields.

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

        fp.flush()
        self.file_size = file_size
        return file_size

    def read_header(self, fp:IO) -> JIo:
        """Parse master configuration descriptor headers grids loading metadata parameters indicators cross-referencing timeline indices numbers.

        Args:
            fp (IO): Source active streaming channel file pointer wrapper proxy.

        Returns:
            JIo: The synchronized processing engine master instance context reference.
        """
        if fp.tell() != 0: fp.seek(0)
        header = fp.read(HEADER_SIZE)
        _len = len(header)
        if _len == HEADER_SIZE:
            sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver = self.HEAD_loads(header)
        else:
            n_records = n_lines = sync_id = swap_id = remv_id = 0
            index_size  = self.index_size
            zip_type    = self.zip_type
            data_type   = self.data_type
            api_ver     = self.api_ver

        if self.file_size > 0:
            # pylint: disable=too-many-boolean-expressions
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
        """Extract unparsed continuous byte chunks arrays sequences straight from active storage device sectors indices coordinates paths.

        Args:
            fp (IO): Persistent active streaming channel handler context.
            pos (int): Absolute destination location offset parameter integer measurement.
            row_size (int): Segment envelope block tracking width parameter.
            val_size (int): True data size.

        Returns:
            bytes: Raw binary block sequence fetched from physical tracks.
        """
        fp.seek(pos)
        return fp.read(val_size if val_size > 0 else row_size)

    def read_value(self, fp:IO, pos:int, row_size:int, val_size:int) -> Any:
        """Extract and deserialize stored data entities records by evaluating physical storage tracking maps coordinates pointers.

        Args:
            fp (IO): Active open file descriptor stream handler instance.
            pos (int): Core target byte position coordinate indicator integer.
            row_size (int): Sizing constraint boundary defining row block structural margins.
            val_size (int): Expected unpadded data byte payload sequence length parameters indicators.

        Returns:
            Any: Unpacked deserialized Python primitive or custom data structure mapping.
        """
        fp.seek(pos)
        val_bytes, zip_type = (fp.read(val_size), -(self.zip_type+1)) if val_size > 0 else (fp.read(row_size), self.zip_type)
        if not val_bytes:
            return None

        return self.loads_with_unzip(val_bytes, zip_type=zip_type)

    def dumps_with_zip(self, data:Any, zip_type:Optional[int]=None) -> bytes:
        """Compress and serialize values blocks payloads utilizing combined encoder algorithms frameworks pipelines.

        Args:
            data (Any): Python data primitive object layout candidate.
            zip_type (Optional[int], optional): Custom compression algorithm code tracker identifier index. Defaults to None.

        Returns:
            bytes: Packed compressed structural binary elements track block sequence array.
        """
        try:
            val_bytes = self.VAL_dumps(data)
            return self.zip(val_bytes, zip_type=zip_type)

        except ValueError as e: # pragma: no cover
            print(Style(f'!!!!!!!!!!! [???|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!dumps_with_zip(data={type(data)}, zip_type={zip_type})\nexception:{e}', red=1))
            raise ValueError from e

    def loads_with_unzip(self, val_bytes:bytes, zip_type:Optional[int]=None) -> Any:
        """Unpack and decompress values blocks sequences backward reconstructing original Python structures layout instances profiles models parameters data fields fields.

        Args:
            val_bytes (bytes): Source compressed binary data chunk payload array block sequence input.
            zip_type (Optional[int], optional): Overriding algorithmic category reference number identifier selection indicator value. Defaults to None.

        Returns:
            Any: Deserialized Python data payload mapping output.
        """
        try:
            unzip_bytes = self.unzip(val_bytes, zip_type=zip_type)
            return self.VAL_loads(unzip_bytes)

        except ValueError as e: # pragma: no cover
            print(Style(f'!!!!!!!!!!! [???|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!loads_with_unzip(val_bytes[{len(val_bytes)}]={val_bytes[-512:]}, zip_type={zip_type})\nexception:{e}', red=1))
            raise ValueError from e

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
        """Synchronize master index tracking datasets maps parsing chronological database operations logs systematically.

        Args:
            fp (IO): Open index file pointer stream handle manager workspace connection object.
            force (bool, optional): Overrule timeline sequence checks rebuilding index table layouts absolutely from zero. Defaults to False.
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
        self.file_size = records = lines = 0
        self.update_days()
        if force or n_lines == 0 or prev_n_lines == 0 or line_diff < 0:
            key_table.clear()
            file_table.clear()
            self._KEY_rows.clear()
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
                    lines = min(n_lines, n_records+line_diff) if line_diff == 0 else n_lines

                # swap_diff == rec_diff == 0 and remv_diff > 0
                elif rec_diff == 0 and remv_diff > 0: # ADD == DEL
                    records = max(0, n_records-remv_diff)
                    lines = min(n_lines, n_records+line_diff+remv_diff) if line_diff == 0 else n_lines

                # swap_diff == 0 and remv_diff > 0 and rec_diff > 0
                elif rec_diff > 0: # ADD > DEL
                    records = max(0, prev_n_records-remv_diff)
                    lines = min(n_lines, n_records+remv_diff) if line_diff == 0 else n_lines

                # swap_diff == 0 and remv_diff > 0 and rec_diff < 0
                else: # ADD < DEL
                    records = max(0, n_records-remv_diff)
                    lines = min(n_lines, n_records+remv_diff) if line_diff == 0 else n_lines

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

                self.update_file_table()
                if records < n_records:
                    KEY_loads = self.KEY_loads
                    fp.seek(HEADER_SIZE + records * index_size)
                    for row in range(records, n_records):
                        key,file_id,offset,row_size,_val_size = KEY_loads(fp.read(index_size))[:5]
                        key_table[key] = row
                        if row_size > 0:
                            file_table[file_id] = max(file_table[file_id], offset + row_size)
                        elif row_size == 0 and file_id == 0x10: # pragma: no cover
                            self.groups.setdefault(key, None)

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
                        fp.seek(HEADER_SIZE + n_records * index_size)
                        for row in range(n_records, min(n_lines, n_records+remv_diff)):
                            del_rec = KEY_loads(fp.read(index_size))
                            old_row = key_table.pop(del_rec[0], -1)
                            if n_records > old_row >= 0:
                                cur_pos = fp.tell()
                                fp.seek(HEADER_SIZE + old_row * index_size)
                                new_rec = KEY_loads(fp.read(index_size))
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

        fp.seek(HEADER_SIZE + lines * self.index_size)
        # read key info line by line
        data_type_s = self.data_type_str
        KEY_loads = self.KEY_loads
        if data_type_s.startswith(('L', 'J')):
            for line in fp: # 1.29% faster than fp.readlines(block_size)
                if line[0] == 10: # pragma: no cover
                    if lines < n_lines or records < n_records:
                        print(Style(f'!!!!!!!!!!! [{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type}|{self.zip_type}] ERROR!load_keys(#{records}/{n_lines} fp:{fp} line:{line})'))
                    break

                try:
                    key, file_id, offset, row_size, _val_size, _ver, _days = KEY_loads(line)

                except ValueError as e: # pragma: no cover
                    if lines < n_lines or records < n_records:
                        print(Style(f'!!!!!!!!!!! [DECODE|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!load_keys(#{records}/{n_lines} fp:{fp} line:{line})\nexception:{e}'))
                    break

                if records < n_records:
                    records += 1
                    key_table[key] = lines

                    if row_size > 0:
                        file_table[file_id] = max(file_table[file_id], offset + row_size)
                    elif row_size == 0 and file_id == 0x10: # pragma: no cover
                        self.groups.setdefault(key, None)

                    lines += 1
                else:
                    lines = n_lines
                    self.update_file_table()
                    break

        else: # M, S
            while lines < n_lines:
                line = fp.read(index_size)
                if not line or len(line) != index_size: # pragma: no cover
                    break

                try:
                    key, file_id, offset, row_size, _val_size, _ver, _days = KEY_loads(line)

                except ValueError as e: # pragma: no cover
                    if lines < n_lines or records < n_records:
                        print(Style(f'!!!!!!!!!!! [DECODE|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!load_keys(#{records}/{n_lines} fp:{fp} line:{line})\nexception:{e}'))
                    break

                if records < n_records:
                    records += 1
                    key_table[key] = lines

                    if row_size > 0:
                        file_table[file_id] = max(file_table[file_id], offset + row_size)
                    elif row_size == 0 and file_id == 0x10: # pragma: no cover
                        self.groups.setdefault(key, None)

                    lines += 1
                else:
                    lines = n_lines
                    self.update_file_table()
                    break

        if lines <= 0: # pragma: no cover
            n_records = n_lines = 0
            key_table.clear()
            file_table.clear()
        else:
            n_records = records
            n_lines = lines

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
        self._KEY_rows.pop(src_row, None)
        self._KEY_rows.pop(dst_row, None)

        size = self.index_size
        src_pos = HEADER_SIZE + src_row * size
        dst_pos = HEADER_SIZE + dst_row * size
        if fp.tell() != src_pos:
            fp.seek(src_pos)
        data = fp.read(size)

        if src_pos != dst_pos:
            if fp.tell() != dst_pos:
                fp.seek(dst_pos)
            fp.write(data)

        return data if not decode else self.KEY_loads(data)

    def shift_keys(self, fp:IO, start:int, offset:int=1, size:int=1, block_size:Optional[int]=None): # pragma: no cover
        """Displace continuous series of index row metadata entries horizontally to allocate open layout rows block zones.

        Args:
            fp (IO): Destination open streaming stream file handler context.
            start (int): Absolute baseline rows row index coordinate position where shifting procedures activate.
            offset (int, optional): Relocation displacement coefficient multiplier integer adjusting target rows coordinates. Defaults to 1.
            size (int, optional): Combined length measure tracking total logical rows objects to shift. Defaults to 1.
            block_size (Optional[int], optional): Internal parsing lookahead width constraining buffered file operations rows loops. Defaults to None.
        """
        n_lines = self.n_lines
        index_size = self.index_size
        if block_size is None:
            block_size = self.window_size

        n_blocks = size // block_size
        if (size % block_size) > 0:
            n_blocks += 1

        _KEY_rows = self._KEY_rows
        src_row = min(start+size, n_lines)
        for row_id in range(n_blocks):
            _KEY_rows.pop(row_id, None)

            if src_row >= block_size:
                rd_size = block_size * index_size
                src_row -= block_size
            else:
                rd_size = (src_row - start) * index_size
                src_row = start

            if rd_size <= 0:
                break

            fp.seek(HEADER_SIZE + src_row * index_size)
            rd_data = fp.read(rd_size)
            fp.seek(HEADER_SIZE + (src_row + offset) * index_size)
            fp.write(rd_data)

    def resize_keys(self, fp:IO, index_size:int, min_ver:bool=False):
        """Re-structure physical index layout files modifying rows padding block sizing constraints permanently.

        Args:
            fp (IO): Persistent open streaming interface proxy connection file object.
            index_size (int): Target row byte allocation width constraint parameter integer number.
            min_ver (bool, optional): Overrule version trackers initializing sequential timeline markers coordinates limits fields back onto compressed baselines. Defaults to False.
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
                    index_size=index_size)

        table = {}
        src_row_id = dst_row_id = 0
        size_diff = index_size - self.index_size
        dst_io.n_lines = n_lines
        n_records = self.n_records
        src_read_key = self.read_key
        fp.flush()
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
        self.load_keys(fp, force=True)
        self.window_size = max(1, int(KEY_FILE_BUF_SIZE / index_size))
        self.row_bytes = index_size - self.min_value_size * (1 + self.reserved_rate)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------

#
