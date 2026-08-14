//! Subaru K-Line (SSM2 / KWP2000) SecurityAccess seed→key algorithm.
//!
//! Ported from FastECU (GPLv3), `modules/ecu/flash_ecu_subaru_denso_sh705x_kline.cpp`,
//! functions `generate_seed_key()` / `calculate_seed_key()`. Because this file incorporates
//! GPLv3 code, the shim as a whole is GPLv3 — see README.
//!
//! WHY THIS EXISTS: on the 2005 Forester XT (ECU 3B12504206), EcuFlash's own key is rejected by
//! the ECU while FastECU's is accepted. FastECU in turn fails one step later, at the kernel
//! upload. This module lets the shim supply FastECU's (correct) key to EcuFlash so EcuFlash can
//! proceed to its own kernel upload — merging the two tools' working halves at the wire level.
//!
//! VERIFIED against three real captures from the car (see tests): two of these keys were
//! explicitly ACCEPTED by the ECU (`67 02` positive response), so this is not a guess.

/// Key schedule, `keytogenerateindex_1` in FastECU.
const KEYGEN: [u16; 16] = [
    0x53DA, 0x33BC, 0x72EB, 0x437D, 0x7CA3, 0x3382, 0x834F, 0x3608, 0xAFB8, 0x503D, 0xDBA3,
    0x9D34, 0x3563, 0x6B70, 0x6E74, 0x88F0,
];

/// S-box, `indextransformation` in FastECU. 32 entries — indices are masked with 0x1F.
const IDXT: [u8; 32] = [
    0x5, 0x6, 0x7, 0x1, 0x9, 0xC, 0xD, 0x8, 0xA, 0xD, 0x2, 0xB, 0xF, 0x4, 0x0, 0x3, 0xB, 0x4,
    0x6, 0x0, 0xF, 0x2, 0xD, 0x9, 0x5, 0xC, 0x1, 0xA, 0x3, 0xD, 0xE, 0x8,
];

/// Compute the 4-byte SecurityAccess key for a 4-byte seed.
///
/// 16 rounds of a Feistel-like construction. All arithmetic is deliberately wrapping to match
/// the C++ `uint16_t`/`uint32_t` overflow behaviour exactly — using checked arithmetic here
/// would produce a different (wrong) key.
pub fn calculate_key(seed_bytes: [u8; 4]) -> [u8; 4] {
    let mut seed = u32::from_be_bytes(seed_bytes);

    for ki in (0..16).rev() {
        let word_to_generate_index = seed as u16;
        let word_to_be_encrypted = (seed >> 16) as u16;

        let mut index = (word_to_generate_index ^ KEYGEN[ki]) as u32;
        index = index.wrapping_add(index << 16);

        let mut encryption_key: u16 = 0;
        for n in 0..4 {
            let nibble = IDXT[((index >> (n * 4)) & 0x1F) as usize] as u16;
            encryption_key = encryption_key.wrapping_add(nibble << (n * 4));
        }
        // 16-bit rotate right by 3, expressed as the C++ does it.
        encryption_key = (encryption_key >> 3).wrapping_add(encryption_key << 13);

        seed = ((encryption_key ^ word_to_be_encrypted) as u32)
            .wrapping_add((word_to_generate_index as u32) << 16);
    }

    // final 32-bit rotate by 16
    seed = (seed >> 16).wrapping_add(seed << 16);
    seed.to_be_bytes()
}

/// SSM2/KWP frame checksum: low byte of the sum of every preceding byte.
pub fn checksum(frame_without_checksum: &[u8]) -> u8 {
    frame_without_checksum
        .iter()
        .fold(0u8, |acc, b| acc.wrapping_add(*b))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Real captures from the car (2026-08-13/14). The first two were ACCEPTED by the ECU with a
    /// `67 02` positive response, so they are ground truth, not synthetic vectors.
    #[test]
    fn matches_keys_the_ecu_accepted() {
        // From car/logging/j2534_shim.log — ECU replied 67 02 (accepted).
        assert_eq!(calculate_key([0xA1, 0x5B, 0xAD, 0x3F]), [0x01, 0xB1, 0x1E, 0xA4]);
        // From the FastECU sh7058 run — "Seed key ok".
        assert_eq!(calculate_key([0x51, 0x66, 0xD5, 0x04]), [0x03, 0x43, 0x46, 0x36]);
        // From the FastECU sh7055_04 run — "Seed key ok".
        assert_eq!(calculate_key([0xC0, 0xA5, 0x76, 0x99]), [0x02, 0x12, 0x2B, 0x02]);
    }

    #[test]
    fn checksum_matches_real_frames() {
        // TX: 80 10 F0 06 27 02 01 B1 1E A4 | 23
        let tx = [0x80, 0x10, 0xF0, 0x06, 0x27, 0x02, 0x01, 0xB1, 0x1E, 0xA4];
        assert_eq!(checksum(&tx), 0x23);
        // RX: 80 F0 10 06 67 01 A1 5B AD 3F | D6
        let rx = [0x80, 0xF0, 0x10, 0x06, 0x67, 0x01, 0xA1, 0x5B, 0xAD, 0x3F];
        assert_eq!(checksum(&rx), 0xD6);
    }

    /// A different seed must give a different key — guards against a degenerate port that
    /// returns a constant and would silently "pass" the vectors above.
    #[test]
    fn distinct_seeds_give_distinct_keys() {
        assert_ne!(calculate_key([0x00, 0x00, 0x00, 0x00]), calculate_key([0xFF, 0xFF, 0xFF, 0xFF]));
        assert_ne!(calculate_key([0xA1, 0x5B, 0xAD, 0x3F]), calculate_key([0xA1, 0x5B, 0xAD, 0x40]));
    }
}
