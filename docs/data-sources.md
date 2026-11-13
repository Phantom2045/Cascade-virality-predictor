# Data Sources, Formats, and Licenses

This project operates **exclusively on real public datasets** supplied locally by the user under `backend/data/raw/`. No datasets are redistributed in this repository, and no synthetic cascades are generated.

## 1. Twitter15 & Twitter16 (Ma et al.) — Recommended Primary Dataset

- **Reference:** Jing Ma, Wei Gao, Prasenjit Mitra, Sejeong Kwon, Bernard J. Jansen, Kam-Fai Wong, Meeyoung Cha, *"Detecting Rumors from Microblogs with Recurrent Neural Networks"* (IJCAI 2016) & *"Rumor Detection on Twitter with Tree-structured Recursive Neural Networks"* (ACL 2018).
- **Typical Distribution Mirrors:**
  - `https://github.com/majingCUHK/Rumor_RvNN`
  - `https://github.com/gszswork/Twitter15_16_dataset`
- **License / Terms:** Non-commercial academic research use only; underlying tweet/user identifiers remain subject to Twitter/X Developer Terms of Service.
- **How the Propagation Tree Is Defined:**
  - `tree/<source_tweet_id>.txt` stores parent-child propagation edges in the form `['p_uid', 'p_tweet_id', 'p_delay_min']->['c_uid', 'c_tweet_id', 'c_delay_min']`.
  - Lines starting from `'ROOT'` denote the root tweet (`parent_id = None`).
  - Relative delays (in minutes) are converted to seconds (`delay_min * 60`).
  - Root chronological timestamps for temporal splitting are decoded from Twitter Snowflake IDs.
- **What Is Deliberately Excluded / Lost:**
  - `label.txt` (veracity categories TR/FR/UR/NR) and `source_tweets.txt` (tweet text) are **strictly ignored**.
  - Tweet text, media, user follower counts, and deleted accounts/edges absent at collection time are unavailable; timestamps are quantized to minute-level precision.

## 2. PHEME Conversation-Tree Dataset (Zubiaga et al.)

- **Reference:** Arkaitz Zubiaga, Maria Liakata, Rob Procter, Geraldine Wong Sak Hoi, Peter Tolmie (2016/2018), *PHEME dataset of rumours and non-rumours*, Figshare.
- **Source URL:** `https://figshare.com/articles/dataset/PHEME_dataset_of_rumours_and_non-rumours/4010619` (and 9-event extended release on Figshare).
- **License / Terms:** Curated annotations and tree structures are licensed under **CC-BY 4.0**; tweet JSON payloads remain subject to Twitter/X terms.
- **How the Propagation Tree Is Defined:**
  - `structure.json` defines the nested reply-to conversation hierarchy (`{root_id: {reply_id: {...}}}`).
  - UTC `created_at` timestamps from `source-tweet/<id>.json` and `reactions/<id>.json` are converted to seconds elapsed since the source tweet.
- **What Is Deliberately Excluded / Lost:**
  - `annotation.json` veracity labels and tweet text/user metadata are **strictly ignored**.
  - PHEME captures **reply conversation trees**, not pure retweet trees without reply links, so total reach is smaller than full retweet cascades.

## 3. SNAP Higgs Twitter Dataset (Reference Note Only)

- **Reference:** M. De Domenico, A. Lima, P. Mougel, M. Musolesi, *"The Anatomy of a Scientific Rumor"*, Scientific Reports 3, 2980 (2013); Stanford SNAP (`https://snap.stanford.edu/data/higgs-twitter.html`).
- **License / Terms:** Academic/research use via SNAP, subject to Twitter/X data terms.
- **Why It Is Not the Primary Dataset (Retweet-Star Artifact):**
  - `higgs-activity_time.txt` records `userA userB timestamp interaction` (`RT`, `MT`, `RE`) across a single topic without per-tweet cascade IDs, and Twitter retweet API records often point directly to the original author rather than the intermediate sharer (producing an artificial star graph where true multi-hop depth is lost).

## 4. Privacy & Opaque Identifiers

All user and tweet identifiers are treated as opaque node strings (`child_id`, `parent_id`). No de-anonymization, user-history lookup, or profile enrichment is performed.
