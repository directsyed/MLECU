"""romread, READ-ONLY extraction of table values from a Subaru ROM image via ECUFlash defs.

Strictly one-directional: bytes in, numbers out. There is deliberately no write/patch path in
this package, ROM writes stay behind safety.apply_proposal + human review (the hard constraint).
"""
from .defs import EcuFlashDefs, TableDef
from .reader import RomImage, read_semantic_tables, read_table

__all__ = ["EcuFlashDefs", "TableDef", "RomImage", "read_table", "read_semantic_tables"]
