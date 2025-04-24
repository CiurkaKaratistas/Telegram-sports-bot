import requests
from datetime import datetime, date
import time
import json
import os

# === KONFIGŪRACIJA ===
API_KEY = '732472ce004902cca850ea2a2537c888'
BOT_TOKEN = '7812183153:AAHz2J6sIhVpWMAqc8hFUTLl7lFha47tPlE'
CHAT_ID = '1077195703'
HEADERS = {'x-apisports-key': API_KEY}
HISTORY_FILE = 'history.json'

# === TELEGRAM ===
def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    requests.post(url, data={'chat_id': CHAT_ID, 'text': message})
    
    # Testinis pranešimas
send_telegram_message("Testas: botas veikia ir siunčia pranešimus!")

# === API UŽKLAUSOS ===
def get_live_matches():
    url = 'https://v3.football.api-sports.io/fixtures?live=all'
    r = requests.get(url, headers=HEADERS)
    return r.json().get('response', []) if r.status_code == 200 else []

def get_statistics(fixture_id):
    url = f'https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}'
    r = requests.get(url, headers=HEADERS)
    return r.json().get('response', []) if r.status_code == 200 else []

def get_fixture_by_id(fixture_id):
    url = f'https://v3.football.api-sports.io/fixtures?id={fixture_id}'
    r = requests.get(url, headers=HEADERS)
    return r.json().get('response', [])[0] if r.status_code == 200 else None

# === ISTORIJA ===
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def update_results(history):
    updated = False
    for item in history:
        if item['result'] is None:
            fixture = get_fixture_by_id(item['fixture_id'])
            if fixture and fixture['fixture']['status']['short'] in ['FT', 'AET', 'PEN']:
                home = fixture['goals']['home']
                away = fixture['goals']['away']
                prediction = item['prediction']
                if prediction == 'Over 1.5':
                    result = 'WIN' if home + away > 1 else 'LOSS'
                elif prediction == 'BTTS':
                    result = 'WIN' if home > 0 and away > 0 else 'LOSS'
                elif prediction == 'Under 1.5':
                    result = 'WIN' if home + away <= 1 else 'LOSS'
                elif prediction == 'Team Win':
                    winner = fixture['teams']['home']['name'] if home > away else fixture['teams']['away']['name']
                    result = 'WIN' if item['team'] == winner else 'LOSS'
                elif prediction == 'Over 0.5':
                    result = 'WIN' if home + away > 0 else 'LOSS'
                elif prediction == 'Over 3.5':
                    result = 'WIN' if home + away > 3 else 'LOSS'
                elif prediction == 'Over 4.5':
                    result = 'WIN' if home + away > 4 else 'LOSS'
                else:
                    result = 'UNKNOWN'
                item['result'] = result
                updated = True
                send_telegram_message(f"Signalas ({item['prediction']}): {item['team1']} vs {item['team2']} – rezultatas: {home}:{away} – {result}")
    if updated:
        save_history(history)

def calculate_stats(history):
    today = date.today()
    win_all = loss_all = win_today = loss_today = 0
    last_signal = None

    for x in history:
        if x['result'] in ['WIN', 'LOSS']:
            if x['result'] == 'WIN':
                win_all += 1
            else:
                loss_all += 1

            entry_date = datetime.fromisoformat(x['time']).date()
            if entry_date == today:
                if x['result'] == 'WIN':
                    win_today += 1
                else:
                    loss_today += 1

        last_signal = x

    total_all = win_all + loss_all
    total_today = win_today + loss_today

    all_ratio = f"{(win_all / total_all * 100):.1f}%" if total_all > 0 else "-"
    today_ratio = f"{(win_today / total_today * 100):.1f}%" if total_today > 0 else "-"

    summary = (
        f"ŠIANDIEN: {win_today} WIN / {loss_today} LOSS ({today_ratio})\n"
        f"VISO: {win_all} WIN / {loss_all} LOSS ({all_ratio})"
    )

    if last_signal:
        summary += (
            f"\n\nPaskutinis signalas:\n"
            f"{last_signal['match']} – {last_signal['bet']} ({last_signal['result']})"
        )

    return summary

# === SIGNALŲ ANALIZĖ ===
def analyze_and_signal(fixture, stats_raw, history):
    try:
        fixture_id = fixture['fixture']['id']
        team1 = fixture['teams']['home']['name']
        team2 = fixture['teams']['away']['name']
        goals1 = fixture['goals']['home']
        goals2 = fixture['goals']['away']
        elapsed = fixture['fixture'].get('status', {}).get('elapsed', 0)
        score_total = goals1 + goals2

        stats = {}
        for item in stats_raw:
            team = item['team']['name']
            data = item['statistics']
            shots = next((x['value'] for x in data if x['type'] == 'Total Shots'), 0) or 0
            corners = next((x['value'] for x in data if x['type'] == 'Corner Kicks'), 0) or 0
            stats[team] = {'shots': shots, 'corners': corners}

        s1 = stats.get(team1, {'shots': 0, 'corners': 0})
        s2 = stats.get(team2, {'shots': 0, 'corners': 0})

        def register_signal(message, prediction, team=None):
            send_telegram_message(message)
            history.append({
                'fixture_id': fixture_id,
                'team1': team1,
                'team2': team2,
                'team': team,
                'prediction': prediction,
                'time': str(datetime.utcnow()),
                'result': None,
                'match': f"{team1} vs {team2}",
                'bet': prediction
            })
            save_history(history)

        if s1['shots'] >= s2['shots'] + 5 and s1['corners'] >= s2['corners'] + 3:
            register_signal(f"{team1} dominuoja – statymas: {team1} laimės / Over 1.5", "Team Win", team1)
        if s2['shots'] >= s1['shots'] + 5 and s2['corners'] >= s1['corners'] + 3:
            register_signal(f"{team2} dominuoja – statymas: {team2} laimės / Over 1.5", "Team Win", team2)

        if s1['shots'] >= 8 and s2['shots'] >= 8:
            register_signal(f"{team1} vs {team2} – abi aktyvios, statymas: BTTS", "BTTS")

        if s1['shots'] + s2['shots'] < 4:
            register_signal(f"{team1} vs {team2} – pasyvus mačas, statymas: Under 1.5", "Under 1.5")

        if s1['shots'] + s2['shots'] >= 20:
            register_signal(f"{team1} vs {team2} – labai aktyvu, statymas: Over 3.5", "Over 3.5")

        if s1['shots'] >= s2['shots'] + 5 and goals1 < goals2:
            register_signal(f"{team1} atsilieka, bet dominuoja – statymas: Over 1.5", "Over 1.5", team1)
        if s2['shots'] >= s1['shots'] + 5 and goals2 < goals1:
            register_signal(f"{team2} atsilieka, bet dominuoja – statymas: Over 1.5", "Over 1.5", team2)

        if score_total == 0 and elapsed >= 65:
            register_signal(f"{team1} vs {team2} – 0:0 po {elapsed} min – statymas: Under 1.5", "Under 1.5")

        if score_total == 1 and elapsed >= 75:
            leading_team = team1 if goals1 > goals2 else team2
            losing_team = team2 if leading_team == team1 else team1
            if stats[leading_team]['shots'] >= stats[losing_team]['shots'] + 5:
                register_signal(f"{leading_team} pirmauja ir dominuoja – statymas: Over 1.5", "Over 1.5", leading_team)

        if score_total in [4, 6] and goals1 == goals2 and elapsed >= 70:
            register_signal(f"{team1} vs {team2} – rezultatas {goals1}:{goals2} – chaotiškas, statymas: Over 4.5", "Over 4.5")

        total_shots = s1['shots'] + s2['shots']
        total_corners = s1['corners'] + s2['corners']
        if score_total == 0 and elapsed >= 65 and (total_shots >= 12 or total_corners >= 8):
            register_signal(f"{team1} vs {team2} – 0:0, bet aktyvu ({total_shots} smūgių, {total_corners} kampinių) – statymas: Over 0.5", "Over 0.5")

    except Exception as e:
        print("Klaida analizėje:", e)

# === TESTAVIMO FUNKCIJA ===
def run_test_mode():
    fake_fixture = {
        'fixture': {
            'id': 999999,
            'status': {'elapsed': 72}
        },
        'teams': {
            'home': {'name': 'FC TestHome'},
            'away': {'name': 'FC TestAway'}
        },
        'goals': {
            'home': 0,
            'away': 0
        }
    }

    fake_stats = [
        {
            'team': {'name': 'FC TestHome'},
            'statistics': [
                {'type': 'Total Shots', 'value': 10},
                {'type': 'Corner Kicks', 'value': 5},
            ]
        },
        {
            'team': {'name': 'FC TestAway'},
            'statistics': [
                {'type': 'Total Shots', 'value': 2},
                {'type': 'Corner Kicks', 'value': 1},
            ]
        }
    ]

    analyze_and_signal(fake_fixture, fake_stats, history)

# === PALEIDIMAS ===
history = load_history()

# Paleidžiame ciklą realioms varžyboms stebėti
while True:
    try:
        update_results(history)  # atnaujina senų signalų rezultatus
        matches = get_live_matches()
        for match in matches:
            stats = get_statistics(match['fixture']['id'])
            if stats:
                analyze_and_signal(match, stats, history)
        time.sleep(60)  # laukia 60 sek.
    except Exception as e:
        print("Klaida cikle:", e)
        time.sleep(30)

