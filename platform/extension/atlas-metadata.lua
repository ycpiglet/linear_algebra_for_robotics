-- Expose stable Knowledge Atlas metadata to the static web UI.
--
-- Add this filter in _quarto.yml:
--
--   filters:
--     - platform/extension/atlas-metadata.lua
--
-- The marker is deliberately an empty, hidden div.  Content remains fully
-- readable without JavaScript, while web enhancements have one stable contract.

local page = nil

local function stringify(value)
  if value == nil then
    return nil
  end
  local rendered = pandoc.utils.stringify(value)
  if rendered == "" then
    return nil
  end
  return rendered
end

local function html_escape(value)
  return tostring(value)
    :gsub("&", "&amp;")
    :gsub('"', "&quot;")
    :gsub("<", "&lt;")
    :gsub(">", "&gt;")
end

local function project_offset()
  if quarto == nil or quarto.project == nil then
    return ""
  end
  local candidate = quarto.project.offset
  if type(candidate) == "function" then
    local ok, result = pcall(candidate)
    if ok then
      candidate = result
    else
      candidate = nil
    end
  end
  if candidate == nil then
    return ""
  end
  candidate = tostring(candidate)
  if candidate == "." then
    return ""
  end
  if candidate ~= "" and candidate:sub(-1) ~= "/" then
    candidate = candidate .. "/"
  end
  return candidate
end

function Meta(meta)
  local identifier = stringify(meta.id)
  local domain = stringify(meta.domain)
  local one_line = stringify(meta.one_line or meta["one-line"])

  -- Proof and path documents also have stable IDs.  Domain + one_line is the
  -- concept-page discriminator, so the concept UI never mounts on those pages.
  if identifier == nil or domain == nil or one_line == nil then
    page = nil
    return meta
  end

  local configured_manifest = stringify(meta.atlas_manifest or meta["atlas-manifest"])
  local offset = project_offset()
  local manifest_path = configured_manifest or "platform/generated/concept-manifest.json"
  local manifest_url = manifest_path
  if not manifest_path:match("^/") and not manifest_path:match("^https?://") then
    manifest_url = offset .. manifest_path
  end

  page = {
    id = identifier,
    domain = domain,
    manifest_path = manifest_path,
    manifest_url = manifest_url,
    project_offset = offset,
  }
  return meta
end

function Pandoc(document)
  if page == nil or not FORMAT:match("html") then
    return document
  end

  local marker = string.format(
    '<div id="concept-meta" class="concept-meta" hidden aria-hidden="true" ' ..
      'data-atlas-schema-version="1.0.0" data-concept-id="%s" ' ..
      'data-concept-domain="%s" data-manifest-path="%s" ' ..
      'data-manifest-url="%s" data-project-offset="%s"></div>',
    html_escape(page.id),
    html_escape(page.domain),
    html_escape(page.manifest_path),
    html_escape(page.manifest_url),
    html_escape(page.project_offset)
  )
  table.insert(document.blocks, 1, pandoc.RawBlock("html", marker))
  return document
end
