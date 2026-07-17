-- Build a visible per-document glossary from inline .atlas-term definitions.
--
-- The web enhancement can add the same glossary at runtime, but PDF/EPUB and
-- no-JavaScript HTML need the definitions in the Pandoc AST. In a Quarto book,
-- file metadata markers let us flush each chapter's terms before the next H1.

local current_source = nil
local terms = {}
local seen = {}
local has_existing_glossary = false

local function has_class(element, wanted)
  for _, class_name in ipairs(element.classes or {}) do
    if class_name == wanted then
      return true
    end
  end
  return false
end

local function source_key()
  local state = quarto and quarto.doc and quarto.doc.file_metadata()
  local file = state and state.file or nil
  if file and file.bookItemFile then
    return tostring(file.bookItemFile)
  end
  return "__single_document__"
end

local function reset(next_source)
  current_source = next_source
  terms = {}
  seen = {}
  has_existing_glossary = false
end

local function glossary_block()
  if #terms == 0 or has_existing_glossary then
    return nil
  end

  local definitions = {}
  for _, term in ipairs(terms) do
    local display = term.label
    local label_lower = string.lower(term.label)
    local english_lower = string.lower(term.english)
    local already_bilingual = term.english ~= ""
      and string.find(label_lower, english_lower, 1, true) ~= nil
    if term.english ~= "" and not already_bilingual then
      display = display .. " (" .. term.english .. ")"
    end
    table.insert(definitions, {
      pandoc.Inlines({ pandoc.Strong({ pandoc.Str(display) }) }),
      { pandoc.Blocks({ pandoc.Para({ pandoc.Str(term.definition) }) }) },
    })
  end

  return pandoc.Div(
    {
      pandoc.Para({
        pandoc.Strong({ pandoc.Str("이 페이지의 용어") }),
        pandoc.Space(),
        pandoc.Str("(" .. tostring(#terms) .. "개)"),
      }),
      pandoc.DefinitionList(definitions),
    },
    pandoc.Attr(
      "",
      { "page-glossary", "page-glossary--static" },
      { { "aria-label", "이 페이지의 용어" } }
    )
  )
end

local page_filter = {
  Header = function(element)
    if element.level ~= 1 then
      return nil
    end

    local next_source = source_key()
    if current_source == nil then
      reset(next_source)
      return nil
    end
    if next_source == current_source then
      return nil
    end

    local glossary = glossary_block()
    reset(next_source)
    if glossary then
      return { glossary, element }
    end
    return nil
  end,

  Span = function(element)
    if not has_class(element, "atlas-term") then
      return nil
    end

    local definition = element.attributes["data-definition"] or ""
    local label = pandoc.utils.stringify(element.content)
    if definition == "" or label == "" then
      return nil
    end

    local key = label:lower()
    if not seen[key] then
      seen[key] = true
      table.insert(terms, {
        label = label,
        english = element.attributes["data-en"] or "",
        definition = definition,
      })
    end
    return nil
  end,

  Div = function(element)
    if has_class(element, "page-glossary") then
      has_existing_glossary = true
    end
    return nil
  end,

  Pandoc = function(document)
    local glossary = glossary_block()
    if glossary then
      table.insert(document.blocks, glossary)
    end
    return document
  end,
}

local combined = quarto.utils.combineFilters({
  quarto.utils.file_metadata_filter(),
  page_filter,
})
-- EPUB and Typst book renders concatenate every source document into one AST.
-- Pandoc's default type-wise traversal visits every Header before every Span,
-- which would move all collected terms into one glossary at the end of the
-- book.  A top-down walk keeps file metadata, H1 boundaries and inline terms
-- in their reading order.  HTML is rendered one source file at a time, so its
-- normal type-wise walk must retain the final Pandoc callback that appends the
-- current page's glossary.
if FORMAT:match("epub") or FORMAT:match("typst") then
  combined.traverse = "topdown"
end

return combined
