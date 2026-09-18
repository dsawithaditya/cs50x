import json
import os
import zipfile

HAT_OPCODES = {
    "event_whenflagclicked",
    "event_whenkeypressed",
    "event_whenbroadcastreceived",
    "event_whenbackdropswitchesto",
    "event_whenthisspriteclicked",
    "control_start_as_clone",
    "procedures_definition"
}

def scripts(target):
    """Return the ids of the blocks that start a real script in target"""
    return [block_id for block_id, block in target["blocks"].items()
            if isinstance(block, dict) and block.get("topLevel") and block["opcode"] in HAT_OPCODES]

def reachable_blocks(target):
    """Yield the blocks reachable from a hat block, following next and inputs"""
    blocks = target["blocks"]
    visited = set()
    pending = scripts(target)

    while pending:
        block_id = pending.pop()
        if block_id in visited:
            continue
        visited.add(block_id)

        block = blocks.get(block_id)
        if not isinstance(block, dict):
            continue

        yield block

        if block.get("next") is not None:
            pending.append(block["next"])

        # Within an input, a string member is the id of a nested block.
        for value in block.get("inputs", {}).values():
            if isinstance(value, list):
                pending.extend(item for item in value if isinstance(item, str))

def used_variables(project):
    """Return the ids of the variables that project's scripts reference"""
    used = set()

    for target in project:
        for block in reachable_blocks(target):
            # Set, change, show and hide name their variable in a field.
            field = block.get("fields", {}).get("VARIABLE")
            if field:
                used.add(field[1])

            # A variable read inside an input is inlined as [12, name, id].
            for value in block.get("inputs", {}).values():
                if isinstance(value, list):
                    used.update(item[2] for item in value
                                if isinstance(item, list) and len(item) > 2 and item[0] == 12)

    return used

def contains_blocks(project, opcodes):
    """Return whether project's scripts contain any blocks with their names in opcodes"""
    return any(block["opcode"] in opcodes
               for target in project
               for block in reachable_blocks(target))

def test_cs50_scratch():
    # 1. Check filename
    filenames = [filename for filename in os.listdir() if filename.endswith(".sb3")]
    assert len(filenames) == 1, f"Found {len(filenames)} .sb3 files"
    filename = filenames[0]
    print(f"PASS: Single .sb3 file found ({filename})")

    # 2. Check valid zip and project.json
    with zipfile.ZipFile(filename, 'r') as z:
        assert "project.json" in z.namelist(), "project.json not found in archive"
        with z.open("project.json") as f:
            project_data = json.load(f)
    project = project_data["targets"]
    print("PASS: Valid .sb3 and project.json")

    # 3. Two sprites check
    num_sprites = sum(not target["isStage"] for target in project)
    assert num_sprites >= 2, f"Expected at least 2 sprites, found {num_sprites}"
    print(f"PASS: Two sprites (found {num_sprites} sprites)")

    # 4. Non-cat check
    cat_sprite_ids = {"bcf454acf82e4504149f7ffe07081dbc", "0fb9be3e8397c983338cb71dc84d0b25"}
    has_non_cat = not all(target["isStage"] or {costume["assetId"] for costume in target["costumes"]} <= cat_sprite_ids for target in project)
    assert has_non_cat, "No non-cat sprite found"
    print("PASS: Non-cat sprite verified")

    # 5. Three scripts check
    num_scripts = sum(len(scripts(target)) for target in project)
    assert num_scripts >= 3, f"Expected >= 3 scripts, found {num_scripts}"
    print(f"PASS: Three scripts (found {num_scripts} scripts across all targets)")

    # 6. Uses condition check
    has_condition = contains_blocks(project, ["control_repeat", "control_if_else", "control_if", "motion_ifonedgebounce"])
    assert has_condition, "No condition found"
    print("PASS: Uses conditional")

    # 7. Uses loop check
    has_loop = contains_blocks(project, ["control_forever", "control_repeat_until", "control_repeat"])
    assert has_loop, "No loop found"
    print("PASS: Uses loop")

    # 8. Uses variable check
    declared = {variable_id for target in project for variable_id in target["variables"]}
    used = used_variables(project)
    assert declared & used, f"No variables used: declared={declared}, used={used}"
    print(f"PASS: Uses variable ({declared & used})")

    # 9. Uses custom block check
    custom_block_found = False
    for target in project:
        for block in target["blocks"].values():
            if isinstance(block, dict) and block["opcode"] == "procedures_definition":
                prototype = target["blocks"][block["inputs"]["custom_block"][1]]
                if len(json.loads(prototype["mutation"]["argumentids"])) >= 1:
                    custom_block_found = True
                    break
    assert custom_block_found, "No custom block taking at least one input found"
    print("PASS: Uses custom block with at least one input")

    print("\nALL CS50 SCRATCH CHECKS PASSED WITH FLYING COLORS! 🚀")

if __name__ == "__main__":
    test_cs50_scratch()
