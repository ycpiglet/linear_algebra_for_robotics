-- Give every rendered web document a URL-independent identity.
--
-- Hypothesis combines DC.relation.ispartof and DC.identifier for ordinary
-- HTML documents.  Both values are independent of the repository URL, so
-- repository and GitHub Pages renames do not split a page's annotation
-- identity.

local function html_escape(value)
  return tostring(value)
    :gsub("&", "&amp;")
    :gsub('"', "&quot;")
    :gsub("<", "&lt;")
    :gsub(">", "&gt;")
end

local function percent_encode(value)
  return (tostring(value):gsub("[^A-Za-z0-9._~-]", function(byte)
    return string.format("%%%02X", string.byte(byte))
  end))
end

local function repository_relative_source()
  if quarto == nil or quarto.doc == nil or quarto.project == nil then
    error("document identity requires a Quarto project render")
  end
  local source = quarto.doc.input_file
  local project = quarto.project.directory
  if source == nil or source == "" or project == nil or project == "" then
    error("document identity requires input file and project directory")
  end
  local relative = pandoc.path.make_relative(source, project):gsub("\\", "/")
  relative = relative:gsub("^%./", "")
  if relative == ".." or relative:match("^%.%./") or relative:match("/%.%./") then
    error("document identity source escapes the project root: " .. relative)
  end
  if relative == "" then
    error("document identity source path is empty")
  end
  return relative
end

function Meta(meta)
  if not quarto.doc.is_format("html:js") then
    return meta
  end
  local source = repository_relative_source()
  local identifier = "urn:robotics-math-atlas:document:v1:" .. percent_encode(source)
  quarto.doc.include_text(
    "in-header",
    '<meta name="DC.relation.ispartof" content="robotics-math-atlas">\n' ..
    '<meta name="DC.identifier" content="' .. html_escape(identifier) .. '">'
  )
  return meta
end
