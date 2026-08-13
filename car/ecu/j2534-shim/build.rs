// Force UNDECORATED stdcall export names (PassThruOpen, not _PassThruOpen@8) so EcuFlash can
// bind them by the standard J2534 names. The mechanism differs per linker:
//   - MSVC : a module-definition (.def) file listing the plain names.
//   - GNU/MinGW : the linker's --kill-at flag strips the @N stdcall suffix from all exports.
// Building with the GNU toolchain is recommended on Windows because rustup ships it self-contained
// (no Visual Studio Build Tools required).
fn main() {
    let dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    let target_env = std::env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default();
    if target_env == "msvc" {
        println!("cargo:rustc-cdylib-link-arg=/DEF:{}\\exports.def", dir);
    } else {
        println!("cargo:rustc-cdylib-link-arg=-Wl,--kill-at");
    }
    println!("cargo:rerun-if-changed=exports.def");
}
