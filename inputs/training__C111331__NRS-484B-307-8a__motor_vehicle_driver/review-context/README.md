# C111331 / NRS-484B-307-8a

## Law

**NRS-484B-307-8a — Traffic controlled by official traffic-control devices (8)(a)**

> Where the signal is a steady red signal alone: Vehicular traffic facing the signal must stop before entering the crosswalk on the nearest side of the intersection where the sign or pavement marking indicates where the stop must be made, or in the absence of any such crosswalk, sign or marking, then before entering the intersection, and, except as otherwise provided in paragraphs (c) and (d) [(c) is appended below, NRS-484B-307-8d], must remain stopped or standing until the green signal is shown. After complying with the requirement to stop, vehicular traffic facing such a signal and situated on the extreme right of the highway may proceed into the intersection for a right turn only when the intersecting highway is two-directional or one-way to the right, or vehicular traffic facing such a signal and situated on the extreme left of a one-way highway may proceed into the intersection for a left turn only when the intersecting highway is one-way to the left, but must yield the right-of-way to pedestrians and other traffic proceeding as directed by the signal at the intersection.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Absence

Comparison: `C111331-absence-v1-stop-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111331-absence-v1-307-8a-no-stop--c927dbeb68c5/video.webm) · [trace](C111331-absence-v1-307-8a-no-stop--c927dbeb68c5/trace.json) · [metadata](C111331-absence-v1-307-8a-no-stop--c927dbeb68c5/metadata.json) | Commanded turn path.remain stopped until actual green: false; Commanded turn path.stop before intersection: false | 2 | None listed | violation |
| 2 | [video](C111331-absence-v1-307-8a-stop-until-green--52ce818c60c1/video.webm) · [trace](C111331-absence-v1-307-8a-stop-until-green--52ce818c60c1/trace.json) · [metadata](C111331-absence-v1-307-8a-stop-until-green--52ce818c60c1/metadata.json) | Commanded turn path.remain stopped until actual green: true; Commanded turn path.stop before intersection: true | 1 | None listed | compliant |

Case IDs: 1: `C111331-absence-v1-307-8a-no-stop`; 2: `C111331-absence-v1-307-8a-stop-until-green`.

### Focused nrs 484b 307 8a comparison

Comparison: `C111331-focused-NRS-484B-307-8a-comparison`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111331-focused-307-8a-no-stop--7c258538b0b0/video.webm) · [trace](C111331-focused-307-8a-no-stop--7c258538b0b0/trace.json) · [metadata](C111331-focused-307-8a-no-stop--7c258538b0b0/metadata.json) | Commanded turn path.stop at red: false | 2 | None listed | violation |
| 2 | [video](C111331-focused-307-8a-stop-until-green--62bbe3d6b420/video.webm) · [trace](C111331-focused-307-8a-stop-until-green--62bbe3d6b420/trace.json) · [metadata](C111331-focused-307-8a-stop-until-green--62bbe3d6b420/metadata.json) | Commanded turn path.stop at red: true | 1 | None listed | compliant |

Case IDs: 1: `C111331-focused-307-8a-no-stop`; 2: `C111331-focused-307-8a-stop-until-green`.

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
