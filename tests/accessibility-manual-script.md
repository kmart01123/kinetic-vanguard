# Accessibility manual script

This script is evidence guidance. A completed report must bind results to a verified release build-manifest hash.

| ID | Profile | Action | Expected result | Pass criteria |
|---|---|---|---|---|
| NAME-001 | both | Load the publication and reach Name by keyboard. | Placeholder is “Select a rule by name”; Open remains tabbable with `aria-disabled=true`, accessible name “Open selected rule”, and described by “Select a rule name, then choose Open.” | All states and strings match; activating Open changes nothing and announces nothing. |
| NAME-002 | both | Change Name while classification filters are active. | No navigation, filter clearing, focus move, URL change, or history write occurs. | State remains unchanged except the selected option and Open name/state. |
| NAME-003 | both | Select a valid Name and activate Open. | Open name is “Open {entity title}”; activation pushes history, focuses the authoritative heading, clears destination filters, and resets Name. | Heading receives focus and title is not duplicated in the live region. |
| HIST-001 | both | Use Back and Forward after NAME-003. | Back restores prior classifications; Forward restores destination; Name is placeholder and Open is aria-disabled in both. | Exact route state restores without transient Name state. |
| ROUTE-001 | both | Load a valid entity fragment. | Entity topic loads; Name remains placeholder. | One or fewer consolidated notices; no unexpected focus move. |
| FILTER-001 | both | Change single- and multi-select facets. | One settled announcement reports result and availability changes. | No live-region storm; focus remains stable. |
| RESULT-001 | both | Activate a result with a disambiguated fixture/title. | Visible and accessible identity contains authoritative title and primary area. | Exact required composition is used. |
| NAV-001 | both | Change category and topic selectors and follow a related link. | Only valid dependent options appear and changes are announced. | All controls work by keyboard. |
| STATUS-P | prototype | Inspect the artifact status. | Prototype banner is visible and exposed to accessibility APIs. | Banner is unmistakable after copying the file. |
| STATUS-R | release | Inspect the artifact status. | Prototype banner is absent. | Release metadata reports release. |
