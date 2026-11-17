# Automatic Arabic RTL / English LTR

The installed desktop UI uses `assets/bidi.js` and `assets/bidi.css` as its shared direction layer. Load the script before text renderers and the stylesheet after component styles.

- Markdown paragraphs, headings, lists and cells determine direction from their own prose. Inline code does not choose the prose language.
- `YoeBidi.plain(text)` presents unformatted messages without changing their text. Plain multiline content retains independent paragraph directions.
- New or streamed DOM content is handled through a bounded, animation-frame-batched observer. Shared renderers also prepare detached content before mounting it.
- Editors use native `dir="auto"`; values, selections and composition are never rewritten. Code, paths, terminal fields, fenced blocks and inline code stay LTR.
- Mixed prose uses DOM `bdi` isolation for technical runs, not reversed characters or injected controls in stored/copyable text. Chart formatters isolate display labels only; datasets and exports retain original values.
- Localized UI containers should set their real `lang` (or call `YoeBidi.setLocale`). English UI remains LTR when a conversation is Arabic. SVG text direction preserves physical anchors; charts and 3D viewports are not mirrored.
- Custom code viewers should declare `data-yoe-code`. Plain document previews should remain prose rather than being marked code merely for monospace styling.

Regression fixtures under `tests_ui` exercise the production shared renderers with synthetic local content. `node Source/tests_ui/bidi.test.cjs` checks direction and isolation without a browser. No AI model, inference prompt or weight is changed by this feature.
