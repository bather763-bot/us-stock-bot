
name: US Stock Market Scanner

on:
  schedule:
    - cron: '*/5 14-21 * * 1-5'
  workflow_dispatch:

jobs:
  scan-market:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Stock Bot
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          CHAT_ID: ${{ secrets.CHAT_ID }}
        run: python bot.py

      - name: Commit and push learning data
        run: |
          git config --global user.name 'GitHub Actions'
          git config --global user.email 'actions@github.com'
          git add learning_data.json bot_settings.json 2>/dev/null || true
          git commit -m "Save learning data [skip ci]" || true
          git push || true
