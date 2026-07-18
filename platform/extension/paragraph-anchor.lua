-- Stable paragraph anchors for the editorial workflow (Phase 1-1).
--
-- Every prose paragraph gets a leading empty <span> whose id is derived from
-- a content hash ("p-" .. first 8 hex chars of sha1 of the stringified text),
-- so unchanged paragraphs keep their anchor across renders and manuscript
-- edits elsewhere in the file.  Formatting-only edits also keep the anchor
-- because stringify() drops inline markup.  Code blocks and tables carry
-- attributes natively, so they receive the id directly instead of a span.
--
-- The anchor is an empty inline span, not a wrapping Div: the DOM shape of
-- rendered paragraphs stays identical, so themes and Quarto's own paragraph
-- handling are unaffected.
--
-- Applies to HTML and EPUB output only (the PDF edition addresses text by
-- section numbering instead).  Duplicate paragraph text within one document
-- gets a deterministic "-2", "-3" suffix; note that the EPUB build hashes the
-- whole book as one document, so duplicated text can suffix differently there
-- than on the website.

local seen = {}

local function anchor_id(text)
  local base = "p-" .. pandoc.utils.sha1(text):sub(1, 8)
  local count = (seen[base] or 0) + 1
  seen[base] = count
  if count == 1 then
    return base
  end
  return base .. "-" .. count
end

local function is_figure_paragraph(paragraph)
  -- A paragraph holding only an image is Quarto's implicit-figure form;
  -- leave it untouched so figure processing and its own ids stay intact.
  for _, inline in ipairs(paragraph.content) do
    if inline.t ~= "Image" and inline.t ~= "Space" and inline.t ~= "SoftBreak" then
      return false
    end
    if inline.t == "Image" then
      return true
    end
  end
  return false
end

local filter = {
  Para = function(paragraph)
    if #paragraph.content == 0 or is_figure_paragraph(paragraph) then
      return paragraph
    end
    local text = pandoc.utils.stringify(paragraph)
    if #text < 2 then
      return paragraph
    end
    table.insert(
      paragraph.content,
      1,
      pandoc.Span({}, pandoc.Attr(anchor_id(text), { "paragraph-anchor" }))
    )
    return paragraph
  end,
  CodeBlock = function(block)
    if block.identifier == "" and #block.text > 0 then
      block.identifier = anchor_id(block.text)
      return block
    end
    return block
  end,
  Table = function(block)
    if block.identifier == "" then
      block.identifier = anchor_id(pandoc.utils.stringify(block.caption.long or {}) ..
        "|" .. tostring(#block.bodies))
      return block
    end
    return block
  end,
}

if FORMAT:match("html") or FORMAT:match("epub") then
  return { filter }
end
return {}
