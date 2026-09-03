//! `op20log`: transparent J2534 pass-through shim for the Tactrix Openport 2.0, with an
//! optional SecurityAccess key fix for the MY2005 Subaru SH7058 ROM-read blocker.
//!
//! Two responsibilities, split so the interesting logic is testable anywhere:
//!
//! * [`seedkey`], the Subaru K-Line seed→key algorithm. Pure arithmetic, no OS dependencies,
//!   unit-tested against real captures from the car. Builds and tests on **any** host, so
//!   `cargo test` validates it on Linux with no Windows and no vehicle attached.
//! * `win_impl`: the actual J2534 DLL: exports the v04.04 C API, forwards every call to the
//!   genuine `op20pt32.dll`, logs traffic, and (only when explicitly enabled) substitutes the
//!   SecurityAccess key. Windows-only by nature.
//!
//! Licence: GPLv3. `seedkey` incorporates code ported from FastECU (GPLv3).

pub mod seedkey;

#[cfg(windows)]
mod win_impl;
