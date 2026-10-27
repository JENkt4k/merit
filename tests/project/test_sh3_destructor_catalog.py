"""Native destructor-section validation preserves the snapshot contract."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from merit.project.build import build, interpret
from merit.project.loader import load_project


def test_native_destructor_catalog_rejects_malformed_sections(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    root = tmp_path / "catalog"
    shutil.copytree(repository / "examples/projects/bootstrap_lexer", root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    lexer = root / "src" / "lexer.mrt"
    lexer_source, renamed = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
                                    lexer.read_text(encoding="utf-8"), count=1)
    assert renamed == 1
    lexer.write_text(lexer_source, encoding="utf-8", newline="\n")
    (root / "src" / "destructor_catalog_probe.mrt").write_text(
        """module destructor_catalog_probe
import bootstrap_mir_functions;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_bundle;
capability allocate;
fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  var descriptors:Vec<MirDestructorDescriptor>=vec_new<MirDestructorDescriptor>(allocator,2);
  var body:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,0);
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,0);
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,0);
  print(canonical_mir_validate_destructor_sections(descriptors,body,cfg,placements));
  vec_push<MirDestructorDescriptor>(descriptors,function_mir_destructor_descriptor(1,0,1,0,0,0,0));
  print(canonical_mir_validate_destructor_sections(descriptors,body,cfg,placements));
  drop(descriptors);
  var unordered:Vec<MirDestructorDescriptor>=vec_new<MirDestructorDescriptor>(allocator,1);
  vec_push<MirDestructorDescriptor>(unordered,function_mir_destructor_descriptor(1,1,0,0,0,0,0));
  print(canonical_mir_validate_destructor_sections(unordered,body,cfg,placements));
  drop(unordered);
  var duplicates:Vec<MirDestructorDescriptor>=vec_new<MirDestructorDescriptor>(allocator,2);
  vec_push<MirDestructorDescriptor>(duplicates,function_mir_destructor_descriptor(1,0,0,0,0,0,0));
  vec_push<MirDestructorDescriptor>(duplicates,function_mir_destructor_descriptor(1,0,0,0,0,0,0));
  print(canonical_mir_validate_destructor_sections(duplicates,body,cfg,placements));
  drop(duplicates);
  var invalid_type:Vec<MirDestructorDescriptor>=vec_new<MirDestructorDescriptor>(allocator,1);
  vec_push<MirDestructorDescriptor>(invalid_type,function_mir_destructor_descriptor(0,0,0,0,0,0,0));
  print(canonical_mir_validate_destructor_sections(invalid_type,body,cfg,placements));
  drop(invalid_type);drop(placements);drop(cfg);drop(body);
 }
 return 0;
}
""", encoding="utf-8", newline="\n",
    )
    manifest = root / "Merit.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace('entry = "src/lexer.mrt"', 'entry = "src/destructor_catalog_probe.mrt"'),
        encoding="utf-8", newline="\n",
    )
    project = load_project(manifest)
    interpreted = interpret(project)
    _, _, executable = build(project, tmp_path / "build" / "catalog")
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert native == interpreted == "0\n1\n2\n3\n1\n"
