"""Helper: conecta o bot ao seu WhatsApp via código (sem QR).

Uso (com as vars de ambiente exportadas):
  export EVOLUTION_API_URL=https://sua-evolution.onrender.com
  export EVOLUTION_APIKEY=sua-chave
  export EVOLUTION_INSTANCE=promocoes

  python3 conectar.py criar                  # cria a instance 1x
  python3 conectar.py codigo 5511999998888   # gera código de 8 letras
  python3 conectar.py status                 # confere se conectou (open)
  python3 conectar.py grupos                 # lista grupos p/ pegar o JID

No celular: WhatsApp → Aparelhos conectados → Conectar aparelho
→ "Conectar com número de telefone" → digite o código (expira em ~1 min).
"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("EVOLUTION_API_URL", "").rstrip("/")
KEY = os.environ.get("EVOLUTION_APIKEY", "")
INST = os.environ.get("EVOLUTION_INSTANCE", "promocoes")


def call(method: str, path: str, body: dict | None = None):
    if not BASE or not KEY:
        sys.exit("Configure EVOLUTION_API_URL e EVOLUTION_APIKEY primeiro.")
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"apikey": KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: conectar.py criar|codigo <numero>|status|grupos")
    cmd = sys.argv[1]
    if cmd == "criar":
        print(call("POST", "/instance/create",
                   {"instanceName": INST, "integration": "WHATSAPP-BAILEYS", "qrcode": True}))
    elif cmd == "codigo":
        if len(sys.argv) < 3:
            sys.exit("Uso: conectar.py codigo 5511999998888 (só números, com DDI+DDD)")
        data = call("GET", f"/instance/connect/{INST}?number={sys.argv[2]}")
        code = data.get("pairingCode")
        print(f"\n  👉 Digite no WhatsApp: {code}\n" if code else data)
    elif cmd == "status":
        print(call("GET", f"/instance/connectionState/{INST}"))
    elif cmd == "grupos":
        for g in call("GET", f"/group/fetchAllGroups/{INST}?getParticipants=false"):
            print(f"{g.get('subject', '?')[:50]}  ->  {g.get('id')}")
        print("\nCopie o id do grupo para TARGET_GROUPS no Render.")
    else:
        sys.exit("Comando inválido.")


if __name__ == "__main__":
    main()
