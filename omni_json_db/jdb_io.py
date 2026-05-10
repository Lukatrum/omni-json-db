from __future__ import annotations # pylint: disable=too-many-lines
from abc import ABCMeta, abstractmethod
from typing import Any, Union, Optional, Tuple, Callable, Generator, IO
from io import DEFAULT_BUFFER_SIZE
from time import time
from functools import reduce
from collections import defaultdict
from datetime import date as dt_date, datetime, timedelta
from pickle import loads as pickle_loads, dumps as pickle_dumps, PicklingError
from marshal import loads as marshal_loads, dumps as marshal_dumps
from bz2 import compress as bz2_compress, decompress as bz2_decompress
from lzma import compress as lzma_compress, decompress as lzma_decompress, LZMAError as XZ_Error
try:
    from gzip import compress as gzip_compress, decompress as gzip_decompress, BadGzipFile as GZ_Error

except ImportError:
    from gzip import compress as gzip_compress, decompress as gzip_decompress
    GZ_Error = OSError

#-----------------------------------------------------------------------------
from bitarray import bitarray

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
        return __json_dumps(obj, default=default, ensure_ascii=False, separators=(',',':')).encode('utf8')

    def json_dumps(obj:Any) -> bytes:
        return __json_dumps(obj, default=_json_default, ensure_ascii=False, separators=(',',':')).encode('utf8')

    json_loads = _json_loads

try:
    from ormsgpack import packb as _msg_dumps, Ext
    from msgpack import unpackb as _msg_loads, Unpacker

    def _msg_encode(obj) -> bytes:
        return Ext(123, marshal_dumps(obj))

except (ModuleNotFoundError, ImportError):
    from msgpack import packb as _msg_dumps, unpackb as _msg_loads, Unpacker, ExtType

    def _msg_encode(obj) -> bytes:
        return ExtType(123, marshal_dumps(obj))

def _msg_decode(code:int, data:bytes):
    if code == 123:
        return marshal_loads(data)

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
from .jdb_file import JFilesBase, JDiskFiles

BZ_Error = OSError
LZ_Error = RuntimeError
from .utils import Style
#from .utils import debug_break
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
MAX_FILE_ID     = 0x8000
DEF_FILE_SIZE   = (2**30) * 2  # 2GB
MIN_FILE_SIZE   = 1024
MAX_FILE_SIZE   = (2**50) * 1  # 1024TB

DEF_INDEX_SIZE  = 128
MIN_INDEX_SIZE  = 16 + 8 * 6  # key(16), (file_id, offset, row_size, val_size, ver, date)
MAX_INDEX_SIZE  = 2**15

DEF_VALUE_SIZE  = 16 # 1-15 bytes can store in KEY file
MIN_VALUE_SIZE  = 1
MAX_VALUE_SIZE  = (2**30) * 4 - 1 # 4GB (32bit)

DEF_FLAG_SIZE   = 2**20 # bitarray size for key search
DEF_FLAG_MASK   = DEF_FLAG_SIZE - 1

DEF_RATIO       = 0.001
MAX_RATIO       = 256.
DEF_KEY_LIMIT   = 0 # 0=DictKeyTable(dict)
HEADER_SIZE     = 128

#HEADER_STRUCT = Struct('@QQQQQQQQ64x') # only for S+S (MsgpackIo)
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
LAST_DATA_TYPE = S_P_TYPE

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
class JDbGroupDict(dict): # pragma: no cover
    __slots__ = []
    def __missing__(self, key):
        return None

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class KeyTable: # pragma: no cover
    def get_mode(self) -> int: ...
    def cache_cleanup(self): ...
    def set(self, _key:str, _row_id:int): ...
    def pop(self, _key:str, _default_row_id:int=-1) -> int: ...
    def get(self, _key:str, _default_row_id:int=-1) -> int: ...
    def items(self) -> Generator[str,int]: ...
    def values(self) -> Generator[int]: ...
    def keys(self) -> Generator[str]: ...
    def copy(self) -> KeyTable: ...
    def clear(self): ...
    def __len__(self) -> int: ...
    def __setitem__(self, _key:str, _row_id:int): ...
    def __getitem__(self, _key:str) -> int: ...
    def __delitem__(self, _key:str): ...
    def __contains__(self, _key:str) -> bool: ...
    def __iter__(self) -> Generator[str]: ...
    def __eq__(self, _obj:Any) -> bool: ...

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class DictKeyTable(dict): # pragma: no cover
    __slots__ = []
    def __missing__(self, key):
        return -1

    def get_mode(self) -> int:
        return -1

    def cache_cleanup(self):
        self.clear()

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
xhash = hash # hash() is not deterministic, can export PYTHONHASHSEED=0
class PartialKeyTable(KeyTable):
    __slots__ = {'cache', 'io', 'flags', 'is_dirty', 'files_obj'}

    def __init__(self, jio:JIo):
        self.cache = DictKeyTable()
        self.io = jio
        self.files_obj = jio.files_obj.copy()
        self.is_dirty = False
        self.flags = bitarray(DEF_FLAG_SIZE) # not all zero
        self.flags.setall(0)

    def cache_cleanup(self):
        return self.cache.clear()

    def get_mode(self) -> int:
        return -1

    def __repr__(self) -> str:
        return f'<{type(self).__name__} {"D" if self.is_dirty else "F"} cache:{len(self.cache)} {self.flags.count(1)*100./len(self.flags):.2f}% at {hex(id(self))}>'

    def set(self, key:str, row_id:int):
        jio = self.io
        cache = self.cache
        if jio.n_records <= 0:
            self.clear()

        if not self.is_dirty and row_id+1 >= jio.n_records:
            self.is_dirty = True

        _hash_id = xhash(key)
        self.flags[_hash_id & DEF_FLAG_MASK] = 1
        if key in cache:
            cache.pop(key, None)
            cache[key] = row_id
            return

        # clean up extra buffer
        key_limit = jio._key_limit
        while len(cache) >= key_limit:
            old_key = next(iter(cache))
            cache.pop(old_key, None)

        cache[key] = row_id

    def pop(self, key:str, default_row_id:int=-1) -> int:
        size = len(self)
        if size <= 0:
            self.clear()
            return default_row_id

        _hash_id = xhash(key)
        if self.is_dirty and not self.flags[_hash_id & DEF_FLAG_MASK]:
            self.cache.pop(key, None)
            return default_row_id

        cache = self.cache
        if key in cache:
            return cache.pop(key, default_row_id)

        fp = None
        try:
            jio = self.io
            read_key = jio.read_key
            fp = self.files_obj.KEY_open('rb')
            fp.seek(HEADER_SIZE)
            for row_id in range(jio.n_records):
                _key, _f, _o, _r, _v, _s, _d = read_key(fp, row_id, seek=False)
                _hash_id = xhash(_key)
                self.flags[_hash_id & DEF_FLAG_MASK] = 1
                if _key == key:
                    if not self.is_dirty and row_id+1 >= jio.n_records:
                        self.is_dirty = True
                    return row_id

            if jio.n_records > 0 and not self.is_dirty:
                self.is_dirty = True

        finally:
            if fp is not None:
                fp.close()

        return default_row_id

    def get(self, key:str, default_row_id:int=-1) -> int:
        size = len(self)
        if size <= 0:
            self.clear()
            return default_row_id

        _hash_id = xhash(key)
        if self.is_dirty and not self.flags[_hash_id & DEF_FLAG_MASK]:
            return default_row_id

        cache = self.cache
        row_id = cache[key]
        if row_id != -1:
            return row_id

        fp = None
        try:
            jio = self.io
            key_limit = jio._key_limit
            read_key = jio.read_key
            fp = self.files_obj.KEY_open('rb')
            fp.seek(HEADER_SIZE)
            for row_id in range(jio.n_records):
                _key, _f, _o, _r, _v, _s, _d = read_key(fp, row_id, seek=False)
                _hash_id = xhash(_key)
                self.flags[_hash_id & DEF_FLAG_MASK] = 1
                if _key != key:
                    continue

                # clean up extra buffer
                while len(cache) >= key_limit:
                    old_key = next(iter(cache))
                    cache.pop(old_key, None)

                cache[key] = row_id
                if not self.is_dirty and row_id+1 >= jio.n_records:
                    self.is_dirty = True

                return row_id

            if jio.n_records > 0 and not self.is_dirty:
                self.is_dirty = True

        finally:
            if fp is not None:
                fp.close()

        return default_row_id

    def items(self) -> Generator[str,int]:
        size = len(self)
        if size <= 0:
            self.clear()
            return

        fp = None
        try:
            jio = self.io
            read_key = jio.read_key
            fp = self.files_obj.KEY_open('rb')
            fp.seek(HEADER_SIZE)
            for row_id in range(jio.n_records):
                key, _f, _o, _r, _v, _s, _d = read_key(fp, row_id, seek=False)
                _hash_id = xhash(key)
                self.flags[_hash_id & DEF_FLAG_MASK] = 1
                yield key, row_id

            if jio.n_records > 0 and not self.is_dirty:
                self.is_dirty = True

        finally:
            if fp is not None:
                fp.close()

    def values(self) -> Generator[int]:
        size = len(self)
        if size <= 0:
            self.clear()
            return

        yield from range(size)

    def keys(self) -> Generator[str]:
        size = len(self)
        if size <= 0:
            self.clear()
            return

        fp = None
        try:
            jio = self.io
            read_key = jio.read_key
            fp = self.files_obj.KEY_open('rb')
            fp.seek(HEADER_SIZE)
            for row_id in range(jio.n_records):
                key, _f, _o, _r, _v, _s, _d = read_key(fp, row_id, seek=False)
                _hash_id = xhash(key)
                self.flags[_hash_id & DEF_FLAG_MASK] = 1
                yield key

            if jio.n_records > 0 and not self.is_dirty:
                self.is_dirty = True

        finally:
            if fp is not None:
                fp.close()

    def copy(self) -> PartialKeyTable:
        obj = PartialKeyTable(self.io)
        if len(self) > 0:
            obj.flags.clear()
            obj.flags.frombytes(self.flags.tobytes())
        else:
            self.clear()

        return obj

    def clear(self):
        if self.is_dirty or self.cache:
            self.flags.setall(0)
            self.cache.clear()
            self.is_dirty = False

    def __len__(self) -> int:
        return self.io.n_records

    def __setitem__(self, key:str, row_id:int):
        self.set(key, row_id)

    def __getitem__(self, key:str) -> int:
        return self.get(key, -1)

    def __delitem__(self, key:str):
        self.pop(key)

    def __contains__(self, key:str) -> bool:
        size = len(self)
        if size <= 0:
            self.clear()
            return False

        _hash_id = xhash(key)
        if self.is_dirty and not self.flags[_hash_id & DEF_FLAG_MASK]:
            return False

        cache = self.cache
        if key in cache:
            return True

        fp = None
        try:
            jio = self.io
            read_key = jio.read_key
            fp = self.files_obj.KEY_open('rb')
            fp.seek(HEADER_SIZE)
            for row_id in range(jio.n_records):
                _key, _f, _o, _r, _v, _s, _d = read_key(fp, row_id, seek=False)
                _hash_id = xhash(_key)
                self.flags[_hash_id & DEF_FLAG_MASK] = 1
                if _key == key:
                    if not self.is_dirty and row_id+1 >= jio.n_records:
                        self.is_dirty = True

                    return True

            if jio.n_records > 0 and not self.is_dirty:
                self.is_dirty = True

        finally:
            if fp is not None:
                fp.close()

        return False

    def __iter__(self) -> Generator[str]:
        size = len(self)
        if size <= 0:
            self.clear()
            return

        fp = None
        try:
            jio = self.io
            read_key = jio.read_key
            fp = self.files_obj.KEY_open('rb')
            fp.seek(HEADER_SIZE)
            for row_id in range(jio.n_records):
                key, _f, _o, _r, _v, _s, _d = read_key(fp, row_id, seek=False)
                _hash_id = xhash(key)
                self.flags[_hash_id & DEF_FLAG_MASK] = 1
                yield key

            if jio.n_records > 0 and not self.is_dirty:
                self.is_dirty = True

        finally:
            if fp is not None:
                fp.close()

    def __eq__(self, obj) -> bool:
        if self is obj:
            return True

        if len(self) != len(obj):
            return False

        if isinstance(obj, PartialKeyTable):
            if self.files_obj == obj.files_obj:
                return True

        for key,val in self.items():
            if key not in obj:
                return False

            if val != obj.get(key, -1):
                return False

        if self.io.n_records > 0 and not self.is_dirty:
            self.is_dirty = True

        return True

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class LiteKeyTable(KeyTable):
    __slots__ = {'groups', 'size', 'mask', 'mode', 'flags', 'flags_mask'}
    def __init__(self, mode:int=0):
        _mode = mode & 0xfff
        if _mode == 0:
            self.mask = 0
            self.flags_mask = DEF_FLAG_MASK
        elif _mode == 1:
            self.mask = 0xf
            self.flags_mask = DEF_FLAG_MASK
        elif _mode == 2:
            self.mask = 0xff
            self.flags_mask = max(DEF_FLAG_MASK, 8*(2**18)-1)
        elif _mode == 3:
            self.mask = 0xfff
            self.flags_mask = max(DEF_FLAG_MASK, 8*(2**19)-1)
        elif _mode == 4:
            self.mask = 0xffff
            self.flags_mask = max(DEF_FLAG_MASK, 8*(2**20)-1)
        elif _mode == 5:
            self.mask = 0xf_ffff
            self.flags_mask = max(DEF_FLAG_MASK, 8*(2**21)-1)
        else:
            raise ValueError(f'invalid mode {mode}!')

        self.groups = [bytearray() for _ in range(self.mask+1)]
        self.flags = bitarray(self.flags_mask+1)
        self.mode = mode
        self.size = -1

    def get_mode(self) -> int:
        return self.mode

    def cache_cleanup(self):
        self.clear()

    def set(self, key:str, row_id:int):
        if self.size < 0:
            self.clear()

        # self.size must >= 0
        _hash_id = xhash(key)
        flag_idx = _hash_id & self.flags_mask
        mask = self.mask
        if mask:
            hash_id = (_hash_id & mask) if key else 0
            key_array = self.groups[hash_id]
        else:
            key_array = self.groups[0]

        n_bytes = len(key_array)
        search_prefix = b'\x92' + (_msg_dumps(key) or b'')
        if n_bytes <= 0 or not self.flags[flag_idx] or self.mode & 0x1000 and row_id >= self.size:
            self.size += 1
            self.flags[flag_idx] = 1
            key_array.extend(search_prefix + (_msg_dumps(row_id) or b''))
            return

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
                    if val_type <= 0x7f:
                        row = val_type

                    elif 0xcf >= val_type >= 0xcc:
                        row = int.from_bytes(key_array[val_idx+1:val_idx_e], 'big')

                    elif 0xd3 >= val_type >= 0xd0:
                        row =  int.from_bytes(key_array[val_idx+1:val_idx_e], 'big', signed=True)

                    elif val_type >= 0xe0:
                        row = val_type - 256

                    else:
                        row = -1

                    if row != row_id:
                        key_array[idx:val_idx_e] = search_prefix + (_msg_dumps(row_id) or b'')

                    return

            idx = key_array.find(search_prefix, idx+1)

        self.size += 1
        self.flags[flag_idx] = 1
        key_array.extend(search_prefix + (_msg_dumps(row_id) or b''))

    def pop(self, key:str, default_row_id:int=-1) -> int:
        if self.size == 0:
            return default_row_id

        if self.size < 0:
            self.clear()
            return default_row_id

        _hash_id = xhash(key)
        mask = self.mask
        if mask:
            hash_id = (_hash_id & mask) if key else 0
            key_array = self.groups[hash_id]
        else:
            key_array = self.groups[0]

        n_bytes = len(key_array)
        if n_bytes <= 0 or not self.flags[_hash_id & self.flags_mask]:
            return default_row_id

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
                    if val_type <= 0x7f:
                        row_id = val_type

                    elif 0xcf >= val_type >= 0xcc:
                        row_id = int.from_bytes(key_array[val_idx+1:val_idx_e], 'big')

                    elif 0xd3 >= val_type >= 0xd0:
                        row_id =  int.from_bytes(key_array[val_idx+1:val_idx_e], 'big', signed=True)

                    elif val_type >= 0xe0:
                        row_id = val_type - 256

                    else:
                        return default_row_id

                    del key_array[idx:val_idx_e]
                    self.size -= 1
                    return row_id

            idx = key_array.find(search_prefix, idx+1)

        return default_row_id

    def get(self, key:str, default_row_id:int=-1) -> int:
        if self.size <= 0:
            return default_row_id

        _hash_id = xhash(key)
        if not self.flags[_hash_id & self.flags_mask]:
            return default_row_id

        mask = self.mask
        if mask:
            hash_id = (_hash_id & mask) if key else 0
            key_array = self.groups[hash_id]
        else:
            key_array = self.groups[0]

        n_bytes = len(key_array)
        if n_bytes <= 0:
            return default_row_id

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
                    if val_type <= 0x7f:
                        return val_type

                    elif 0xcf >= val_type >= 0xcc:
                        return int.from_bytes(key_array[val_idx+1:val_idx_e], 'big')

                    elif 0xd3 >= val_type >= 0xd0:
                        return int.from_bytes(key_array[val_idx+1:val_idx_e], 'big', signed=True)

                    elif val_type >= 0xe0:
                        return val_type - 256

            idx = key_array.find(search_prefix, idx+1)

        return default_row_id

    def items(self) -> Generator[str,int]:
        if self.size <= 0:
            return

        unpacker = Unpacker()
        for key_array in self.groups:
            if not key_array: continue
            unpacker.feed(key_array)
            yield from unpacker

    def values(self) -> Generator[int]:
        if self.size <= 0:
            return

        unpacker = Unpacker()
        for key_array in self.groups:
            if not key_array: continue
            unpacker.feed(key_array)
            for _key,row in unpacker:
                yield row

    def keys(self) -> Generator[str]:
        if self.size <= 0:
            return

        unpacker = Unpacker()
        for key_array in self.groups:
            if not key_array: continue
            unpacker.feed(key_array)
            for key,_row in unpacker:
                yield key

    def copy(self) -> LiteKeyTable:
        obj = LiteKeyTable(self.mode)
        if self.size > 0:
            for dst_array,src_array in zip(obj.groups, self.groups):
                dst_array.extend(src_array)

            obj.flags.clear()
            obj.flags.frombytes(self.flags.tobytes())
            obj.size = self.size
        else:
            obj.flags.setall(0)

        return obj

    def clear(self):
        if self.size != 0:
            for key_array in self.groups:
                key_array.clear()

            self.flags.setall(0)
            self.size = 0

    def __repr__(self) -> str:
        _bytes = len(self.flags) // 8
        for key_array in self.groups:
            _bytes += len(key_array)

        return f'<{type(self).__name__} mode:{self.mode:x} #{self.size:,}({_bytes/1024/1024:,.2f}MB)+{self.flags.count(1)*100./len(self.flags):.2f}% at {hex(id(self))}>'

    def __len__(self) -> int:
        return max(self.size, 0)

    def __setitem__(self, key:str, row_id:int):
        self.set(key, row_id)

    def __getitem__(self, key:str) -> int:
        return self.get(key, -1)

    def __delitem__(self, key:str):
        self.pop(key)

    def __contains__(self, key:str) -> bool:
        return self.get(key, -1) != -1

    def __iter__(self) -> Generator[str]:
        yield from self.keys()

    def __eq__(self, obj) -> bool:
        if self is obj:
            return True

        if len(self) != len(obj):
            return False

        if isinstance(obj, LiteKeyTable):
            if self.groups == obj.groups:
                return True

        for key,val in self.items():
            if key not in obj:
                return False

            if val != obj.get(key, -1):
                return False

        return True

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
try:
    from BTrees.OLBTree import OLBTree as BTree # pylint: disable=no-name-in-module, import-error

    class BTreeKeyTable(BTree):
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
            return BTreeKeyTable(self)

        def __getitem__(self, key:str) -> int:
            return self.get(key, -1)

        def get_mode(self) -> int:
            return -1

        def cache_cleanup(self):
            self.clear()

except ModuleNotFoundError:
    BTreeKeyTable = DictKeyTable

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoHEAD:
    def dumps_v0(self, sync_id:int, n_records:int, n_lines:int, index_size:int, zip_type:int, data_type:int, swap_id:int, remv_id:int, api_ver:int) -> bytes:
        '''
            > 1| sync_id [int]
                - current JDb sync ID

            > 2| n_records [int]
                - total valid keys

            > 3| n_lines [int]
                - total valid keys + invalid keys (deleted)

            > 4| index_size [int] (default=128)
                - total row size for each key in KEY file

            > 5| zip_type [int]
                no = [0] no compression for VAL
                gz = [1] gzip compression(9) for VAL
                bz = [2] bz2 compression(9) for VAL
                xz = [3] lzma compression for VAL
                zs = [4] zstandard compression(22) for VAL
                br = [5] brotli compression(6) for VAL
                z1 = [6] zstandard compression(6) for VAL
                z2 = [7] zstandard compression(11) for VAL
                lz = [8] lz4 compression(0) for VAL

            > 6| data_type [int]
                L+J = [1] KEY=split   : VAL=Json
                M+M = [2] KEY=Marshal : VAL=Marshal
                J+J = [3] KEY=Json    : VAL=Json
                J+M = [4] KEY=Json    : VAL=Marshal
                J+P = [5] KEY=Json    : VAL=Pickle
                S+S = [6] KEY=msgpack : VAL=msgpack
                J+S = [7] KEY=Json    : VAL=msgpack
                S+M = [8] KEY=msgpack : VAL=Marshal
                S+J = [9] KEY=msgpack : VAL=Json
                S+P = [10]KEY=msgpack : VAL=Pickle

            > 7| swap_id [int]
                - +1 when swapping key to differnt row

            > 8| remv_id [int]
                - +1 when deleting key

        '''
        return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver))

    def loads_v0(self, header:bytes) -> Tuple[int,int,int,int,int,int,int,int,int]:
        if header[0] == 91: # '['
            info = _json_loads(header)
        else:
            # deprecated
            info = [int(v) for v in header.decode('utf8').split(',')]

        nn = len(info)
        if nn >= 9:
            sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver = info[:9]

        elif nn >= 8:
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

    def dumps_v1(self, sync_id:int, n_records:int, n_lines:int, index_size:int, zip_type:int, data_type:int, swap_id:int, remv_id:int, api_ver:int) -> bytes:
        '''
            > 1| sync_id [int]
                - current JDb sync ID

            > 2| n_records [int]
                - total valid keys

            > 3| n_lines [int]
                - total valid keys + invalid keys (deleted)

            > 4| index_size [int] (default=128)
                - total row size for each key in KEY file

            > 5| zip_type [int]
                no = [0] no compression for VAL
                gz = [1] gzip compression(9) for VAL
                bz = [2] bz2 compression(9) for VAL
                xz = [3] lzma compression for VAL
                zs = [4] zstandard compression(22) for VAL
                br = [5] brotli compression(6) for VAL
                z1 = [6] zstandard compression(6) for VAL
                z2 = [7] zstandard compression(11) for VAL
                lz = [8] lz4 compression(0) for VAL

            > 6| data_type [int]
                L+J = [1] replaced by J+J
                M+M = [2] KEY=Marshal : VAL=Marshal
                J+J = [3] KEY=Json    : VAL=Json
                J+M = [4] KEY=Json    : VAL=Marshal
                J+P = [5] KEY=Json    : VAL=Pickle
                S+S = [6] KEY=msgpack : VAL=msgpack
                J+S = [7] KEY=Json    : VAL=msgpack
                S+M = [8] KEY=msgpack : VAL=Marshal
                S+J = [9] KEY=msgpack : VAL=Json
                S+P = [10]KEY=msgpack : VAL=Pickle

            > 7| swap_id [int]
                - +1 when swapping key to differnt row

            > 8| remv_id [int]
                - +1 when deleting key

            > 9| api_ver [int]
                - JIo API version (default=0)

        '''
        return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver))

    def loads_v1(self, header:bytes) -> Tuple[int,int,int,int,int,int,int,int,int]:
        try:
            return _json_loads(header)

        except (ValueError, JSONDecodeError):
            try:
                return self.loads_v0(header)
            except (ValueError, JSONDecodeError) as e:
                raise ValueError from e

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoKEY(metaclass=ABCMeta): # pragma: no cover
    @abstractmethod
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes: ...
    @abstractmethod
    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]: ...
    @abstractmethod
    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes: ...
    @abstractmethod
    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]: ...

class JIoKEY_J(JIoKEY):
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        return _json_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days))

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        args = _json_loads(data)
        if len(args) != 6:
            args.append(0)

        key, file_id, offset, row_size, ver, days = args[:6]
        val_size = row_size >> 32
        row_size &= 0X_FFFF_FFFF
        return key, file_id, offset, row_size, val_size, ver, days

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        return _json_dumps((key, file_id, offset, row_size, val_size, ver, days))

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        return _json_loads(data)

class JIoKEY_S(JIoKEY):
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        info_b = _msg_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days)) or b''
        info_len = len(info_b)
        return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        prefix0, prefix1, prefix2, info0 = data[:4]
        if prefix0 != 0xcd or info0 != 0x96:
            raise ValueError

        info_len = (prefix1 << 8)| prefix2
        end_idx = info_len + 3
        key, file_id, offset, row_size, ver, days = _msg_loads(data[3:end_idx])
        return key, file_id, offset, row_size & 0X_FFFF_FFFF, row_size >> 32, ver, days

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        info_b = _msg_dumps((key, file_id, offset, row_size, val_size, ver, days)) or b''
        info_len = len(info_b)
        return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        prefix0, prefix1, prefix2, info0 = data[:4]
        if prefix0 != 0xcd or info0 != 0x97:
            raise ValueError

        info_len = (prefix1 << 8)| prefix2
        end_idx = info_len + 3
        return _msg_loads(data[3:end_idx])

class JIoKEY_M(JIoKEY):
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        return marshal_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days)) # tuple smaller than list

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        args = marshal_loads(data)
        if len(args) != 6:
            args.append(0)

        key, file_id, offset, row_size, ver, days = args[:6]
        val_size = row_size >> 32
        row_size &= 0X_FFFF_FFFF
        return key, file_id, offset, row_size, val_size, ver, days

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        return marshal_dumps((key, file_id, offset, row_size, val_size, ver, days)) # tuple smaller than list

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        return marshal_loads(data)

class JIoKEY_L(JIoKEY):
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        data = f'{key},{file_id},{offset},{row_size | (val_size << 32)}|{ver}|{days}'
        return data.encode('utf8')

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
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
        elif n_extra > 1:
            row_size = int(extra[0])
            ver = int(extra[1])
            days = 0
        else:
            row_size = int(extra[0])
            ver = 0
            days = 0

        return key, file_id, offset, row_size & 0X_FFFF_FFFF, row_size >> 32, ver, days

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int) -> bytes:
        data = f'{key},{file_id},{offset},{row_size},{val_size},{ver},{days}'
        return data.encode('utf8')

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int]:
        data_s = data.decode('utf8').rstrip()
        fields = data_s.split(',')
        n_fields = len(fields)
        key = ','.join(fields[:-6]) if n_fields > 7 else fields[0]
        file_id, offset, row_size, val_size, ver, days = (int(field) for field in fields[-6:])
        return key, file_id, offset, row_size, val_size, ver, days

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoVAL(metaclass=ABCMeta): # pragma: no cover
    @abstractmethod
    def dumps(self, data:Any) -> bytes: ...
    @abstractmethod
    def loads(self, data:bytes) -> Any: ...

class JIoVAL_J(JIoVAL):
    def dumps(self, data:Any) -> bytes:
        return _json_dumps(data, default=_json_default)

    def loads(self, data:bytes) -> Any:
        try:
            val = json_loads(data)
            if isinstance(val, str) and val[:4] == '\0\1\0\1':
                try:
                    _bytes = bytes.fromhex(val[4:])
                    if reduce(lambda x,y: (x+y) & 0xff, _bytes) == 0:
                        return _bytes[:-1]

                except ValueError:
                    return val

            return val

        except Exception as e:
            raise ValueError from e

class JIoVAL_S(JIoVAL):
    def dumps(self, data:Any) -> bytes:
        return _msg_dumps(data, default=_msg_encode) or b''

    def loads(self, data:bytes) -> Any:
        for _ in range(9):
            try:
                return _msg_loads(data, ext_hook=_msg_decode, strict_map_key=False)

            except (ValueError, EOFError):
                data = data + b'\xc1'

        raise ValueError

class JIoVAL_M(JIoVAL):
    def dumps(self, data:Any) -> bytes:
        return marshal_dumps(data)

    def loads(self, data:bytes) -> Any:
        for _ in range(9):
            try:
                return marshal_loads(data)

            except (ValueError, EOFError):
                data = data + b'\n'

        raise ValueError

class JIoVAL_P(JIoVAL):
    def dumps(self, data:Any) -> bytes:
        return pickle_dumps(data)

    def loads(self, data:bytes) -> Any:
        for _ in range(9):
            try:
                return pickle_loads(data)

            except (ValueError, EOFError, PicklingError):
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
g_HEAD = JIoHEAD()

class JIo:
    # reduce memory usage --> __dict__, but child class cannot have member
    __slots__ = {'days', 'sync_id', 'swap_id', 'remv_id', 'min_days',\
            '_sync_id', '_swap_id', '_remv_id', '_n_records',\
            '_n_lines', 'file_size', 'n_records', 'n_lines', 'groups',\
            '_data_type', '_zip_type', '_key_limit', 'index_size',\
            'max_file_size', 'reserved_rate', 'api_ver', 'file_table',\
            'files_obj', 'key_table', 'window_size', 'min_value_size',\
            'row_bytes', 'pad_byte', 'pad0_byte',\
            'KEY_dumps', 'KEY_loads', 'VAL_dumps', 'VAL_loads',\
            'HEAD_dumps', 'HEAD_loads','VAL_zip', 'VAL_unzip', 'VAL_unzip0'}

    @staticmethod
    def z_zip_type_str(zip_type:int) -> str:
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
        if data_type == DEF_TYPE: return 'J+J'
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

        raise ValueError(f'unknown data type {data_type}')

    @staticmethod
    def z_key_limit_str(key_limit:int) -> str:
        if key_limit == 0:      return 'no'
        if key_limit == -0x100: return 'bt'
        if key_limit > 0:       return f'<{key_limit+1}'
        return f'l{-key_limit-1}'

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

        if not isinstance(files_obj, JFilesBase):
            raise TypeError

        if index_size is None or index_size == 0:
            index_size = DEF_INDEX_SIZE if isinstance(files_obj, JDiskFiles) else MIN_INDEX_SIZE

        if reserved_rate is None:
            reserved_rate = DEF_RATIO

        if max_file_size is None or max_file_size == 0:
            max_file_size = DEF_FILE_SIZE

        if min_value_size is None or min_value_size == 0:
            min_value_size = DEF_VALUE_SIZE # key file allow to store below 15 bytes

        if key_limit is None:
            key_limit = DEF_KEY_LIMIT

        if data_type is None:
            data_type = DEF_TYPE

        if zip_type is None:
            zip_type = DEF_ZIP

        if api_ver is None:
            api_ver = API_LATEST

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
                                LiteKeyTable((-self._key_limit-1) | 0x1000)

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
        #pass;0;assert API_LATEST >= self.api_ver >= API_V0
        #pass;0;assert self.VAL_zip is not None
        #pass;0;assert self.VAL_unzip is not None
        #pass;0;assert self.VAL_unzip0 is not None
        #pass;0;assert self.VAL_dumps is not None
        #pass;0;assert self.VAL_loads is not None
        #pass;0;assert self.KEY_dumps is not None
        #pass;0;assert self.KEY_loads is not None
        #pass;0;assert self.HEAD_dumps is not None
        #pass;0;assert self.HEAD_loads is not None
        #pass;0;assert self.load_keys is not None

    def __repr__(self) -> str:
        return f'<{type(self).__name__}[v{self.api_ver}|{self.data_type_str}|{self.zip_type_str}|{self.key_limit_str}|{self.index_size}|{self.n_records}+{self.n_lines-self.n_records}|k:{self.file_size:,}|s:{self.sync_id}/{self.swap_id}/{self.remv_id}] at {hex(id(self))}>'

    def init_APIs(self, api_ver:Optional[int], reset:bool=False):
        files_obj = self.files_obj
        if self.min_days < 0:
            self.min_days = self.conv_days(files_obj.KEY_date())

        fp = None
        data_type = self._data_type
        zip_type = self._zip_type
        try:
            fp = files_obj.KEY_open('rb')
            header = fp.read(HEADER_SIZE)
            if len(header) == HEADER_SIZE:
                if header[0] == 91: # = '['
                    info = json_loads(header)
                else:
                    # deprecated
                    info = [int(v) for v in header.decode('utf8').split(',')]
                nn = len(info)
                if nn >= 9:
                    api_ver = info[8]
                    if data_type == DEF_TYPE:
                        data_type = info[5]

                    if zip_type == DEF_ZIP:
                        zip_type = info[4]
                elif nn >= 6:
                    api_ver = API_V0
                    if data_type == DEF_TYPE:
                        data_type = info[5]

                    if zip_type == DEF_ZIP:
                        zip_type = info[4]
                else:
                    api_ver = API_V0

        except Exception as e:
            print(e)

        finally:
            if fp is not None:
                fp.close()

        self.change_APIs(api_ver, data_type, zip_type, reset=reset)

    @property
    def zip_type_str(self) -> str:
        return self.z_zip_type_str(self._zip_type)

    @property
    def zip_type(self) -> int:
        return self._zip_type

    @zip_type.setter
    def zip_type(self, value:Union[int,str]):
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

        if ZIP_lut[value] is None:
            raise ValueError(f'cannot use this zip type, please pip install. {value}')

        self._zip_type = value

    @property
    def data_type_str(self) -> str:
        return self.z_data_type_str(self._data_type)

    @property
    def data_type(self) -> int:
        return self._data_type

    @data_type.setter
    def data_type(self, value:Union[int,str]):
        if isinstance(value, str):
            value = value.upper()
            if not value:
                value = J_J_TYPE
            else:
                if value.find('(') > 0 and value[-1] == ')':
                    value, zip_type = value.split('(')
                    self.zip_type = zip_type[:-1]

                if value in {'L+J', 'L:J'}:
                    value = L_J_TYPE
                elif value in {'M+M', 'M:M'}:
                    value = M_M_TYPE
                elif value in {'J+J', 'J:J'}:
                    value = J_J_TYPE
                elif value in {'J+M', 'J:M'}:
                    value = J_M_TYPE
                elif value in {'J+P', 'J:P'}:
                    value = J_P_TYPE
                elif value in {'S+S', 'S:S'}:
                    value = S_S_TYPE
                elif value in {'J+S', 'J:S'}:
                    value = J_S_TYPE
                elif value in {'S+M', 'S:M'}:
                    value = S_M_TYPE
                elif value in {'S+J', 'S:J'}:
                    value = S_J_TYPE
                elif value in {'S+P', 'S:P'}:
                    value = S_P_TYPE
                else:
                    raise ValueError(f'invalid data string {value}')

        if not isinstance(value, int):
            raise TypeError(f'invalid data type {value}')

        if not LAST_DATA_TYPE >= value >= 0:
            raise ValueError(f'invalid data type {value}')

        self._data_type = value

    @property
    def key_limit(self) -> int:
        return self._key_limit

    @key_limit.setter
    def key_limit(self, value:Union[int,str]):
        if isinstance(value, str):
            value = value.lower()
            if not value or value in {'no', '-', '--'}:
                value = 0
            elif value.startswith('l'):
                value = -(int(value[1:]) + 1)
            elif value in {'tr', 'bt', 'btree', 'tree'}:
                value = -0x100
            elif value.startswith('<='):
                value = max(1, int(value[2:]))
            elif value.startswith('<'):
                value = max(1, int(value[1:])-1)
            else:
                raise ValueError(f'invalid key limit string {value}')

        if not isinstance(value, int):
            raise TypeError(f'invalid key limit type {value}')

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
                    self.key_table = LiteKeyTable(_mode)
                    self._n_records = self._n_lines = self.file_size = 0

            elif value > 0:
                if self._key_limit <= 0:
                    self.key_table.clear()
                    self.key_table = PartialKeyTable(self)
                    self._n_records = self._n_lines = self.file_size = 0

        self._key_limit = value

    @property
    def key_limit_str(self) -> str:
        return self.z_key_limit_str(self._key_limit)

    def change_APIs(self, version:Optional[int]=None, data_type:int=DEF_TYPE, zip_type:int=DEF_ZIP, reset:bool=False):
        if reset:
            if self.index_size is None:
                self.index_size = DEF_INDEX_SIZE if isinstance(self.files_obj, JDiskFiles) else MIN_INDEX_SIZE

            if self.reserved_rate is None:
                self.reserved_rate = DEF_RATIO

            if self.max_file_size is None:
                self.max_file_size = DEF_FILE_SIZE

            if self.min_value_size is None:
                self.min_value_size = DEF_VALUE_SIZE

            self.file_table.clear()
            self.key_table.clear()
            self.groups.clear()
            self._swap_id = self._remv_id = -1
            self._sync_id = self._n_records = self._n_lines = self.file_size = self.n_records = self.n_lines = 0
            self.update_days()

        if version is None:
            version = API_LATEST

        if data_type == DEF_TYPE:
            data_type = J_J_TYPE

        if zip_type == DEF_ZIP:
            zip_type = NO_ZIP

        if not isinstance(data_type, int):
            raise TypeError
        if not isinstance(zip_type, int):
            raise TypeError
        if not isinstance(version, int):
            raise TypeError

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
            else:
                raise ValueError(f'invalid data type {self.api_ver}->{version} type:{data_type}')

        else:
            raise ValueError(f'invalid version {self.api_ver}->{version} type:{data_type}')

    def sorted_key_table_items(self, copy:bool=False, reverse:bool=False) -> Generator[str,int]:
        if self._key_limit > 0 or copy:
            fp = None
            try:
                files_obj = self.files_obj.copy()
                read_key = self.read_key
                fp = files_obj.KEY_open('rb')
                if reverse:
                    for row_id in range(self.n_records-1, -1, -1):
                        _key, _f, _o, _r, _v, _s, _d = read_key(fp, row_id)
                        yield _key, row_id
                else:
                    fp.seek(HEADER_SIZE)
                    for row_id in range(self.n_records):
                        _key, _f, _o, _r, _v, _s, _d = read_key(fp, row_id, seek=False)
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

            if lut:
                for row in sorted(lut, reverse=True):
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

            if lut:
                for row in sorted(lut):
                    yield lut.pop(row, ''), row

    def zip(self, data:bytes, zip_type:Optional[int]=None) -> bytes:
        zip_type_i = self._zip_type if zip_type is None else zip_type
        if zip_type_i == NO_ZIP:
            return data
        try:
            return self.VAL_zip(data)

        except Exception as e:
            print(Style(f'!!!!!!!!!!! [{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!zip(bytes[{len(data)}]={data[-512:]}, zip_type={zip_type_i})\nexception:{e}', red=1))
            raise ValueError from e

    def unzip(self, data:bytes, zip_type:Optional[int]=None) -> bytes:
        zip_type_i = self._zip_type if zip_type is None else zip_type
        try:
            try:
                if zip_type_i < 0:
                    zip_type_i = -zip_type_i-1
                    return data if zip_type_i == NO_ZIP else self.VAL_unzip0(data)

                return self.VAL_unzip(self.pad0_byte, data)

            except (GZ_Error, BZ_Error, XZ_Error, ZS_Error, BR_Error, LZ_Error) as e:
                pad = self.pad_byte
                data = data.rstrip(pad) + pad
                for ii in range(8):
                    try:
                        print(Style(f'!!!!!!!!!!! [{ii}|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!unzip(bytes[{len(data)}]={data[-512:]}, zip_type={zip_type})', yellow=1))
                        return self.VAL_unzip0(data)

                    except (GZ_Error, BZ_Error, XZ_Error, ZS_Error, BR_Error, LZ_Error):
                        data += pad

                raise ValueError from e

        except Exception as e:
            print(Style(f'!!!!!!!!!!! [{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!unzip(bytes[{len(data)}]={data[-512:]}, zip_type={zip_type_i})\nexception:{e}', red=1))
            raise ValueError from e

    def seek(self, fp:IO, row_id:int):
        if row_id < 0:
            row_id = self.n_lines + row_id

        return fp.seek(HEADER_SIZE + row_id * self.index_size)

    def write_key(self, fp:IO, row_id:int, key:str, file_id:int, offset:int, row_size:int, val_size:int=0, ver:Optional[int]=None, days:int=-1) -> int:
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

        if pad_size > 0:
            return fp.write(data + b' ' * pad_size + b'\n')

        return fp.write(data + b'\n')

    def read_key(self, fp:IO, row_id:int, seek:bool=True) -> Tuple[str, int, int, int, int, int, int]:
        index_size = self.index_size
        if seek:
            pos = HEADER_SIZE + row_id * index_size
            if fp.tell() != pos:
                fp.seek(pos)

        data = fp.read(index_size)
        return self.KEY_loads(data)

    def conv_days(self, timestamp:Union[int,float,datetime,dt_date]) -> int:
        if isinstance(timestamp, datetime):
            timestamp = timestamp.date()

        if isinstance(timestamp, dt_date):
            if timestamp < THE_1ST_DATE:
                return 0

            return (timestamp - THE_1ST_DATE).days

        return NUM_1970_DAYS + max(0, int(timestamp) - THE_1ST_SEC) // DAY_SEC

    def conv_date(self, days:int) -> Tuple[dt_date, dt_date]:
        old_days = days & OLD_DAY_MASK
        new_days = (days & NEW_DAY_MASK) >> NEW_DAY_SHIFT

        if old_days < NUM_1970_DAYS and old_days+new_days < NUM_1996_DAYS: # NOTES: remove after API v3
            old_days += NUM_2000_DAYS
            old_date = THE_1ST_DATE + timedelta(days=old_days)
            if old_date > dt_date.today():
                old_date -= timedelta(days=NUM_2000_DAYS)
        else:
            old_date = THE_1ST_DATE + timedelta(days=old_days)

        new_date = old_date + timedelta(days=new_days)
        return old_date, new_date

    def update_days(self) -> int:
        timestamp = int(time())
        self.days = NUM_1970_DAYS + max(0, timestamp - THE_1ST_SEC) // DAY_SEC
        return self.days

    def is_updated(self) -> bool:
        if self.file_size <= 0:
            return False

        return self.sync_id == self._sync_id

    def reset(self, **kwargs):
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
        self.update_days()
        self.row_bytes = self.index_size - self.min_value_size * (1 + self.reserved_rate)
        self.window_size = max(1, int(KEY_FILE_BUF_SIZE / self.index_size))

    def write_header(self, fp:IO, seek:bool=True, truncate:bool=False) -> int:
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
        if seek: fp.seek(0)
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

    def read_header(self, fp:IO, seek:bool=True) -> JIo:
        if seek: fp.seek(0)
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
            if api_ver != self.api_ver:
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

    def unpad(self, data:bytes) -> bytes:
        pad_byte = self.pad_byte
        if pad_byte == b'\n' or pad_byte == b'\xc1':
            return data.rstrip(pad_byte)

        return data.rstrip(pad_byte) + pad_byte

    def read_bytes(self, fp:IO, pos:int, row_size:int, val_size:int) -> bytes:
        fp.seek(pos)
        return fp.read(val_size if val_size > 0 else row_size)

    def read_value(self, fp:IO, pos:int, row_size:int, val_size:int) -> Any:
        fp.seek(pos)
        if val_size > 0:
            val_bytes = fp.read(val_size)
            zip_type = -(self.zip_type+1)
        else:
            val_bytes = fp.read(row_size)
            zip_type = self.zip_type

        if not val_bytes:
            return None

        return self.loads_with_unzip(val_bytes, zip_type=zip_type)

    def dumps_with_zip(self, data:Any, zip_type:Optional[int]=None) -> bytes:
        try:
            val_bytes = self.VAL_dumps(data)
            return self.zip(val_bytes, zip_type=zip_type)

        except Exception as e:
            print(Style(f'!!!!!!!!!!! [???|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!dumps_with_zip(data={type(data)}, zip_type={zip_type})\nexception:{e}', red=1))
            raise ValueError from e

    def loads_with_unzip(self, val_bytes:bytes, zip_type:Optional[int]=None) -> Any:
        try:
            unzip_bytes = self.unzip(val_bytes, zip_type=zip_type)
            return self.VAL_loads(unzip_bytes)

        except Exception as e:
            print(Style(f'!!!!!!!!!!! [???|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!loads_with_unzip(val_bytes[{len(val_bytes)}]={val_bytes[-512:]}, zip_type={zip_type})\nexception:{e}', red=1))
            raise ValueError from e

    def load_keys(self, fp:IO, force:bool=False):
        n_records       = self.n_records
        n_lines         = self.n_lines
        prev_n_records  = self._n_records
        prev_n_lines    = self._n_lines
        index_size      = self.index_size
        key_limit       = self._key_limit
        file_table      = self.file_table
        key_table       = self.key_table
        swap_id         = self.swap_id
        remv_id         = self.remv_id
        sync_id         = self.sync_id

        rec_diff  = n_records - prev_n_records          # new/del records
        line_diff = n_lines - prev_n_lines              # new rows
        self.file_size = records = lines = 0
        self.update_days()

        if force or n_lines == 0 or prev_n_lines == 0 or line_diff < 0:
            if key_table: key_table.clear()
            if file_table: file_table.clear()

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

            # [A] no swapping
            if swap_diff == 0:
                # swap_diff == rec_diff == remv_diff == 0
                if rec_diff == remv_diff == 0:
                    # swap_diff == rec_diff == remv_diff == line_diff == 0
                    if line_diff == 0:
                        if n_records <= 0 and key_table:
                            key_table.clear()

                        self._n_lines   = n_lines
                        self._n_records = n_records
                        self._sync_id   = sync_id
                        self._swap_id   = swap_id
                        self._remv_id   = remv_id
                        self.file_size  = fp.seek(0, 2)

                    # swap_diff == rec_diff == remv_diff == 0 and line_diff > 0
                    else:
                        if n_records <= 0 and key_table:
                            key_table.clear()

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

                if n_records <= 0 or records == 0:
                    if key_table:
                        key_table.clear()

                elif key_limit > 0:
                    key_table.cache_cleanup()

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

                read_key = self.read_key
                for row in range(records, lines):
                    rec = read_key(fp, row)
                    key,file_id,offset,row_size,_val_size = rec[:5]
                    if row < n_records:
                        key_table[key] = row
                        if row_size > 0:
                            file_table[file_id] = max(file_table[file_id], offset + row_size)
                        elif row_size == 0 and file_id == 0x10:
                            self.groups.setdefault(key, None)

                    elif row_size > 0:
                        file_table[file_id] = max(file_table[file_id], offset + row_size)

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
                    if key_limit > 0:
                        key_table.cache_cleanup()
                    else:
                        read_key = self.read_key
                        for row in range(n_records, min(n_lines, n_records+remv_diff)):
                            del_rec = read_key(fp, row)
                            old_row = key_table.pop(del_rec[0], -1)
                            if n_records > old_row >= 0:
                                new_rec = read_key(fp, old_row)
                                key_table[new_rec[0]] = old_row

                    self._sync_id   = sync_id
                    self._swap_id   = swap_id
                    self._remv_id   = remv_id
                    self._n_records = n_records
                    self._n_lines   = n_lines
                    self.file_size  = fp.seek(0, 2)
                    return

                # swap_diff > 0 and key_limit > 0
                if key_limit > 0:
                    key_table.clear()

                # swap_diff > 0 and sync_diff == remv_diff == line_diff (rec_diff == 0)
                elif sync_diff == remv_diff == line_diff:
                    read_key = self.read_key
                    chg_keys = {}
                    chk_rows = []
                    for row in range(n_records, n_lines):
                        del_rec = read_key(fp, row)
                        old_row = key_table[del_rec[0]]
                        if old_row < 0 or old_row >= n_records:
                            continue

                        new_rec = read_key(fp, old_row)
                        new_key,file_id,offset,row_size,_val_size = new_rec[:5]
                        if row_size > 0:
                            file_table[file_id] = max(file_table[file_id], offset + row_size)
                        elif row_size == 0 and file_id == 0x10:
                            self.groups.setdefault(new_key, None)

                        chg_keys[new_key] = old_row
                        old_row = key_table[new_key]
                        if n_records > old_row >= 0:
                            chk_rows.append(old_row)

                    for key,row in chg_keys.items():
                        key_table[key] = row

                    for row in chk_rows:
                        chg_rec = read_key(fp, row)
                        chg_key,file_id,offset,row_size,_val_size = chg_rec[:5]
                        key_table[chg_key] = row
                        if row_size > 0:
                            file_table[file_id] = max(file_table[file_id], offset + row_size)
                        elif row_size == 0 and file_id == 0x10:
                            self.groups.setdefault(chg_key, None)

                    self._sync_id   = sync_id
                    self._swap_id   = swap_id
                    self._remv_id   = remv_id
                    self._n_records = n_records
                    self._n_lines   = n_lines
                    self.file_size  = fp.seek(0, 2)
                    return

                # swap_diff == sync_diff == 1 and (sync_diff != remv_diff or sync_diff != line_diff)
                elif sync_diff == 1:
                    read_key = self.read_key
                    t_record = n_records-1
                    chg_rec1 = read_key(fp, t_record)
                    key1,file_id1,offset1,row_size1,_val_size1 = chg_rec1[:5]
                    chg_row1 = key_table[key1]
                    if n_records > chg_row1 >= 0:
                        chg_rec2 = read_key(fp, chg_row1)
                        key2,file_id2,offset2,row_size2,_val_size2 = chg_rec2[:5]
                        chg_row2 = key_table[key2]

                        if n_records > chg_row2 >= 0:
                            key_table[key1] = t_record
                            key_table[key2] = chg_row1
                            if row_size1 > 0:
                                file_table[file_id1] = max(file_table[file_id1], offset1 + row_size1)
                            elif row_size1 == 0 and file_id1 == 0x10:
                                self.groups.setdefault(key1, None)

                            if row_size2 > 0:
                                file_table[file_id2] = max(file_table[file_id2], offset2 + row_size2)
                            elif row_size2 == 0 and file_id2 == 0x10:
                                self.groups.setdefault(key2, None)

                            self._sync_id   = sync_id
                            self._swap_id   = swap_id
                            self._remv_id   = remv_id
                            self._n_records = n_records
                            self._n_lines   = n_lines
                            self.file_size  = fp.seek(0, 2)
                            return

                # swap_diff > 0 and (sync_diff != remv_diff or sync_diff != line_diff)
                else:
                    if n_records == 0:
                        pass

                    elif rec_diff == 0:
                        pass

                    elif rec_diff > 0:
                        pass

                    else:
                        pass

                # reset
                if key_table:
                    key_table.clear()
                if file_table:
                    file_table.clear()

        if n_lines <= 0:
            self._sync_id   = sync_id
            self._swap_id   = swap_id
            self._remv_id   = remv_id
            self._n_records = self._n_lines = self.n_lines = self.n_records = 0
            self.file_size  = fp.seek(0, 2)
            return

        fp.seek(HEADER_SIZE + lines * self.index_size)
        # read key info line by line
        data_type_s = self.data_type_str
        KEY_loads = self.KEY_loads
        if data_type_s.startswith(('L', 'J')):
            for line in fp: # 1.29% faster than fp.readlines(block_size)
                if line[0] == 10:
                    if lines < n_lines or records < n_records:
                        print(Style(f'!!!!!!!!!!! [{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type}|{self.zip_type}] ERROR!load_keys(#{records}/{n_lines} fp:{fp} line:{line})'))
                    break

                try:
                    key, file_id, offset, row_size, _val_size, _ver, _days = KEY_loads(line)

                except Exception as e:
                    if lines < n_lines or records < n_records:
                        print(Style(f'!!!!!!!!!!! [DECODE|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!load_keys(#{records}/{n_lines} fp:{fp} line:{line})\nexception:{e}'))
                    break

                if lines < n_lines:
                    if records < n_records:
                        records += 1
                        key_table[key] = lines

                        if row_size > 0:
                            file_table[file_id] = max(file_table[file_id], offset + row_size)
                        elif row_size == 0 and file_id == 0x10:
                            self.groups.setdefault(key, None)

                    elif row_size > 0:
                        file_table[file_id] = max(file_table[file_id], offset + row_size)

                    lines += 1
                    if lines >= n_lines:
                        break

                else:
                    break
        else: # M, S
            while lines < n_lines:
                line = fp.read(index_size)
                if not line or len(line) != index_size:
                    break

                try:
                    key, file_id, offset, row_size, _val_size, _ver, _days = KEY_loads(line)

                except Exception as e:
                    if lines < n_lines or records < n_records:
                        print(Style(f'!!!!!!!!!!! [DECODE|{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] ERROR!load_keys(#{records}/{n_lines} fp:{fp} line:{line})\nexception:{e}'))
                    break

                if lines < n_lines:
                    if records < n_records:
                        records += 1
                        key_table[key] = lines

                        if row_size > 0:
                            file_table[file_id] = max(file_table[file_id], offset + row_size)
                        elif row_size == 0 and file_id == 0x10:
                            self.groups.setdefault(key, None)

                    elif row_size > 0:
                        file_table[file_id] = max(file_table[file_id], offset + row_size)

                    lines += 1

        if lines <= 0:
            n_records = n_lines = 0
            if key_table: key_table.clear()
            if file_table: file_table.clear()
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

    def shift_keys(self, fp:IO, start:int, offset:int=1, size:int=1, block_size:Optional[int]=None):
        n_lines = self.n_lines
        index_size = self.index_size
        if block_size is None:
            block_size = self.window_size

        n_blocks = size // block_size
        if (size % block_size) > 0:
            n_blocks += 1

        src_row = min(start+size, n_lines)
        for _ in range(n_blocks):
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
                row_info = src_read_key(fp, src_row_id, seek=False)
                if row_info:
                    table[src_row_id] = row_info

                src_row_id += 1

        print(Style(f'!!! [{hex(id(self))[-5:-1]}|{self.sync_id%10000}|{self.key_limit_str}|{self.files_obj.get_KEY()}|{self.data_type_str}({self.zip_type_str})] WAIT until KEY file resize is DONE!!! size:{self.index_size}->{index_size} buffer:{len(table)}/{n_lines}', cyan=1, bold=1, underscore=1))
        dst_write_key = dst_io.write_key
        while dst_row_id < n_lines:
            if src_row_id < n_lines:
                row_info = src_read_key(fp, src_row_id, seek=True)
                if row_info:
                    table[src_row_id] = row_info

                src_row_id += 1

            key_info = table.pop(dst_row_id, None)
            if not key_info:
                break

            if min_ver:
                _key, _file_id, _offset, _row_size, _val_size, _ver, _days = key_info
                _ver = max(1, _ver - sync_id + n_lines)
                if dst_row_id >= n_records:
                    _key = ''
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
