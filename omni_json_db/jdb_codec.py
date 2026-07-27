# pylint: disable=ungrouped-imports,too-many-lines,chained-comparison,too-few-public-methods, unused-import
from __future__ import annotations
from typing import Optional, Any, Dict, Set, List, Tuple, Callable
from functools import reduce
from pickle import loads as pickle_loads, dumps as pickle_dumps, PicklingError # nosec B403
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
    from ormsgpack import packb as _msg_dumps, Ext
    from msgpack import unpackb as _msg_loads, Unpacker

    msg_dumps = lambda obj : _msg_dumps(obj, default=_msg_encode)
    msg_loads = lambda _bytes : _msg_loads(_bytes, ext_hook=_msg_decode, strict_map_key=False)

except (ModuleNotFoundError, ImportError):
    try:
        from msgpack import packb as _msg_dumps, unpackb as _msg_loads, Unpacker, ExtType as Ext

        msg_dumps = lambda obj : _msg_dumps(obj, default=_msg_encode)
        msg_loads = lambda _bytes : _msg_loads(_bytes, ext_hook=_msg_decode, strict_map_key=False)

    except (ModuleNotFoundError, ImportError):
        # pylint: disable=unused-argument
        from struct import Struct, error as StructError
        from sys import intern
        from collections import namedtuple
        from .jdb_file import JBytesIO

        class Ext(namedtuple("ExtType", "code data")):
            """A MessagePack Ext type: a user ``code`` (0..127) plus raw ``data`` bytes."""
            __slots__ = ()

            def __new__(cls, code: int, data: bytes) -> Ext:
                return super().__new__(cls, code, data)

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
                    # Truncated object at the buffer tail: end iteration rather
                    # than raise (KeyTable feeds only complete records).
                    raise StopIteration from e

                return obj

            next = __next__

def _msg_encode(obj:Any) -> Ext:
    """Pack non-primitive objects into MsgPack ExtType objects.

    Args:
        obj (Any): The non-primitive input object (a ``set`` or ``frozenset``).

    Returns:
        Ext: ``set`` -> ExtType code 123, ``frozenset`` -> ExtType code 124,
        each wrapping the msgpack-encoded list of members.

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

#
