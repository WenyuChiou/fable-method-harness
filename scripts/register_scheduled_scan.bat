@echo off
REM register_scheduled_scan.bat - one-time registration of the weekly
REM report-only AI-review scan (Windows Task Scheduler, Mon 09:05).
REM
REM Doctrine-safe by construction: --mode scheduled_review is report-only
REM BY CODE (rejects --ingest, never writes the proposals ledger, writes
REM only under reports/ which is gitignored). The task prepares a machine
REM report for a human; it cannot apply, decide, or mutate anything.
REM
REM Portable: paths derive from this file's location (%~dp0), so the same
REM script works on any machine after `git clone` with no editing.
REM Re-running updates the task in place (/f). Delete with:
REM   schtasks /delete /tn ClaudeAiReviewScheduledScan /f

set "HARNESS=%~dp0.."
schtasks /create /f /tn ClaudeAiReviewScheduledScan /sc weekly /d MON /st 09:05 ^
  /tr "cmd /c cd /d \"%HARNESS%\" && python scripts\run_ai_review.py --mode scheduled_review"
if %errorlevel%==0 (
  echo Registered: ClaudeAiReviewScheduledScan - weekly Mon 09:05, report-only.
  echo Reports land in "%HARNESS%\reports\ai-review\" ^(gitignored, local^).
) else (
  echo Registration failed ^(try an elevated prompt^).
)
