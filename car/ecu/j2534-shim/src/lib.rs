//! Transparent J2534 pass-through logging shim for the Tactrix Openport 2.0 (`op20pt32.dll`).
//!
//! Purpose: capture the EXACT bytes exchanged between EcuFlash and the ECU during a read
//! attempt — specifically the reflash-mode security handshake (Requesting Seed / Sending Key) —
//! to decide whether the clone cable is delivering a valid seed (=> ECU-side fault) or garbage
//! (=> cable-side fault). See car/ecu/ROM-READ-BLOCKER.md.
//!
//! It exports the J2534 v04.04 C API under the standard undecorated names, forwards every call
//! unchanged to the REAL Tactrix DLL, and logs message traffic. It NEVER modifies traffic and
//! NEVER writes to the ECU itself — the real DLL does exactly what it always did. Read-only,
//! brick-safe. Removing the EcuFlash registration reverts everything; no vendor file is touched.
//!
//! Build (32-bit, because EcuFlash is a 32-bit app; GNU toolchain needs no Visual Studio):
//!   rustup toolchain install stable-i686-pc-windows-gnu
//!   cargo +stable-i686-pc-windows-gnu build --release
//! Output: target/i686-pc-windows-gnu/release/op20log.dll
//!
//! Config via environment variables (set them in the shell that launches EcuFlash):
//!   TACTRIX_SHIM_REAL  full path to the genuine DLL (default C:\WINDOWS\SysWOW64\op20pt32.dll)
//!   TACTRIX_SHIM_LOG   full path for the log file    (default %TEMP%\j2534_shim.log)

use std::ffi::c_void;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::{Mutex, OnceLock};

// ---- Win32 imports (kernel32 is linked by default on the Windows target) ----
extern "system" {
    fn LoadLibraryA(name: *const u8) -> *mut c_void;
    fn GetProcAddress(module: *mut c_void, name: *const u8) -> *mut c_void;
    fn OutputDebugStringA(s: *const u8);
    fn GetEnvironmentVariableA(name: *const u8, buf: *mut u8, size: u32) -> u32;
}

/// J2534 message. Layout is fixed by the J2534 spec; `#[repr(C)]` matches the DLL's expectation.
/// We only ever READ this (bounded by `data_size`) for logging — never hand a self-built one to
/// the real DLL — so even a harmless layout slip cannot corrupt a transfer.
#[repr(C)]
pub struct PassThruMsg {
    protocol_id: u32,
    rx_status: u32,
    tx_flags: u32,
    timestamp: u32,
    data_size: u32,
    extra_data_index: u32,
    data: [u8; 4128],
}

// ---- Real-DLL function-pointer table, resolved once on first use ----
struct Real {
    open: usize,
    close: usize,
    connect: usize,
    disconnect: usize,
    read_msgs: usize,
    write_msgs: usize,
    start_periodic: usize,
    stop_periodic: usize,
    start_filter: usize,
    stop_filter: usize,
    set_prog_voltage: usize,
    read_version: usize,
    get_last_error: usize,
    ioctl: usize,
}

static REAL: OnceLock<Real> = OnceLock::new();
static LOG: OnceLock<Mutex<Option<File>>> = OnceLock::new();
static SEQ: AtomicU32 = AtomicU32::new(0);

fn env(name: &str, default: &str) -> String {
    let mut cname: Vec<u8> = name.bytes().collect();
    cname.push(0);
    let mut buf = [0u8; 1024];
    let n = unsafe { GetEnvironmentVariableA(cname.as_ptr(), buf.as_mut_ptr(), buf.len() as u32) };
    if n == 0 || n as usize >= buf.len() {
        default.to_string()
    } else {
        String::from_utf8_lossy(&buf[..n as usize]).into_owned()
    }
}

fn log_path() -> String {
    let explicit = env("TACTRIX_SHIM_LOG", "");
    if !explicit.is_empty() {
        return explicit;
    }
    let tmp = env("TEMP", "C:\\");
    format!("{}\\j2534_shim.log", tmp.trim_end_matches('\\'))
}

fn logger() -> &'static Mutex<Option<File>> {
    LOG.get_or_init(|| {
        let f = OpenOptions::new().create(true).append(true).open(log_path()).ok();
        Mutex::new(f)
    })
}

fn line(msg: &str) {
    let n = SEQ.fetch_add(1, Ordering::Relaxed);
    let text = format!("[{:06}] {}\n", n, msg);
    // Mirror to DebugView as well, so a locked-down log path still shows something.
    let mut c = text.clone().into_bytes();
    c.push(0);
    unsafe { OutputDebugStringA(c.as_ptr()) };
    if let Ok(mut g) = logger().lock() {
        if let Some(f) = g.as_mut() {
            let _ = f.write_all(text.as_bytes());
            let _ = f.flush();
        }
    }
}

fn ensure_init() {
    REAL.get_or_init(|| {
        let path = env("TACTRIX_SHIM_REAL", "C:\\WINDOWS\\SysWOW64\\op20pt32.dll");
        let mut cpath: Vec<u8> = path.bytes().collect();
        cpath.push(0);
        let h = unsafe { LoadLibraryA(cpath.as_ptr()) };
        let get = |name: &str| -> usize {
            if h.is_null() {
                return 0;
            }
            let mut c: Vec<u8> = name.bytes().collect();
            c.push(0);
            unsafe { GetProcAddress(h, c.as_ptr()) as usize }
        };
        line(&format!("==== shim init: real DLL '{}' loaded={} ; log='{}' ====",
            path, !h.is_null(), log_path()));
        Real {
            open: get("PassThruOpen"),
            close: get("PassThruClose"),
            connect: get("PassThruConnect"),
            disconnect: get("PassThruDisconnect"),
            read_msgs: get("PassThruReadMsgs"),
            write_msgs: get("PassThruWriteMsgs"),
            start_periodic: get("PassThruStartPeriodicMsg"),
            stop_periodic: get("PassThruStopPeriodicMsg"),
            start_filter: get("PassThruStartMsgFilter"),
            stop_filter: get("PassThruStopMsgFilter"),
            set_prog_voltage: get("PassThruSetProgrammingVoltage"),
            read_version: get("PassThruReadVersion"),
            get_last_error: get("PassThruGetLastError"),
            ioctl: get("PassThruIoctl"),
        }
    });
}

fn real() -> &'static Real {
    ensure_init();
    REAL.get().unwrap()
}

/// Hex-dump one PASSTHRU_MSG's payload, bounded by data_size (spec caps at 4128).
unsafe fn dump(tag: &str, idx: u32, m: *const PassThruMsg) {
    if m.is_null() {
        line(&format!("  {}[{}]: <null>", tag, idx));
        return;
    }
    let n = ((*m).data_size as usize).min(4128);
    // Read through the raw pointer without creating an intermediate reference to the array
    // (dangerous_implicit_autorefs): copy byte-by-byte from the computed element addresses.
    let base = std::ptr::addr_of!((*m).data) as *const u8;
    let hex: Vec<String> = (0..n).map(|i| format!("{:02X}", *base.add(i))).collect();
    line(&format!("  {}[{}]: proto={} txf=0x{:X} rxs=0x{:X} len={} | {}",
        tag, idx, (*m).protocol_id, (*m).tx_flags, (*m).rx_status, n, hex.join(" ")));
}

unsafe fn dump_many(tag: &str, msgs: *const PassThruMsg, count: u32) {
    let c = count.min(64); // guard against a wild count
    for i in 0..c {
        dump(tag, i, msgs.add(i as usize));
    }
}

// ============================ exported J2534 v04.04 API ============================
// Each fn forwards unchanged to the real DLL. extern "system" = stdcall on 32-bit Windows.
// Undecorated export names: exports.def (MSVC) or -Wl,--kill-at (GNU) - see build.rs.

type FOpen = unsafe extern "system" fn(*mut c_void, *mut u32) -> i32;
type FClose = unsafe extern "system" fn(u32) -> i32;
type FConnect = unsafe extern "system" fn(u32, u32, u32, u32, *mut u32) -> i32;
type FDisconnect = unsafe extern "system" fn(u32) -> i32;
type FRW = unsafe extern "system" fn(u32, *mut PassThruMsg, *mut u32, u32) -> i32;
type FStartPeriodic = unsafe extern "system" fn(u32, *mut PassThruMsg, *mut u32, u32) -> i32;
type FStopPeriodic = unsafe extern "system" fn(u32, u32) -> i32;
type FStartFilter =
    unsafe extern "system" fn(u32, u32, *mut PassThruMsg, *mut PassThruMsg, *mut PassThruMsg, *mut u32) -> i32;
type FStopFilter = unsafe extern "system" fn(u32, u32) -> i32;
type FSetVolt = unsafe extern "system" fn(u32, u32, u32) -> i32;
type FReadVersion = unsafe extern "system" fn(u32, *mut u8, *mut u8, *mut u8) -> i32;
type FGetLastError = unsafe extern "system" fn(*mut u8) -> i32;
type FIoctl = unsafe extern "system" fn(u32, u32, *mut c_void, *mut c_void) -> i32;

#[no_mangle]
pub unsafe extern "system" fn PassThruOpen(name: *mut c_void, dev: *mut u32) -> i32 {
    let f: FOpen = std::mem::transmute(real().open);
    let r = f(name, dev);
    line(&format!("PassThruOpen -> {} (deviceID={})", r, if dev.is_null() { 0 } else { *dev }));
    r
}

#[no_mangle]
pub unsafe extern "system" fn PassThruClose(dev: u32) -> i32 {
    let f: FClose = std::mem::transmute(real().close);
    let r = f(dev);
    line(&format!("PassThruClose(dev={}) -> {}", dev, r));
    r
}

#[no_mangle]
pub unsafe extern "system" fn PassThruConnect(dev: u32, proto: u32, flags: u32, baud: u32, chan: *mut u32) -> i32 {
    let f: FConnect = std::mem::transmute(real().connect);
    let r = f(dev, proto, flags, baud, chan);
    line(&format!("PassThruConnect(dev={} proto={} flags=0x{:X} baud={}) -> {} chan={}",
        dev, proto, flags, baud, r, if chan.is_null() { 0 } else { *chan }));
    r
}

#[no_mangle]
pub unsafe extern "system" fn PassThruDisconnect(chan: u32) -> i32 {
    let f: FDisconnect = std::mem::transmute(real().disconnect);
    let r = f(chan);
    line(&format!("PassThruDisconnect(chan={}) -> {}", chan, r));
    r
}

#[no_mangle]
pub unsafe extern "system" fn PassThruReadMsgs(chan: u32, msgs: *mut PassThruMsg, num: *mut u32, timeout: u32) -> i32 {
    let f: FRW = std::mem::transmute(real().read_msgs);
    let r = f(chan, msgs, num, timeout);
    let n = if num.is_null() { 0 } else { *num };
    line(&format!("PassThruReadMsgs(chan={} timeout={}) -> {} num={}", chan, timeout, r, n));
    if r == 0 {
        dump_many("RX", msgs, n);
    }
    r
}

#[no_mangle]
pub unsafe extern "system" fn PassThruWriteMsgs(chan: u32, msgs: *mut PassThruMsg, num: *mut u32, timeout: u32) -> i32 {
    let n = if num.is_null() { 0 } else { *num };
    line(&format!("PassThruWriteMsgs(chan={} timeout={} num={})", chan, timeout, n));
    dump_many("TX", msgs, n);
    let f: FRW = std::mem::transmute(real().write_msgs);
    let r = f(chan, msgs, num, timeout);
    line(&format!("  PassThruWriteMsgs -> {}", r));
    r
}

#[no_mangle]
pub unsafe extern "system" fn PassThruStartPeriodicMsg(chan: u32, msg: *mut PassThruMsg, id: *mut u32, interval: u32) -> i32 {
    dump("PERIODIC", 0, msg);
    let f: FStartPeriodic = std::mem::transmute(real().start_periodic);
    let r = f(chan, msg, id, interval);
    line(&format!("PassThruStartPeriodicMsg(chan={} interval={}) -> {}", chan, interval, r));
    r
}

#[no_mangle]
pub unsafe extern "system" fn PassThruStopPeriodicMsg(chan: u32, id: u32) -> i32 {
    let f: FStopPeriodic = std::mem::transmute(real().stop_periodic);
    f(chan, id)
}

#[no_mangle]
pub unsafe extern "system" fn PassThruStartMsgFilter(
    chan: u32, ftype: u32, mask: *mut PassThruMsg, pattern: *mut PassThruMsg, flow: *mut PassThruMsg, id: *mut u32,
) -> i32 {
    line(&format!("PassThruStartMsgFilter(chan={} type={})", chan, ftype));
    dump("  MASK", 0, mask);
    dump("  PATT", 0, pattern);
    if !flow.is_null() {
        dump("  FLOW", 0, flow);
    }
    let f: FStartFilter = std::mem::transmute(real().start_filter);
    f(chan, ftype, mask, pattern, flow, id)
}

#[no_mangle]
pub unsafe extern "system" fn PassThruStopMsgFilter(chan: u32, id: u32) -> i32 {
    let f: FStopFilter = std::mem::transmute(real().stop_filter);
    f(chan, id)
}

#[no_mangle]
pub unsafe extern "system" fn PassThruSetProgrammingVoltage(dev: u32, pin: u32, voltage: u32) -> i32 {
    let f: FSetVolt = std::mem::transmute(real().set_prog_voltage);
    let r = f(dev, pin, voltage);
    line(&format!("PassThruSetProgrammingVoltage(dev={} pin={} v={}) -> {}", dev, pin, voltage, r));
    r
}

#[no_mangle]
pub unsafe extern "system" fn PassThruReadVersion(dev: u32, fw: *mut u8, dll: *mut u8, api: *mut u8) -> i32 {
    let f: FReadVersion = std::mem::transmute(real().read_version);
    f(dev, fw, dll, api)
}

#[no_mangle]
pub unsafe extern "system" fn PassThruGetLastError(desc: *mut u8) -> i32 {
    let f: FGetLastError = std::mem::transmute(real().get_last_error);
    f(desc)
}

#[no_mangle]
pub unsafe extern "system" fn PassThruIoctl(handle: u32, ioctl_id: u32, input: *mut c_void, output: *mut c_void) -> i32 {
    let f: FIoctl = std::mem::transmute(real().ioctl);
    let r = f(handle, ioctl_id, input, output);
    line(&format!("PassThruIoctl(handle={} id=0x{:X}) -> {}", handle, ioctl_id, r));
    r
}
