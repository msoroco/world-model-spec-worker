"""Apply the exact fallback proof driver to six curve direction cases."""

import complete_remaining_crest_fallbacks as driver

driver.NAMES = (
    "canonical-curve-short-a", "canonical-curve-short-b",
    "canonical-curve-at-a", "canonical-curve-at-b",
    "canonical-curve-beyond-a", "canonical-curve-beyond-b",
)

if __name__ == "__main__":
    driver.main()
