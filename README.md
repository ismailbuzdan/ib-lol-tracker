# IB LoL Tracker

Personal League of Legends Solo/Duo ranked statistics overlay for OBS Studio. Tracks **Âsk#ice** using Riot Account-V1, League-V4 and Match-V5. Features seasonal ranked win rate, last five ranked matches and local stream-session win/loss tracking.

## Setup (Windows)

1. Install Python 3.11+.
2. Download or clone this repository.
3. Run `BASLAT.bat` once to create `.env`.
4. Add your own Riot API key to the **local** `.env` file, then restart.
5. Open `http://127.0.0.1:8000/` for the local dashboard.
6. In OBS, add Browser Source URL `http://127.0.0.1:8000/overlay`, width **340**, height **340**, positioned over the in-game minimap.

`RIOT_PLATFORM=tr1` is for Turkish accounts; use `euw1` for EUW. Keep `RIOT_REGION=europe` for both. By default, only ranked Solo/Duo queue **420** is included. Set `MATCH_SCOPE=ranked` to include Flex 440 too.

## Security

Never commit `.env`, API keys, virtual environments or `tracker.sqlite3`. API access is server-side and Flask binds only to localhost. This is a personal, non-commercial project and is not affiliated with or endorsed by Riot Games.

## Limitations

Rank and season win rate come from League-V4. Session win/loss stats are derived from newly retrieved ranked matches. LP changes are accurate only within the same division because Riot does not expose historical LP changes through match history. Demonstration data must not be mistaken for live Riot statistics.

## Developer

The personal API key is requested separately through Riot Developer Portal; this source repository itself does not contain a key.
