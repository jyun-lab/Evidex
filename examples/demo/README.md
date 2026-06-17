# Synthetic Demo Data

This folder contains fully synthetic oscilloscope-style demo data for Evidex.
It is intended for screenshots, onboarding, and local testing.

The demo includes:

- ten synthetic experiment records in `runs.csv`
- sine-wave oscilloscope CSV files under `signals/`
- one generated attachment image under `images/`
- no real researchers, lab records, unpublished results, or instrument data

Open `runs.csv` in Evidex and select the `oscilloscope_demo` pack if you want
labels tailored to the screenshot demo. The generic time-series pack can also
read the CSV files because they use a `time` column followed by numeric channels.

Do not replace these files with real laboratory data before committing to Git.
