// Force UNDECORATED stdcall export names (PassThruOpen, not _PassThruOpen@8) so EcuFlash can
// bind them by the standard J2534 names. The MSVC linker takes a module-definition (.def) file.
fn main() {
    let dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    // MSVC linker (default for -pc-windows-msvc targets).
    println!("cargo:rustc-cdylib-link-arg=/DEF:{}\\exports.def", dir);
    println!("cargo:rerun-if-changed=exports.def");
}
