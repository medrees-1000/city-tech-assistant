# Dry check of the chain walk against the golds (step 4b, part 3)

The walk is `cta.graph.chain` (the tool), the extraction runs on the question text. No model call.

| id | extraction | walk (records) | levels | truncated | gold sources | missing from walk | extra in walk | note |
|---|---|---|---|---|---|---|---|---|
| q76 | code CST 2412 | CST 2412, CST 2402, CST 1201, CST 1204, MAT 1375, CST 1100, CST 1101, MAT 1275, MAT 1275CO | 3 | False | CST 2412, CST 2402, CST 1201, CST 1204, MAT 1375, CST 1100, CST 1101, MAT 1275, MAT 1275CO | - | - |  |
| q77 | code EET 2150 | EET 2150, EET 1222, EET 1122, MAT 1375, EET 1102, MAT 1275, MAT 1275CO | 3 | False | EET 2150, EET 1222, EET 1122, MAT 1375, EET 1102, MAT 1275, MAT 1275CO | - | - |  |
| q78 | code MAT 1375 | MAT 1375, MAT 1275, MAT 1275CO | 1 | False | MAT 1375, MAT 1275, MAT 1275CO | - | - |  |
| q79 | code EET 3572 | EET 3572 | 0 | False | EET 3572 | - | - |  |
| q80 | code MAT 1372 | MAT 1372, MAT 1275CO, MAT 1275 | 1 | False | MAT 1372, MAT 1275CO, MAT 1275 | - | - |  |
| q81 | code CST 2304 | CST 2304 | 0 | False | CST 2304 | - | - |  |
| q82 | code CST 3508 | CST 3508 | 0 | False | - | - | CST 3508 | unanswerable: the text is shorthand (UNPARSED), the walk shows it verbatim; the gold has no sources by the unanswerable convention (reference record catalog:CST 3508) |
| q83 | code CST 4999 | - | - | - | - | - | - | ABSTAIN: no record, the chain node abstains; the gold has no sources |
| q84 | code ENG 1101 | - | - | - | - | - | - | ABSTAIN: no record in the four departments; the chain node abstains; the gold has no sources |
| q85 | title CST 3504 | CST 3504, CST 1204, CST 1100, CST 1101 | 2 | False | CST 3504, CST 1204, CST 1100, CST 1101 | - | - |  |
| q86 | code DEN 1100 | DEN 1100, DEN 1112 | 1 | False | DEN 1100, DEN 1112 | - | - |  |
| q87 | code MAT 2440 | MAT 2440, MAT 1375, CST 1201, CST 2403, MAT 1630, MAT 1275, MAT 1275CO, CST 1100, CST 1101, MAT 1475 | 2 | False | MAT 2440 | - | MAT 1375, CST 1201, CST 2403, MAT 1630, MAT 1275, MAT 1275CO, CST 1100, CST 1101, MAT 1475 | control, not a chain question: the classifier must not send it to the chain tool; the gold is the root record only |
| q22 | code MAT 2675 | MAT 2675, MAT 1575, MAT 2580, MAT 1475, MAT 1375, MAT 1275, MAT 1275CO | 4 | True | MAT 2675 | - | MAT 1575, MAT 2580, MAT 1475, MAT 1375, MAT 1275, MAT 1275CO | older gold lists the root only (its gold answer text names the chain); the walk adds the whole chain |
| q39 | code CST 3602 | CST 3602, CST 3512, MAT 2572, CST 2312, MAT 1575, CST 1101, MAT 1475, MAT 1375 | 4 | True | CST 3602, CST 3512, CST 2312, CST 1101, MAT 2572, MAT 1575, MAT 1475, MAT 1375, MAT 1275, MAT 1275CO | MAT 1275, MAT 1275CO | - | older gold has MAT 1275 and MAT 1275CO at level 5, beyond the depth limit of 4 (the walk records the cut) |
| q40 | code CST 3613 | CST 3613, CST 1201, CST 1204, CST 1100, CST 1101 | 2 | False | CST 3613, CST 1201, CST 1100, CST 1101, CST 1204 | - | - |  |

Unexplained differences: none.
