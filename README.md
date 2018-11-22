# otrs_report
The reporting tool for OTRS, it generates the html-report on total tickets completed for period.
It uses web-scapping for getting data (there is no technical opportunity to use otrs web-services).

## Using
Connection setting, report file path are specified in **config.py**.

Command `python report.py N` builds the html-report for *N* days (default is 1 day).

Example:
`python report.py 3` will generate the report for 3 days.
