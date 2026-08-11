# pylint: disable=ungrouped-imports,too-many-lines,chained-comparison,too-few-public-methods, unused-import
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from functools import reduce
from typing import Optional, Any, Dict, Set, List, Tuple, Callable
from pickle import loads as pickle_loads, dumps as pickle_dumps, PicklingError, UnpicklingError # nosec B403
from marshal import loads as marshal_loads, dumps as marshal_dumps # nosec B403

try:
    import yaml

    def frozenset_representer(dumper, data):
        return dumper.represent_set(set(data))

    yaml.SafeDumper.add_representer(frozenset, frozenset_representer)
    # bytes is natively dumped as !!binary by SafeRepresenter; register the same
    # representer for bytearray so dumps_with_zip() fully supports bytearray payloads.
    yaml.SafeDumper.add_representer(bytearray, yaml.SafeDumper.represent_binary)

    yaml_dumps = yaml.safe_dump
    yaml_loads = yaml.safe_load
    YAMLError = yaml.YAMLError

except ImportError:
    yaml_dumps = yaml_loads = None
    YAMLError = ValueError

def _json_default(obj:Any):
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

    def _json_dumps(obj:Any, default:Optional[Callable[[Any], Any]]=None) -> bytes:
        """Internal JSON string dump utility function acting as alternative to orjson.

        Args:
            obj (Any): Target object structure payload to serialize.
            default (Optional[Callable[[Any], Any]], optional): Fallback serialization routing encoder. Defaults to None.

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

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
try:
    from msgpack import packb as _msg_dumps, unpackb as _msg_loads, Unpacker, ExtType

    msg_dumps = lambda obj : _msg_dumps(obj, default=_msg_encode)
    msg_loads = lambda _bytes : _msg_loads(_bytes, ext_hook=_msg_decode, strict_map_key=False)

except (ModuleNotFoundError, ImportError):
    # pylint: disable=unused-argument
    from struct import Struct, error as StructError
    from sys import intern
    from collections import namedtuple
    from .jdb_file import JBytesIO

    EXT_SET: int = 123
    EXT_FROZENSET: int = 124
    B_pack = Struct("B").pack
    b_pack = Struct('b').pack
    BB_pack = Struct("BB").pack
    Bb_pack = Struct(">Bb").pack
    BH_pack = Struct(">BH").pack
    Bh_pack = Struct(">Bh").pack
    BI_pack = Struct(">BI").pack
    Bi_pack = Struct(">Bi").pack
    BQ_pack = Struct(">BQ").pack
    Bq_pack = Struct(">Bq").pack
    Bd_pack = Struct(">Bd").pack

    _u16 = Struct(">H").unpack_from
    _u32 = Struct(">I").unpack_from
    _u64 = Struct(">Q").unpack_from
    _i8 = Struct(">b").unpack_from
    _i16 = Struct(">h").unpack_from
    _i32 = Struct(">i").unpack_from
    _i64 = Struct(">q").unpack_from
    _f32 = Struct(">f").unpack_from
    _f64 = Struct(">d").unpack_from

    def _msg_pack(obj, bytesio:JBytesIO, nest_limit:int=1024) -> bytes:
        bytesio_write = bytesio.write
        idx = bytesio.idx
        ext_code = 0
        while True:
            if nest_limit < 0:
                raise ValueError("recursion limit exceeded")

            if obj is None:
                return bytesio_write(b"\xc0")

            if isinstance(obj, bool):
                return bytesio_write(b"\xc3" if obj else b"\xc2")

            if isinstance(obj, int):
                if 0 <= obj < 0x80:
                    return bytesio_write(B_pack(obj))
                if -0x20 <= obj < 0:
                    return bytesio_write(b_pack(obj))
                if 0x80 <= obj <= 0xFF:
                    return bytesio_write(BB_pack(0xCC, obj))
                if -0x80 <= obj < 0:
                    return bytesio_write(Bb_pack(0xD0, obj))
                if 0xFF < obj <= 0xFFFF:
                    return bytesio_write(BH_pack(0xCD, obj))
                if -0x8000 <= obj < -0x80:
                    return bytesio_write(Bh_pack(0xD1, obj))
                if 0xFFFF < obj <= 0xFFFFFFFF:
                    return bytesio_write(BI_pack(0xCE, obj))
                if -0x80000000 <= obj < -0x8000:
                    return bytesio_write(Bi_pack(0xD2, obj))
                if 0xFFFFFFFF < obj <= 0xFFFFFFFFFFFFFFFF:
                    return bytesio_write(BQ_pack(0xCF, obj))
                if -0x8000000000000000 <= obj < -0x80000000:
                    return bytesio_write(Bq_pack(0xD3, obj))

                raise ValueError("Integer value out of range")

            if isinstance(obj, (bytes, bytearray)):
                n = len(obj)
                if n >= 2**32:
                    raise ValueError(f"{type(obj).__name__} is too large")

                bytesio_write(BB_pack(0xC4, n) if n <= 0xFF else \
                                BH_pack(0xC5, n) if n <= 0xFFFF else \
                                BI_pack(0xC6, n))

                bytesio_write(obj)
                return bytesio.idx - idx

            if isinstance(obj, str):
                obj = obj.encode("utf-8", "strict")
                n = len(obj)
                if n >= 2**32:
                    raise ValueError("String is too large")

                idx = bytesio.idx
                bytesio_write(B_pack(0xA0 + n) if n <= 0x1F else \
                                BB_pack(0xD9, n) if n <= 0xFF else \
                                BH_pack(0xDA, n) if n <= 0xFFFF else \
                                BI_pack(0xDB, n))

                bytesio_write(obj)
                return bytesio.idx - idx

            if isinstance(obj, memoryview):
                n = obj.nbytes
                if n >= 2**32:
                    raise ValueError("Memoryview is too large")

                bytesio_write(BB_pack(0xC4, n) if n <= 0xFF else \
                                BH_pack(0xC5, n) if n <= 0xFFFF else \
                                BI_pack(0xC6, n))

                bytesio_write(obj)
                return bytesio.idx - idx

            if isinstance(obj, float):
                return bytesio_write(Bd_pack(0xCB, obj))

            if ext_code > 0 or isinstance(obj, (list, tuple)):
                n = len(obj)
                if n >= 2**32:
                    raise ValueError("Array is too large")

                bytesio_write(B_pack(0x90 + n) if n  <= 0xF else \
                                BH_pack(0xDC, n) if n <= 0xFFFF else \
                                BI_pack(0xDD, n))

                for val in obj:
                    _msg_pack(val, bytesio, nest_limit-1)

                if ext_code > 0:
                    L = bytesio.idx - idx
                    data = bytesio.buf[idx:idx+L]
                    bytesio.idx = idx
                    bytesio_write(BI_pack(0xC9, L) if L > 0xFFFF else \
                                    BH_pack(0xC8, L) if L > 0xFF else \
                                    b"\xd8" if L == 16 else \
                                    b"\xd7" if L == 8 else \
                                    b"\xd6" if L == 4 else \
                                    b"\xd5" if L == 2 else \
                                    b"\xd4" if L == 1 else BB_pack(0xC7, L))

                    bytesio_write(b_pack(ext_code))
                    bytesio_write(data)
                    ext_code = 0

                return bytesio.idx - idx

            if isinstance(obj, dict):
                n = len(obj)
                if n >= 2**32:
                    raise ValueError("Dict is too large")

                bytesio_write(B_pack(0x80 + n) if n <= 0x0F else \
                                BH_pack(0xDE, n) if n <= 0xFFFF else \
                                BI_pack(0xDF, n))

                for key,val in obj.items():
                    _msg_pack(key, bytesio, nest_limit-1)
                    _msg_pack(val, bytesio, nest_limit-1)

                return bytesio.idx - idx

            if isinstance(obj, set):
                ext_code = EXT_SET
                continue

            if isinstance(obj, frozenset):
                ext_code = EXT_FROZENSET
                continue

            raise TypeError(f"Cannot serialize {obj!r}")

    def _msg_dumps(obj:Any, default=None) -> bytearray:
        """Serialize ``obj`` to MessagePack bytes.

        ``set`` / ``frozenset`` are handled natively (ext codes 123 / 124),
        so ``default`` is accepted for call-site compatibility and ignored.

        Args:
            obj (Any): The object to serialize.
            default (Any, optional): Accepted and ignored. Defaults to None.

        Returns:
            bytearray: The MessagePack-encoded buffer.
        """
        bytesio = JBytesIO(None)
        _msg_pack(obj, bytesio)
        return bytesio.buf

    msg_dumps = _msg_dumps

    def _msg_unpack(buf:bytearray, idx:int=0) -> Tuple[Any, int]:
        """Decode one MessagePack object from ``buf`` starting at byte ``idx``.

        Args:
            buf: A 1-byte-itemsize ``memoryview`` (or bytes-like) to read from.
            idx (int): Offset of the object's first byte.

        Returns:
            Tuple[Any, int]: The decoded object and the offset just past it.

        Raises:
            ValueError: On the never-used byte 0xC1 or any unknown header byte.
        """
        b = buf[idx]
        idx += 1

        # positive fixint 0x00-0x7f
        if b < 0x80:
            return b, idx
        # fixmap 0x80-0x8f / fixarray 0x90-0x9f / fixstr 0xa0-0xbf
        if b <= 0x8F:
            return _read_map(buf, idx, b & 0x0F)
        if b <= 0x9F:
            return _read_array(buf, idx, b & 0x0F)
        if b <= 0xBF:
            end = idx + (b & 0x1F)
            return str(bytes(buf[idx:end]), "utf-8"), end
        # negative fixint 0xe0-0xff
        if b >= 0xE0:
            return b - 0x100, idx

        # --- prefixed types 0xc0-0xdf --------------------------------------------
        if b == 0xC0:                       # nil
            return None, idx
        if b == 0xC2:                       # false
            return False, idx
        if b == 0xC3:                       # true
            return True, idx
        if b == 0xCC:                       # uint8
            return buf[idx], idx + 1
        if b == 0xCD:                       # uint16
            return _u16(buf, idx)[0], idx + 2
        if b == 0xCE:                       # uint32
            return _u32(buf, idx)[0], idx + 4
        if b == 0xCF:                       # uint64
            return _u64(buf, idx)[0], idx + 8
        if b == 0xD0:                       # int8
            return _i8(buf, idx)[0], idx + 1
        if b == 0xD1:                       # int16
            return _i16(buf, idx)[0], idx + 2
        if b == 0xD2:                       # int32
            return _i32(buf, idx)[0], idx + 4
        if b == 0xD3:                       # int64
            return _i64(buf, idx)[0], idx + 8
        if b == 0xCB:                       # float64 (the only float _msg_pack emits)
            return _f64(buf, idx)[0], idx + 8
        if b == 0xCA:                       # float32 (accepted for interop)
            return _f32(buf, idx)[0], idx + 4
        if b == 0xD9:                       # str8
            n = buf[idx]; idx += 1
            end = idx + n
            return str(bytes(buf[idx:end]), "utf-8"), end
        if b == 0xDA:                       # str16
            n = _u16(buf, idx)[0]; idx += 2
            end = idx + n
            return str(bytes(buf[idx:end]), "utf-8"), end
        if b == 0xDB:                       # str32
            n = _u32(buf, idx)[0]; idx += 4
            end = idx + n
            return str(bytes(buf[idx:end]), "utf-8"), end
        if b == 0xC4:                       # bin8
            n = buf[idx]; idx += 1
            end = idx + n
            return bytes(buf[idx:end]), end
        if b == 0xC5:                       # bin16
            n = _u16(buf, idx)[0]; idx += 2
            end = idx + n
            return bytes(buf[idx:end]), end
        if b == 0xC6:                       # bin32
            n = _u32(buf, idx)[0]; idx += 4
            end = idx + n
            return bytes(buf[idx:end]), end
        if b == 0xDC:                       # array16
            return _read_array(buf, idx + 2, _u16(buf, idx)[0])
        if b == 0xDD:                       # array32
            return _read_array(buf, idx + 4, _u32(buf, idx)[0])
        if b == 0xDE:                       # map16
            return _read_map(buf, idx + 2, _u16(buf, idx)[0])
        if b == 0xDF:                       # map32
            return _read_map(buf, idx + 4, _u32(buf, idx)[0])
        if b == 0xD4:                       # fixext1
            return _read_ext(buf, idx, 1)
        if b == 0xD5:                       # fixext2
            return _read_ext(buf, idx, 2)
        if b == 0xD6:                       # fixext4
            return _read_ext(buf, idx, 4)
        if b == 0xD7:                       # fixext8
            return _read_ext(buf, idx, 8)
        if b == 0xD8:                       # fixext16
            return _read_ext(buf, idx, 16)
        if b == 0xC7:                       # ext8
            return _read_ext(buf, idx + 1, buf[idx])
        if b == 0xC8:                       # ext16
            return _read_ext(buf, idx + 2, _u16(buf, idx)[0])
        if b == 0xC9:                       # ext32
            return _read_ext(buf, idx + 4, _u32(buf, idx)[0])

        # 0xC1 is msgpack's "never used" byte -> corrupt data / stray padding.
        raise ValueError(f"Unknown msgpack header byte: 0x{b:02x}")

    def _read_array(buf:bytearray, idx: int, n: int) -> Tuple[List[Any],int]:
        """Decode ``n`` consecutive elements into a list."""
        arr = [None] * n
        for i in range(n):
            arr[i], idx = _msg_unpack(buf, idx)
        return arr, idx

    def _read_map(buf:bytearray, idx: int, n: int) -> Tuple[Dict[Any,Any], int]:
        """Decode ``n`` key/value pairs into a dict (str keys are interned)."""
        out = {}
        for _ in range(n):
            key, idx = _msg_unpack(buf, idx)
            if isinstance(key, str):
                key = intern(key)
            out[key], idx = _msg_unpack(buf, idx)
        return out, idx

    def _read_ext(buf:bytearray, idx: int, size: int) -> Tuple[Set[Any], int]:
        """Decode an ext object; codes 123/124 become set/frozenset natively.

        The payload of a set/frozenset ext is itself one MessagePack array of
        the members, so it is decoded in place and wrapped -- no slicing needed.

        Args:
            buf: A 1-byte-itemsize ``memoryview`` (or bytes-like) to read from.
            idx (int): Offset of the ext type-code byte.
            size (int): Byte length of the ext payload (used to advance ``idx``).

        Returns:
            Tuple[Any, int]: The decoded set/frozenset and the offset just past
            the payload.

        Raises:
            ValueError: If the ext type code is not 123 or 124.
        """
        code = buf[idx]                     # ext type code (signed on the wire)
        if code > 0x7F:
            code -= 0x100

        idx += 1
        if code == EXT_SET or code == EXT_FROZENSET:
            members, _ = _msg_unpack(buf, idx)
            result = frozenset(members) if code == EXT_FROZENSET else set(members)
            return result, idx + size

        raise ValueError(f"Unsupported ext type code: {code}")

    def _msg_loads(data:bytearray, ext_hook:Any=None, strict_map_key:bool=False) -> Any:
        """Deserialize one MessagePack object from ``data`` (mirror of ``_msg_dumps``).

        ``set`` / ``frozenset`` ext types (codes 123 / 124) are restored natively,
        so no ext_hook is needed. Any bytes trailing the first decoded object are
        ignored, which tolerates reserved-row slack without the old pad-and-retry
        loop.

        Args:
            data: ``bytes`` / ``bytearray`` / ``memoryview`` holding one object.
            ext_hook (Any, optional): Accepted for call-site compatibility and
                ignored; ext codes 123 / 124 are decoded natively. Defaults to None.
            strict_map_key (bool, optional): Accepted for call-site compatibility
                and ignored; map keys are never restricted (jdb stores int keys).
                Defaults to ``False``.

        Returns:
            Any: The decoded Python object.

        Raises:
            ValueError: If ``data`` is empty, truncated, or not valid MessagePack.
        """
        if not data:
            raise ValueError("Unpack failed: empty input")

        own = not isinstance(data, memoryview)
        mv = memoryview(data) if own else data
        try:
            obj, _ = _msg_unpack(mv, 0)
            return obj

        except (IndexError, StructError) as e:
            raise ValueError("Unpack failed: incomplete or invalid input") from e

        finally:
            if own:
                mv.release() # let jdb keep mutating the source bytearray

    msg_loads = _msg_loads

    class Unpacker:
        """Streaming MessagePack unpacker built on :func:`_msg_unpack`.

        Load a whole buffer with :meth:`feed`, then iterate to obtain each
        top-level object in order; ``set`` / ``frozenset`` (ext 123 / 124) are
        decoded natively. Arrays decode to lists, str types to ``str``, bin
        types to ``bytes``, and map keys are never restricted.

        A single instance is reusable: each :meth:`feed` replaces the buffer,
        and iterating drains it. This is tailored to ``KeyTable``, which feeds
        one fully-formed group (a run of complete ``(key, row_id)`` records) at
        a time and drains it before feeding the next.

        Note:
            :meth:`feed` does **not** copy or accumulate. Each call replaces the
            buffer with a reference to ``data``; a partial object left at the end
            of one buffer is *not* carried into the next feed, and the caller
            must not mutate the fed object while iterating.
        """

        __slots__ = ("_buf", "_idx")

        def __init__(self) -> None:
            """Create an empty streaming unpacker."""
            self._buf = bytearray()
            self._idx = 0

        def feed(self, data:bytearray) -> None:
            """Set the buffer to ``data`` and rewind to its start.

            Replaces (does not append to) any current buffer. ``data`` is
            referenced, not copied, so the caller must not mutate it while
            iterating this unpacker.

            Args:
                data: ``bytes`` / ``bytearray`` / ``memoryview`` holding a run of
                    one or more complete MessagePack objects.
            """
            self._buf = data
            self._idx = 0

        def __iter__(self) -> Unpacker:
            return self

        def __next__(self) -> Any:
            """Decode and return the next object from the buffer.

            Returns:
                Any: The next decoded object.

            Raises:
                StopIteration: When the buffer is fully consumed, or an
                    incomplete object remains at its end.
            """
            idx = self._idx
            buf = self._buf
            if idx >= len(buf):
                raise StopIteration

            try:
                obj, self._idx = _msg_unpack(buf, idx)

            except (IndexError, StructError) as e: # pragma: no cover
                raise StopIteration from e

            return obj

        next = __next__

    class ExtType(namedtuple("ExtType", "code data")):
        """A MessagePack Ext type: a user ``code`` (0..127) plus raw ``data`` bytes."""
        __slots__ = ()

        def __new__(cls, code: int, data: bytes) -> ExtType:
            return super().__new__(cls, code, data)

def _msg_encode(obj:Any) -> ExtType:
    """Pack non-primitive objects into MsgPack ExtType objects.

    Args:
        obj (Any): The non-primitive input object (a ``set`` or ``frozenset``).

    Returns:
        ExtType: ``set`` -> ExtType code 123, ``frozenset`` -> ExtType code 124,
        each wrapping the msgpack-encoded list of members.

    Raises:
        TypeError: If the object type is not supported.
    """
    if isinstance(obj, set):
        return ExtType(123, _msg_dumps(list(obj)))

    if isinstance(obj, frozenset):
        return ExtType(124, _msg_dumps(list(obj)))

    raise TypeError

def _msg_decode(code:int, data:bytes):
    """Decode custom MsgPack extensions.

    Args:
        code (int): The extension type code (123 for ``set``, 124 for ``frozenset``).
        data (bytes): The raw binary payload associated with the extension.

    Returns:
        Any: The unpacked Python object (a ``set`` for code 123, a ``frozenset``
        for code 124).

    Raises:
        TypeError: If the extension type code is unregistered.
    """
    if code == 123:
        try:
            return set(_msg_loads(data))

        except ValueError: # pragma: no cover
            pass

    if code == 124:
        try:
            return frozenset(_msg_loads(data))

        except ValueError: # pragma: no cover
            pass

    raise TypeError(f'code={code} data={data}')

from .utils import JValueError, JKeyFlag, KEY_FLAG_MASK

FULL_DAY_MASK = 0xFFFF_FFFF_FFFF
KEY_FLAG_SHIFT = 48
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JIoHEAD:
    """Codec module for packing and unpacking the database layout header."""
    def dumps_v0(self, sync_id:int, n_records:int, n_lines:int, index_size:int, zip_type:int, data_type:int, swap_id:int, remv_id:int, api_ver:int, max_vfiles:int=-1) -> bytes:
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
            max_vfiles (int, optional): Stored as the 10th field. Older releases
                stop reading at ``api_ver``, so writing it stays backward compatible
                for anything that decodes the header as a variable-length int list.

        Returns:
            bytes: The header line bytes.
        """
        return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver, max_vfiles))

    def loads_v0(self, header:bytes) -> List[int]:
        """Parse a V0 header line back into its fields.

        Args:
            header (bytes): The raw header bytes.

        Returns:
            List[int]: ``[sync_id, n_records, n_lines, index_size, zip_type,
            data_type, swap_id, remv_id, api_ver, max_vfiles]`` -- always exactly 10
            entries. Headers shorter than that are widened with the historical
            defaults (``api_ver`` becomes ``API_V0``, ``max_vfiles`` becomes ``-1``);
            longer ones are truncated, so a future 11-field header still decodes here.
        """
        try:
            if header[0] == 91: # '['
                info = _json_loads(header)
            else: # pragma: no cover
                # deprecated
                info = [int(v) for v in header.decode('utf8').split(',')]

            nn = len(info)
            if nn >= 10:
                return info[:10]

            if nn >= 4: # pragma: no cover
                if nn >= 9:
                    return info + [-1]
                elif nn >= 8:
                    return info + [0, -1]
                elif nn == 7:
                    return info + [info[0] % 10, 0, -1]
                elif nn == 6:
                    return info + [info[0] % 10, info[0] % 10, 0, -1]
                elif nn == 5:
                    return info + [1, info[0] % 10, info[0] % 10, 0, -1]
                else:
                    return info + [0, 1, info[0] % 10, info[0] % 10, 0, -1]

            raise ValueError(f'cannot decode header (n={nn})')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise ValueError from e

    def dumps_v1(self, sync_id:int, n_records:int, n_lines:int, index_size:int, zip_type:int, data_type:int, swap_id:int, remv_id:int, api_ver:int, max_vfiles:int=-1) -> bytes:
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
            max_vfiles (int, optional): Stored as the 10th field. See the note in :meth:`dumps_v0`.

        Returns:
            bytes: The header line bytes.
        """
        try:
            return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver, max_vfiles))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v1(self, header:bytes) -> List[int]:
        """Parse a V1 header line back into its fields.

        Args:
            header (bytes): The raw header bytes.

        Returns:
            List[int]: ``[sync_id, n_records, n_lines, index_size, zip_type,
            data_type, swap_id, remv_id, api_ver, max_vfiles]`` -- always exactly 10
            entries. A 9-field header yields ``max_vfiles = -1``; anything else is
            delegated to :meth:`loads_v0`.
        """
        try:
            info = _json_loads(header)
            nn = len(info)
            if nn >= 10: # a V2 header opened by a V1-configured engine
                return info[:10]

            if nn >= 9: # pragma: no cover
                return info + [-1]

            raise ValueError(f'cannot decode header (n={nn})')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError): # pragma: no cover
            return self.loads_v0(header)

    def dumps_v2(self, sync_id:int, n_records:int, n_lines:int, index_size:int, zip_type:int, data_type:int, swap_id:int, remv_id:int, api_ver:int, max_vfiles:int=-1) -> bytes:
        """Serialize the database header (V2 layout) as a fixed-size JSON line.

        V2 is V1 plus a trailing ``max_vfiles`` field, so the header holds ten
        integers instead of nine.

        Args:
            sync_id (int): Write-session counter.
            n_records (int): Number of active records.
            n_lines (int): Total rows including dead/history rows.
            index_size (int): Byte size of one KEY index row.
            zip_type (int): Compression code (see :meth:`dumps_v1`).
            data_type (int): Serialization format code (see :meth:`dumps_v1`).
            swap_id (int): Compaction counter.
            remv_id (int): Deletion counter.
            api_ver (int): On-disk format version.
            max_vfiles (int, optional): One past the highest VAL file id in use
                (``max(file_id) + 1``). This is an upper bound on the id range, not
                a count: with sparse ids the two differ. ``-1`` means "unknown,
                probe the filesystem".

        Returns:
            bytes: The header line bytes.
        """
        try:
            return _json_dumps((sync_id, n_records, n_lines, index_size, zip_type, data_type, swap_id, remv_id, api_ver, max_vfiles))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise ValueError from e

    def loads_v2(self, header:bytes) -> List[int]:
        """Parse a V2 header line back into its fields.

        Falls back to :meth:`loads_v0`, which decodes every historical header
        width, when the header on disk was written by an older release. That lets
        a V2-configured engine open a legacy KEY file.

        Args:
            header (bytes): The raw header bytes.

        Returns:
            List[int]: ``[sync_id, n_records, n_lines, index_size, zip_type,
            data_type, swap_id, remv_id, api_ver, max_vfiles]`` -- always exactly 10
            entries.
        """
        try:
            info = _json_loads(header)
            nn = len(info)
            if nn >= 10:
                return info[:10]

            raise ValueError(f'cannot decode header (n={nn})')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError):
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
        ``(key, file_id, offset, row_size, val_size, ver, days, flags)``.

    All ``loads_*`` methods return the same 8-field tuple regardless of the
    on-disk layout, and all ``dumps_*`` methods accept the same 8 arguments, so
    callers never have to branch on ``api_ver``:

    * ``_v0`` -- 6 stored fields; ``val_size`` is packed into the high 32 bits of
      ``row_size`` and ``flags`` is dropped on write / returned as
      ``0`` on read.
    * ``_v1`` -- 7 stored fields; ``flags`` is dropped on write / returned as
      ``0`` on read.
    * ``_v2`` -- 8 stored fields; ``flags`` round-trips (see :class:`JKeyFlag`).
    """
    @abstractmethod
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row in the v0 layout (``val_size`` packed into ``row_size``, ``flags`` dropped)."""
    @abstractmethod
    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v0 KEY row; ``flags`` is always ``0``."""
    @abstractmethod
    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row in the v1 layout (all fields separate, ``flags`` dropped)."""
    @abstractmethod
    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v1 KEY row; ``flags`` is always ``0``."""
    @abstractmethod
    def dumps_v2(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row in the v2 layout (all 8 fields stored separately)."""
    @abstractmethod
    def loads_v2(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v2 KEY row into ``(key, file_id, offset, row_size, val_size, ver, days, flags)``."""

class JIoKEY_J(JIoKEY):
    """KEY row codec using JSON (one JSON array per row)."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row as a JSON array (v0 layout); ``flags`` is dropped."""
        try:
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            return _json_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v0 JSON KEY row, unpacking val_size from the high bits of row_size."""
        try:
            args = _json_loads(data)
            key, file_id, offset, row_size, ver, days = args[:6]
            val_size = row_size >> 32
            row_size &= 0X_FFFF_FFFF
            flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
            days &= FULL_DAY_MASK
            return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise JValueError from e

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row as a JSON array (v1 layout); ``flags`` is dropped."""
        try:
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            return _json_dumps((key, file_id, offset, row_size, val_size, ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v1 JSON KEY row."""
        try:
            key, file_id, offset, row_size, val_size, ver, days = _json_loads(data)[:7]
            flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
            days &= FULL_DAY_MASK
            return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise JValueError from e

    def dumps_v2(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row as a JSON array (v2 layout, 8 fields)."""
        try:
            return _json_dumps((key, file_id, offset, row_size, val_size, ver, days, flags))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v2(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v2 JSON KEY row (8 fields; a v1 row is rejected, not widened)."""
        try:
            args = _json_loads(data)
            return args[:8]

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, JSONDecodeError) as e: # pragma: no cover
            raise JValueError from e

class JIoKEY_S(JIoKEY):
    """KEY row codec using msgpack, prefixed with a 3-byte length header."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row with msgpack behind a 3-byte length prefix (v0 layout); ``flags`` is dropped."""
        try:
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            info_b = _msg_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days)) or b''
            info_len = len(info_b)
            return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v0 msgpack KEY row, unpacking val_size from the high bits of row_size."""
        try:
            prefix0, prefix1, prefix2, info0 = data[:4]
            if prefix0 == 0xcd and info0 == 0x96:
                info_len = (prefix1 << 8)| prefix2
                end_idx = info_len + 3
                key, file_id, offset, row_size, ver, days = _msg_loads(data[3:end_idx])
                flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
                days &= FULL_DAY_MASK
                return key, file_id, offset, row_size & 0X_FFFF_FFFF, row_size >> 32, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row with msgpack behind a 3-byte length prefix (v1 layout); ``flags`` is dropped."""
        try:
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            info_b = _msg_dumps((key, file_id, offset, row_size, val_size, ver, days)) or b''
            info_len = len(info_b)
            return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int, int]:
        """Parse a v1 msgpack KEY row."""
        try:
            prefix0, prefix1, prefix2, info0 = data[:4]
            if prefix0 == 0xcd and info0 == 0x97:
                info_len = (prefix1 << 8)| prefix2
                end_idx = info_len + 3
                key, file_id, offset, row_size, val_size, ver, days = _msg_loads(data[3:end_idx])[:7]
                flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
                days &= FULL_DAY_MASK
                return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v2(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row with msgpack behind a 3-byte length prefix (v2 layout, 8 fields)."""
        try:
            info_b = _msg_dumps((key, file_id, offset, row_size, val_size, ver, days, flags)) or b''
            info_len = len(info_b)
            return bytes((0xcd, info_len >> 8, info_len & 0xff)) + info_b

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v2(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v2 msgpack KEY row (fixarray(8); a v1 fixarray(7) row is rejected)."""
        try:
            prefix0, prefix1, prefix2, info0 = data[:4]
            if prefix0 == 0xcd and info0 == 0x98: # 0x98 = msgpack fixarray(8)
                info_len = (prefix1 << 8)| prefix2
                end_idx = info_len + 3
                return _msg_loads(data[3:end_idx])[:8]

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

class JIoKEY_M(JIoKEY):
    """KEY row codec using Python ``marshal`` (fast, CPython-specific)."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row with marshal (v0 layout); ``flags`` is dropped."""
        try:
            # nosemgrep
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            return marshal_dumps((key, file_id, offset, row_size | (val_size << 32), ver, days)) # tuple smaller than list

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v0 marshal KEY row, unpacking val_size from the high bits of row_size."""
        try:
            # nosemgrep
            args = marshal_loads(data) # nosec B302
            key, file_id, offset, row_size, ver, days = args[:6]
            val_size = row_size >> 32
            row_size &= 0X_FFFF_FFFF
            flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
            days &= FULL_DAY_MASK
            return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row with marshal (v1 layout); ``flags`` is dropped."""
        try:
            # nosemgrep
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            return marshal_dumps((key, file_id, offset, row_size, val_size, ver, days)) # tuple smaller than list

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v1 marshal KEY row."""
        try:
            # nosemgrep
            key, file_id, offset, row_size, val_size, ver, days = marshal_loads(data)[:7] # nosec B302
            flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
            days &= FULL_DAY_MASK
            return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v2(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row with marshal (v2 layout, 8 fields)."""
        try:
            # nosemgrep
            return marshal_dumps((key, file_id, offset, row_size, val_size, ver, days, flags)) # tuple smaller than list

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v2(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v2 marshal KEY row (8 fields; a v1 row is rejected, not widened)."""
        try:
            # nosemgrep
            args = list(marshal_loads(data)) # nosec B302
            return args[:8]

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

class JIoKEY_L(JIoKEY):
    """KEY row codec using a plain comma-separated text line."""
    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row as comma-separated text (v0 layout); ``flags`` is dropped."""
        try:
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            data = f'{key},{file_id},{offset},{row_size | (val_size << 32)}|{ver}|{days}'
            return data.encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
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

            val_size = row_size >> 32
            row_size &= 0X_FFFF_FFFF
            flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
            days &= FULL_DAY_MASK
            return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row as comma-separated text (v1 layout); ``flags`` is dropped."""
        try:
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            data = f'{key},{file_id},{offset},{row_size},{val_size},{ver},{days}'
            return data.encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v1 comma-separated KEY row (keys may contain commas)."""
        try:
            if isinstance(data, memoryview):
                data = bytes(data)

            data_s = data.decode('utf8').rstrip()
            fields = data_s.split(',')
            n_fields = len(fields)
            key = ','.join(fields[:-6]) if n_fields > 7 else fields[0]
            file_id, offset, row_size, val_size, ver, days = (int(field) for field in fields[-6:])
            flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
            days &= FULL_DAY_MASK
            return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError) as e: # pragma: no cover
            raise JValueError from e

    def dumps_v2(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row as comma-separated text (v2 layout, 8 fields)."""
        try:
            data = f'{key},{file_id},{offset},{row_size},{val_size},{ver},{days},{int(flags)}'
            return data.encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v2(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a v2 comma-separated KEY row (keys may contain commas)."""
        try:
            if isinstance(data, memoryview):
                data = bytes(data)

            data_s = data.decode('utf8').rstrip()
            fields = data_s.split(',')
            n_fields = len(fields)
            key = ','.join(fields[:-7]) if n_fields > 8 else fields[0]
            file_id, offset, row_size, val_size, ver, days, flags = (int(field) for field in fields[-7:])
            return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError) as e: # pragma: no cover
            raise JValueError from e

class JIoKEY_U(JIoKEY):
    """Pluggable KEY (row index) codec ("U+U" data_type).

    Like :class:`JIoVAL_U`, but for the KEY row metadata
    ``(key, file_id, offset, row_size, val_size, ver, days, flags)``. Most
    developers only need to customize the VAL codec (``J+U`` / ``S+U``); this
    exists for the rarer case where the KEY row itself must be transformed too
    (e.g. to obfuscate record keys on disk).

    ``dumps``/``loads`` describe the *current* (API v2, 8-field) layout. When no
    version-specific callables are supplied they are reused for the v0/v1
    layouts as well, which is correct for length-agnostic encoders such as
    msgpack or JSON. Supply ``dumps_v1``/``loads_v1`` (7 fields) or
    ``dumps_v0``/``loads_v0`` (6 fields) only when byte-exact compatibility with
    an older on-disk layout is required.
    """
    __slots__ = ('_dumps', '_loads', '_dumps_v1', '_loads_v1', '_dumps_v0', '_loads_v0')

    def __init__(self):
        self._dumps: Optional[Callable[..., bytes]] = None
        self._loads: Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int,int]]] = None
        self._dumps_v0: Optional[Callable[..., bytes]] = None
        self._loads_v0: Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int,int]]] = None
        self._dumps_v1: Optional[Callable[..., bytes]] = None
        self._loads_v1: Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int,int]]] = None

    def register(self, \
            dumps:Callable[..., bytes], \
            loads:Callable[[bytes], Tuple[str,int,int,int,int,int,int,int]], \
            dumps_v0:Optional[Callable[..., bytes]]=None, \
            loads_v0:Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int,int]]]=None, \
            dumps_v1:Optional[Callable[..., bytes]]=None, \
            loads_v1:Optional[Callable[[bytes], Tuple[str,int,int,int,int,int,int,int]]]=None) -> None:

        """Register the developer-defined KEY codec.

        Args:
            dumps (Callable): Receives a single packed row tuple
                ``(key, file_id, offset, row_size, val_size, ver, days, flags)``
                (API v2 layout) and returns ``bytes``. Called with *one* tuple
                argument, not 8 separate positional arguments.
            loads (Callable[[bytes], Tuple]): ``bytes -> (key, file_id, offset,
                row_size, val_size, ver, days, flags)``.
            dumps_v0 (Callable, optional): Same as ``dumps`` but for the legacy v0
                layout. Defaults to reusing ``dumps``.
            loads_v0 (Callable, optional): Same as ``loads`` but for the legacy v0
                layout. Defaults to reusing ``loads``.
            dumps_v1 (Callable, optional): Same as ``dumps`` but for the v1 layout
                (7 fields, no ``flags``). Defaults to reusing ``dumps``.
            loads_v1 (Callable, optional): Same as ``loads`` but for the v1 layout.
                Defaults to reusing ``loads``.

        Raises:
            TypeError: If any provided argument is not callable, or if the
                dumps/loads round-trip self-test fails. A codec that only handles
                the old 7-field layout is rejected with an explicit upgrade hint.
        """
        for fn in (dumps, loads) + tuple(f for f in (dumps_v0, loads_v0, dumps_v1, loads_v1) if f is not None):
            if not callable(fn):
                raise TypeError('dumps/loads must be callable')

        # test_val mirrors the real call convention: dumps() always receives ONE
        # packed 8-tuple (key, file_id, offset, row_size, val_size, ver, days, flags).
        test_val = ('1', 2, 3, 4, 5, 6, 7, 8)
        try:
            if tuple(loads(dumps(test_val))) != test_val:
                raise TypeError
        except Exception as e:
            try:
                legacy = ('1', 2, 3, 4, 5, 6, 7)
                is_v1_only = tuple(loads(dumps(legacy))) == legacy
            except Exception: # pylint: disable=broad-except
                is_v1_only = False

            if is_v1_only:
                raise TypeError(
                    'dumps/loads only handle the API v1 KEY layout (7 fields). '
                    'API v2 rows carry a trailing flags field: update the codec to '
                    '(key, file_id, offset, row_size, val_size, ver, days, flags), '
                    'or pass it as dumps_v1=/loads_v1= and supply a v2 codec.') from e

            raise TypeError('dumps/loads cannot work correctly') from e

        self._dumps = dumps
        self._loads = loads
        self._dumps_v1 = dumps_v1 or dumps
        self._loads_v1 = loads_v1 or loads
        self._dumps_v0 = dumps_v0 or dumps
        self._loads_v0 = loads_v0 or loads

    def unregister(self) -> None:
        """Clear a previously registered codec, e.g. between tests."""
        self._dumps = self._loads = self._dumps_v1 = self._loads_v1 = self._dumps_v0 = self._loads_v0 = None

    @property
    def is_registered(self) -> bool:
        """bool: Whether a developer codec has been registered yet."""
        return self._dumps is not None and self._loads is not None

    def _missing(self): # pragma: no cover
        raise UserCodecNotRegisteredError(
            "data_type 'U+U' (KEY) is selected but no codec is registered. "
            "Call register_user_key_codec(dumps, loads) before opening the JDb.")

    def dumps_v2(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row (v2 layout) using the registered developer codec."""
        if self._dumps is None: # pragma: no cover
            self._missing()

        try:
            return self._dumps((key, file_id, offset, row_size, val_size, ver, days, flags))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v2(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a KEY row (v2 layout) using the registered developer codec."""
        if self._loads is None: # pragma: no cover
            self._missing()

        try:
            args = self._loads(data)
            return args[:8]

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v1(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row (v1 layout) using the registered developer codec; ``flags`` is dropped."""
        if self._dumps is None: # pragma: no cover
            self._missing()
        try:
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            return self._dumps((key, file_id, offset, row_size, val_size, ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v1(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a KEY row (v1 layout) using the registered developer codec."""
        if self._loads is None: # pragma: no cover
            self._missing()

        try:
            key, file_id, offset, row_size, val_size, ver, days = self._loads(data)[:7]
            flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
            days &= FULL_DAY_MASK
            return key, file_id, offset, row_size, val_size, ver, days, flags

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

        raise JValueError

    def dumps_v0(self, key:str, file_id:int, offset:int, row_size:int, val_size:int, ver:int, days:int, flags:int=0) -> bytes:
        """Serialize a KEY row (v0 layout) using the registered developer codec; ``flags`` is dropped."""
        if self._dumps_v0 is None: # pragma: no cover
            self._missing()
        try:
            days = ((flags & KEY_FLAG_MASK) << KEY_FLAG_SHIFT) | (days & FULL_DAY_MASK)
            return self._dumps_v0((key, file_id, offset, row_size, val_size, ver, days))

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads_v0(self, data:bytes) -> Tuple[str,int,int,int,int,int,int,int]:
        """Parse a KEY row (v0 layout) using the registered developer codec."""
        if self._loads_v0 is None: # pragma: no cover
            self._missing()
        try:
            key, file_id, offset, row_size, val_size, ver, days = self._loads_v0(data)[:7]
            flags = ((days >> KEY_FLAG_SHIFT) & 0XFFFF | JKeyFlag.GROUP) if row_size == 0 and file_id == 0x10 else ((days >> KEY_FLAG_SHIFT) & 0XFFFF)
            days &= FULL_DAY_MASK
            return key, file_id, offset, row_size, val_size, ver, days, flags

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

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, UnpicklingError): # pragma: no cover
                data = data + b'\n'

        raise JValueError

class JIoVAL_Y(JIoVAL):
    """Value codec using YAML (human-readable; requires PyYAML)."""
    def dumps(self, data:Any) -> bytes:
        """Serialize a value as YAML."""
        if yaml_dumps is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

        try:
            return yaml_dumps(data, allow_unicode=True).encode('utf8')

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, YAMLError) as e: # pragma: no cover
            raise JValueError from e

    def loads(self, data:bytes) -> Any:
        """Deserialize a YAML value (retries with padding to tolerate reserved-row slack)."""
        if yaml_loads is None: # pragma: no cover
            raise ModuleNotFoundError("PyYAML is not installed. Please pip install pyyaml.")

        if isinstance(data, (bytearray, memoryview)): # pragma: no cover
            # PyYAML only accepts str/bytes; any other object is treated as a
            # file-like stream (and fails with AttributeError: no 'read').
            data = bytes(data)

        for _ in range(9):
            try:
                return yaml_loads(data)

            except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError, YAMLError): # pragma: no cover
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
        if self._dumps is None: # pragma: no cover
            raise UserCodecNotRegisteredError(
                "data_type 'U' (VAL) is selected but no codec is registered. "
                "Call register_user_val_codec(dumps, loads) before opening the JDb.")
        try:
            return self._dumps(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

    def loads(self, data:bytes) -> Any:
        """Deserialize a value using the registered developer codec."""
        if self._loads is None: # pragma: no cover
            raise UserCodecNotRegisteredError(
                "data_type 'U' (VAL) is selected but no codec is registered. "
                "Call register_user_val_codec(dumps, loads) before opening the JDb.")
        try:
            return self._loads(data)

        except (ValueError, TypeError, RuntimeError, AttributeError, EOFError, ArithmeticError, IndexError) as e: # pragma: no cover
            raise JValueError from e

#
