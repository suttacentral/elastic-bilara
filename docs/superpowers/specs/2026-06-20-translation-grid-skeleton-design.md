# Translation Grid Loading Skeleton

## Goal

Replace the blank central translation area shown during initial data loading with a lightweight skeleton that resembles the translation grid.

## Design

- Add an explicit `loading` boolean to the Alpine component returned by `fetchTranslation()`.
- Keep `loading` true throughout the existing asynchronous `init()` sequence.
- Set `loading` to false in a `finally` block so failed initialization cannot leave the skeleton visible indefinitely.
- Render the skeleton only in the central grid area. Keep navigation, project header, related-project controls, and search panel unchanged.
- Render the real translation grid only after loading completes.
- Use translation-specific CSS class names and a shimmer animation consistent with the existing Git status skeleton.
- Use a fixed representative layout rather than deriving skeleton dimensions from data that has not loaded yet.

## Error Behavior

The skeleton represents loading only. If initialization fails, it is removed when the request settles and the existing error behavior remains responsible for reporting the failure.

## Testing

- Add or update frontend tests to verify the component starts in the loading state and clears it after successful or failed initialization.
- Run the focused translation frontend test suite.

## Scope

No API, data-loading order, translation rendering, or search-panel behavior changes are included.
