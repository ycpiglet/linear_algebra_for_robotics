-- Resolve source-document links in Quarto's single-file EPUB book.
--
-- Quarto concatenates a book and leaves file-boundary metadata markers in the
-- AST.  Two top-down passes are required: the first indexes every included
-- source file, and the second adds a stable entry anchor and rewrites .qmd/.md
-- links to internal anchors.  Pandoc's EPUB writer then emits chNNN.xhtml links.

local files = {}
local anchored = {}

local function normalize(base, relative)
  relative = relative:gsub("\\", "/")
  local joined
  if relative:sub(1, 1) == "/" then
    joined = relative:sub(2)
  else
    joined = (base == "." or base == "") and relative or (base .. "/" .. relative)
  end

  local parts = {}
  for part in joined:gmatch("[^/]+") do
    if part == ".." then
      if #parts == 0 then
        error("EPUB source link escapes the project root: " .. joined)
      end
      table.remove(parts)
    elseif part ~= "." and part ~= "" then
      table.insert(parts, part)
    end
  end
  return table.concat(parts, "/")
end

local function anchor(path)
  return "qmd-" .. path:gsub(".", function(character)
    return string.format("%02x", string.byte(character))
  end)
end

local function current_file()
  local state = quarto.doc.file_metadata()
  return state and state.file or nil
end

local collect = quarto.utils.combineFilters({
  quarto.utils.file_metadata_filter(),
  {
    Header = function(element)
      local file = current_file()
      if file and file.bookItemFile then
        files[normalize(".", file.bookItemFile)] = true
      end
      return element
    end,
  },
})
collect.traverse = "topdown"

local rewrite = quarto.utils.combineFilters({
  quarto.utils.file_metadata_filter(),
  {
    Header = function(element)
      local file = current_file()
      if element.level == 1 and file and file.bookItemFile then
        local source = normalize(".", file.bookItemFile)
        if not anchored[source] then
          anchored[source] = true
          table.insert(
            element.content,
            1,
            pandoc.Span({}, pandoc.Attr(anchor(source), { "source-anchor" }))
          )
        end
      end
      return element
    end,
    Link = function(element)
      if element.target:match("^[%a][%w+.-]*:") or element.target:sub(1, 2) == "//" then
        return element
      end

      local before_fragment, fragment = element.target:match("^([^#]*)(.*)$")
      local path = before_fragment:match("^([^?]*)")
      if not path:lower():match("%.q?md$") then
        return element
      end
      path = path:gsub("%%(%x%x)", function(hexadecimal)
        return string.char(tonumber(hexadecimal, 16))
      end)

      local file = current_file()
      if not (file and file.bookItemFile) then
        return element
      end
      local target = normalize(file.resourceDir or ".", path)
      if not files[target] then
        error("EPUB source link target is not an included book file: " .. target)
      end

      -- Existing section anchors remain the most precise destination.  Bare
      -- file links use the stable entry anchor inserted above.
      element.target = fragment ~= "" and fragment or ("#" .. anchor(target))
      return element
    end,
  },
})
rewrite.traverse = "topdown"

if FORMAT:match("epub") then
  return { collect, rewrite }
end
return {}
