# AgroSmart — plataforma web + ESP32

Projeto-base para abrir no VS Code. Inclui:
- Login pelo número/ID do dispositivo (protótipo: `AGRO-001`)
- Painel com instruções e informações do produto
- Página de relatório com umidade, temperatura e pH
- Botão de irrigação manual com confirmação
- API Flask + SQLite para telemetria e comandos
- Exemplo de firmware Arduino para ESP32 consultar comandos e enviar leituras

## Importante antes de usar
Este projeto é uma base funcional de demonstração, não um sistema já publicado na internet. O botão só aciona a bomba se o ESP32 estiver programado, conectado à rede, configurado com o endereço do servidor e ligado ao circuito de relé/bomba corretamente. Nunca ligue uma bomba diretamente ao pino do ESP32. Use módulo de relé/driver adequado, fonte apropriada, proteção elétrica e orientação de um responsável técnico.

O login por ID sozinho serve apenas para demonstração. Para uso real, implemente senha/PIN por dispositivo, HTTPS, autenticação forte, limites de tempo de irrigação e proteção contra acionamentos repetidos.

## Requisitos
- Python 3.10 ou superior
- VS Code
- Extensão Python no VS Code
- Arduino IDE (opcional, para gravar o ESP32)

## Executar no Windows
1. Extraia a pasta `AgroSmart_Web`.
2. Abra essa pasta no VS Code.
3. Abra o terminal do VS Code e execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Se o PowerShell bloquear a ativação, tente:
```powershell
.\.venv\Scripts\activate.bat
```
ou instale as dependências com `py -m pip install -r requirements.txt` e execute `py app.py`.

4. Acesse `http://127.0.0.1:5000`.
5. ID de demonstração: `AGRO-001`.

## Como funciona
- O navegador envia o ID para `/api/login`.
- O ESP32 envia leituras para `POST /api/telemetry` com `device_id` e `device_token`.
- A página de relatório consulta `GET /api/telemetry/<device_id>`.
- O botão cria um comando de irrigação em `POST /api/irrigation`.
- O ESP32 consulta `GET /api/device/command` e recebe `ON` ou `OFF`.
- Quando a irrigação é solicitada, o servidor define um tempo máximo padrão de 10 segundos. O ESP32 também deve impor um limite local independente.

## Configurar o ESP32
Edite `esp32/agrosmart_esp32.ino`:
- `WIFI_SSID` e `WIFI_PASSWORD`
- `SERVER_URL`: endereço acessível pelo ESP32. Não use `127.0.0.1` no ESP32. Se o computador e o ESP32 estiverem na mesma rede, use o IP local do computador, por exemplo `http://192.168.0.10:5000`.
- `DEVICE_ID` e `DEVICE_TOKEN` para corresponder ao `app.py`.

O servidor deve permitir conexões da rede local. Para demonstração, o Flask é iniciado em `0.0.0.0`. Em redes escolares, firewall pode precisar de ajuste.

## Dados de demonstração
Se ainda não houver leituras reais, o site mostra valores ilustrativos identificados como demonstração. Não use dados fictícios para decisões de irrigação real.
