# Setup on Windows 11

## 1. Prerequisites
- **Python 3.10 or newer** from python.org. Tick "Add python.exe to PATH" in the installer.
- **Git** from git-scm.com.
- **Optional:** Tailscale (tailscale.com/download), for the phone app.

## 2. Install and check
```powershell
git clone https://github.com/F0rger123/ultimate-claude-trading-skill
cd ultimate-claude-trading-skill
python -m unittest discover -s tests
```
Expect `OK`. The core needs no `pip install`.

## 3. Data and research
```powershell
python -m tradedesk data --gran 3600 --days 2870
python research/corrected_tournament.py
python research/summarize_corrected.py
python research/make_charts.py
```
Open `reports/corrected/summary.md`.

## 4. Paper trading around the clock
The private dashboard repo contains `desk/install-tasks.ps1`. It:
- creates `%USERPROFILE%\TradingDeskState\api-token.txt` (never printed)
- registers the `TradingDesk-Desk` and `TradingDesk-API` scheduled tasks, which start at log-on and
  restart on failure
- publishes the API to your tailnet with `tailscale serve --http=8787`, so no firewall change is needed

Without that script, run in two terminals:
```powershell
python -m tradedesk desk --state %USERPROFILE%\TradingDeskState
python -m tradedesk serve --state %USERPROFILE%\TradingDeskState --token-file %USERPROFILE%\TradingDeskState\api-token.txt
```

Set the PC to never sleep while plugged in (Settings > System > Power).

## 5. Phone
1. Install Tailscale on the phone and join the same tailnet.
2. Install the Trading Desk APK. It updates itself from the desk afterwards.
3. In Rules > Connection, enter `http://<pc-name>.<tailnet>.ts.net:8787` and the token.

## 6. Stop everything
```powershell
Stop-ScheduledTask TradingDesk-Desk
Stop-ScheduledTask TradingDesk-API
```
Or press **Stop all trading** in the app.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `python` not found | reinstall with "Add to PATH", or use the `py` launcher |
| App says "Can't reach your desk" | Tailscale is on in both places (same tailnet), the PC is awake, `tailscale serve status` shows port 8787 |
| HTTP 401 in the app | the token in the app doesn't match `api-token.txt` |
| Data download stalls | Coinbase rate limits; rerun, the cache resumes |
