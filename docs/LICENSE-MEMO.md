# Dataset selection and licence memo

Pengjun Lu, 2026-11-06. Written after the archive was downloaded and before any analysis was run, as the first deliverable of retention-bench.

## Purpose

retention-bench publishes, under the author's own name and the MIT licence, three kinds of artifact: code, aggregate results (metric tables, calibration bins, decile tables, model coefficients) and a written label definition. It does not redistribute any raw dataset. Every candidate below was judged on whether its terms permit those three publications, and on whether it holds per-player timestamped activity, since the label must be constructed from behaviour and not read from a column.

## Candidates

Four candidates were named in the work package. Each was checked at its original publisher, not only at a mirror. All URLs were accessed on 2026-11-06.

### WoWAH, World of Warcraft Avatar History: selectedd

- **Publisher.** Lee, Chen, Cheng and Lei, Academia Sinica and National Taiwan University. Y.-T. Lee, K.-T. Chen, Y.-M. Cheng, C.-L. Lei, "World of Warcraft Avatar History Dataset", *Proc. ACM MMSys 2011*. Original host `mmnet.iis.sinica.edu.tw/dl/wowah/` no longer resolves. The last Wayback capture of the website was taken on 2020-02-01
- **Live source.** The ACM MMSys dataset track mirror at WPI, https://web.cs.wpi.edu/~claypool/mmsys-dataset/2011/wow/, serves `wowah.rar` (577,556,091 bytes, last modified 2011-02-19). This is the copy retention-bench downloads.
- **Terms, verbatim.** The paper: "We believe the WOWAH dataset could be used for various creative purposes, now that it is a public asset of the research community. It is available for free download." The MMSys track index: "Use of the datasets in published work should be acknowledged by a full citation to the authors' papers at the MMSys conference." No formal licence text exists at the source. A Kaggle mirror (`mylesoneill/warcraft-avatar-history`, 2008 subset only) carries the field "CC0: Public Domain", but that label was applied by the uploader, not by the authors, and is not relied on here.
- **What this memo relies on.** The authors' own statement that the dataset is a public research asset for free download, plus the citation condition. Publishing derived aggregates and code with the MMSys 2011 citation is squarely within that statement. Redistributing the raw archive is not clearly granted, so retention-bench does not do it. The pipeline downloads from the public host at run time.
- **Contents.** 10-minute snapshots of every online avatar on one realm (TW-Light's Hope, Horde) from 2006-01-01 to 2009-01-10: 91,065 avatars, 667,032 sessions, 138,084 samples. Each record is query time, avatar id, guild id, level, race, class, zone. Avatar and guild names were replaced by random integers by the authors; no account identifiers exist.
- **Fit.** Timestamps per avatar per 10 minutes, so a first-day/next-day label can be constructed. A new avatar is identifiable by its level at first sighting. Tens of thousands of avatars, so cells of ten are easy. Prior work on it includes Tarng, Chen and Huang, "On prophesying online gamer departure", NetGames 2009, and Khan, "Predicting customer churn in World of Warcraft", arXiv:2006.15735 (2020).
- **Limitation.** The unit is an avatar, not a person. One player may create several avatars, so a "new avatar" is a new character, not necessarily a new player. The original paper makes the same assumption and the report states it.

### Cookie Cats: rejected

- **Publisher.** A DataCamp project (no. 184, "Mobile Games A/B Testing with Cookie Cats"), data supplied by Tactile Entertainment. The project page is no longer reachable at its original address.
- **Terms.** No licence at the source. Kaggle mirrors: `yufengsui/mobile-games-ab-testing` reads "Unknown"; `mursideyarkin/mobile-games-ab-testing-cookie-cats` reads "Other (specified in description)" with no terms in the description. DataCamp's Terms of Use (§4.1(d), §7.1) reserve all rights in its materials and forbid redistribution beyond personal use.
- **Contents.** One row per player (90,189 rows): `userid`, `version`, `sum_gamerounds`, `retention_1`, `retention_7`. No timestamps, no sessions.
- **Why rejected.** No grant from the rights holder, and the day-one label is pre-computed rather than constructible. Unusable as a primary dataset.

### KKBox Churn Prediction Challenge: rejected

- **Terms, verbatim** (competition rules, Wayback capture of 2019-08-19). §7.A: data may be used "only for the purposes of the Competition, participation on Kaggle Website forums, academic research and education." §7.B: "You agree not to transmit, duplicate, publish, redistribute or otherwise provide or make available the Data to any party not participating in the Competition."
- **Why rejected.** Music streaming, not a game. Redistribution forbidden; no licence granted.

### Steam Web API: rejected

- **Terms, verbatim** (Steam Web API Terms of Use, §2). "You will only retrieve Steam Data about a Steam end user as requested by the end user." Distribution is permitted only "to end users for their personal use via your Application." 100,000 calls per day.
- **Why rejected.** Bulk polling of users who did not ask for it is outside the terms; playtime is cumulative, so sessions would have to be inferred by repeated polling; SteamIDs are persistent identifiers of real people, so a published panel would be personal data. Public Steam datasets (e.g. `tamber/steam-video-games`, ODC Database Contents License) carry total hours only, no timestamps.

## Obligations retention-bench takes on

1. Cite Lee, Chen, Cheng and Lei, ACM MMSys 2011, in the README, the results files and the report.
2. Never commit or redistribute the raw archive or any per-avatar extract. `data/` is ignored by git.
3. Publish only aggregates. Every published cell counts at least 10 returning and 10 non-returning avatars; the three result tables are suppressed jointly so no smaller cell can be recovered by differencing.
4. Name no avatar id, guild id or per-avatar value in any published artifact.
5. State the avatar-versus-player limitation wherever a result is reported.
