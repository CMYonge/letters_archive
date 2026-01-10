local stringify = pandoc.utils.stringify

local function meta_get(meta, key)
  if not meta then
    return nil
  end
  local value = meta[key]
  if value == nil then
    return nil
  end
  local text = stringify(value)
  if text == "" then
    return nil
  end
  return text
end

local function para(label, value)
  return pandoc.Para({
    pandoc.Strong(pandoc.Str(label .. ":")),
    pandoc.Space(),
    pandoc.Str(value),
  })
end

local function build_block(meta, pairs)
  local blocks = {}
  for _, pair in ipairs(pairs) do
    local label = pair[1]
    local key = pair[2]
    local value = meta_get(meta, key)
    if value ~= nil and value ~= "—" then
      table.insert(blocks, para(label, value))
    end
  end
  if #blocks == 0 then
    return nil
  end
  return pandoc.Div(blocks, pandoc.Attr("", { "entity-meta" }))
end

local function meta_has(meta, key)
  return meta_get(meta, key) ~= nil
end

function Pandoc(doc)
  local meta = doc.meta

  local pairs = nil

  -- Quarto renders via an intermediate markdown file, so we can't rely on
  -- PANDOC_STATE.input_files matching the original source path. Instead, infer
  -- entity type from the presence of specific metadata keys.
  if meta_has(meta, "from-name") or meta_has(meta, "to-name") or meta_has(meta, "manuscript-location") then
    pairs = {
      { "Date", "display-date" },
      { "From", "from-name" },
      { "From address", "from-address" },
      { "To", "to-name" },
      { "Manuscript location", "manuscript-location" },
    }
  elseif meta_has(meta, "publication-format") or meta_has(meta, "publication-date") or meta_has(meta, "author-name") then
    pairs = {
      { "Publication date", "publication-date" },
      { "Genre", "genre" },
      { "Format", "publication-format" },
      { "Publisher", "publisher" },
      { "Serialization", "serialization" },
      { "Illustrator", "illustrator" },
      { "Author", "author-name" },
    }
  elseif meta_has(meta, "full-name") or meta_has(meta, "dates") then
    pairs = {
      { "Name", "full-name" },
      { "Dates", "dates" },
      { "Title", "title" },
    }
  elseif meta_has(meta, "reference-type") and meta_has(meta, "name") then
    pairs = {
      { "Type", "reference-type" },
      { "Name", "name" },
    }
  end

  if pairs ~= nil then
    local block = build_block(meta, pairs)
    if block ~= nil then
      table.insert(doc.blocks, 1, block)
    end
  end

  return doc
end
