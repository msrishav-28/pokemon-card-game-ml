# Official card data

The unchanged CSV files in this directory are the repository's card-data
inputs. The frozen player uses `EN Card Data.csv`; the build script copies
that file into the portable bundle and records its SHA-256.

The operator also supplied four card-ID reference PDFs. They are not read by
the player, evaluator, tests, or bundle, and each exceeds GitHub's per-file
limit. The local copies are preserved unchanged but intentionally ignored by
Git.

| Local file | Bytes | SHA-256 |
|---|---:|---|
| `Card_ID List_EN.pdf` | 137,654,485 | `1931b6880b3568cc3b8af00ee2f62512138fb9292d00ccbe2d0278c7e6d58432` |
| `Card_ID List_EN_.pdf` | 137,654,485 | `1931b6880b3568cc3b8af00ee2f62512138fb9292d00ccbe2d0278c7e6d58432` |
| `Card_ID List_JP.pdf` | 182,284,028 | `ca963b82e1da854c19597928e4c11b223c118468a797545d1b3db75ee3b07e74` |
| `Card_ID List_JP_.pdf` | 182,284,028 | `ca963b82e1da854c19597928e4c11b223c118468a797545d1b3db75ee3b07e74` |

Their duplicate hashes are expected: the underscored and non-underscored
copies are byte-identical within each language.
