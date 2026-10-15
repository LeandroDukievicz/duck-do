#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$PROJECT_DIR"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

mkdir -p "$HOME/.local/bin"
ln -sfn "$PROJECT_DIR/.venv/bin/dukielist" "$HOME/.local/bin/dukielist"
if [ -L "$HOME/.local/bin/duck-do" ] &&
   { [ "$(readlink "$HOME/.local/bin/duck-do")" = "$PROJECT_DIR/.venv/bin/duck-do" ] ||
     [ "$(readlink "$HOME/.local/bin/duck-do")" = "$(dirname "$PROJECT_DIR")/duck-do/.venv/bin/duck-do" ]; }; then
    rm -f "$HOME/.local/bin/duck-do"
fi

DESKTOP_DIR="$HOME/Desktop"
if command -v xdg-user-dir >/dev/null 2>&1; then
    USER_DESKTOP="$(xdg-user-dir DESKTOP)"
    if [ -d "$USER_DESKTOP" ]; then
        DESKTOP_DIR="$USER_DESKTOP"
    fi
elif [ -d "$HOME/Área de Trabalho" ]; then
    DESKTOP_DIR="$HOME/Área de Trabalho"
fi
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/DukieList.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=DukieList
Comment=Gerenciador de tarefas no terminal
Exec=$PROJECT_DIR/.venv/bin/dukielist
TryExec=$PROJECT_DIR/.venv/bin/dukielist
Icon=$PROJECT_DIR/assets/mascot/duck-do-small.png
Path=$PROJECT_DIR
Terminal=true
Categories=Utility;ProjectManagement;
StartupNotify=true
EOF
chmod +x "$DESKTOP_DIR/DukieList.desktop"
rm -f "$DESKTOP_DIR/Duck-Do.desktop" "$HOME/Desktop/Duck-Do.desktop"

echo "DukieList instalado em $HOME/.local/bin/dukielist"
echo "Atalho criado em $DESKTOP_DIR/DukieList.desktop"
echo "Se o comando não for encontrado, abra um novo terminal ou adicione ~/.local/bin ao PATH."
