//! Optional Rust accelerator for omni-json-db.
//!
//! Every function here is a drop-in for a pure-Python path in `omni_json_db`
//! and must be **byte-for-byte / value-for-value identical** to it. The rule
//! that makes that tractable: this module only handles the canonical shape the
//! Python writer produces. Anything else -- whitespace inside a row, a float, a
//! number that overflows i64, an escape that needs a lone surrogate, the sub-day
//! TTL layout -- is a *bail*: the call is handed to the Python
//! implementation it replaces (registered with `set_key_j_fallbacks`), which then
//! succeeds or raises exactly as it always did. A bail is never an error here.
//!
//! Only the *decode* side is here. A Rust `dumps_v*` was built, fuzzed
//! byte-identical and dropped: orjson already does the work in C, and it saved
//! 25 ns of 285 ns per row -- inside the noise of `f_extend`
//! (`claude/rust-core-port.md` §4).
//!
//! The JSON KEY row layouts (`omni_json_db/jdb_codec.py`, `JIoKEY_J`):
//!
//! * v0: `[key, file_id, offset, row_size | val_size << 32, ver, days | flags << 48]`
//! * v1: `[key, file_id, offset, row_size, val_size, ver, days | flags << 48]`
//! * v2: `[key, file_id, offset, row_size, val_size, ver, days, flags]`
//!
//! followed by JSON-whitespace padding up to `index_size`.

use pyo3::exceptions::PyRuntimeError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::GILOnceCell;
use pyo3::types::{PyDict, PyString, PyTuple};
use std::os::raw::c_char;

// --- constants, mirrored from jdb_codec.py / utils.py / jdb_io.py ------------
const KEY_FLAG_SHIFT: u32 = 48;
const KEY_FLAG_MASK: i128 = 0xFFFF;
const NEW_DAY_SHIFT: u32 = 26;
const OLD_DAY_MASK: i128 = 0x3FF_FFFF;
const NEW_DAY_MASK: i128 = 0xFFFF_FC00_0000;
const SUB_DAY_BIT: i128 = 1 << 22;
const TTL_SHIFT: u32 = 39;
const TTL_MASK: i128 = 0xFF80_0000_0000;
const EXP_DELTA_MASK: i128 = 0x7F_FC00_0000;
const KF_GROUP: i128 = 0x4;
const KF_EXPIRE: i128 = 0x80;
const ROW_ID_SHIFT: u32 = 16; // KEY_FLAG_MASK.bit_length()

/// Number of stored fields per layout version (key included).
const N_FIELDS: [usize; 3] = [6, 7, 8];

static FALLBACK_LOADS: [GILOnceCell<PyObject>; 3] = [GILOnceCell::new(), GILOnceCell::new(), GILOnceCell::new()];

// --- byte access --------------------------------------------------------------

/// Borrow the bytes of a bytes / bytearray / memoryview without copying.
///
/// The returned slice is only valid while the GIL is held and `obj` is not
/// resized; every caller uses it immediately and never releases the GIL.
struct Buf {
    view: ffi::Py_buffer,
}

impl Buf {
    fn new(obj: &Bound<'_, PyAny>) -> PyResult<Buf> {
        let mut view: ffi::Py_buffer = unsafe { std::mem::zeroed() };
        let rc = unsafe { ffi::PyObject_GetBuffer(obj.as_ptr(), &mut view, ffi::PyBUF_SIMPLE) };
        if rc != 0 {
            return Err(PyErr::fetch(obj.py()));
        }
        Ok(Buf { view })
    }
    fn as_slice(&self) -> &[u8] {
        if self.view.len <= 0 {
            return &[];
        }
        unsafe { std::slice::from_raw_parts(self.view.buf as *const u8, self.view.len as usize) }
    }
}

impl Drop for Buf {
    fn drop(&mut self) {
        unsafe { ffi::PyBuffer_Release(&mut self.view) };
    }
}

// --- row parser -----------------------------------------------------------------

/// A parsed canonical KEY row: the key (raw UTF-8 slice or unescaped copy) and
/// up to 7 integer fields.
struct Row<'a> {
    key_raw: &'a [u8],
    key_owned: Option<String>,
    f: [i64; 7],
}

impl<'a> Row<'a> {
    #[inline]
    fn key_str(&self) -> Option<&str> {
        match &self.key_owned {
            Some(s) => Some(s.as_str()),
            None => std::str::from_utf8(self.key_raw).ok(),
        }
    }
}

#[inline]
fn hex4(b: &[u8]) -> Option<u32> {
    if b.len() < 4 {
        return None;
    }
    let mut v = 0u32;
    for &c in &b[..4] {
        let d = match c {
            b'0'..=b'9' => c - b'0',
            b'a'..=b'f' => c - b'a' + 10,
            b'A'..=b'F' => c - b'A' + 10,
            _ => return None,
        } as u32;
        v = (v << 4) | d;
    }
    Some(v)
}

/// Unescape a JSON string body. `None` = bail (lone surrogate, bad escape,
/// invalid UTF-8, raw control character).
fn unescape(s: &[u8]) -> Option<String> {
    let mut out: Vec<u8> = Vec::with_capacity(s.len());
    let mut i = 0;
    while i < s.len() {
        let c = s[i];
        if c != b'\\' {
            if c < 0x20 {
                return None;
            }
            out.push(c);
            i += 1;
            continue;
        }
        let e = *s.get(i + 1)?;
        i += 2;
        let ch: u32 = match e {
            b'"' => 0x22,
            b'\\' => 0x5C,
            b'/' => 0x2F,
            b'b' => 0x08,
            b'f' => 0x0C,
            b'n' => 0x0A,
            b'r' => 0x0D,
            b't' => 0x09,
            b'u' => {
                let hi = hex4(&s[i..])?;
                i += 4;
                if (0xD800..0xDC00).contains(&hi) {
                    if s.get(i) != Some(&b'\\') || s.get(i + 1) != Some(&b'u') {
                        return None;
                    }
                    let lo = hex4(&s[i + 2..])?;
                    if !(0xDC00..0xE000).contains(&lo) {
                        return None;
                    }
                    i += 6;
                    0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
                } else if (0xDC00..0xE000).contains(&hi) {
                    return None;
                } else {
                    hi
                }
            }
            _ => return None,
        };
        let mut tmp = [0u8; 4];
        out.extend_from_slice(char::from_u32(ch)?.encode_utf8(&mut tmp).as_bytes());
    }
    String::from_utf8(out).ok()
}

/// Parse `["key",i,i,...]` + JSON-whitespace padding with exactly `n_ints` integers.
#[inline]
fn parse_row(b: &[u8], n_ints: usize) -> Option<Row<'_>> {
    if b.len() < 2 || b[0] != b'[' || b[1] != b'"' {
        return None;
    }
    // key
    let mut i = 2;
    let start = i;
    let mut escaped = false;
    loop {
        let c = *b.get(i)?;
        if c == b'"' {
            break;
        }
        if c == b'\\' {
            escaped = true;
            i += 2;
            continue;
        }
        if c < 0x20 {
            return None;
        }
        i += 1;
    }
    let key_raw = &b[start..i];
    let key_owned = if escaped { Some(unescape(key_raw)?) } else { None };
    i += 1;
    let mut f = [0i64; 7];
    for slot in f.iter_mut().take(n_ints) {
        if *b.get(i)? != b',' {
            return None;
        }
        i += 1;
        let neg = *b.get(i)? == b'-';
        if neg {
            i += 1;
        }
        let d0 = *b.get(i)?;
        if !d0.is_ascii_digit() {
            return None;
        }
        let mut v: i64 = (d0 - b'0') as i64;
        i += 1;
        if d0 == b'0' {
            if b.get(i).map_or(false, |c| c.is_ascii_digit()) {
                return None; // leading zero: not canonical JSON
            }
        } else {
            while let Some(&c) = b.get(i) {
                if !c.is_ascii_digit() {
                    break;
                }
                v = v.checked_mul(10)?.checked_add((c - b'0') as i64)?;
                i += 1;
            }
        }
        *slot = if neg { -v } else { v };
    }
    if *b.get(i)? != b']' {
        return None; // '.', 'e', more elements, whitespace...: let Python decide
    }
    i += 1;
    for &c in &b[i..] {
        if !matches!(c, b' ' | b'\n' | b'\t' | b'\r') {
            return None;
        }
    }
    Some(Row { key_raw, key_owned, f })
}

/// `(file_id, offset, row_size, val_size, ver, cdays, mdays, ttl, flags)` from the
/// raw fields, exactly as `JIoKEY_J.loads_v{ver}` computes them. Python ints are
/// unbounded, so the arithmetic runs in i128 and bails if a result leaves i64.
#[inline]
fn decode(f: &[i64; 7], ver: usize) -> Option<[i64; 9]> {
    let g = |k: usize| f[k] as i128;
    let (file_id, offset, mut row_size, val_size, rver, days, flags);
    match ver {
        0 => {
            file_id = g(0);
            offset = g(1);
            row_size = g(2);
            rver = g(3);
            days = g(4);
            val_size = row_size >> 32;
            row_size &= 0xFFFF_FFFF;
            flags = ((days >> KEY_FLAG_SHIFT) & KEY_FLAG_MASK)
                | if row_size == 0 && file_id == 0x10 { KF_GROUP } else { 0 };
        }
        1 => {
            file_id = g(0);
            offset = g(1);
            row_size = g(2);
            val_size = g(3);
            rver = g(4);
            days = g(5);
            flags = ((days >> KEY_FLAG_SHIFT) & KEY_FLAG_MASK)
                | if row_size == 0 && file_id == 0x10 { KF_GROUP } else { 0 };
        }
        _ => {
            file_id = g(0);
            offset = g(1);
            row_size = g(2);
            val_size = g(3);
            rver = g(4);
            days = g(5);
            flags = g(6);
        }
    }
    let cdays = days & OLD_DAY_MASK;
    let (mdays, ttl);
    if flags & KF_EXPIRE != 0 {
        if days & SUB_DAY_BIT != 0 {
            return None; // minute layout: unpack_days() stays in Python
        }
        mdays = cdays + ((days & EXP_DELTA_MASK) >> NEW_DAY_SHIFT);
        ttl = (days & TTL_MASK) >> TTL_SHIFT;
    } else {
        mdays = cdays + ((days & NEW_DAY_MASK) >> NEW_DAY_SHIFT);
        ttl = 0;
    }
    let out = [file_id, offset, row_size, val_size, rver, cdays, mdays, ttl, flags];
    let mut r = [0i64; 9];
    for (d, s) in r.iter_mut().zip(out.iter()) {
        *d = i64::try_from(*s).ok()?;
    }
    Some(r)
}

#[inline]
fn new_str<'py>(py: Python<'py>, s: &str) -> Bound<'py, PyString> {
    PyString::new_bound(py, s)
}

fn fallback<'py>(
    py: Python<'py>,
    cell: &GILOnceCell<PyObject>,
    args: Bound<'py, PyTuple>,
) -> PyResult<Bound<'py, PyAny>> {
    match cell.get(py) {
        Some(f) => f.bind(py).call1(args),
        None => Err(PyRuntimeError::new_err("omni_json_db_rs: fallbacks not registered")),
    }
}

fn loads_impl<'py>(py: Python<'py>, data: &Bound<'py, PyAny>, ver: usize) -> PyResult<Bound<'py, PyAny>> {
    {
        let buf = Buf::new(data)?;
        if let Some(row) = parse_row(buf.as_slice(), N_FIELDS[ver] - 1) {
            if let (Some(key), Some(v)) = (row.key_str(), decode(&row.f, ver)) {
                let key = new_str(py, key).into_any();
                let items: [Bound<'py, PyAny>; 10] = [
                    key,
                    v[0].into_py(py).into_bound(py),
                    v[1].into_py(py).into_bound(py),
                    v[2].into_py(py).into_bound(py),
                    v[3].into_py(py).into_bound(py),
                    v[4].into_py(py).into_bound(py),
                    v[5].into_py(py).into_bound(py),
                    v[6].into_py(py).into_bound(py),
                    v[7].into_py(py).into_bound(py),
                    v[8].into_py(py).into_bound(py),
                ];
                return Ok(PyTuple::new_bound(py, items).into_any());
            }
        }
    }
    fallback(py, &FALLBACK_LOADS[ver], PyTuple::new_bound(py, [data]))
}

/// Drop-in for `JIoKEY_J.loads_v0`.
#[pyfunction]
fn key_j_loads_v0<'py>(py: Python<'py>, data: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    loads_impl(py, data, 0)
}
/// Drop-in for `JIoKEY_J.loads_v1`.
#[pyfunction]
fn key_j_loads_v1<'py>(py: Python<'py>, data: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    loads_impl(py, data, 1)
}
/// Drop-in for `JIoKEY_J.loads_v2`.
#[pyfunction]
fn key_j_loads_v2<'py>(py: Python<'py>, data: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    loads_impl(py, data, 2)
}

/// Register the pure-Python implementations a bail hands over to.
#[pyfunction]
fn set_key_j_fallbacks(py: Python<'_>, loads: (PyObject, PyObject, PyObject)) -> PyResult<()> {
    for (i, f) in [loads.0, loads.1, loads.2].into_iter().enumerate() {
        let _ = FALLBACK_LOADS[i].set(py, f);
    }
    Ok(())
}

// --- bulk index rebuild ------------------------------------------------------------

/// Fill a `DictKeyTable.table` from a block of JSON KEY rows.
///
/// For each row `i` this does what `load_keys()` does through
/// `KEY_iter()` + `DictKeyTable.set(key, row, flags | KF_EXCL)`:
/// `table[key] = (row << 16) | (flags & 0xFFFF)`, and for a GROUP row below
/// `n_records`, `groups.setdefault(key, None)`.
///
/// Returns the number of leading rows handled. It stops at the first row it
/// would bail on; the caller decodes that row in Python and calls again.
#[pyfunction]
#[pyo3(signature = (buf, index_size, ver, start_row, n_records, table, groups))]
fn load_rows_j(
    py: Python<'_>,
    buf: &Bound<'_, PyAny>,
    index_size: usize,
    ver: usize,
    start_row: i64,
    n_records: i64,
    table: &Bound<'_, PyDict>,
    groups: &Bound<'_, PyAny>,
) -> PyResult<usize> {
    if index_size == 0 || ver > 2 {
        return Ok(0);
    }
    let n_ints = N_FIELDS[ver] - 1;
    let b = Buf::new(buf)?;
    let data = b.as_slice();
    let n = data.len() / index_size;
    let tp = table.as_ptr();
    let none = py.None();
    for i in 0..n {
        let row_b = &data[i * index_size..(i + 1) * index_size];
        let Some(row) = parse_row(row_b, n_ints) else { return Ok(i) };
        let Some(v) = decode(&row.f, ver) else { return Ok(i) };
        let row_id = start_row + i as i64;
        let flags = v[8] as i128;
        let packed = ((row_id as i128) << ROW_ID_SHIFT) | (flags & KEY_FLAG_MASK);
        let Ok(packed) = i64::try_from(packed) else { return Ok(i) };
        unsafe {
            let k = match &row.key_owned {
                Some(s) => ffi::PyUnicode_FromStringAndSize(s.as_ptr() as *const c_char, s.len() as ffi::Py_ssize_t),
                None => ffi::PyUnicode_DecodeUTF8(
                    row.key_raw.as_ptr() as *const c_char,
                    row.key_raw.len() as ffi::Py_ssize_t,
                    std::ptr::null(),
                ),
            };
            if k.is_null() {
                ffi::PyErr_Clear(); // invalid UTF-8: Python's decoder decides
                return Ok(i);
            }
            let val = ffi::PyLong_FromLongLong(packed);
            if val.is_null() {
                ffi::Py_DECREF(k);
                return Err(PyErr::fetch(py));
            }
            let rc = ffi::PyDict_SetItem(tp, k, val);
            ffi::Py_DECREF(val);
            if rc != 0 {
                ffi::Py_DECREF(k);
                return Err(PyErr::fetch(py));
            }
            if flags & KF_GROUP != 0 && row_id < n_records {
                let key = Bound::from_owned_ptr(py, k);
                groups.call_method1("setdefault", (key, &none))?;
            } else {
                ffi::Py_DECREF(k);
            }
        }
    }
    Ok(n)
}

#[pymodule]
fn omni_json_db_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(key_j_loads_v0, m)?)?;
    m.add_function(wrap_pyfunction!(key_j_loads_v1, m)?)?;
    m.add_function(wrap_pyfunction!(key_j_loads_v2, m)?)?;
    m.add_function(wrap_pyfunction!(set_key_j_fallbacks, m)?)?;
    m.add_function(wrap_pyfunction!(load_rows_j, m)?)?;
    Ok(())
}
