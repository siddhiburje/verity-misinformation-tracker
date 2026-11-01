#!/usr/bin/env bash
# Verity — one-time environment setup.
# Usage: ./setup.sh
set -e

echo "== Verity setup =="

# 1. Python virtual environment
if [ ! -d "backend/.venv" ]; then
  echo "Creating virtual environment in backend/.venv ..."
  python3 -m venv backend/.venv
fi
source backend/.venv/bin/activate

# 2. Python dependencies
echo "Installing Python dependencies ..."
pip install --upgrade pip -q
pip install -r backend/requirements.txt -q

# 3. spaCy English model (not a normal PyPI package)
echo "Installing spaCy English NER model ..."
pip install -q "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl" \
  || echo "  (warning: could not install the spaCy model — named-entity extraction will degrade gracefully but keywords/similarity still work)"

# 4. Tesseract OCR binary (system package, required for image analysis)
if ! command -v tesseract >/dev/null 2>&1; then
  echo ""
  echo "  NOTE: the 'tesseract' OCR binary was not found on this system."
  echo "  Install it with your package manager, e.g.:"
  echo "    Ubuntu/Debian:  sudo apt-get install tesseract-ocr"
  echo "    macOS (brew):   brew install tesseract"
  echo "  Image upload analysis will not work until this is installed."
  echo ""
else
  echo "Tesseract OCR found: $(command -v tesseract)"
fi

# 5. .env file
if [ ! -f "backend/.env" ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from backend/.env.example — edit it to add your NEWSAPI_KEY and generate real secret keys."
fi

echo ""
echo "Setup complete. Next steps:"
echo "  1. Edit backend/.env (at minimum, set JWT_SECRET_KEY / FLASK_SECRET_KEY; NEWSAPI_KEY is optional)."
echo "  2. Run ./run.sh to start the server."
