# NewsExplorer data validation

`validate_data.py` checks the JSON export used by the NewsExplorer website. Run it from the project directory:

```bash
python validate_data.py
```

Use another data directory with `--data`:

```bash
python validate_data.py --data path/to/data
```

The command passes only when there are zero errors. `--strict` also treats warnings as failures:

```bash
python validate_data.py --strict
```

## Required files

The data directory must contain:

```text
data/
  topics.json
  dailytopicfreq.json
  monthlytopicfreq.json
  documents/
    topic_<id>.json
```

`metadata.json` is optional. The current website does not read it, but if it exists it must contain valid JSON whose root is an object or an array.

All JSON files must be UTF-8 encoded and contain valid JSON.

## `topics.json`

The root value must be an array of topic objects. Each topic must have a unique integer `Topic` value. Topic ID `-1` is allowed for outliers.

A topic can contain the following fields:

| Field | Required in practice | Type and rules | Used for |
| --- | --- | --- | --- |
| `Topic` | Yes | Integer; unique across the file | Topic ID and URL routing |
| `Count` | Yes for a non-empty topic | Non-negative integer | Headline count and consistency checks |
| `Name` | Recommended | String when present; defaults to `"<id>_topic"` | Fallback display name |
| `Custom Name` | Optional | String when present | Display name shown by the website |
| `Representation` | Recommended | Array of strings; defaults to `[]` | Topic words shown in the topic list and search |
| `word_weight` | Optional | Array of `[word, weight]` pairs; word is a string and weight is a non-negative finite number | Word cloud and ranked word list |
| `perc` | Recommended | Non-negative finite number; defaults to `0` | Percentage shown in the topic list and topic page |
| `Representative_Docs` | Optional | Array of strings; defaults to `[]` | Representative text available to the loader |

Example:

```json
{
  "Topic": 0,
  "Name": "0_president_minister_government",
  "Custom Name": "Government and ministers",
  "Representation": ["president", "minister", "government"],
  "Count": 1234,
  "perc": 12.34,
  "word_weight": [
    ["president", 0.85],
    ["minister", 0.62]
  ],
  "Representative_Docs": ["Example representative headline"]
}
```

Although several fields have defaults in the loader, a topic's `Count` should be supplied and should match the corresponding document file and monthly frequency total. Missing `Count` is treated as `0`, so a topic with documents or monthly frequencies will fail the consistency check.

## Frequency files

Both frequency files must have an array root. Every row must contain:

```json
{
  "date": "2024-03-17",
  "topic_id": 0,
  "frequency": 12
}
```

Rules for both files:

- `topic_id` must be an integer listed in `topics.json`.
- `frequency` must be a non-negative integer.
- There may be only one row for each `date` and `topic_id` pair within a file.
- A date must use zero-padded numeric components.

### `dailytopicfreq.json`

`date` must be a real calendar date in `YYYY-MM-DD` format, for example `2024-02-29`. Invalid dates such as `2023-02-29` fail.

### `monthlytopicfreq.json`

`date` must be a month in `YYYY-MM` format, for example `2024-02`. It must not include a day.

For each topic, the sum of its monthly `frequency` values must equal that topic's `Count` in `topics.json`. The validator checks this monthly total because the website uses the monthly file for the topic timeline.

The validator checks the shape of daily rows but does not compare daily totals with `Count`.

## Document files

The `documents/` directory must contain one JSON file for every topic ID in `topics.json`, including `topic_-1.json` when topic `-1` exists:

```text
documents/topic_0.json
documents/topic_1.json
documents/topic_-1.json
```

Each file must have an array root. Each array item must be an object with the following fields:

| Field | Required | Type and rules |
| --- | --- | --- |
| `headline` or `text` | At least one | At least one must be a string. If both exist, both must be strings. |
| `topic_id` | Yes | Integer equal to the ID in the filename |
| `probability` | Yes | Finite number from `0` through `1` |
| `year` | Yes | Positive integer |
| `month` | Yes | Full month name, three-letter month name, or integer `1` through `12` |
| `day` | Yes | Valid day for the supplied year and month |
| `published_time` | Optional | String or `null`; accepted as `H:MM`, `HH:MM`, `H:MM:SS`, optionally followed by `am` or `pm` |
| `url` | Optional | String when present; an empty string is allowed |
| `category` | Optional | String when present; an empty string is allowed |

Example:

```json
{
  "headline": "A news headline",
  "url": "https://example.com/article",
  "category": "Breaking News",
  "topic_id": 0,
  "probability": 0.734,
  "year": 2024,
  "month": "March",
  "day": 17,
  "published_time": "8:40 am"
}
```

`headline`-only records are valid. If `headline` is absent, `text` must be a string and is used as the fallback headline by the loader. A missing or non-string value for both fields fails.

Month names are case-sensitive and must be English full names or three-letter names, such as `March` or `Mar`. Numeric months are also accepted by the validator and loader. Dates must be real dates, so April 31 and February 30 fail.

The number of records in `documents/topic_<id>.json` must equal that topic's `Count`.

## Cross-file rules

A complete passing export satisfies all of these relationships:

- Every topic ID is unique.
- Every frequency row refers to an ID in `topics.json`.
- Every document filename refers to an ID in `topics.json`.
- Every topic ID has a corresponding document file.
- Every document's `topic_id` matches its filename.
- Each topic's document count equals its `Count`.
- Each topic's monthly frequency total equals its `Count`.
- Every probability is between `0` and `1`.
- Every date and time has an accepted, valid format.

## Common failure causes

- Using `YYYY-MM-DD` in `monthlytopicfreq.json` instead of `YYYY-MM`.
- Omitting `topic_-1.json` when `-1` appears in `topics.json`.
- Using a topic ID in a document that does not match its filename.
- Having `Count` disagree with the number of document records.
- Having monthly frequencies that do not add up to `Count`.
- Supplying `null` for both `headline` and `text`.
- Using probabilities outside the inclusive range `0..1`.
- Supplying invalid calendar dates or unsupported time strings.

A successful run ends with:

```text
Errors: 0  Warnings: 0
VALIDATION PASSED
```
