-- Root-project entry point for the Knowledge Atlas metadata filter.
-- The implementation also serves the installable extension.

local script_file = PANDOC_SCRIPT_FILE or "platform/filters/concept-page.lua"
local script_directory = pandoc.path.directory(script_file)
local implementation = pandoc.path.join({script_directory, "..", "extension", "atlas-metadata.lua"})
dofile(implementation)
