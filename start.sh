[[ "$VIRTUAL_ENV" == "" ]] && . venv/bin/activate
[[ -f .env ]] && set -a && . .env && set +a
streamlit run youtuber.py --server.port ${SERVER_PORT:-7086}
