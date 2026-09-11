# Chapter 2: Temporal Split, Chronological Buffering & Contamination Check

**Scientific Status:** `VALIDATED`

## 1. Split Partitioning Design
- **Train Split:** 730 cycles (2000–2013, 547,500 rows, ~70.2%)
- **Validation Split:** 155 cycles (2014–2016, 116,250 rows, ~14.9%)
- **Test Split:** 155 cycles (2017–2019, 116,250 rows, ~14.9%)
- **Buffer Separation:** 2-week explicit dead-band buffer between splits to prevent auto-correlation leakage across boundaries.

## 2. Leakage Protection Verifications
- Zero cycle overlap between Train, Validation, and Test partitions.
- Calibration fitting performed STRICTLY on Validation partition; Test partition remains 100% untouched until evaluation.
- Feature extraction computed strictly using information available at issue time $t_0$.
