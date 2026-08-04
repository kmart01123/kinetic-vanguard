# Accessibility manual script

This script is evidence guidance. A completed report must bind results to a verified release build-manifest hash.

| ID | Profile | Action | Expected result | Pass criteria |
|---|---|---|---|---|
| NAME-001 | both | Load the publication and reach Name by keyboard. | Placeholder is “Select a rule by name”; the native select has the accessible label “Name” and a visible focus indicator; no Open button is present. | Label, placeholder, focus, and control type match. |
| NAME-002 | both | With classification filters active, open the Name menu and navigate choices without committing one. | No navigation, filter clearing, focus move, URL change, history write, or announcement occurs before the native selection is committed. | State remains unchanged while the menu is only open or being traversed. |
| NAME-003 | both | Commit a valid Name selection with mouse, touch, and keyboard interaction. | One history entry is pushed, the selected card and canonical route appear immediately, destination filters clear, Name stays synchronized, and focus remains on the native select. | Exactly one update occurs with no duplicate title announcement. |
| HIST-001 | both | Use Back and Forward after NAME-003. | Back restores prior classifications and its Name state; Forward restores the destination and selected Name. | Exact route and classification state restore without transient selection activation. |
| ROUTE-001 | both | Load a valid entity fragment. | Entity topic loads and Name synchronizes to the entity. | One or fewer consolidated notices; no unexpected focus move. |
| FILTER-001 | both | Change single- and multi-select facets. | One settled announcement reports result and availability changes. | No live-region storm; focus remains stable. |
| RESULT-001 | both | Activate a result with a disambiguated fixture/title. | Visible and accessible identity contains authoritative title and primary area. | Exact required composition is used. |
| NAV-001 | both | Change category and topic selectors and follow a related link. | Only valid dependent options appear and changes are announced. | All controls work by keyboard. |
| STATUS-P | prototype | Inspect the artifact status. | Prototype banner is visible and exposed to accessibility APIs. | Banner is unmistakable after copying the file. |
| STATUS-R | release | Inspect the artifact status. | Prototype banner is absent. | Release metadata reports release. |
