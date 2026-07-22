// Quarto 1.9 book projects replace the standard Typst show partial with the
// bundled orange-book partial, which does not consume mainfont or codefont.
// Apply the PDF type adapter after that show rule and before body content.
#set text(font: "Atlas Sans KR")
#show raw: set text(font: "Noto Sans Mono CJK KR")
#show emph: it => text(fill: rgb("#6740a5"), underline(it.body))
